"""Application entry point."""

import sys

from PySide6.QtWidgets import QApplication

from .core.logging_config import setup_logging
from .ui.main_window import MainWindow


def run() -> None:
    setup_logging()
    app = QApplication(sys.argv)
    app.setApplicationName("AI Reading Studio")
    app.setOrganizationName("AIReadingStudio")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())
