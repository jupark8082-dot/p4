"""
P4 데이터 샘플링 엔진.

TB_REALTIME_DATA의 초 단위 데이터를 분 단위 평균으로 집계하여
TB_HISTORY_MIN에 저장한다.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta

from sqlalchemy import func, and_

from p4.config import AppConfig, get_config
from p4.db.connection import get_session
from p4.db.models import RealtimeData, HistoryMin

logger = logging.getLogger(__name__)


class SamplingEngine:
    """분 단위 데이터 집계 엔진.
    
    주기적으로 TB_REALTIME_DATA에서 이전 분의 데이터를 읽어
    태그별 AVG, MIN, MAX, STD, COUNT를 계산하고
    TB_HISTORY_MIN에 저장한다.
    """

    def __init__(self, config: AppConfig | None = None):
        self._config = config or get_config()
        self._interval_min = self._config.data.sampling_interval_min
        self._running = False
        self._timer: threading.Timer | None = None
        self._processed_count = 0

    @property
    def processed_count(self) -> int:
        """처리된 집계 횟수."""
        return self._processed_count

    def start(self) -> None:
        """주기적 집계를 시작한다."""
        if self._running:
            logger.warning("Sampling engine already running.")
            return

        self._running = True
        self._schedule_next()
        logger.info(
            f"Sampling engine started. "
            f"Interval: {self._interval_min} min."
        )

    def stop(self) -> None:
        """집계를 중지한다."""
        self._running = False
        if self._timer:
            self._timer.cancel()
            self._timer = None
        logger.info(
            f"Sampling engine stopped. "
            f"Total aggregations: {self._processed_count}"
        )

    def aggregate_now(self) -> int:
        """즉시 집계를 수행한다 (수동 호출용).
        
        Returns:
            저장된 레코드 수
        """
        now = datetime.utcnow()
        # 현재 분의 시작~종료 범위 계산
        period_end = now.replace(second=0, microsecond=0)
        period_start = period_end - timedelta(minutes=self._interval_min)

        return self._do_aggregate(period_start, period_end)

    def _schedule_next(self) -> None:
        """다음 집계 타이머를 예약한다."""
        if not self._running:
            return

        # 다음 분 경계까지 대기 + 5초 여유 (데이터 수집 지연 고려)
        now = datetime.utcnow()
        next_minute = (now + timedelta(minutes=self._interval_min)).replace(
            second=5, microsecond=0
        )
        delay = (next_minute - now).total_seconds()
        if delay < 0:
            delay = self._interval_min * 60

        self._timer = threading.Timer(delay, self._tick)
        self._timer.daemon = True
        self._timer.start()

    def _tick(self) -> None:
        """타이머 콜백: 집계 수행 후 다음 타이머 예약."""
        try:
            count = self.aggregate_now()
            logger.info(f"Sampling aggregation complete. {count} records saved.")
        except Exception as e:
            logger.error(f"Sampling aggregation error: {e}")
        finally:
            self._schedule_next()

    def _do_aggregate(
        self, period_start: datetime, period_end: datetime
    ) -> int:
        """지정된 기간에 대해 태그별 통계를 계산하고 저장한다."""
        session = get_session(self._config)
        saved = 0

        try:
            # 태그별 집계 쿼리
            results = (
                session.query(
                    RealtimeData.tag_name,
                    func.avg(RealtimeData.value).label("avg_val"),
                    func.min(RealtimeData.value).label("min_val"),
                    func.max(RealtimeData.value).label("max_val"),
                    func.count(RealtimeData.value).label("cnt"),
                )
                .filter(
                    and_(
                        RealtimeData.timestamp >= period_start,
                        RealtimeData.timestamp < period_end,
                    )
                )
                .group_by(RealtimeData.tag_name)
                .all()
            )

            for row in results:
                # 표준편차는 별도 계산 (SQLite 호환)
                std_val = self._calc_std(
                    session, row.tag_name, period_start, period_end, row.avg_val
                )

                history = HistoryMin(
                    tag_name=row.tag_name,
                    avg_value=round(row.avg_val, 6),
                    min_value=round(row.min_val, 6),
                    max_value=round(row.max_val, 6),
                    std_value=round(std_val, 6) if std_val is not None else None,
                    sample_count=row.cnt,
                    period_start=period_start,
                    period_end=period_end,
                )
                session.add(history)
                saved += 1

            session.commit()
            self._processed_count += 1
            return saved

        except Exception as e:
            session.rollback()
            logger.error(f"Aggregation failed: {e}")
            raise
        finally:
            session.close()

    @staticmethod
    def _calc_std(
        session, tag_name: str,
        period_start: datetime, period_end: datetime,
        mean_val: float,
    ) -> float | None:
        """표준편차를 수동 계산한다 (SQLite 호환).
        
        SQLite는 내장 STDEV 함수가 없으므로 수동으로 계산한다.
        """
        values = (
            session.query(RealtimeData.value)
            .filter(
                and_(
                    RealtimeData.tag_name == tag_name,
                    RealtimeData.timestamp >= period_start,
                    RealtimeData.timestamp < period_end,
                )
            )
            .all()
        )

        if len(values) < 2:
            return None

        sq_diffs = [(v[0] - mean_val) ** 2 for v in values]
        variance = sum(sq_diffs) / (len(sq_diffs) - 1)
        return variance ** 0.5
