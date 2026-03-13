"""
P4 OPC DA 클라이언트.

OPC DA 서버와의 통신을 담당하는 메인 클라이언트.
실제 OPC 연결과 시뮬레이터를 동일한 인터페이스로 제공한다.
"""

from __future__ import annotations

import time
import logging
import threading
from datetime import datetime
from typing import Callable, Protocol

from p4.config import AppConfig, get_config
from p4.opc.simulator import OpcSimulator, TagReading
from p4.opc.deadband import DeadbandFilter
from p4.db.connection import get_session
from p4.db.models import RealtimeData

logger = logging.getLogger(__name__)


class OpcDataSource(Protocol):
    """OPC 데이터 소스 인터페이스."""

    def connect(self) -> None: ...
    def disconnect(self) -> None: ...
    def subscribe(self, tag_names: list[str] | None = None) -> list[str]: ...
    def read_all(self) -> list[TagReading]: ...
    def start(self, callback: Callable[[list[TagReading]], None]) -> None: ...
    def stop(self) -> None: ...

    @property
    def is_connected(self) -> bool: ...
    @property
    def is_running(self) -> bool: ...
    @property
    def tag_names(self) -> list[str]: ...


class OpcClient:
    """OPC DA 클라이언트 (수집 엔진).
    
    시뮬레이터 모드와 실제 OPC DA 모드를 자동 전환한다.
    수집된 데이터는 Deadband 필터를 거쳐 DB에 저장된다.
    """

    def __init__(self, config: AppConfig | None = None):
        self._config = config or get_config()
        self._source: OpcDataSource | None = None
        self._deadband = DeadbandFilter(
            default_type=self._config.deadband.default_type,
            default_threshold=self._config.deadband.default_threshold,
        )
        self._running = False
        self._save_count = 0
        self._skip_count = 0

    @property
    def stats(self) -> dict:
        """수집 통계."""
        return {
            "saved": self._save_count,
            "skipped": self._skip_count,
            "total": self._save_count + self._skip_count,
        }

    def start(self, simulate: bool = False) -> None:
        """데이터 수집을 시작한다.
        
        Args:
            simulate: True이면 시뮬레이터 사용
        """
        if simulate or self._config.simulator.enabled:
            self._source = OpcSimulator(
                tags=self._config.simulator.tags,
                interval_sec=self._config.simulator.base_interval_sec,
            )
            logger.info("Using OPC Simulator mode.")
        else:
            # 실제 OPC DA 연결 (Phase 1에서는 시뮬레이터만 지원)
            raise NotImplementedError(
                "Real OPC DA connection is not yet implemented. "
                "Use simulate=True or set simulator.enabled=True in config."
            )

        self._connect_with_retry()
        self._source.subscribe()
        self._source.start(callback=self._on_data_batch)
        self._running = True
        logger.info("OPC Client started. Collecting data...")

    def stop(self) -> None:
        """수집을 중지한다."""
        self._running = False
        if self._source:
            self._source.stop()
            self._source.disconnect()
        logger.info(f"OPC Client stopped. Stats: {self.stats}")

    def _connect_with_retry(self) -> None:
        """지수 백오프 재접속 로직."""
        max_retries = self._config.opc.reconnect_max_retries
        base_delay = self._config.opc.reconnect_base_delay_sec

        for attempt in range(max_retries):
            try:
                self._source.connect()
                return
            except Exception as e:
                delay = base_delay * (2 ** attempt)
                logger.warning(
                    f"Connection attempt {attempt + 1}/{max_retries} failed: {e}. "
                    f"Retrying in {delay}s..."
                )
                time.sleep(delay)

        raise ConnectionError(
            f"Failed to connect after {max_retries} attempts."
        )

    def _on_data_batch(self, readings: list[TagReading]) -> None:
        """데이터 배치 콜백: Deadband 필터 → DB 저장."""
        to_save = []
        for reading in readings:
            if self._deadband.should_save(reading.tag_name, reading.value):
                to_save.append(reading)
                self._save_count += 1
            else:
                self._skip_count += 1

        if not to_save:
            return

        try:
            session = get_session(self._config)
            try:
                for reading in to_save:
                    record = RealtimeData(
                        tag_name=reading.tag_name,
                        value=reading.value,
                        quality=reading.quality,
                        timestamp=reading.timestamp,
                        source_timestamp=reading.timestamp,
                    )
                    session.add(record)
                session.commit()
                logger.debug(
                    f"Saved {len(to_save)}/{len(readings)} readings "
                    f"(filtered by deadband)."
                )
            except Exception as e:
                session.rollback()
                logger.error(f"DB save failed: {e}")
            finally:
                session.close()
        except Exception as e:
            logger.error(f"Session creation failed: {e}")
