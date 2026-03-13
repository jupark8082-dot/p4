"""
P4 데이터베이스 ORM 모델 정의.

PRD v2 섹션 5.1의 테이블 구조를 SQLAlchemy ORM으로 구현한다.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Column, Integer, Float, String, DateTime, Text, Boolean, Index,
)
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """SQLAlchemy 선언적 기반 클래스."""
    pass


class RealtimeData(Base):
    """TB_REALTIME_DATA: OPC에서 수집되는 초 단위 데이터.
    
    보관 정책: [기본값] 24시간 보관 후 아카이브.
    파티셔닝: 일(Day) 단위 (MS SQL 배포 시 적용).
    """
    __tablename__ = "TB_REALTIME_DATA"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tag_name = Column(String(128), nullable=False, index=True)
    value = Column(Float, nullable=False)
    quality = Column(Integer, default=192)  # OPC Quality: 192 = Good
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    source_timestamp = Column(DateTime, nullable=True)  # OPC 서버 타임스탬프

    __table_args__ = (
        Index("ix_realtime_tag_ts", "tag_name", "timestamp"),
    )

    def __repr__(self) -> str:
        return f"<RealtimeData({self.tag_name}={self.value} @ {self.timestamp})>"


class HistoryMin(Base):
    """TB_HISTORY_MIN: 분 단위 평균 데이터.
    
    보관 정책: [기본값] 2년.
    파티셔닝: 월(Month) 단위.
    """
    __tablename__ = "TB_HISTORY_MIN"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tag_name = Column(String(128), nullable=False, index=True)
    avg_value = Column(Float, nullable=False)
    min_value = Column(Float, nullable=True)
    max_value = Column(Float, nullable=True)
    std_value = Column(Float, nullable=True)
    sample_count = Column(Integer, default=0)
    period_start = Column(DateTime, nullable=False, index=True)  # 집계 시작 시각
    period_end = Column(DateTime, nullable=False)                # 집계 종료 시각

    __table_args__ = (
        Index("ix_history_tag_period", "tag_name", "period_start"),
    )

    def __repr__(self) -> str:
        return f"<HistoryMin({self.tag_name} avg={self.avg_value} @ {self.period_start})>"


class PredictResult(Base):
    """TB_PREDICT_RESULT: DL 모델 예측 결과.
    
    보관 정책: [기본값] 1년.
    """
    __tablename__ = "TB_PREDICT_RESULT"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tag_name = Column(String(128), nullable=False, index=True)
    predicted_value = Column(Float, nullable=False)
    actual_value = Column(Float, nullable=True)            # 나중에 비교용으로 채움
    deviation_pct = Column(Float, nullable=True)           # |actual - predicted| / predicted * 100
    model_version = Column(String(256), nullable=True)     # 사용된 모델 버전
    prediction_time = Column(DateTime, nullable=False, index=True)   # 예측 대상 시각
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_predict_tag_time", "tag_name", "prediction_time"),
    )


class ModelInfo(Base):
    """TB_MODEL_INFO: DL 모델 메타데이터.
    
    보관 정책: 영구.
    """
    __tablename__ = "TB_MODEL_INFO"

    id = Column(Integer, primary_key=True, autoincrement=True)
    model_name = Column(String(256), nullable=False, unique=True)  # e.g. model_lstm_tag001_20260312
    algorithm = Column(String(32), nullable=False)                  # LSTM / GRU / RNN
    target_tag = Column(String(128), nullable=False)                # 예측 대상 태그
    input_tags = Column(Text, nullable=False)                       # JSON: 입력 태그 목록
    hyperparameters = Column(Text, nullable=True)                   # JSON: 하이퍼파라미터
    rmse = Column(Float, nullable=True)                             # 검증 RMSE
    mae = Column(Float, nullable=True)                              # 검증 MAE
    status = Column(String(32), default="active")                   # active / archived / discarded
    onnx_path = Column(String(512), nullable=True)                  # ONNX 파일 경로
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=True, onupdate=datetime.utcnow)


class User(Base):
    """TB_USER: 웹 대시보드 사용자.
    
    보관 정책: 영구.
    """
    __tablename__ = "TB_USER"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(64), nullable=False, unique=True, index=True)
    hashed_password = Column(String(256), nullable=False)
    full_name = Column(String(128), nullable=True)
    role = Column(String(32), default="viewer")  # admin / viewer
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class LayoutConfig(Base):
    """TB_LAYOUT_CONFIG: 사용자별 PFD 레이아웃 설정.
    
    보관 정책: 영구.
    """
    __tablename__ = "TB_LAYOUT_CONFIG"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    layout_name = Column(String(128), default="default")
    config_json = Column(Text, nullable=False)  # JSON: 카드 위치, 크기, 바인딩 태그 등
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=True, onupdate=datetime.utcnow)


class DriftLog(Base):
    """TB_DRIFT_LOG: 데이터 Drift 감지 이력.
    
    보관 정책: [기본값] 1년.
    """
    __tablename__ = "TB_DRIFT_LOG"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tag_name = Column(String(128), nullable=False, index=True)
    psi_value = Column(Float, nullable=False)
    is_drifted = Column(Boolean, nullable=False)
    details = Column(Text, nullable=True)  # JSON: 분포 비교 상세
    checked_at = Column(DateTime, nullable=False, default=datetime.utcnow)
