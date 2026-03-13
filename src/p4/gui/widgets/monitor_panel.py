"""
P4 CS Tool — 시스템 모니터 패널.

OPC 수집 상태, DB 상태, 서비스 시작/중지를 제공한다.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QLabel, QPushButton, QTextEdit, QProgressBar,
    QGridLayout,
)
from PySide6.QtCore import Qt, QTimer, Signal, Slot

from p4.config import load_config

logger = logging.getLogger(__name__)


class StatCard(QWidget):
    """통계 카드 위젯."""

    def __init__(self, title: str, value: str = "0", color: str = "#64ffda", parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)

        self._title = QLabel(title)
        self._title.setStyleSheet(f"color: #8892b0; font-size: 11px; font-weight: bold;")
        self._title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._title)

        self._value = QLabel(value)
        self._value.setStyleSheet(f"color: {color}; font-size: 28px; font-weight: bold;")
        self._value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._value)

        self.setStyleSheet("""
            StatCard {
                background-color: #0d1b2a;
                border: 1px solid #2d2d44;
                border-radius: 8px;
            }
        """)

    def set_value(self, value: str):
        self._value.setText(value)


class MonitorPanel(QWidget):
    """시스템 모니터 패널."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._config = load_config()
        self._opc_client = None
        self._sampling_engine = None
        self._is_collecting = False
        self._setup_ui()

        # 타이머: 1초마다 통계 갱신
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._refresh_stats)
        self._refresh_timer.start(1000)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        # --- 수집 상태 카드 ---
        stats_group = QGroupBox("수집 통계")
        stats_grid = QGridLayout()
        stats_grid.setSpacing(12)

        self._saved_card = StatCard("저장됨", "0", "#2ecc71")
        self._skipped_card = StatCard("필터링됨", "0", "#f39c12")
        self._total_card = StatCard("전체", "0", "#3498db")
        self._uptime_card = StatCard("가동 시간", "00:00:00", "#64ffda")

        stats_grid.addWidget(self._saved_card, 0, 0)
        stats_grid.addWidget(self._skipped_card, 0, 1)
        stats_grid.addWidget(self._total_card, 0, 2)
        stats_grid.addWidget(self._uptime_card, 0, 3)

        stats_group.setLayout(stats_grid)
        layout.addWidget(stats_group)

        # --- 서비스 제어 ---
        control_group = QGroupBox("서비스 제어")
        control_layout = QVBoxLayout()

        # 상태 바
        status_row = QHBoxLayout()
        self._service_status = QLabel("● 수집 중지됨")
        self._service_status.setStyleSheet("color: #e74c3c; font-weight: bold; font-size: 14px;")
        status_row.addWidget(self._service_status)
        status_row.addStretch()
        control_layout.addLayout(status_row)

        # 버튼
        btn_row = QHBoxLayout()

        self._start_btn = QPushButton("▶ 수집 시작")
        self._start_btn.setObjectName("btn_success")
        self._start_btn.clicked.connect(self._on_start)
        btn_row.addWidget(self._start_btn)

        self._stop_btn = QPushButton("⏹ 수집 중지")
        self._stop_btn.setObjectName("btn_danger")
        self._stop_btn.setEnabled(False)
        self._stop_btn.clicked.connect(self._on_stop)
        btn_row.addWidget(self._stop_btn)

        btn_row.addStretch()
        control_layout.addLayout(btn_row)

        control_group.setLayout(control_layout)
        layout.addWidget(control_group)

        # --- DB 상태 ---
        db_group = QGroupBox("데이터베이스 상태")
        db_layout = QGridLayout()
        db_layout.setSpacing(8)

        db_layout.addWidget(QLabel("DB URL:"), 0, 0)
        self._db_url_label = QLabel(self._config.database.url)
        self._db_url_label.setStyleSheet("color: #a8b2d1;")
        db_layout.addWidget(self._db_url_label, 0, 1)

        db_layout.addWidget(QLabel("실시간 행 수:"), 1, 0)
        self._rt_count_label = QLabel("조회 중...")
        self._rt_count_label.setStyleSheet("color: #64ffda;")
        db_layout.addWidget(self._rt_count_label, 1, 1)

        db_layout.addWidget(QLabel("히스토리 행 수:"), 2, 0)
        self._hist_count_label = QLabel("조회 중...")
        self._hist_count_label.setStyleSheet("color: #64ffda;")
        db_layout.addWidget(self._hist_count_label, 2, 1)

        db_group.setLayout(db_layout)
        layout.addWidget(db_group)

        # --- 시스템 로그 ---
        log_group = QGroupBox("시스템 로그")
        log_layout = QVBoxLayout()

        self._log_text = QTextEdit()
        self._log_text.setReadOnly(True)
        self._log_text.setMaximumHeight(180)
        log_layout.addWidget(self._log_text)

        log_group.setLayout(log_layout)
        layout.addWidget(log_group)

        layout.addStretch()

    def _on_start(self):
        """수집 시작."""
        self._append_log("수집을 시작합니다...")
        try:
            from p4.config import load_config
            from p4.db.connection import get_engine
            from p4.db.schema import init_db
            from p4.opc.client import OpcClient
            from p4.sampling.engine import SamplingEngine

            config = load_config()

            # DB 초기화
            engine = get_engine(config)
            init_db(engine)

            # OPC + 샘플링 시작
            self._opc_client = OpcClient(config)
            self._sampling_engine = SamplingEngine(config)

            self._opc_client.start(simulate=config.simulator.enabled)
            self._sampling_engine.start()

            self._is_collecting = True
            self._start_time = datetime.now()
            self._start_btn.setEnabled(False)
            self._stop_btn.setEnabled(True)
            self._service_status.setText("● 수집 중")
            self._service_status.setStyleSheet("color: #2ecc71; font-weight: bold; font-size: 14px;")
            self._append_log("✅ 수집이 시작되었습니다.")
        except Exception as e:
            self._append_log(f"❌ 수집 시작 실패: {e}")
            logger.error(f"Collection start failed: {e}")

    def _on_stop(self):
        """수집 중지."""
        self._append_log("수집을 중지합니다...")
        try:
            if self._opc_client:
                self._opc_client.stop()
            if self._sampling_engine:
                self._sampling_engine.stop()

            self._is_collecting = False
            self._start_btn.setEnabled(True)
            self._stop_btn.setEnabled(False)
            self._service_status.setText("● 수집 중지됨")
            self._service_status.setStyleSheet("color: #e74c3c; font-weight: bold; font-size: 14px;")
            self._append_log("✅ 수집이 중지되었습니다.")
        except Exception as e:
            self._append_log(f"❌ 수집 중지 실패: {e}")
            logger.error(f"Collection stop failed: {e}")

    @Slot()
    def _refresh_stats(self):
        """통계 카드 갱신."""
        if self._is_collecting and self._opc_client:
            stats = self._opc_client.stats
            self._saved_card.set_value(f"{stats['saved']:,}")
            self._skipped_card.set_value(f"{stats['skipped']:,}")
            self._total_card.set_value(f"{stats['total']:,}")

            # 가동 시간
            elapsed = datetime.now() - self._start_time
            hours, remainder = divmod(int(elapsed.total_seconds()), 3600)
            minutes, seconds = divmod(remainder, 60)
            self._uptime_card.set_value(f"{hours:02d}:{minutes:02d}:{seconds:02d}")

        # DB 행 수 조회 (5초마다)
        if not hasattr(self, "_db_refresh_counter"):
            self._db_refresh_counter = 0
        self._db_refresh_counter += 1
        if self._db_refresh_counter % 5 == 0:
            self._refresh_db_stats()

    def _refresh_db_stats(self):
        """DB 통계 갱신."""
        try:
            from p4.db.connection import get_session
            from p4.db.models import RealtimeData, HistoryMin
            from sqlalchemy import func

            config = load_config()
            session = get_session(config)
            try:
                rt_count = session.query(func.count(RealtimeData.id)).scalar() or 0
                hist_count = session.query(func.count(HistoryMin.id)).scalar() or 0
                self._rt_count_label.setText(f"{rt_count:,}")
                self._hist_count_label.setText(f"{hist_count:,}")
            finally:
                session.close()
        except Exception:
            self._rt_count_label.setText("N/A")
            self._hist_count_label.setText("N/A")

    def _append_log(self, message: str):
        """로그 텍스트 추가."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self._log_text.append(f"[{timestamp}] {message}")
