"""
P4 CS Tool — 메인 윈도우.

탭 기반 레이아웃으로 OPC 설정, 태그 관리, AI 모델 빌더, 시스템 모니터를 제공한다.
"""

from __future__ import annotations

import logging

from PySide6.QtWidgets import (
    QMainWindow, QTabWidget, QStatusBar, QMenuBar, QToolBar,
    QLabel, QVBoxLayout, QWidget,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QIcon

from p4.gui.widgets.opc_panel import OpcPanel
from p4.gui.widgets.tag_panel import TagPanel
from p4.gui.widgets.monitor_panel import MonitorPanel

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """CS Tool 메인 윈도우."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("P4 CS Tool — Power Plant Performance Predictor")
        self.setMinimumSize(1000, 700)
        self.resize(1200, 800)

        # --- 중앙 탭 위젯 ---
        self._tabs = QTabWidget()
        self._tabs.setTabPosition(QTabWidget.TabPosition.West)
        self._tabs.setDocumentMode(True)

        # 패널 생성
        self._opc_panel = OpcPanel()
        self._tag_panel = TagPanel()
        self._monitor_panel = MonitorPanel()

        # 탭 추가
        self._tabs.addTab(self._opc_panel, "⚡ OPC 설정")
        self._tabs.addTab(self._tag_panel, "🏷️ 태그 관리")
        # AI 모델 빌더는 Sprint 2에서 추가
        self._ai_placeholder = QWidget()
        _ai_layout = QVBoxLayout(self._ai_placeholder)
        _ai_label = QLabel("AI 모델 빌더 — Sprint 2에서 구현 예정")
        _ai_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        _ai_label.setStyleSheet("color: #888; font-size: 16px;")
        _ai_layout.addWidget(_ai_label)
        self._tabs.addTab(self._ai_placeholder, "🧠 AI 모델")
        self._tabs.addTab(self._monitor_panel, "📊 시스템 모니터")

        self.setCentralWidget(self._tabs)

        # --- 상태 바 ---
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_bar.showMessage("P4 CS Tool 준비 완료")

        # --- 메뉴 바 ---
        self._setup_menu()

        # --- 스타일 ---
        self._apply_style()

        logger.info("MainWindow initialized.")

    def _setup_menu(self):
        """메뉴 바 설정."""
        menu_bar = self.menuBar()

        # 파일 메뉴
        file_menu = menu_bar.addMenu("파일(&F)")
        exit_action = QAction("종료(&X)", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # 도움말 메뉴
        help_menu = menu_bar.addMenu("도움말(&H)")
        about_action = QAction("P4 CS Tool 정보(&A)", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _show_about(self):
        """정보 다이얼로그."""
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.about(
            self,
            "P4 CS Tool",
            "<h3>P4 — AI-Powered Power Plant Performance Predictor</h3>"
            "<p>CS Tool v0.1.0</p>"
            "<p>발전소 OPC DA 데이터 관리 및 AI 모델 구축 도구</p>"
        )

    def _apply_style(self):
        """다크 테마 스타일시트 적용."""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1a1a2e;
            }
            QTabWidget::pane {
                border: 1px solid #2d2d44;
                background-color: #16213e;
                border-radius: 4px;
            }
            QTabBar::tab {
                background-color: #1a1a2e;
                color: #8892b0;
                padding: 12px 8px;
                margin: 2px;
                border-radius: 4px;
                min-width: 40px;
                font-size: 13px;
            }
            QTabBar::tab:selected {
                background-color: #0f3460;
                color: #64ffda;
                font-weight: bold;
            }
            QTabBar::tab:hover {
                background-color: #233554;
                color: #ccd6f6;
            }
            QStatusBar {
                background-color: #0a0a1a;
                color: #64ffda;
                font-size: 12px;
                padding: 4px;
            }
            QMenuBar {
                background-color: #0a0a1a;
                color: #ccd6f6;
            }
            QMenuBar::item:selected {
                background-color: #0f3460;
            }
            QMenu {
                background-color: #1a1a2e;
                color: #ccd6f6;
                border: 1px solid #2d2d44;
            }
            QMenu::item:selected {
                background-color: #0f3460;
            }
            QLabel {
                color: #ccd6f6;
            }
            QGroupBox {
                color: #64ffda;
                border: 1px solid #2d2d44;
                border-radius: 6px;
                margin-top: 12px;
                padding-top: 16px;
                font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
            }
            QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
                background-color: #0d1b2a;
                color: #ccd6f6;
                border: 1px solid #2d2d44;
                border-radius: 4px;
                padding: 6px 10px;
                font-size: 13px;
            }
            QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
                border-color: #64ffda;
            }
            QPushButton {
                background-color: #0f3460;
                color: #ccd6f6;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1a5276;
            }
            QPushButton:pressed {
                background-color: #0a2647;
            }
            QPushButton:disabled {
                background-color: #2d2d44;
                color: #555;
            }
            QPushButton#btn_success {
                background-color: #1b4332;
            }
            QPushButton#btn_success:hover {
                background-color: #2d6a4f;
            }
            QPushButton#btn_danger {
                background-color: #641220;
            }
            QPushButton#btn_danger:hover {
                background-color: #85182a;
            }
            QTableWidget {
                background-color: #0d1b2a;
                color: #ccd6f6;
                border: 1px solid #2d2d44;
                gridline-color: #2d2d44;
                border-radius: 4px;
            }
            QTableWidget::item {
                padding: 4px 8px;
            }
            QTableWidget::item:selected {
                background-color: #0f3460;
            }
            QHeaderView::section {
                background-color: #1a1a2e;
                color: #64ffda;
                padding: 6px;
                border: 1px solid #2d2d44;
                font-weight: bold;
            }
            QCheckBox {
                color: #ccd6f6;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border-radius: 3px;
                border: 2px solid #2d2d44;
                background-color: #0d1b2a;
            }
            QCheckBox::indicator:checked {
                background-color: #64ffda;
                border-color: #64ffda;
            }
            QProgressBar {
                border: 1px solid #2d2d44;
                border-radius: 4px;
                background-color: #0d1b2a;
                text-align: center;
                color: #ccd6f6;
            }
            QProgressBar::chunk {
                background-color: #64ffda;
                border-radius: 3px;
            }
            QTextEdit {
                background-color: #0d1b2a;
                color: #a8b2d1;
                border: 1px solid #2d2d44;
                border-radius: 4px;
                font-family: 'Consolas', 'D2Coding', monospace;
                font-size: 12px;
            }
            QScrollBar:vertical {
                background: #0d1b2a;
                width: 10px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical {
                background: #2d2d44;
                border-radius: 5px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background: #64ffda;
            }
        """)
