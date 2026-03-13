"""
P4 FastAPI 메인 앱.

REST API + WebSocket 엔드포인트, CORS, 정적 파일 서빙을 담당한다.
"""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import desc, func, and_

from p4.config import get_config, load_config
from p4.db.connection import get_engine, get_session
from p4.db.schema import init_db
from p4.db.models import RealtimeData, HistoryMin, PredictResult, LayoutConfig
from p4.opc.client import OpcClient
from p4.opc.simulator import TagReading
from p4.sampling.engine import SamplingEngine
from p4.api.auth import (
    Token, UserCreate, UserResponse,
    authenticate_user, create_access_token, get_current_user,
    hash_password, ensure_admin_exists,
)

# AI 모듈 임포트 (DLL 이슈 대비)
try:
    from p4.ai import ONNXInferencer, ModelManager
except ImportError as e:
    logger.warning(f"AI modules could not be fully loaded due to environment issues: {e}")
    ONNXInferencer = None
    ModelManager = None

logger = logging.getLogger(__name__)

# 전역 상태
opc_client: OpcClient | None = None
sampling_engine: SamplingEngine | None = None
ai_inferencer: ONNXInferencer | None = None
model_manager: ModelManager | None = None


# ---------------------------------------------------------------------------
# WebSocket 연결 매니저
# ---------------------------------------------------------------------------

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, data: dict):
        dead = []
        for conn in self.active_connections:
            try:
                await conn.send_json(data)
            except Exception:
                dead.append(conn)
        for conn in dead:
            self.active_connections.remove(conn)


ws_manager = ConnectionManager()


# ---------------------------------------------------------------------------
# 라이프사이클
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """앱 시작/종료 시 OPC 수집 및 WebSocket 브로드캐스트를 관리한다."""
    global opc_client, sampling_engine
    config = get_config()

    # DB 초기화
    engine = get_engine(config)
    init_db(engine)
    ensure_admin_exists()

    # OPC 시뮬레이터 시작
    opc_client = OpcClient(config)
    sampling_engine = SamplingEngine(config)

    opc_client.start(simulate=config.simulator.enabled)
    sampling_engine.start()

    # AI 엔진 초기화
    if ONNXInferencer and ModelManager:
        ai_inferencer = ONNXInferencer()
        model_manager = ModelManager()
        logger.info("AI Inference Engine initialized.")

    # WebSocket 브로드캐스트 태스크
    broadcast_task = asyncio.create_task(_broadcast_loop(config))

    logger.info("P4 API Server started.")
    yield

    # 종료 정리
    broadcast_task.cancel()
    opc_client.stop()
    sampling_engine.stop()
    logger.info("P4 API Server stopped.")


async def _broadcast_loop(config):
    """주기적으로 최신 데이터를 WebSocket 클라이언트에 브로드캐스트."""
    while True:
        try:
            if ws_manager.active_connections:
                readings = _get_latest_readings(config)
                predictions = _get_latest_predictions(config)
                
                # 병합 로직: 실시간 데이터에 예측값 매칭
                data_with_predict = []
                for r in readings:
                    p_val = predictions.get(r["tag_name"])
                    # 예측값이 있으면 실제 연동, 없으면 하위 호환을 위해 유지 (또는 UI 노출용 0.0)
                    r["predict"] = round(p_val, 2) if p_val is not None else None
                    data_with_predict.append(r)

                await ws_manager.broadcast({
                    "type": "realtime",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "data": data_with_predict,
                })
        except Exception as e:
            logger.error(f"Broadcast error: {e}")
        await asyncio.sleep(2)  # 2초 주기


def _get_latest_readings(config) -> list[dict]:
    """DB에서 태그별 최신 값을 조회한다."""
    session = get_session(config)
    try:
        from sqlalchemy import distinct
        # 각 태그의 최신 레코드
        subq = (
            session.query(
                RealtimeData.tag_name,
                func.max(RealtimeData.id).label("max_id")
            )
            .group_by(RealtimeData.tag_name)
            .subquery()
        )
        results = (
            session.query(RealtimeData)
            .join(subq, RealtimeData.id == subq.c.max_id)
            .all()
        )
        return [
            {
                "tag_name": r.tag_name,
                "value": round(r.value, 2),
                "quality": r.quality,
                "timestamp": r.timestamp.isoformat() if r.timestamp else None,
            }
            for r in results
        ]
    finally:
        session.close()


def _get_latest_predictions(config) -> dict[str, float]:
    """DB에서 태그별 최신 예측 결과(1h 뒤)를 조회한다."""
    session = get_session(config)
    try:
        # 각 태그의 최신 예측값
        subq = (
            session.query(
                PredictResult.tag_name,
                func.max(PredictResult.id).label("max_id")
            )
            .group_by(PredictResult.tag_name)
            .subquery()
        )
        results = (
            session.query(PredictResult)
            .join(subq, PredictResult.id == subq.c.max_id)
            .all()
        )
        return {r.tag_name: r.predict_value for r in results}
    except Exception as e:
        logger.error(f"Error fetching predictions: {e}")
        return {}
    finally:
        session.close()


# ---------------------------------------------------------------------------
# FastAPI 앱 생성
# ---------------------------------------------------------------------------

