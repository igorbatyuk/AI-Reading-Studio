"""Continue reading dialog."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from ..core.database import Book
from ..core.i18n import tr


class ContinueDialog(QDialog):
    def __init__(self, book: Book, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("continue.title"))
        self.setFixedSize(420, 240)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.result_action = "skip"

        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(30, 30, 30, 30)

        title = QLabel(tr("continue.title"))
        title.setObjectName("titleLabel")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        book_label = QLabel(book.title)
        book_label.setStyleSheet("font-size: 20px; font-weight: 600;")
        book_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(book_label)

        progress = QLabel(f"{book.progress_percent:.0f}%")
        progress.setStyleSheet("font-size: 16px; color: #4a7c59;")
        progress.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(progress)

        block_info = QLabel(tr("continue.block", n=book.current_block + 1))
        block_info.setStyleSheet("font-size: 13px; color: #888;")
        block_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(block_info)

        btn_row = QHBoxLayout()
        continue_btn = QPushButton(tr("continue.btn"))
        continue_btn.clicked.connect(self._on_continue)
        btn_row.addWidget(continue_btn)

        new_btn = QPushButton(tr("continue.choose"))
        new_btn.setObjectName("secondaryBtn")
        new_btn.clicked.connect(self._on_choose)
        btn_row.addWidget(new_btn)

        skip_btn = QPushButton(tr("continue.skip"))
        skip_btn.setObjectName("secondaryBtn")
        skip_btn.clicked.connect(self._on_skip)
        btn_row.addWidget(skip_btn)
        layout.addLayout(btn_row)

    def _on_continue(self) -> None:
        self.result_action = "continue"
        self.accept()

    def _on_choose(self) -> None:
        self.result_action = "choose"
        self.accept()

    def _on_skip(self) -> None:
        self.result_action = "skip"
        self.accept()
