"""
P4 메인 진입점.

CS Tool의 데이터 수집 프로세스를 시작/관리한다.
--simulate 플래그로 시뮬레이터 모드 전환.
"""

from __future__ import annotations

import sys
import signal
import logging
import argparse
from pathlib import Path

from p4.config import load_config
from p4.db.schema import init_db
from p4.db.connection import get_engine
from p4.opc.client import OpcClient
from p4.sampling.engine import SamplingEngine


# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)-7s] %(name)-25s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("p4")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="P4 - AI-Powered Power Plant Performance Predictor"
    )
    parser.add_argument(
        "--simulate", "-s",
        action="store_true",
        default=False,
        help="OPC 시뮬레이터 모드로 실행 (기본: config 파일의 simulator.enabled 설정 따름)"
    )
    parser.add_argument(
        "--config", "-c",
        type=str,
        default=None,
        help="설정 파일 경로 (기본: config/defaults.yaml)"
    )
    parser.add_argument(
        "--init-db-only",
        action="store_true",
        default=False,
        help="DB 테이블만 생성하고 종료"
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    # 설정 로딩
    config = load_config(args.config)
    logger.info("=" * 60)
    logger.info("P4 - AI-Powered Power Plant Performance Predictor")
    logger.info("=" * 60)
    logger.info(f"Database: {config.database.url}")
    logger.info(f"Simulator: {'ON' if (args.simulate or config.simulator.enabled) else 'OFF'}")
    logger.info(f"Sampling interval: {config.data.sampling_interval_min} min")

    # DB 디렉토리 확인 (SQLite 사용 시)
    if config.database.url.startswith("sqlite"):
        db_path = config.database.url.replace("sqlite:///", "")
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    # DB 초기화
    engine = get_engine(config)
    init_db(engine)
    logger.info("Database initialized.")

    if args.init_db_only:
        logger.info("DB initialization complete. Exiting (--init-db-only).")
        return

    # OPC 클라이언트 시작
    opc_client = OpcClient(config)
    sampling_engine = SamplingEngine(config)

    # Graceful shutdown 핸들러
    def shutdown_handler(signum, frame):
        logger.info("Shutdown signal received. Stopping...")
        opc_client.stop()
        sampling_engine.stop()
        logger.info("Shutdown complete.")
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    try:
        # 시뮬레이터 모드 결정
        use_simulate = args.simulate or config.simulator.enabled
        opc_client.start(simulate=use_simulate)
        sampling_engine.start()

        logger.info("System running. Press Ctrl+C to stop.")

        # 메인 스레드 유지
        signal.pause() if hasattr(signal, 'pause') else _windows_wait()

    except KeyboardInterrupt:
        pass
    finally:
        opc_client.stop()
        sampling_engine.stop()
        logger.info("P4 terminated.")


def _windows_wait() -> None:
    """Windows에서 signal.pause() 대용."""
    import time
    while True:
        time.sleep(1)


if __name__ == "__main__":
    main()
