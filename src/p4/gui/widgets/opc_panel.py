"""
P4 CS Tool — OPC 설정 패널.

OPC DA 서버 접속 정보 설정, 연결 테스트, 시뮬레이터 모드 전환을 제공한다.
"""

from __future__ import annotations

import logging
import threading

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QLabel, QLineEdit, QSpinBox, QPushButton, QCheckBox,
    QFormLayout, QTextEdit,
)
from PySide6.QtCore import Qt, Signal, QTimer

from p4.config import load_config, AppConfig

logger = logging.getLogger(__name__)


class OpcPanel(QWidget):
    """OPC DA 서버 설정 패널."""

    # 시그널
    connection_status_changed = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._config: AppConfig = load_config()
        self._opc_client = None
        self._is_connected = False
        self._setup_ui()
        self._load_from_config()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        # --- OPC 서버 설정 ---
        server_group = QGroupBox("OPC DA 서버 설정")
        server_form = QFormLayout()
        server_form.setSpacing(10)

        self._host_edit = QLineEdit()
        self._host_edit.setPlaceholderText("예: localhost 또는 192.168.1.100")
        server_form.addRow("호스트:", self._host_edit)

        self._prog_id_edit = QLineEdit()
        self._prog_id_edit.setPlaceholderText("예: Matrikon.OPC.Simulation.1")
        server_form.addRow("ProgID:", self._prog_id_edit)

        self._update_rate_spin = QSpinBox()
        self._update_rate_spin.setRange(100, 10000)
        self._update_rate_spin.setSuffix(" ms")
        self._update_rate_spin.setSingleStep(100)
        server_form.addRow("갱신 주기:", self._update_rate_spin)

        self._reconnect_spin = QSpinBox()
        self._reconnect_spin.setRange(1, 30)
        self._reconnect_spin.setSuffix(" 회")
        server_form.addRow("재접속 시도:", self._reconnect_spin)

        server_group.setLayout(server_form)
        layout.addWidget(server_group)

        # --- 시뮬레이터 모드 ---
        sim_group = QGroupBox("시뮬레이터 모드")
        sim_layout = QVBoxLayout()

        self._sim_checkbox = QCheckBox("시뮬레이터 모드 사용 (실제 OPC 서버 불필요)")
        self._sim_checkbox.stateChanged.connect(self._on_sim_toggle)
        sim_layout.addWidget(self._sim_checkbox)

        sim_info = QLabel(
            "시뮬레이터 모드 활성화 시 가상 태그 데이터가 자동 생성됩니다.\n"
            "OPC DA 서버가 없는 개발/테스트 환경에서 사용합니다."
        )
        sim_info.setStyleSheet("color: #8892b0; font-size: 12px; padding: 4px;")
        sim_info.setWordWrap(True)
        sim_layout.addWidget(sim_info)

        sim_group.setLayout(sim_layout)
        layout.addWidget(sim_group)

        # --- 연결 상태 & 버튼 ---
        action_group = QGroupBox("연결 관리")
        action_layout = QVBoxLayout()

        # 상태 표시
        status_row = QHBoxLayout()
        status_label = QLabel("연결 상태:")
        self._status_indicator = QLabel("● 미연결")
        self._status_indicator.setStyleSheet("color: #e74c3c; font-weight: bold; font-size: 14px;")
        status_row.addWidget(status_label)
        status_row.addWidget(self._status_indicator)
        status_row.addStretch()
        action_layout.addLayout(status_row)

        # 버튼 행
        btn_row = QHBoxLayout()

        self._test_btn = QPushButton("🔌 연결 테스트")
        self._test_btn.clicked.connect(self._on_test_connection)
        btn_row.addWidget(self._test_btn)

        self._save_btn = QPushButton("💾 설정 저장")
        self._save_btn.setObjectName("btn_success")
        self._save_btn.clicked.connect(self._on_save_config)
        btn_row.addWidget(self._save_btn)

        self._reset_btn = QPushButton("↩️ 초기화")
        self._reset_btn.clicked.connect(self._load_from_config)
        btn_row.addWidget(self._reset_btn)

        btn_row.addStretch()
        action_layout.addLayout(btn_row)

        action_group.setLayout(action_layout)
        layout.addWidget(action_group)

        # --- 로그 출력 ---
        log_group = QGroupBox("OPC 로그")
        log_layout = QVBoxLayout()

        self._log_text = QTextEdit()
        self._log_text.setReadOnly(True)
        self._log_text.setMaximumHeight(200)
        log_layout.addWidget(self._log_text)

        log_group.setLayout(log_layout)
        layout.addWidget(log_group)

        layout.addStretch()

    def _load_from_config(self):
        """설정 파일에서 UI 값 로드."""
        self._host_edit.setText(self._config.opc.host)
        self._prog_id_edit.setText(self._config.opc.prog_id)
        self._update_rate_spin.setValue(self._config.opc.update_rate_ms)
        self._reconnect_spin.setValue(self._config.opc.reconnect_max_retries)
        self._sim_checkbox.setChecked(self._config.simulator.enabled)
        self._append_log("설정 파일에서 값을 불러왔습니다.")

    def _on_sim_toggle(self, state):
        """시뮬레이터 토글."""
        enabled = state == Qt.CheckState.Checked.value
        self._host_edit.setEnabled(not enabled)
        self._prog_id_edit.setEnabled(not enabled)
        self._append_log(f"시뮬레이터 모드: {'ON' if enabled else 'OFF'}")

    def _on_test_connection(self):
        """연결 테스트."""
        self._test_btn.setEnabled(False)
        self._test_btn.setText("⏳ 연결 중...")
        self._append_log("연결 테스트를 시작합니다...")

        if self._sim_checkbox.isChecked():
            # 시뮬레이터 모드: 즉시 성공
            QTimer.singleShot(500, self._on_sim_connect_success)
        else:
            # 실제 OPC: 비동기 연결 시도
            self._append_log(f"OPC 서버 접속 시도: {self._host_edit.text()} / {self._prog_id_edit.text()}")
            QTimer.singleShot(1000, self._on_real_connect_attempt)

    def _on_sim_connect_success(self):
        """시뮬레이터 연결 성공 처리."""
        self._is_connected = True
        self._status_indicator.setText("● 연결됨 (시뮬레이터)")
        self._status_indicator.setStyleSheet("color: #2ecc71; font-weight: bold; font-size: 14px;")
        self._test_btn.setEnabled(True)
        self._test_btn.setText("🔌 연결 테스트")
        self._append_log("✅ 시뮬레이터 연결 성공!")
        self.connection_status_changed.emit(True)

    def _on_real_connect_attempt(self):
        """실제 OPC 연결 시도 (현재는 미구현 알림)."""
        self._test_btn.setEnabled(True)
        self._test_btn.setText("🔌 연결 테스트")
        self._append_log("⚠️ 실제 OPC DA 연결은 추후 구현 예정입니다. 시뮬레이터 모드를 사용해 주세요.")
        self._status_indicator.setText("● 미연결")
        self._status_indicator.setStyleSheet("color: #e74c3c; font-weight: bold; font-size: 14px;")

    def _on_save_config(self):
        """현재 UI 값을 config/defaults.yaml에 저장."""
        import yaml
        from p4.config import PROJECT_ROOT

        config_path = PROJECT_ROOT / "config" / "defaults.yaml"
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}

            data.setdefault("opc", {})
            data["opc"]["host"] = self._host_edit.text()
            data["opc"]["prog_id"] = self._prog_id_edit.text()
            data["opc"]["update_rate_ms"] = self._update_rate_spin.value()
            data["opc"]["reconnect_max_retries"] = self._reconnect_spin.value()

            data.setdefault("simulator", {})
            data["simulator"]["enabled"] = self._sim_checkbox.isChecked()

            with open(config_path, "w", encoding="utf-8") as f:
                yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

            self._append_log(f"✅ 설정이 저장되었습니다: {config_path}")
        except Exception as e:
            self._append_log(f"❌ 설정 저장 실패: {e}")

    def _append_log(self, message: str):
        """로그 텍스트 추가."""
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        self._log_text.append(f"[{timestamp}] {message}")

    @property
    def is_simulator_mode(self) -> bool:
        return self._sim_checkbox.isChecked()

    def get_opc_settings(self) -> dict:
        """현재 OPC 설정값 반환."""
        return {
            "host": self._host_edit.text(),
            "prog_id": self._prog_id_edit.text(),
            "update_rate_ms": self._update_rate_spin.value(),
            "reconnect_max_retries": self._reconnect_spin.value(),
            "simulator_enabled": self._sim_checkbox.isChecked(),
        }
