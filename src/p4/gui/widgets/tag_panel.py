"""
P4 CS Tool — 태그 관리 패널.

OPC 태그 목록 조회, 추가/삭제, 데드밴드 설정을 제공한다.
config/defaults.yaml의 simulator.tags와 deadband 설정을 GUI로 관리한다.
"""

from __future__ import annotations

import logging

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QLabel, QLineEdit, QDoubleSpinBox, QComboBox,
    QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QMessageBox,
)
from PySide6.QtCore import Qt

from p4.config import load_config

logger = logging.getLogger(__name__)


class TagPanel(QWidget):
    """태그 관리 패널."""

    TAG_COLUMNS = ["태그명", "단위", "기준값", "노이즈 범위", "데드밴드 타입", "데드밴드 임계값"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._config = load_config()
        self._setup_ui()
        self._load_tags()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # --- 데드밴드 기본 설정 ---
        db_group = QGroupBox("데드밴드 기본 설정")
        db_layout = QHBoxLayout()

        db_layout.addWidget(QLabel("기본 타입:"))
        self._db_type_combo = QComboBox()
        self._db_type_combo.addItems(["percent", "absolute"])
        self._db_type_combo.setCurrentText(self._config.deadband.default_type)
        db_layout.addWidget(self._db_type_combo)

        db_layout.addWidget(QLabel("기본 임계값:"))
        self._db_threshold_spin = QDoubleSpinBox()
        self._db_threshold_spin.setRange(0.01, 100.0)
        self._db_threshold_spin.setDecimals(2)
        self._db_threshold_spin.setValue(self._config.deadband.default_threshold)
        db_layout.addWidget(self._db_threshold_spin)

        db_layout.addStretch()
        db_group.setLayout(db_layout)
        layout.addWidget(db_group)

        # --- 태그 테이블 ---
        table_group = QGroupBox("태그 목록")
        table_layout = QVBoxLayout()

        self._table = QTableWidget()
        self._table.setColumnCount(len(self.TAG_COLUMNS))
        self._table.setHorizontalHeaderLabels(self.TAG_COLUMNS)
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for i in range(1, len(self.TAG_COLUMNS)):
            self._table.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        table_layout.addWidget(self._table)

        # 버튼 행
        btn_row = QHBoxLayout()

        self._add_btn = QPushButton("➕ 태그 추가")
        self._add_btn.clicked.connect(self._on_add_tag)
        btn_row.addWidget(self._add_btn)

        self._remove_btn = QPushButton("🗑️ 선택 삭제")
        self._remove_btn.setObjectName("btn_danger")
        self._remove_btn.clicked.connect(self._on_remove_tag)
        btn_row.addWidget(self._remove_btn)

        btn_row.addStretch()

        self._save_btn = QPushButton("💾 설정 저장")
        self._save_btn.setObjectName("btn_success")
        self._save_btn.clicked.connect(self._on_save)
        btn_row.addWidget(self._save_btn)

        table_layout.addLayout(btn_row)
        table_group.setLayout(table_layout)
        layout.addWidget(table_group)

        # --- 통계 ---
        stats_layout = QHBoxLayout()
        self._tag_count_label = QLabel("등록 태그: 0개")
        self._tag_count_label.setStyleSheet("color: #64ffda; font-size: 13px;")
        stats_layout.addWidget(self._tag_count_label)
        stats_layout.addStretch()
        layout.addLayout(stats_layout)

    def _load_tags(self):
        """설정 파일에서 태그 목록 로드."""
        self._table.setRowCount(0)
        db_type = self._config.deadband.default_type
        db_threshold = self._config.deadband.default_threshold

        for tag in self._config.simulator.tags:
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, QTableWidgetItem(tag.name))
            self._table.setItem(row, 1, QTableWidgetItem(tag.unit))
            self._table.setItem(row, 2, QTableWidgetItem(str(tag.base_value)))
            self._table.setItem(row, 3, QTableWidgetItem(str(tag.noise_amplitude)))
            self._table.setItem(row, 4, QTableWidgetItem(db_type))
            self._table.setItem(row, 5, QTableWidgetItem(str(db_threshold)))

        self._update_count()

    def _on_add_tag(self):
        """새 태그 행 추가."""
        row = self._table.rowCount()
        self._table.insertRow(row)
        self._table.setItem(row, 0, QTableWidgetItem("NEW_TAG"))
        self._table.setItem(row, 1, QTableWidgetItem(""))
        self._table.setItem(row, 2, QTableWidgetItem("100.0"))
        self._table.setItem(row, 3, QTableWidgetItem("1.0"))
        self._table.setItem(row, 4, QTableWidgetItem(self._db_type_combo.currentText()))
        self._table.setItem(row, 5, QTableWidgetItem(str(self._db_threshold_spin.value())))
        self._table.scrollToBottom()
        self._table.editItem(self._table.item(row, 0))
        self._update_count()

    def _on_remove_tag(self):
        """선택된 태그 삭제."""
        selected = self._table.selectedItems()
        if not selected:
            return
        rows = sorted(set(item.row() for item in selected), reverse=True)
        for row in rows:
            tag_name = self._table.item(row, 0).text()
            self._table.removeRow(row)
            logger.info(f"Tag removed: {tag_name}")
        self._update_count()

    def _on_save(self):
        """테이블 내용을 config/defaults.yaml에 저장."""
        import yaml
        from p4.config import PROJECT_ROOT

        config_path = PROJECT_ROOT / "config" / "defaults.yaml"
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}

            # 데드밴드 기본 설정
            data.setdefault("deadband", {})
            data["deadband"]["default_type"] = self._db_type_combo.currentText()
            data["deadband"]["default_threshold"] = self._db_threshold_spin.value()

            # 태그 목록
            tags = []
            for row in range(self._table.rowCount()):
                tag = {
                    "name": self._table.item(row, 0).text(),
                    "unit": self._table.item(row, 1).text(),
                    "base_value": float(self._table.item(row, 2).text()),
                    "noise_amplitude": float(self._table.item(row, 3).text()),
                }
                tags.append(tag)

            data.setdefault("simulator", {})
            data["simulator"]["tags"] = tags

            with open(config_path, "w", encoding="utf-8") as f:
                yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

            QMessageBox.information(self, "저장 완료", f"태그 설정이 저장되었습니다.\n{config_path}")
        except Exception as e:
            QMessageBox.critical(self, "저장 실패", f"설정 저장 중 오류:\n{e}")

    def _update_count(self):
        """태그 수 표시 업데이트."""
        count = self._table.rowCount()
        self._tag_count_label.setText(f"등록 태그: {count}개")

    def get_tag_names(self) -> list[str]:
        """현재 태그명 목록 반환."""
        return [
            self._table.item(row, 0).text()
            for row in range(self._table.rowCount())
        ]