app = FastAPI(
    title="P4 - Power Plant Performance Predictor",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# 인증 API
# ---------------------------------------------------------------------------

@app.post("/api/auth/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    token = create_access_token(data={"sub": user.username})
    return Token(access_token=token)


@app.get("/api/auth/me", response_model=UserResponse)
async def get_me(current_user: UserResponse = Depends(get_current_user)):
    return current_user


# ---------------------------------------------------------------------------
# 실시간 데이터 API
# ---------------------------------------------------------------------------

@app.get("/api/realtime")
async def get_realtime_data():
    """모든 태그의 최신 실시간 값을 반환한다."""
    config = get_config()
    data = _get_latest_readings(config)
    return {"data": data, "count": len(data)}


@app.get("/api/tags")
async def get_tag_list():
    """사용 가능한 태그 목록을 반환한다."""
    config = get_config()
    session = get_session(config)
    try:
        tags = (
            session.query(RealtimeData.tag_name)
            .distinct()
            .order_by(RealtimeData.tag_name)
            .all()
        )
        return {"tags": [t[0] for t in tags]}
    finally:
        session.close()


# ---------------------------------------------------------------------------
# 히스토리 API
# ---------------------------------------------------------------------------

class HistoryQuery(BaseModel):
    tag_name: str
    hours: int = 24


@app.get("/api/history/{tag_name}")
async def get_history(tag_name: str, hours: int = Query(default=24, ge=1, le=720)):
    """태그의 분 단위 히스토리 데이터를 반환한다."""
    config = get_config()
    session = get_session(config)
    try:
        cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - __import__("datetime").timedelta(hours=hours)
        results = (
            session.query(HistoryMin)
            .filter(
                HistoryMin.tag_name == tag_name,
                HistoryMin.period_start >= cutoff,
            )
            .order_by(HistoryMin.period_start)
            .all()
        )
        return {
            "tag_name": tag_name,
            "data": [
                {
                    "timestamp": r.period_start.isoformat(),
                    "avg": round(r.avg_value, 4),
                    "min": round(r.min_value, 4) if r.min_value else None,
                    "max": round(r.max_value, 4) if r.max_value else None,
                    "std": round(r.std_value, 4) if r.std_value else None,
                    "count": r.sample_count,
                }
                for r in results
            ],
        }
    finally:
        session.close()


# ---------------------------------------------------------------------------
# 시스템 상태 API
# ---------------------------------------------------------------------------

@app.get("/api/status")
async def get_system_status():
    """시스템 수집 상태를 반환한다."""
    global opc_client, ai_inferencer
    stats = opc_client.stats if opc_client else {"saved": 0, "skipped": 0, "total": 0}
    return {
        "opc_connected": opc_client is not None,
        "ai_engine_active": ai_inferencer is not None,
        "collection_stats": stats,
        "uptime": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# AI 관리 API
# ---------------------------------------------------------------------------

@app.post("/api/ai/train")
async def trigger_training(tag_name: str = "ALL"):
    """모델 학습 파이프라인 수동 트리거 (비동기 수행)."""
    # 실제 구현 시 BackgroundTasks 활용하여 trainer.find_best_model 호출
    return {"status": "accepted", "message": f"Training started for {tag_name}"}


@app.get("/api/ai/models")
async def get_models_info():
    """현재 사용 가능한 모델 목록 및 정확도 정보."""
    config = get_config()
    session = get_session(config)
    try:
        # TB_MODEL_INFO 조회 로직
        return {"models": []}
    finally:
        session.close()


# ---------------------------------------------------------------------------
# 레이아웃 API
# ---------------------------------------------------------------------------

class LayoutSave(BaseModel):
    layout_name: str = "default"
    config_json: str  # JSON string


@app.get("/api/layout")
async def get_layout(current_user: UserResponse = Depends(get_current_user)):
    """현재 사용자의 레이아웃 설정을 반환한다."""
    config = get_config()
    session = get_session(config)
    try:
        layout = (
            session.query(LayoutConfig)
            .filter_by(user_id=current_user.id)
            .order_by(desc(LayoutConfig.updated_at))
            .first()
        )
        if layout:
            return {"layout": json.loads(layout.config_json)}
        return {"layout": None}
    finally:
        session.close()


@app.post("/api/layout")
async def save_layout(
    body: LayoutSave,
    current_user: UserResponse = Depends(get_current_user),
):
    """사용자의 레이아웃 설정을 저장한다."""
    config = get_config()
    session = get_session(config)
    try:
        existing = (
            session.query(LayoutConfig)
            .filter_by(user_id=current_user.id, layout_name=body.layout_name)
            .first()
        )
        if existing:
            existing.config_json = body.config_json
            existing.updated_at = datetime.now(timezone.utc)
        else:
            session.add(LayoutConfig(
                user_id=current_user.id,
                layout_name=body.layout_name,
                config_json=body.config_json,
            ))
        session.commit()
        return {"status": "saved"}
    finally:
        session.close()


# ---------------------------------------------------------------------------
# WebSocket
# ---------------------------------------------------------------------------

@app.websocket("/ws/realtime")
async def websocket_endpoint(websocket: WebSocket):
    """실시간 데이터 WebSocket 스트림."""
    await ws_manager.connect(websocket)
    try:
        while True:
            # 클라이언트의 메시지를 수신 (핑/구독 변경 등)
            data = await websocket.receive_text()
            # 향후 구독 태그 필터링 등 구현 가능
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)


# ---------------------------------------------------------------------------
# React SPA 정적 파일 서빙
# ---------------------------------------------------------------------------

FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent.parent / "frontend" / "dist"


def setup_static_files():
    """프론트엔드 빌드 디렉토리가 있으면 정적 파일 서빙 설정."""
    if FRONTEND_DIR.exists():
        app.mount("/assets", StaticFiles(directory=FRONTEND_DIR / "assets"), name="assets")

        @app.get("/{full_path:path}")
        async def serve_spa(full_path: str):
            file_path = FRONTEND_DIR / full_path
            if file_path.exists() and file_path.is_file():
                return FileResponse(file_path)
            response = FileResponse(FRONTEND_DIR / "index.html")
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
            return response


setup_static_files()
