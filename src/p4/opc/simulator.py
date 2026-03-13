"""
P4 OPC DA 시뮬레이터.

OPC DA 서버 없이 개발/테스트할 수 있는 가상 데이터 생성기.
실제 OPC 클라이언트와 동일한 인터페이스를 제공한다.
"""

from __future__ import annotations

import math
import time
import random
import logging
import threading
from datetime import datetime
from dataclasses import dataclass, field
from typing import Callable

from p4.config import SimulatorTagConfig

logger = logging.getLogger(__name__)


@dataclass
class TagReading:
    """단일 태그 읽기 결과."""
    tag_name: str
    value: float
    quality: int = 192  # OPC Good Quality
    timestamp: datetime = field(default_factory=datetime.utcnow)


class OpcSimulator:
    """OPC DA 서버 시뮬레이터.
    
    사인파, 노이즈, 드리프트를 조합하여 발전소 유사 데이터를 생성한다.
    
    사용 예:
        sim = OpcSimulator(tags=config.simulator.tags)
        sim.start(callback=on_data_received)
        ...
        sim.stop()
    """

    def __init__(
        self,
        tags: list[SimulatorTagConfig],
        interval_sec: float = 1.0,
    ):
        self._tags = tags
        self._interval = interval_sec
        self._running = False
        self._thread: threading.Thread | None = None
        self._callback: Callable[[list[TagReading]], None] | None = None
        self._start_time = time.time()
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def tag_names(self) -> list[str]:
        """구독 중인 태그 이름 목록."""
        return [t.name for t in self._tags]

    def connect(self) -> None:
        """시뮬레이터 연결 (항상 성공)."""
        self._connected = True
        self._start_time = time.time()
        logger.info(f"OPC Simulator connected. {len(self._tags)} tags available.")

    def disconnect(self) -> None:
        """시뮬레이터 연결 해제."""
        self.stop()
        self._connected = False
        logger.info("OPC Simulator disconnected.")

    def subscribe(self, tag_names: list[str] | None = None) -> list[str]:
        """태그를 구독한다. None이면 전체 구독.
        
        Returns:
            실제 구독된 태그 이름 목록
        """
        if tag_names is None:
            subscribed = self.tag_names
        else:
            available = set(self.tag_names)
            subscribed = [t for t in tag_names if t in available]
            missing = [t for t in tag_names if t not in available]
            if missing:
                logger.warning(f"Tags not found in simulator: {missing}")
        
        logger.info(f"Subscribed to {len(subscribed)} tags.")
        return subscribed

    def read(self, tag_name: str) -> TagReading | None:
        """단일 태그의 현재값을 읽는다."""
        tag_cfg = next((t for t in self._tags if t.name == tag_name), None)
        if tag_cfg is None:
            return None
        return self._generate_reading(tag_cfg)

    def read_all(self) -> list[TagReading]:
        """모든 태그의 현재값을 읽는다."""
        return [self._generate_reading(t) for t in self._tags]

    def start(self, callback: Callable[[list[TagReading]], None]) -> None:
        """주기적 데이터 생성을 시작한다.
        
        Args:
            callback: 데이터 배치를 받을 콜백 함수
        """
        if self._running:
            logger.warning("Simulator already running.")
            return
        if not self._connected:
            self.connect()

        self._callback = callback
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info(f"Simulator started. Interval: {self._interval}s")

    def stop(self) -> None:
        """데이터 생성을 중지한다."""
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=5.0)
            self._thread = None
        logger.info("Simulator stopped.")

    def _run_loop(self) -> None:
        """데이터 생성 루프."""
        while self._running:
            try:
                readings = self.read_all()
                if self._callback:
                    self._callback(readings)
            except Exception as e:
                logger.error(f"Simulator error: {e}")
            time.sleep(self._interval)

    def _generate_reading(self, tag: SimulatorTagConfig) -> TagReading:
        """단일 태그에 대해 발전소 유사 데이터를 생성한다.
        
        패턴:
        - 사인파: 느린 주기적 변동 (발전소 부하 변동 모사)
        - 가우시안 노이즈: 계측 잡음
        - 일간 사이클: 24시간 주기 부하 패턴 (낮에 높고 밤에 낮음)
        """
        elapsed = time.time() - self._start_time
        
        # 느린 사인파 변동 (주기 ~600초 = 10분)
        slow_wave = math.sin(2 * math.pi * elapsed / 600.0) * tag.noise_amplitude * 0.5
        
        # 빠른 사인파 (주기 ~60초)
        fast_wave = math.sin(2 * math.pi * elapsed / 60.0) * tag.noise_amplitude * 0.2
        
        # 가우시안 노이즈
        noise = random.gauss(0, tag.noise_amplitude * 0.3)
        
        # 일간 사이클 (24시간 주기)
        hour_of_day = datetime.now().hour + datetime.now().minute / 60.0
        daily_cycle = math.sin(2 * math.pi * (hour_of_day - 6) / 24.0) * tag.noise_amplitude * 0.3

        value = tag.base_value + slow_wave + fast_wave + noise + daily_cycle

        return TagReading(
            tag_name=tag.name,
            value=round(value, 4),
            quality=192,
            timestamp=datetime.utcnow(),
        )
