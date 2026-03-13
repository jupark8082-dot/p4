"""
P4 CS Tool — 애플리케이션 진입점.

PySide6 QApplication을 생성하고 메인 윈도우를 실행한다.
시스템 트레이 아이콘을 지원한다.
"""

from __future__ import annotations

import sys
import logging

from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PySide6.QtGui import QIcon, QAction, QPixmap, QPainter, QColor, QFont
from PySide6.QtCore import Qt

from p4.gui.main_window import MainWindow

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)-7s] %(name)-25s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("p4.gui")


def _create_default_icon() -> QIcon:
    """기본 아이콘 생성 (아이콘 파일이 없을 때 사용)."""
    pixmap = QPixmap(64, 64)
    pixmap.fill(QColor(0, 0, 0, 0))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    # 배경 원
    painter.setBrush(QColor("#0f3460"))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(2, 2, 60, 60)

    # 텍스트
    font = QFont("Arial", 24, QFont.Weight.Bold)
    painter.setFont(font)
    painter.setPen(QColor("#64ffda"))
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "P4")
    painter.end()

    return QIcon(pixmap)


def main():
    """CS Tool 메인 진입점."""
    app = QApplication(sys.argv)
    app.setApplicationName("P4 CS Tool")
    app.setOrganizationName("WAtech")

    icon = _create_default_icon()
    app.setWindowIcon(icon)

    # 메인 윈도우
    window = MainWindow()
    window.setWindowIcon(icon)
    window.show()

    # 시스템 트레이
    if QSystemTrayIcon.isSystemTrayAvailable():
        tray = QSystemTrayIcon(icon, app)
        tray.setToolTip("P4 CS Tool")

        tray_menu = QMenu()
        show_action = QAction("열기", tray_menu)
        show_action.triggered.connect(window.showNormal)
        tray_menu.addAction(show_action)

        quit_action = QAction("종료", tray_menu)
        quit_action.triggered.connect(app.quit)
        tray_menu.addAction(quit_action)

        tray.setContextMenu(tray_menu)
        tray.activated.connect(
            lambda reason: window.showNormal()
            if reason == QSystemTrayIcon.ActivationReason.DoubleClick
            else None
        )
        tray.show()

    logger.info("P4 CS Tool started.")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
