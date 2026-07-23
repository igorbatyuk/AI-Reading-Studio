"""Word translation popup on click."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..core.i18n import tr
from ..core.user_errors import humanize_error
from ..core.translation_service import TranslationService, WordTranslation
from ..core.tts_engine import TTSEngine


class WordPopup(QDialog):
    closed = Signal()

    def __init__(
        self,
        word: str,
        sentence: str,
        translator: TranslationService,
        tts: TTSEngine,
        *,
        word_tts_enabled: bool = True,
        parent: QWidget | None = None,
        global_pos=None,
    ) -> None:
        super().__init__(parent)
        self.word = word
        self.sentence = sentence
        self.translator = translator
        self.tts = tts
        self.word_tts_enabled = word_tts_enabled

        self.setWindowTitle(word)
        self.setMinimumWidth(280)
        self.setWindowFlags(
            Qt.WindowType.Dialog | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setModal(False)

        self._build_ui()
        self._load_translation()
        self.adjustSize()
        self._position(global_pos, parent)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        self.word_label = QLabel(self.word)
        self.word_label.setStyleSheet("font-size: 22px; font-weight: 700;")
        layout.addWidget(self.word_label)

        self.translation_label = QLabel(tr("word.loading"))
        self.translation_label.setStyleSheet("font-size: 20px; color: #4a7c59;")
        self.translation_label.setWordWrap(True)
        layout.addWidget(self.translation_label)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        if self.word_tts_enabled:
            self.play_btn = QPushButton(tr("word.play"))
            self.play_btn.setObjectName("secondaryBtn")
            self.play_btn.clicked.connect(self._play_word)
            btn_row.addWidget(self.play_btn)
        close_btn = QPushButton(tr("word.close"))
        close_btn.setObjectName("secondaryBtn")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    def _position(self, global_pos, parent) -> None:
        if global_pos:
            self.move(
                max(10, global_pos.x() - self.width() // 2),
                max(10, global_pos.y() + 10),
            )
        elif parent:
            center = parent.mapToGlobal(parent.rect().center())
            self.move(
                max(10, center.x() - self.width() // 2),
                max(10, center.y() - self.height() // 2),
            )

    def _load_translation(self) -> None:
        if self.word_tts_enabled:
            self.tts.prefetch(self.word)
        self.translator.lookup_word(self.word, self.sentence, self._apply_info)

    def _play_word(self) -> None:
        if not self.word_tts_enabled:
            return
        self.tts.speak_word(self.word)

    def _apply_info(self, info: WordTranslation | None) -> None:
        if not info or not info.translation:
            message = tr("word.unavailable")
            if self.translator.last_error:
                message = (
                    f"{message}\n\n"
                    f"{humanize_error(self.translator.last_error, area='translation')}"
                )
            self.translation_label.setText(message)
            return

        self.translation_label.setText(info.translation)

    def done(self, result: int) -> None:
        self.closed.emit()
        super().done(result)

    def closeEvent(self, event) -> None:
        self.closed.emit()
        super().closeEvent(event)
