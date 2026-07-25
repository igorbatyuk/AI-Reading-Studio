"""Main reading view with TTS playback."""

from __future__ import annotations

import re
import time
from PySide6.QtCore import QEvent, QPoint, Qt, QTimer, Signal
from PySide6.QtGui import (
    QFont,
    QMouseEvent,
    QPixmap,
    QResizeEvent,
    QShowEvent,
    QTextCursor,
)
from PySide6.QtWidgets import (
    QAbstractScrollArea,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..core.cover_service import CoverService
from ..core.database import Book, Database
from ..core.i18n import tr
from ..core.reading_stats import format_reading_duration
from ..core.translation_service import TranslationService, is_lookup_word
from ..core.tts_engine import TTSEngine
from ..core.user_errors import humanize_error
from ..core.word_highlight import (
    HIGHLIGHT_STYLE_GRADIENT,
    HighlightColors,
    highlight_colors_from_settings,
    normalize_highlight_style,
)
from .block_translation_popup import BlockTranslationPopup
from .highlight_overlay import HighlightOverlay
from .jump_dialog import JumpDialog
from .reading_highlight_controller import ReadingHighlightController
from .word_popup import WordPopup


class ReadingView(QWidget):
    block_finished = Signal()
    progress_updated = Signal()
    focus_mode_changed = Signal(bool)

    def __init__(
        self,
        db: Database,
        tts: TTSEngine,
        translator: TranslationService,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.db = db
        self.covers = CoverService(db.app_dir)
        self.tts = tts
        self.translator = translator

        self.current_book: Book | None = None
        self.current_block_index = 0
        self.current_text = ""
        self.current_chapter = ""
        self.is_playing = False
        self.is_paused = False
        self._word_popup: WordPopup | None = None
        self._mouse_press_pos: QPoint | None = None
        self._timer_segment_start: float | None = None
        self._session_seconds = 0
        self._reading_timer = QTimer(self)
        self._reading_timer.setInterval(1000)
        self._reading_timer.timeout.connect(self._update_reading_time_label)
        self._highlight_timer = QTimer(self)
        self._highlight_timer.setInterval(33)
        self._highlight_timer.timeout.connect(self._tick_word_highlight)
        self._prefetch_block_index = -1
        self._book_block_texts: list[str] | None = None
        self._word_highlight_enabled = True
        self._word_tts_enabled = True
        self._word_highlight_style = HIGHLIGHT_STYLE_GRADIENT
        self._highlight_colors = HighlightColors(
            primary=(255, 224, 138),
            secondary=(142, 197, 255),
            accent=(196, 168, 255),
            text=(26, 26, 26),
            text_soft=(68, 68, 68),
        )
        self._word_spans: list[tuple[int, int]] = []
        self._word_timings: list[tuple[int, int]] | None = None
        self._word_timings_estimated = False
        self._highlight_word_index = -1
        self._highlight_blend = -1.0
        self._highlight_float_index = -1.0
        self._line_width = 680
        self._frame_padding = 120

        self.tts.playback_finished.connect(self._on_tts_finished)
        self.tts.playback_started.connect(self._on_tts_started)
        self.tts.playback_error.connect(self._on_tts_error)
        self.tts.provider_skipped.connect(self._on_tts_provider_skipped)
        self.tts.timings_ready.connect(self._on_timings_ready)
        self.tts.generating_changed.connect(self._on_tts_generating)

        self._build_ui()
        self._update_controls_state()
        self._update_goal_label()

    @property
    def highlight_sync_mode(self) -> str:
        if not self.is_playing or self.is_paused:
            return "idle"
        if self._highlight_ctrl.timings_estimated or not self._highlight_ctrl.timings:
            return "estimated"
        return "exact"

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)

        self.reading_frame = QFrame()
        self.reading_frame.setObjectName("readingCard")
        reading_layout = QVBoxLayout(self.reading_frame)
        reading_layout.setContentsMargins(0, 0, 0, 0)

        header_row = QHBoxLayout()
        header_row.setContentsMargins(24, 16, 24, 0)
        header_row.setSpacing(14)

        self.cover_label = QLabel()
        self.cover_label.setFixedSize(56, 76)
        self.cover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cover_label.setStyleSheet("border-radius: 4px;")
        self.cover_label.hide()
        header_row.addWidget(self.cover_label)

        meta_col = QVBoxLayout()
        meta_col.setSpacing(4)
        self.book_title_label = QLabel("")
        self.book_title_label.setWordWrap(True)
        self.book_title_label.setStyleSheet("font-size: 16px; font-weight: 600;")
        self.book_title_label.hide()
        meta_col.addWidget(self.book_title_label)

        self.chapter_label = QLabel("")
        self.chapter_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.chapter_label.setStyleSheet("font-size: 13px; color: #888;")
        self.chapter_label.setWordWrap(True)
        meta_col.addWidget(self.chapter_label)
        header_row.addLayout(meta_col, stretch=1)
        reading_layout.addLayout(header_row)

        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setFrameShape(QFrame.Shape.NoFrame)
        self.text_edit.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.text_edit.setSizeAdjustPolicy(
            QAbstractScrollArea.SizeAdjustPolicy.AdjustIgnored
        )
        self.text_edit.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Expanding,
        )
        self.text_edit.setMinimumHeight(160)
        self.text_edit.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.text_edit.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.text_edit.setPlaceholderText(tr("reading.placeholder"))
        self.text_edit.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.text_edit.viewport().installEventFilter(self)
        self.text_edit.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.text_edit.customContextMenuRequested.connect(
            self._show_text_context_menu
        )
        self.text_edit.selectionChanged.connect(self._on_text_selection_changed)
        self._highlight_overlay = HighlightOverlay(self.text_edit)
        self._highlight_ctrl = ReadingHighlightController(
            self.text_edit, self._highlight_overlay
        )
        self._highlight_ctrl.attach_tts(self.tts)
        self.text_edit.verticalScrollBar().valueChanged.connect(
            self._on_text_scroll
        )
        reading_layout.addWidget(self.text_edit, stretch=1)
        self.reading_frame.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Expanding,
        )
        self._reading_row = QHBoxLayout()
        self._reading_row.setContentsMargins(0, 0, 0, 0)
        self._reading_row.addStretch(1)
        self._reading_row.addWidget(self.reading_frame)
        self._reading_row.addStretch(1)
        layout.addLayout(self._reading_row, stretch=1)

        controls = QHBoxLayout()
        controls.setAlignment(Qt.AlignmentFlag.AlignCenter)
        controls.setSpacing(10)

        self.play_btn = QPushButton(tr("reading.start"))
        self.play_btn.setFixedWidth(140)
        self.play_btn.setToolTip(tr("reading.tip.play"))
        self.play_btn.clicked.connect(self._toggle_playback)
        controls.addWidget(self.play_btn)

        self.restart_btn = QPushButton(tr("reading.restart"))
        self.restart_btn.setObjectName("secondaryBtn")
        self.restart_btn.setFixedWidth(100)
        self.restart_btn.setToolTip(tr("reading.tip.restart"))
        self.restart_btn.clicked.connect(self._restart_audio)
        controls.addWidget(self.restart_btn)

        self.rewind_btn = QPushButton(tr("reading.rewind"))
        self.rewind_btn.setObjectName("secondaryBtn")
        self.rewind_btn.setFixedWidth(90)
        self.rewind_btn.setToolTip(tr("reading.tip.rewind"))
        self.rewind_btn.clicked.connect(self._rewind_audio)
        controls.addWidget(self.rewind_btn)

        self.speed_btn = QPushButton(self._speed_button_text())
        self.speed_btn.setObjectName("secondaryBtn")
        self.speed_btn.setFixedWidth(72)
        self.speed_btn.setToolTip(tr("reading.tip.speed"))
        self.speed_btn.clicked.connect(self._cycle_playback_speed)
        controls.addWidget(self.speed_btn)

        self.prev_btn = QPushButton(tr("reading.prev"))
        self.prev_btn.setObjectName("secondaryBtn")
        self.prev_btn.setFixedWidth(100)
        self.prev_btn.setToolTip(tr("reading.tip.prev"))
        self.prev_btn.clicked.connect(self._prev_block)
        controls.addWidget(self.prev_btn)

        self.next_btn = QPushButton(tr("reading.next"))
        self.next_btn.setObjectName("secondaryBtn")
        self.next_btn.setFixedWidth(100)
        self.next_btn.setToolTip(tr("reading.tip.next"))
        self.next_btn.clicked.connect(self._next_block_manual)
        controls.addWidget(self.next_btn)

        self.jump_btn = QPushButton(tr("reading.jump"))
        self.jump_btn.setObjectName("secondaryBtn")
        self.jump_btn.setToolTip(tr("reading.tip.jump"))
        self.jump_btn.clicked.connect(self._jump_to_block)
        controls.addWidget(self.jump_btn)

        self.fullscreen_btn = QPushButton(tr("reading.fullscreen"))
        self.fullscreen_btn.setObjectName("secondaryBtn")
        self.fullscreen_btn.setToolTip(tr("reading.tip.fullscreen"))
        self.fullscreen_btn.clicked.connect(self._toggle_focus_mode)
        controls.addWidget(self.fullscreen_btn)

        self.translation_btn = QPushButton(tr("reading.translation"))
        self.translation_btn.setObjectName("secondaryBtn")
        self.translation_btn.setToolTip(tr("reading.tip.translation"))
        self.translation_btn.clicked.connect(self._show_block_translation)
        controls.addWidget(self.translation_btn)

        self.selection_translation_btn = QPushButton(tr("reading.translate_selection"))
        self.selection_translation_btn.setObjectName("secondaryBtn")
        self.selection_translation_btn.setToolTip(tr("reading.tip.translate_selection"))
        self.selection_translation_btn.setEnabled(False)
        self.selection_translation_btn.clicked.connect(
            self._show_selected_text_translation
        )
        controls.addWidget(self.selection_translation_btn)

        layout.addLayout(controls)

        self.info_frame = QFrame()
        self.info_frame.setObjectName("card")
        info_layout = QVBoxLayout(self.info_frame)
        info_layout.setContentsMargins(20, 12, 20, 12)
        info_layout.setSpacing(4)

        self.progress_label = QLabel(tr("reading.progress"))
        self.progress_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.progress_label.setStyleSheet("font-size: 15px; font-weight: 600;")
        info_layout.addWidget(self.progress_label)

        self.goal_label = QLabel("")
        self.goal_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.goal_label.setStyleSheet("font-size: 13px; color: #888;")
        info_layout.addWidget(self.goal_label)

        self.tts_status_label = QLabel("")
        self.tts_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.tts_status_label.setStyleSheet("font-size: 12px; color: #4a7c59;")
        self.tts_status_label.hide()
        info_layout.addWidget(self.tts_status_label)

        self.reading_time_label = QLabel("")
        self.reading_time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.reading_time_label.setStyleSheet("font-size: 13px; color: #5a7a9a;")
        self.reading_time_label.hide()
        info_layout.addWidget(self.reading_time_label)

        layout.addWidget(self.info_frame)
        self._focus_mode = False
        self._update_reading_layout()

    def _effective_reading_width(self) -> int:
        target = self._line_width + self._frame_padding
        available = max(360, self.width() - 48)
        return min(target, available)

    def _on_text_scroll(self, _value: int) -> None:
        if self._highlight_overlay.isVisible():
            self._highlight_overlay.update()

    def _update_reading_layout(self) -> None:
        width = self._effective_reading_width()
        self.reading_frame.setFixedWidth(width)
        self.text_edit.setMinimumWidth(max(280, width - self._frame_padding))

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._update_reading_layout()
        self._highlight_overlay.sync_geometry()

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        self._update_reading_layout()

    def eventFilter(self, obj, event) -> bool:
        if obj is self.text_edit.viewport():
            if event.type() == QEvent.Type.Resize:
                self._highlight_overlay.sync_geometry()
            elif isinstance(event, QMouseEvent):
                if (
                    event.type() == QEvent.Type.MouseButtonPress
                    and event.button() == Qt.MouseButton.LeftButton
                ):
                    self._mouse_press_pos = event.position().toPoint()
                elif (
                    event.type() == QEvent.Type.MouseButtonRelease
                    and event.button() == Qt.MouseButton.LeftButton
                ):
                    if self._mouse_press_pos is None:
                        return False
                    moved = (
                        event.position().toPoint() - self._mouse_press_pos
                    ).manhattanLength()
                    self._mouse_press_pos = None
                    if moved > 4:
                        return False
                    cursor = self.text_edit.textCursor()
                    if cursor.hasSelection():
                        return False
                    cursor = self.text_edit.cursorForPosition(
                        event.position().toPoint()
                    )
                    cursor.select(QTextCursor.SelectionType.WordUnderCursor)
                    word = cursor.selectedText().strip(".,!?;:\"'()[]-«»""''")
                    if is_lookup_word(word):
                        self._on_word_clicked(
                            word, event.globalPosition().toPoint()
                        )
                        return True
        return super().eventFilter(obj, event)

    def _selected_text(self) -> str:
        cursor = self.text_edit.textCursor()
        if not cursor.hasSelection():
            return ""
        text = cursor.selectedText().replace("\u2029", " ").strip()
        if len(text) < 2:
            return ""
        if not re.search(r"[\w]", text, flags=re.UNICODE):
            return ""
        return text

    def _on_text_selection_changed(self) -> None:
        has_selection = bool(self._selected_text())
        has_book = self.current_book is not None
        self.selection_translation_btn.setEnabled(has_book and has_selection)

    def _show_text_context_menu(self, pos: QPoint) -> None:
        selected = self._selected_text()
        if not selected:
            return
        menu = QMenu(self)
        translate_action = menu.addAction(tr("reading.translate_selection"))
        chosen = menu.exec(self.text_edit.mapToGlobal(pos))
        if chosen == translate_action:
            self._show_selection_translation(selected)

    def _show_selected_text_translation(self) -> None:
        selected = self._selected_text()
        if not selected:
            return
        self._show_selection_translation(selected)

    def _show_selection_translation(self, text: str) -> None:
        popup = BlockTranslationPopup(
            text,
            self.translator,
            self.window(),
            mode="selection",
            show_source=True,
            title=tr("reading.translate_selection"),
        )
        popup.exec()

    def _on_word_clicked(self, word: str, global_pos=None) -> None:
        if self._word_popup:
            self._word_popup.close()
            self._word_popup = None

        self._word_popup = WordPopup(
            word,
            self.current_text,
            self.translator,
            self.tts,
            word_tts_enabled=self._word_tts_enabled,
            parent=self.window(),
            global_pos=global_pos,
        )
        self._word_popup.closed.connect(self._on_word_popup_closed)
        self._word_popup.show()
        self._word_popup.raise_()
        self._word_popup.activateWindow()

    def _on_word_popup_closed(self) -> None:
        self._word_popup = None

    def _speed_button_text(self, rate: float | None = None) -> str:
        if rate is None:
            rate = self.tts.playback_rate()
        return tr("reading.speed_fmt", rate=f"{rate:g}")

    def _update_audio_controls_state(self) -> None:
        has_book = self.current_book is not None
        has_text = bool(self.current_text)
        can_transport = has_text and (
            self.is_playing or self.is_paused or self.tts.can_control_playback()
        )
        self.restart_btn.setEnabled(has_book and has_text)
        self.rewind_btn.setEnabled(has_book and can_transport)
        self.speed_btn.setEnabled(has_book and has_text)

    def _update_controls_state(self) -> None:
        has_book = self.current_book is not None
        self.play_btn.setEnabled(has_book)
        self.prev_btn.setEnabled(has_book and self.current_block_index > 0)
        self.next_btn.setEnabled(
            has_book
            and self.current_book is not None
            and self.current_block_index + 1 < self.current_book.total_blocks
        )
        self.translation_btn.setEnabled(has_book and bool(self.current_text))
        self._on_text_selection_changed()
        self.jump_btn.setEnabled(has_book)
        self.fullscreen_btn.setEnabled(has_book)
        self._update_audio_controls_state()

    def load_book(self, book: Book, start_block: int | None = None) -> None:
        switching = self.current_book is None or self.current_book.id != book.id

        if self.current_book:
            self._save_progress()
            self._reset_reading_session()

        self.tts.stop()
        self.is_playing = False
        self.is_paused = False
        self._sync_playback_intent()
        self.play_btn.setText(tr("reading.start"))

        if switching and start_block is None:
            fresh = self.db.get_book(book.id)
            if fresh:
                book = fresh

        self.current_book = book
        self._book_block_texts = None
        self.tts.set_reading_book(book.id)
        self.current_block_index = (
            start_block if start_block is not None else book.current_block
        )
        self._update_info_labels()
        self._update_book_header()
        self._load_block(self.current_block_index)
        self._update_controls_state()
        self._update_reading_time_label()

    def _update_book_header(self) -> None:
        if not self.current_book:
            self.book_title_label.hide()
            self.cover_label.hide()
            return

        book = self.current_book
        self.book_title_label.setText(book.title)
        self.book_title_label.show()

        cover_path = self.covers.get_cover_path(book.id, book.cover_path)
        if cover_path:
            pix = QPixmap(str(cover_path))
            if not pix.isNull():
                self.cover_label.setPixmap(
                    pix.scaled(
                        56,
                        76,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
                self.cover_label.show()
            else:
                self.cover_label.hide()
        else:
            self.cover_label.hide()

    def apply_settings(self, settings: dict[str, str]) -> None:
        font_size = int(settings.get("font_size", "18"))
        font_family = settings.get("font_family", "Segoe UI")
        self._line_width = int(settings.get("line_width", "680"))
        self._word_highlight_enabled = settings.get("word_highlight", "1") == "1"
        self._word_tts_enabled = settings.get("word_tts", "1") == "1"
        self._word_highlight_style = normalize_highlight_style(
            settings.get("word_highlight_style", HIGHLIGHT_STYLE_GRADIENT)
        )
        self._highlight_colors = highlight_colors_from_settings(settings)
        theme = settings.get("theme", "light")
        if theme == "dark" and not settings.get("word_highlight_text_color", "").strip():
            self._highlight_colors = HighlightColors(
                primary=self._highlight_colors.primary,
                secondary=self._highlight_colors.secondary,
                accent=self._highlight_colors.accent,
                text=(245, 245, 245),
                text_soft=(204, 204, 204),
            )
        self._highlight_ctrl.configure(
            enabled=self._word_highlight_enabled,
            style=self._word_highlight_style,
            colors=self._highlight_colors,
        )
        font = QFont(font_family, font_size)
        self.text_edit.setFont(font)
        self.text_edit.setStyleSheet(
            "QTextEdit { padding: 20px 40px 40px 40px; line-height: 1.6; }"
        )
        self._update_reading_layout()
        voice = settings.get("tts_voice", "en-US-AriaNeural")
        self.tts.set_voice(voice)
        new_speed = float(settings.get("tts_speed", "1.0"))
        speed_changed = abs(new_speed - self.tts.speed) > 0.001
        self.tts.set_speed(new_speed)
        playback_rate = float(settings.get("playback_rate", "1.0") or 1.0)
        if playback_rate < 1.0:
            playback_rate = 1.0
            self.db.set_setting("playback_rate", "1.0")
        self.tts.set_playback_rate(playback_rate)
        self._highlight_ctrl.set_playback_rate(playback_rate)
        self.speed_btn.setText(self._speed_button_text(playback_rate))
        if speed_changed:
            self._regenerate_current_block_audio()
        if not self._word_highlight_enabled:
            self._clear_word_highlight()
        elif self._highlight_word_index >= 0 or self._highlight_float_index >= 0:
            self._refresh_highlight_from_state()
        self._update_goal_label()

    def on_speech_rate_changed(self, speed: float) -> None:
        """Apply speech-rate change live (Settings combo or save)."""
        speed_changed = abs(speed - self.tts.speed) > 0.001
        self.tts.set_speed(speed)
        if speed_changed:
            self._regenerate_current_block_audio()

    def _regenerate_current_block_audio(self) -> None:
        """Force new TTS at current speech rate (also when paused)."""
        if not self.current_text.strip():
            return
        was_playing = self.is_playing
        self.tts.stop(emit_finished=False)
        if self.tts.should_prefetch_blocks():
            self.tts.prefetch(
                self.current_text,
                block_index=self.current_block_index,
            )
        if was_playing:
            self.tts.speak(self.current_text)

    def _load_block(self, block_index: int) -> None:
        if not self.current_book:
            return

        result = self.db.get_block(self.current_book.id, block_index)
        if not result:
            return

        text, chapter = result
        self.tts.stop(emit_finished=False)
        self.current_text = text
        self.current_chapter = chapter
        self.current_block_index = block_index
        self._render_text(text)
        self._save_progress()
        self._update_controls_state()

        block_texts = self._book_block_texts_for_current_book()
        ahead = self.tts.block_prefetch_ahead()
        self.tts.set_reading_book(self.current_book.id)
        use_saved = self.db.get_book_use_saved_audio(self.current_book.id)
        self.tts.set_use_saved_audio(use_saved)
        self.tts.set_reading_focus(block_index, block_texts, ahead=ahead)
        self._prefetch_block_resources(text, block_index)
        self.tts.schedule_book_audio_prefetch(block_index, block_texts)

    def _book_block_texts_for_current_book(self) -> list[str]:
        if not self.current_book:
            return []
        if (
            self._book_block_texts is not None
            and len(self._book_block_texts) == self.current_book.total_blocks
        ):
            return self._book_block_texts
        texts: list[str] = []
        for index in range(self.current_book.total_blocks):
            row = self.db.get_block(self.current_book.id, index)
            texts.append(row[0] if row else "")
        self._book_block_texts = texts
        return texts

    def _prefetch_block_resources(self, text: str, block_index: int) -> None:
        self._prefetch_block_index = block_index
        if self.tts.should_prefetch_blocks():
            self.tts.prefetch(text, block_index=block_index)
        self.translator.prefetch_sentence(text)
        QTimer.singleShot(400, self._prefetch_deferred)

    def _prefetch_deferred(self) -> None:
        if not self.current_book:
            return
        block_index = self._prefetch_block_index
        if block_index != self.current_block_index:
            return
        if self.is_playing and not self.is_paused:
            self.translator.prefetch_words(self.current_text)
        if self._word_tts_enabled and self.tts.should_prefetch_words():
            self.tts.prefetch_words(self.current_text)

        ahead = self.tts.block_prefetch_ahead()
        for offset in range(1, ahead + 1):
            next_index = block_index + offset
            if next_index >= self.current_book.total_blocks:
                break
            next_block = self.db.get_block(self.current_book.id, next_index)
            if not next_block:
                break
            next_text = next_block[0]
            if self.tts.should_prefetch_blocks():
                self.tts.prefetch(next_text, block_index=next_index)
            self.translator.prefetch_sentence(next_text)
            if self._word_tts_enabled and self.tts.should_prefetch_words():
                self.tts.prefetch_words(next_text)

    def _render_text(self, text: str) -> None:
        self._clear_word_highlight()
        self._highlight_ctrl.prepare_for_text(text)
        self._word_spans = self._highlight_ctrl.spans
        self._word_timings = self._highlight_ctrl.timings
        self._word_timings_estimated = self._highlight_ctrl.timings_estimated
        self.text_edit.setPlainText(text)
        self.text_edit.moveCursor(QTextCursor.MoveOperation.Start)
        self.text_edit.verticalScrollBar().setValue(0)
        if self.current_chapter:
            self.chapter_label.setText(self.current_chapter)
            self.chapter_label.show()
        else:
            self.chapter_label.hide()

    def _clear_word_highlight(self) -> None:
        self._highlight_word_index = -1
        self._highlight_blend = -1.0
        self._highlight_float_index = -1.0
        self._highlight_timer.stop()
        self._highlight_ctrl.clear()
        self._word_spans = []
        self._word_timings = None
        self._word_timings_estimated = False

    def _refresh_highlight_from_state(self) -> None:
        self._highlight_ctrl.refresh()

    def _apply_style_highlight(self, float_index: float) -> None:
        self._highlight_ctrl.apply(float_index)

    def _ensure_word_timings(self, duration_ms: int) -> None:
        self._highlight_ctrl._ensure_timings(duration_ms)
        self._word_timings = self._highlight_ctrl.timings
        self._word_timings_estimated = self._highlight_ctrl.timings_estimated

    def _update_highlight_at_position(
        self, position_ms: int, duration_ms: int
    ) -> None:
        if (
            not self._word_highlight_enabled
            or not self.is_playing
            or self.is_paused
            or not self._word_spans
        ):
            return
        self._highlight_ctrl.update_position(
            position_ms,
            duration_ms,
            playing=self.is_playing,
            paused=self.is_paused,
        )
        self._highlight_word_index = self._highlight_ctrl.word_index
        self._highlight_blend = self._highlight_ctrl.blend
        self._highlight_float_index = self._highlight_ctrl.float_index

    def _tick_word_highlight(self) -> None:
        self._update_highlight_at_position(
            self.tts.playback_position_ms(),
            self.tts.playback_duration_ms(),
        )

    def _start_highlight_timer(self) -> None:
        if self._word_highlight_enabled:
            self._highlight_timer.start()

    def _stop_highlight_timer(self) -> None:
        self._highlight_timer.stop()

    def _restart_audio(self) -> None:
        if not self.current_text:
            return
        if self.tts.restart_playback():
            if not self.is_playing:
                self.is_playing = True
            self.is_paused = False
            self._sync_playback_intent()
            self._start_reading_timer()
            self.play_btn.setText(tr("reading.pause"))
            self._highlight_word_index = -1
            self._highlight_blend = -1.0
            self._highlight_float_index = -1.0
            self._start_highlight_timer()
            self._tick_word_highlight()
            self._update_audio_controls_state()
            return
        if not self.tts.is_cached(self.current_text):
            self._set_tts_loading(True)
        self.is_playing = True
        self.is_paused = False
        self._sync_playback_intent()
        self.tts.speak(self.current_text)
        self.play_btn.setText(tr("reading.pause"))
        self._update_audio_controls_state()

    def _rewind_audio(self) -> None:
        if self.tts.rewind_playback():
            self._highlight_word_index = -1
            self._highlight_blend = -1.0
            self._highlight_float_index = -1.0
            self._tick_word_highlight()

    def _cycle_playback_speed(self) -> None:
        rate = self.tts.cycle_playback_rate()
        self._highlight_ctrl.set_playback_rate(rate)
        self.db.set_setting("playback_rate", str(rate))
        self.speed_btn.setText(self._speed_button_text(rate))
        self.speed_btn.setToolTip(tr("reading.tip.speed"))

    def _show_block_translation(self) -> None:
        if not self.current_text:
            QMessageBox.information(self, "", tr("msg.no_book"))
            return
        popup = BlockTranslationPopup(
            self.current_text, self.translator, self.window()
        )
        popup.exec()

    def _sync_playback_intent(self) -> None:
        self.tts.set_playback_intent(
            active=self.is_playing,
            paused=self.is_paused,
        )

    def _toggle_playback(self) -> None:
        if not self.current_book:
            QMessageBox.information(self, "", tr("msg.no_book"))
            return

        if self.is_playing and not self.is_paused:
            self.is_paused = True
            self._sync_playback_intent()
            self._pause_reading_timer()
            self._stop_highlight_timer()
            if not self.tts.pause():
                self.tts.stop(emit_finished=False)
            self.play_btn.setText(tr("reading.resume"))
        elif self.is_paused:
            self.is_paused = False
            self._sync_playback_intent()
            self._start_highlight_timer()
            self._tick_word_highlight()
            if self.tts.resume():
                self._start_reading_timer()
            else:
                if not self.tts.is_cached(self.current_text):
                    self._set_tts_loading(True)
                self.tts.speak(self.current_text)
            self.play_btn.setText(tr("reading.pause"))
            self.progress_updated.emit()
        else:
            self.is_playing = True
            self.is_paused = False
            self._sync_playback_intent()
            self._session_seconds = 0
            self.translator.prefetch_words(self.current_text)
            if self._word_tts_enabled and self.tts.should_prefetch_words():
                self.tts.prefetch_words(self.current_text)
            if not self.tts.is_cached(self.current_text):
                self._set_tts_loading(True)
            self.tts.speak(self.current_text)
            self.play_btn.setText(tr("reading.pause"))

        self._update_audio_controls_state()

    def _segment_elapsed(self) -> int:
        if self._timer_segment_start is None:
            return 0
        return max(0, int(time.monotonic() - self._timer_segment_start))

    def _start_reading_timer(self) -> None:
        if self._timer_segment_start is None:
            self._timer_segment_start = time.monotonic()
        if not self._reading_timer.isActive():
            self._reading_timer.start()
        self._update_reading_time_label()

    def _pause_reading_timer(self) -> None:
        elapsed = self._segment_elapsed()
        if elapsed > 0:
            self.db.add_reading_seconds(elapsed)
            self._session_seconds += elapsed
        self._timer_segment_start = None
        self._reading_timer.stop()
        self._update_reading_time_label()
        self.progress_updated.emit()

    def _reset_reading_session(self) -> None:
        self._pause_reading_timer()
        self._session_seconds = 0
        self._update_reading_time_label()

    def _session_total_seconds(self) -> int:
        return self._session_seconds + self._segment_elapsed()

    def _today_total_seconds(self) -> int:
        return self.db.get_today_reading_seconds() + self._segment_elapsed()

    def _update_reading_time_label(self) -> None:
        if not self.current_book:
            self.reading_time_label.hide()
            return
        session = self._session_total_seconds()
        today = self._today_total_seconds()
        if session > 0 or today > 0 or (self.is_playing and not self.is_paused):
            self.reading_time_label.setText(
                tr(
                    "reading.time_fmt",
                    session=format_reading_duration(session),
                    today=format_reading_duration(today),
                )
            )
            if self.is_playing and not self.is_paused:
                self.reading_time_label.setStyleSheet(
                    "font-size: 13px; color: #4a7c59; font-weight: 600;"
                )
            else:
                self.reading_time_label.setStyleSheet("font-size: 13px; color: #5a7a9a;")
            self.reading_time_label.show()
        else:
            self.reading_time_label.hide()
        if self.db.get_daily_goal_settings().get("daily_goal_type") == "time":
            self._update_goal_label()

    def _set_tts_loading(self, loading: bool) -> None:
        if loading:
            self.tts_status_label.setText(self.tts.describe_main_engine().loading_hint)
            self.tts_status_label.show()
        else:
            self.tts_status_label.hide()

    def _on_tts_generating(self, active: bool) -> None:
        if active and self.is_playing and not self.is_paused:
            self._set_tts_loading(True)
        elif not active and not self.tts.is_generating():
            self._set_tts_loading(False)

    def _on_tts_started(self) -> None:
        self._set_tts_loading(False)
        if self.is_playing and not self.is_paused:
            self._start_reading_timer()
        bundle = self.tts.word_timings_info_for(self.current_text)
        if bundle:
            self._highlight_ctrl.set_timings(bundle)
            self._word_timings = bundle.timings
            self._word_timings_estimated = bundle.estimated
        else:
            self._highlight_ctrl.timings = None
            self._highlight_ctrl.timings_estimated = True
            self._word_timings = None
            self._word_timings_estimated = True
        self._highlight_ctrl.sync_engine = self.tts.sync_engine_name()
        self._highlight_ctrl.set_playback_rate(self.tts.playback_rate())
        self._highlight_ctrl.reset_playback_sync()
        self._highlight_word_index = -1
        self._highlight_blend = -1.0
        self._highlight_float_index = -1.0
        if self.is_playing and not self.is_paused:
            self._start_highlight_timer()
            self._tick_word_highlight()
        else:
            self._stop_highlight_timer()
        self._update_audio_controls_state()

    def _on_tts_finished(self) -> None:
        if self.is_paused or not self.is_playing:
            return
        self._pause_reading_timer()
        self._record_current_block()
        self._advance_block()

    def _on_tts_error(self, message: str) -> None:
        self._set_tts_loading(False)
        self._clear_word_highlight()
        self._reset_reading_session()
        self.is_playing = False
        self.is_paused = False
        self._sync_playback_intent()
        self.play_btn.setText(tr("reading.start"))
        self._update_audio_controls_state()
        QMessageBox.warning(
            self,
            tr("errors.title.tts"),
            humanize_error(message, area="tts"),
        )

    def _on_timings_ready(self, text: str) -> None:
        if text.strip() != self.current_text.strip():
            return
        bundle = self.tts.timings_bundle_for(text)
        if not bundle:
            return
        self._highlight_ctrl.set_timings(bundle)
        self._word_timings = bundle.timings
        self._word_timings_estimated = bundle.estimated
        if self.is_playing and not self.is_paused:
            self._tick_word_highlight()

    def _on_tts_provider_skipped(self, provider: str) -> None:
        self.tts_status_label.setText(tr("tts.quota_skipped_fmt", provider=provider))

    def _record_current_block(self) -> None:
        if not self.current_book:
            return
        word_count = len(self.current_text.split())
        self.db.record_block_read(
            self.current_book.id,
            self.current_block_index,
            word_count,
        )
        self._update_goal_label()
        self.progress_updated.emit()

    def _advance_block(self) -> None:
        if not self.current_book:
            return

        total = self.current_book.total_blocks
        if self.current_block_index + 1 >= total:
            self._reset_reading_session()
            self.is_playing = False
            self.is_paused = False
            self.play_btn.setText(tr("reading.start"))
            self._update_controls_state()
            self.progress_updated.emit()
            self.block_finished.emit()
            return

        self.current_block_index += 1
        self._load_block(self.current_block_index)
        self.progress_updated.emit()

        if self.is_playing and not self.is_paused:
            self._sync_playback_intent()
            self.tts.speak(self.current_text)

        self.block_finished.emit()

    def _next_block_manual(self) -> None:
        if not self.current_book:
            return
        if self.current_block_index + 1 < self.current_book.total_blocks:
            self._record_current_block()
            self.tts.stop()
            self.current_block_index += 1
            self._load_block(self.current_block_index)
            if self.is_playing and not self.is_paused:
                self.tts.speak(self.current_text)

    def _prev_block(self) -> None:
        if not self.current_book:
            return
        if self.current_block_index > 0:
            self._record_current_block()
            self.tts.stop()
            self.current_block_index -= 1
            self._load_block(self.current_block_index)
            if self.is_playing and not self.is_paused:
                self.tts.speak(self.current_text)

    def _update_info_labels(self) -> None:
        if not self.current_book:
            self.progress_label.setText(tr("reading.progress"))
            return
        progress = (self.current_block_index / max(1, self.current_book.total_blocks)) * 100
        self.progress_label.setText(
            tr(
                "reading.progress_fmt",
                title=self.current_book.title,
                percent=progress,
                current=self.current_block_index + 1,
                total=self.current_book.total_blocks,
            )
        )

    def _update_goal_label(self) -> None:
        from ..core.reading_stats import (
            format_reading_duration,
            goal_target_seconds,
            parse_daily_goal_settings,
        )

        goal_settings = self.db.get_daily_goal_settings()
        goal = parse_daily_goal_settings(goal_settings)
        if goal["type"] == "time":
            today = self._today_total_seconds()
            target = goal_target_seconds(goal_settings)
            today_label = format_reading_duration(today)
            goal_label = format_reading_duration(target)
            if today >= target:
                self.goal_label.setText(
                    tr("reading.goal_time_done", today=today_label)
                )
            else:
                self.goal_label.setText(
                    tr(
                        "reading.goal_time_fmt",
                        today=today_label,
                        goal=goal_label,
                    )
                )
            return

        goal_blocks = int(goal["blocks"])
        today = self.db.get_today_blocks_read()
        if self.db.is_goal_met_today():
            self.goal_label.setText(tr("reading.goal_done", today=today))
        else:
            self.goal_label.setText(
                tr("reading.goal_fmt", today=today, goal=goal_blocks)
            )

    def retranslate(self) -> None:
        self.text_edit.setPlaceholderText(tr("reading.placeholder"))
        self.play_btn.setToolTip(tr("reading.tip.play"))
        self.restart_btn.setToolTip(tr("reading.tip.restart"))
        self.rewind_btn.setToolTip(tr("reading.tip.rewind"))
        self.speed_btn.setToolTip(tr("reading.tip.speed"))
        self.prev_btn.setToolTip(tr("reading.tip.prev"))
        self.next_btn.setToolTip(tr("reading.tip.next"))
        self.translation_btn.setToolTip(tr("reading.tip.translation"))
        if self.is_playing and not self.is_paused:
            self.play_btn.setText(tr("reading.pause"))
        elif self.is_paused:
            self.play_btn.setText(tr("reading.resume"))
        else:
            self.play_btn.setText(tr("reading.start"))
        self.prev_btn.setText(tr("reading.prev"))
        self.next_btn.setText(tr("reading.next"))
        self.restart_btn.setText(tr("reading.restart"))
        self.rewind_btn.setText(tr("reading.rewind"))
        self.speed_btn.setText(self._speed_button_text())
        self.jump_btn.setText(tr("reading.jump"))
        self.fullscreen_btn.setText(
            tr("reading.exit_fullscreen") if self._focus_mode else tr("reading.fullscreen")
        )
        self.translation_btn.setText(tr("reading.translation"))
        self.selection_translation_btn.setText(tr("reading.translate_selection"))
        self.jump_btn.setToolTip(tr("reading.tip.jump"))
        self.fullscreen_btn.setToolTip(tr("reading.tip.fullscreen"))
        self.translation_btn.setToolTip(tr("reading.tip.translation"))
        self.selection_translation_btn.setToolTip(tr("reading.tip.translate_selection"))
        self._update_info_labels()
        self._update_goal_label()
        if self.tts_status_label.isVisible():
            self.tts_status_label.setText(self.tts.describe_main_engine().loading_hint)
        self._update_reading_time_label()

    def _jump_to_block(self) -> None:
        if not self.current_book:
            return
        dialog = JumpDialog(
            self.db,
            self.current_book.id,
            self.current_book.total_blocks,
            self.current_block_index,
            self.window(),
        )
        if dialog.exec():
            self.tts.stop()
            self._load_block(dialog.selected_block)
            if self.is_playing and not self.is_paused:
                self.tts.speak(self.current_text)

    def _toggle_focus_mode(self) -> None:
        self._focus_mode = not self._focus_mode
        self.info_frame.setVisible(not self._focus_mode)
        self._update_reading_layout()
        win = self.window()
        if self._focus_mode:
            self.fullscreen_btn.setText(tr("reading.exit_fullscreen"))
            win.showFullScreen()
        else:
            self.fullscreen_btn.setText(tr("reading.fullscreen"))
            win.showNormal()
        self.focus_mode_changed.emit(self._focus_mode)

    def _save_progress(self) -> None:
        if not self.current_book:
            return
        total = max(1, self.current_book.total_blocks)
        progress = (self.current_block_index / total) * 100
        self.db.update_book_progress(self.current_book.id, self.current_block_index, progress)
        self.current_book.current_block = self.current_block_index
        self.current_book.progress_percent = progress
        self._update_info_labels()
        self.progress_updated.emit()

    def stop_reading(self) -> None:
        self.tts.stop()
        self._clear_word_highlight()
        self._reset_reading_session()
        self.is_playing = False
        self.is_paused = False
        self._sync_playback_intent()
        self.play_btn.setText(tr("reading.start"))
        self._save_progress()

    def pause_reading(self) -> None:
        if self.is_playing and not self.is_paused:
            self.is_paused = True
            self._sync_playback_intent()
            self._pause_reading_timer()
            self._stop_highlight_timer()
            if not self.tts.pause():
                self.tts.stop(emit_finished=False)
            self.play_btn.setText(tr("reading.resume"))
        self._save_progress()
