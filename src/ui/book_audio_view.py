"""Book audio cache management — generate, inspect, and toggle saved narration."""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..core.database import Database
from ..core.i18n import tr
from ..core.tts_engine import TTSEngine


class BookAudioView(QWidget):
    def __init__(self, db: Database, tts: TTSEngine, reading_view, parent=None) -> None:
        super().__init__(parent)
        self.db = db
        self.tts = tts
        self.reading_view = reading_view
        self._selected_book_id: int | None = None
        self._block_texts: list[str] = []
        self._refresh_pending = False

        root = QVBoxLayout(self)
        root.setContentsMargins(30, 30, 30, 30)
        root.setSpacing(12)

        self.title_label = QLabel()
        self.title_label.setObjectName("titleLabel")
        root.addWidget(self.title_label)

        self.hint_label = QLabel()
        self.hint_label.setObjectName("hintLabel")
        self.hint_label.setWordWrap(True)
        root.addWidget(self.hint_label)

        book_row = QHBoxLayout()
        self.book_combo = QComboBox()
        self.book_combo.setMinimumWidth(280)
        self.book_combo.currentIndexChanged.connect(self._on_book_changed)
        book_row.addWidget(self.book_combo, stretch=1)
        self.refresh_btn = QPushButton()
        self.refresh_btn.setObjectName("secondaryBtn")
        self.refresh_btn.clicked.connect(self.refresh)
        book_row.addWidget(self.refresh_btn)
        root.addLayout(book_row)

        profile_card = QFrame()
        profile_card.setObjectName("card")
        profile_layout = QVBoxLayout(profile_card)
        profile_layout.setContentsMargins(14, 12, 14, 12)
        self.profile_label = QLabel()
        self.profile_label.setWordWrap(True)
        profile_layout.addWidget(self.profile_label)
        root.addWidget(profile_card)

        summary_row = QHBoxLayout()
        self.summary_label = QLabel()
        self.summary_label.setObjectName("cardTitle")
        summary_row.addWidget(self.summary_label, stretch=1)
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(10)
        self.progress_bar.setTextVisible(False)
        summary_row.addWidget(self.progress_bar, stretch=2)
        root.addLayout(summary_row)

        self.use_saved_checkbox = QCheckBox()
        self.use_saved_checkbox.toggled.connect(self._on_use_saved_toggled)
        root.addWidget(self.use_saved_checkbox)

        filter_row = QHBoxLayout()
        self.filter_combo = QComboBox()
        self.filter_combo.currentIndexChanged.connect(
            lambda _index: self._rebuild_block_list()
        )
        filter_row.addWidget(self.filter_combo)
        filter_row.addStretch()
        root.addLayout(filter_row)

        self.block_list = QListWidget()
        self.block_list.setAlternatingRowColors(True)
        root.addWidget(self.block_list, stretch=1)

        actions = QHBoxLayout()
        self.generate_btn = QPushButton()
        self.generate_btn.clicked.connect(self._generate_all)
        actions.addWidget(self.generate_btn)
        self.cancel_btn = QPushButton()
        self.cancel_btn.setObjectName("secondaryBtn")
        self.cancel_btn.clicked.connect(self._cancel_generation)
        actions.addWidget(self.cancel_btn)
        actions.addStretch()
        root.addLayout(actions)

        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._poll_status)
        self.tts.activity_changed.connect(self._schedule_refresh)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.refresh()
        self._timer.start()

    def hideEvent(self, event) -> None:
        self._timer.stop()
        super().hideEvent(event)

    def retranslate(self) -> None:
        self.title_label.setText(tr("book_audio.title"))
        self.hint_label.setText(tr("book_audio.hint"))
        self.refresh_btn.setText(tr("status.panel.refresh"))
        self.use_saved_checkbox.setText(tr("book_audio.use_saved"))
        self.generate_btn.setText(tr("book_audio.generate_all"))
        self.cancel_btn.setText(tr("book_audio.cancel"))
        self._rebuild_filter_combo()
        self._update_labels()

    def refresh(self) -> None:
        current_id = self._selected_book_id
        self.book_combo.blockSignals(True)
        self.book_combo.clear()
        books = self.db.get_all_books()
        selected_index = 0
        reading_book = self.reading_view.current_book
        for index, book in enumerate(books):
            label = book.title
            if book.author:
                label = f"{book.title} — {book.author}"
            self.book_combo.addItem(label, book.id)
            if current_id == book.id:
                selected_index = index
            elif current_id is None and reading_book and reading_book.id == book.id:
                selected_index = index
        if books:
            self.book_combo.setCurrentIndex(selected_index)
        else:
            self._selected_book_id = None
            self._block_texts = []
        self.book_combo.blockSignals(False)
        if books:
            self._on_book_changed(selected_index)
        else:
            self._update_empty_state()

    def _schedule_refresh(self) -> None:
        if self._refresh_pending:
            return
        self._refresh_pending = True
        QTimer.singleShot(250, self._run_scheduled_refresh)

    def _run_scheduled_refresh(self) -> None:
        self._refresh_pending = False
        if self.isVisible():
            self._update_status()

    def _poll_status(self) -> None:
        if self.isVisible() and self._selected_book_id is not None:
            self._update_status()

    def _on_book_changed(self, index: int) -> None:
        book_id = self.book_combo.itemData(index)
        if book_id is None:
            self._update_empty_state()
            return
        self._selected_book_id = int(book_id)
        self._block_texts = self.db.get_book_block_texts(self._selected_book_id)
        book = self.db.get_book(self._selected_book_id)
        use_saved = book.use_saved_audio if book else True
        self.use_saved_checkbox.blockSignals(True)
        self.use_saved_checkbox.setChecked(use_saved)
        self.use_saved_checkbox.blockSignals(False)
        if (
            self.reading_view.current_book
            and self.reading_view.current_book.id == self._selected_book_id
        ):
            self.tts.set_use_saved_audio(use_saved)
        self._update_profile()
        self._update_status()

    def _on_use_saved_toggled(self, checked: bool) -> None:
        if self._selected_book_id is None:
            return
        self.db.set_book_use_saved_audio(self._selected_book_id, checked)
        if (
            self.reading_view.current_book
            and self.reading_view.current_book.id == self._selected_book_id
        ):
            self.tts.set_use_saved_audio(checked)

    def _generate_all(self) -> None:
        if self._selected_book_id is None or not self._block_texts:
            return
        self.tts.schedule_full_book_generation(
            self._selected_book_id,
            self._block_texts,
        )
        self._update_status()

    def _cancel_generation(self) -> None:
        self.tts.stop_background_generation()
        self._update_status()

    def _rebuild_filter_combo(self) -> None:
        current = self.filter_combo.currentData()
        self.filter_combo.blockSignals(True)
        self.filter_combo.clear()
        for key in ("all", "missing", "ready", "active", "failed"):
            self.filter_combo.addItem(tr(f"book_audio.filter.{key}"), key)
        if current is not None:
            idx = self.filter_combo.findData(current)
            if idx >= 0:
                self.filter_combo.setCurrentIndex(idx)
        self.filter_combo.blockSignals(False)

    def _update_empty_state(self) -> None:
        self.summary_label.setText(tr("book_audio.no_books"))
        self.progress_bar.setValue(0)
        self.profile_label.setText("")
        self.block_list.clear()
        self.generate_btn.setEnabled(False)
        self.cancel_btn.setEnabled(False)
        self.use_saved_checkbox.setEnabled(False)

    def _update_profile(self) -> None:
        info = self.tts.describe_main_engine()
        self.profile_label.setText(
            tr(
                "book_audio.profile",
                mode=info.mode_label,
                engine=info.engine_label,
                speed=f"{self.tts.speed:g}",
            )
        )

    def _update_status(self) -> None:
        if self._selected_book_id is None or not self._block_texts:
            self._update_empty_state()
            return
        self.generate_btn.setEnabled(True)
        self.cancel_btn.setEnabled(True)
        self.use_saved_checkbox.setEnabled(True)
        overview = self.tts.book_audio_overview(self._block_texts)
        total = int(overview["total"])
        ready = int(overview["ready"])
        queued = int(overview["queued"])
        generating = int(overview["generating"])
        failed = int(overview["failed"])
        missing = int(overview["missing"])
        percent = int(round(ready * 100 / total)) if total else 0
        self.progress_bar.setValue(percent)
        self.summary_label.setText(
            tr(
                "book_audio.summary",
                ready=ready,
                total=total,
                missing=missing,
                queued=queued + generating,
                failed=failed,
            )
        )
        self._rebuild_block_list(overview.get("blocks") or overview["blocks"])

    def _update_labels(self) -> None:
        if self._selected_book_id is not None and self._block_texts:
            self._update_status()

    def _rebuild_block_list(self, blocks: list[dict[str, object]] | None = None) -> None:
        if blocks is None:
            if not self._block_texts:
                return
            overview = self.tts.book_audio_overview(self._block_texts)
            blocks = overview["blocks"]  # type: ignore[assignment]
        filter_key = self.filter_combo.currentData() or "all"
        reading_index = -1
        if (
            self.reading_view.current_book
            and self.reading_view.current_book.id == self._selected_book_id
        ):
            reading_index = self.reading_view.current_block_index

        self.block_list.clear()
        for item in blocks:
            status = str(item["status"])
            if filter_key == "missing" and status != "missing":
                continue
            if filter_key == "ready" and status != "ready":
                continue
            if filter_key == "active" and status not in ("queued", "generating"):
                continue
            if filter_key == "failed" and status != "failed":
                continue
            index = int(item["index"])
            preview = str(item["text"]).replace("\n", " ")[:90]
            label = tr(
                "book_audio.block_item",
                n=index + 1,
                status=tr(f"book_audio.status.{status}"),
                preview=preview,
            )
            row = QListWidgetItem(label)
            if index == reading_index:
                font = row.font()
                font.setBold(True)
                row.setFont(font)
            if status == "ready":
                row.setForeground(Qt.GlobalColor.darkGreen)
            elif status in ("queued", "generating"):
                row.setForeground(Qt.GlobalColor.darkYellow)
            elif status == "failed":
                row.setForeground(Qt.GlobalColor.red)
            self.block_list.addItem(row)
