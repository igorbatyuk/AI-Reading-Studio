"""Block translation popup — translation only."""

from __future__ import annotations

import threading

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QDialog, QPushButton, QTextEdit, QVBoxLayout

from ..core.i18n import tr
from ..core.translation_service import TranslationService
from ..core.user_errors import humanize_error


class _TranslationBridge(QObject):
    ready = Signal(str)


class BlockTranslationPopup(QDialog):
    def __init__(
        self,
        sentence: str,
        translator: TranslationService,
        parent=None,
        *,
        mode: str = "block",
        show_source: bool = False,
        title: str | None = None,
    ) -> None:
        super().__init__(parent)
        self._translator = translator
        self.setWindowTitle(title or tr("reading.translation"))
        self.setMinimumSize(420, 200)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        if show_source:
            source = QTextEdit()
            source.setReadOnly(True)
            source.setMaximumHeight(100)
            source.setPlainText(sentence)
            layout.addWidget(source)

        self.content = QTextEdit()
        self.content.setReadOnly(True)
        self.content.setPlaceholderText(tr("reading.translation_loading"))
        layout.addWidget(self.content)

        close_btn = QPushButton(tr("dialog.close"))
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

        bridge = _TranslationBridge()
        bridge.ready.connect(self._show_translation)
        threading.Thread(
            target=self._fetch_translation,
            args=(sentence, translator, bridge, mode),
            daemon=True,
        ).start()

    @staticmethod
    def _fetch_translation(
        sentence: str,
        translator: TranslationService,
        bridge: _TranslationBridge,
        mode: str,
    ) -> None:
        if mode == "selection":
            text = translator.translate_selection(sentence).strip()
        else:
            text = translator.translate_sentence(sentence).strip()
        bridge.ready.emit(text)

    def _show_translation(self, text: str) -> None:
        if text:
            self.content.setPlainText(text)
            return
        message = tr("reading.translation_unavailable")
        if self._translator and self._translator.last_error:
            message = (
                f"{message}\n\n"
                f"{humanize_error(self._translator.last_error, area='translation')}"
            )
        self.content.setPlainText(message)
