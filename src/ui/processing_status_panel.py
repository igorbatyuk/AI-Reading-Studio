"""On-demand panel showing audio and translation processing status."""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..core.i18n import tr
from ..core.processing_status import ProcessingSnapshot, ProcessingStatusTracker
from ..core.user_errors import humanize_error


class ProcessingStatusPanel(QDialog):
    def __init__(self, tracker: ProcessingStatusTracker, parent=None) -> None:
        super().__init__(parent)
        self.tracker = tracker
        self.setWindowTitle(tr("status.panel.title"))
        self.setMinimumWidth(440)
        self.setMaximumWidth(560)
        self.setModal(False)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel(tr("status.panel.title"))
        title.setObjectName("titleLabel")
        title.setStyleSheet("font-size: 18px;")
        header.addWidget(title)
        header.addStretch()
        refresh_btn = QPushButton(tr("status.panel.refresh"))
        refresh_btn.setObjectName("secondaryBtn")
        refresh_btn.setFixedWidth(90)
        refresh_btn.clicked.connect(self.refresh)
        header.addWidget(refresh_btn)
        root.addLayout(header)

        hint = QLabel(tr("status.panel.hint"))
        hint.setObjectName("hintLabel")
        hint.setWordWrap(True)
        root.addWidget(hint)

        self.summary_banner = QLabel()
        self.summary_banner.setWordWrap(True)
        self.summary_banner.setContentsMargins(12, 10, 12, 10)
        root.addWidget(self.summary_banner)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        root.addWidget(scroll, stretch=1)

        content = QWidget()
        scroll.setWidget(content)
        self._layout = QVBoxLayout(content)
        self._layout.setSpacing(10)
        self._layout.setContentsMargins(0, 0, 0, 0)

        self.reading_card, self.reading_body = self._make_card(
            tr("status.panel.reading")
        )
        self.network_card, self.network_value = self._make_card(
            tr("status.panel.network")
        )
        self.audio_card, self.audio_body = self._make_card(tr("status.panel.tts"))
        self.queue_card, self.queue_body = self._make_card(tr("status.panel.queue"))
        self.queue_cancel_btn = QPushButton(tr("status.panel.queue_cancel_all"))
        self.queue_cancel_btn.setObjectName("secondaryBtn")
        self.queue_cancel_btn.clicked.connect(self._cancel_all_queued)
        self.queue_body.addWidget(self.queue_cancel_btn)
        self.queue_list_host = QVBoxLayout()
        self.queue_body.addLayout(self.queue_list_host)
        self.translation_card, self.translation_body = self._make_card(
            tr("status.panel.translation")
        )
        self.import_card, self.import_body = self._make_card(tr("status.panel.import"))
        self.error_label = QLabel("")
        self.error_label.setWordWrap(True)
        self.error_label.setObjectName("errorLabel")
        self.error_label.hide()
        self._layout.addWidget(self.error_label)

        close_btn = QPushButton(tr("dialog.close"))
        close_btn.setObjectName("secondaryBtn")
        close_btn.clicked.connect(self.hide)
        root.addWidget(close_btn)

        self._timer = QTimer(self)
        self._timer.setInterval(500)
        self._timer.timeout.connect(self._on_timer)
        tracker.changed.connect(self.refresh)

        self.refresh()

    def _on_timer(self) -> None:
        self.refresh()
        snap = self.tracker.snapshot()
        self._timer.setInterval(500 if snap.summary_level != "ok" else 2000)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.refresh()
        self._timer.start()

    def hideEvent(self, event) -> None:
        self._timer.stop()
        super().hideEvent(event)

    def _make_card(self, title: str) -> tuple[QFrame, QVBoxLayout]:
        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)
        heading = QLabel(title)
        heading.setObjectName("cardTitle")
        layout.addWidget(heading)
        body = QVBoxLayout()
        body.setSpacing(6)
        layout.addLayout(body)
        self._layout.addWidget(card)
        return card, body

    def refresh(self) -> None:
        self._apply(self.tracker.snapshot())

    def _apply(self, snap: ProcessingSnapshot) -> None:
        self._apply_summary(snap)

        self._clear_layout(self.reading_body)
        if snap.book_title:
            self.reading_card.show()
            self._add_row(
                self.reading_body,
                tr("status.panel.book"),
                snap.book_title,
            )
            if snap.block_position:
                self._add_row(
                    self.reading_body,
                    tr("status.panel.block"),
                    snap.block_position,
                    highlight=snap.tts_playback == "playing",
                )
            self._add_row(
                self.reading_body,
                tr("status.panel.highlight_sync"),
                self._highlight_label(snap.highlight_sync),
            )
        else:
            self.reading_card.show()
            self._add_row(
                self.reading_body,
                tr("status.panel.book"),
                tr("status.panel.none"),
            )

        self._clear_layout(self.network_value)
        self._add_row(
            self.network_value,
            tr("status.panel.network_state"),
            self._network_text(snap),
        )

        self._clear_layout(self.audio_body)
        self._add_row(
            self.audio_body,
            tr("status.panel.tts_mode"),
            snap.tts_mode_label,
        )
        self._add_row(
            self.audio_body,
            tr("status.panel.tts_engine"),
            snap.tts_engine_label,
        )
        if snap.tts_slow_hint:
            note = QLabel(snap.tts_slow_hint)
            note.setObjectName("hintLabel")
            note.setWordWrap(True)
            self.audio_body.addWidget(note)
        self._add_meter_row(
            self.audio_body,
            tr("status.panel.tts_current"),
            snap.audio_current,
            snap.audio_current_error,
        )
        self._add_meter_row(
            self.audio_body,
            tr("status.panel.tts_next"),
            snap.audio_next,
            snap.audio_next_error,
        )
        self._add_row(
            self.audio_body,
            tr("status.panel.tts_playback"),
            self._playback_label(snap.tts_playback),
            highlight=snap.tts_playback == "playing",
        )
        self._add_row(
            self.audio_body,
            tr("status.panel.tts_generating"),
            tr("status.panel.active_n", n=snap.tts_generating)
            if snap.tts_generating
            else tr("status.panel.idle"),
            highlight=snap.tts_generating > 0,
        )
        self._add_row(
            self.audio_body,
            tr("status.panel.tts_cache"),
            tr(
                "status.panel.tts_cache_value",
                memory=snap.tts_cache_memory,
                disk=snap.tts_cache_disk,
            ),
        )

        self._refresh_queue_section()

        self._clear_layout(self.translation_body)
        self._add_row(
            self.translation_body,
            tr("status.panel.translation_engine"),
            snap.translation_provider_label,
        )
        self._add_meter_row(
            self.translation_body,
            tr("status.panel.translation_current"),
            snap.translation_current,
        )
        self._add_meter_row(
            self.translation_body,
            tr("status.panel.translation_next"),
            snap.translation_next,
        )
        self._add_row(
            self.translation_body,
            tr("status.panel.translation_busy"),
            tr("status.panel.active_n", n=snap.translation_busy)
            if snap.translation_busy
            else tr("status.panel.idle"),
            highlight=snap.translation_busy > 0,
        )
        if snap.translation_activity:
            self._add_row(
                self.translation_body,
                tr("status.panel.translation_last"),
                snap.translation_activity,
            )
        self._add_row(
            self.translation_body,
            tr("status.panel.translation_cache"),
            tr(
                "status.panel.translation_cache_value",
                words=snap.translation_words_cached,
                sentences=snap.translation_sentences_cached,
            ),
        )

        self._clear_layout(self.import_body)
        if snap.import_status:
            self.import_card.show()
            self._add_row(
                self.import_body,
                tr("status.panel.import_state"),
                self._import_text(snap.import_status),
                highlight=True,
            )
        else:
            self.import_card.show()
            self._add_row(
                self.import_body,
                tr("status.panel.import_state"),
                tr("status.panel.idle"),
            )

        if snap.last_error:
            lower = snap.last_error.lower()
            if any(
                token in lower
                for token in (
                    "apify",
                    "deepl",
                    "translation",
                    "bergamot",
                    "ollama",
                    "translate",
                )
            ):
                area = "translation"
            else:
                area = "tts"
            detail = humanize_error(snap.last_error, area=area)
            self.error_label.setText(
                tr("status.panel.last_error", error=detail)
            )
            self.error_label.show()
        else:
            self.error_label.hide()

    def _cancel_all_queued(self) -> None:
        self.tracker.tts.cancel_queued_jobs()
        self.refresh()

    def _cancel_job(self, key: str) -> None:
        self.tracker.tts.cancel_queued_jobs([key])
        self.refresh()

    def _refresh_queue_section(self) -> None:
        self._clear_layout(self.queue_list_host)
        jobs = self.tracker.tts.list_queue_jobs()
        if not jobs:
            self.queue_card.show()
            self._add_row(
                self.queue_list_host,
                tr("status.panel.queue_items"),
                tr("status.panel.idle"),
            )
            self.queue_cancel_btn.setEnabled(False)
            return
        self.queue_cancel_btn.setEnabled(
            any(item["state"] == "queued" for item in jobs)
        )
        for item in jobs[:20]:
            preview = str(item.get("text") or "")
            block_index = item.get("block_index")
            if block_index is not None:
                label = tr(
                    "status.panel.queue_block",
                    n=int(block_index) + 1,
                    preview=preview[:60],
                )
            else:
                label = preview[:80] or str(item.get("key", ""))[:12]
            state = str(item.get("state", ""))
            row = QHBoxLayout()
            name = QLabel(label)
            name.setObjectName("statusRowLabel")
            name.setWordWrap(True)
            status = QLabel(self._state_label(state))
            status.setObjectName(self._state_object_name(state))
            row.addWidget(name, stretch=1)
            cancel_btn = QPushButton(tr("status.panel.queue_cancel"))
            cancel_btn.setObjectName("secondaryBtn")
            cancel_btn.setFixedWidth(72)
            key = str(item.get("key", ""))
            if state != "queued":
                cancel_btn.setEnabled(False)
            cancel_btn.clicked.connect(
                lambda checked=False, job_key=key: self._cancel_job(job_key)
            )
            row.addWidget(status)
            row.addWidget(cancel_btn)
            self.queue_list_host.addLayout(row)
        if len(jobs) > 20:
            extra = QLabel(tr("status.panel.queue_more", n=len(jobs) - 20))
            extra.setObjectName("hintLabel")
            self.queue_list_host.addWidget(extra)

    @staticmethod
    def _clear_layout(layout: QVBoxLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                ProcessingStatusPanel._clear_layout(item.layout())

    def _add_row(
        self,
        layout: QVBoxLayout,
        label: str,
        value: str,
        highlight: bool = False,
    ) -> None:
        row = QHBoxLayout()
        name = QLabel(label)
        name.setObjectName("statusRowLabel")
        val = QLabel(value)
        val.setObjectName("statusRowValueActive" if highlight else "statusRowValue")
        val.setWordWrap(True)
        val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(name, stretch=1)
        row.addWidget(val, stretch=1)
        layout.addLayout(row)

    def _apply_summary(self, snap: ProcessingSnapshot) -> None:
        styles = {
            "ok": ("statusBannerOk", tr("status.panel.summary_ok")),
            "working": ("statusBannerWorking", snap.summary_text),
            "error": ("statusBannerError", snap.summary_text),
        }
        object_name, text = styles.get(
            snap.summary_level, ("statusBannerOk", snap.summary_text)
        )
        self.summary_banner.setObjectName(object_name)
        self.summary_banner.setText(text)
        self.summary_banner.style().unpolish(self.summary_banner)
        self.summary_banner.style().polish(self.summary_banner)

    def _add_meter_row(
        self,
        layout: QVBoxLayout,
        label: str,
        state: str,
        error: str = "",
    ) -> None:
        row = QVBoxLayout()
        top = QHBoxLayout()
        name = QLabel(label)
        name.setObjectName("statusRowLabel")
        status = QLabel(self._state_label(state))
        status.setObjectName(self._state_object_name(state))
        top.addWidget(name)
        top.addStretch()
        top.addWidget(status)
        row.addLayout(top)

        bar = QProgressBar()
        bar.setFixedHeight(8)
        if state in ("generating", "queued", "preparing"):
            bar.setRange(0, 0)
        else:
            bar.setRange(0, 100)
            bar.setValue(self._state_progress(state))
        bar.setTextVisible(False)
        bar.setObjectName(self._meter_bar_object_name(state))
        bar.style().unpolish(bar)
        bar.style().polish(bar)
        row.addWidget(bar)

        if error and state == "failed":
            err = QLabel(error)
            err.setWordWrap(True)
            err.setObjectName("errorLabel")
            row.addWidget(err)

        layout.addLayout(row)

    @staticmethod
    def _meter_bar_object_name(state: str) -> str:
        if state == "ready":
            return "statusMeterOk"
        if state in ("generating", "queued", "preparing"):
            return "statusMeterWorking"
        if state == "failed":
            return "statusMeterError"
        if state == "waiting":
            return "statusMeterWaiting"
        return "statusMeterWaiting"

    @staticmethod
    def _playback_label(state: str) -> str:
        mapping = {
            "playing": tr("status.panel.playback_playing"),
            "paused": tr("status.panel.playback_paused"),
            "idle": tr("status.panel.idle"),
        }
        return mapping.get(state, state)

    @staticmethod
    def _highlight_label(state: str) -> str:
        mapping = {
            "exact": tr("status.panel.highlight_exact"),
            "estimated": tr("status.panel.highlight_estimated"),
            "idle": tr("status.panel.idle"),
            "na": tr("status.panel.na"),
        }
        return mapping.get(state, state)

    @staticmethod
    def _state_label(state: str) -> str:
        mapping = {
            "ready": tr("status.panel.ready"),
            "generating": tr("status.panel.generating"),
            "queued": tr("status.panel.queued"),
            "waiting": tr("status.panel.waiting"),
            "failed": tr("status.panel.failed"),
            "preparing": tr("status.panel.preparing"),
            "none": tr("status.panel.none"),
            "na": tr("status.panel.na"),
        }
        return mapping.get(state, state)

    @staticmethod
    def _state_object_name(state: str) -> str:
        if state == "ready":
            return "statusValueOk"
        if state in ("generating", "queued", "preparing"):
            return "statusValueWorking"
        if state == "failed":
            return "statusValueError"
        return "statusRowValue"

    @staticmethod
    def _state_progress(state: str) -> int:
        if state == "ready":
            return 100
        if state == "waiting":
            return 15
        if state == "failed":
            return 0
        return 45

    @staticmethod
    def _network_text(snap: ProcessingSnapshot) -> str:
        parts = [
            tr("status.online") if snap.online else tr("status.offline"),
        ]
        if snap.ollama_ready:
            parts.append(tr("status.ollama"))
        return " · ".join(parts)

    @staticmethod
    def _import_text(message: str) -> str:
        if message == "reading":
            return tr("status.panel.import_reading")
        if message.startswith("blocks:"):
            return tr("status.panel.import_blocks", n=message.split(":", 1)[1])
        if message.startswith("ocr:"):
            parts = message.split(":")
            if len(parts) >= 3:
                return tr("status.panel.import_ocr", current=parts[1], total=parts[2])
        return message
