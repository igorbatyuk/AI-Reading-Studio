"""Word highlight rendering for the reading view."""

from __future__ import annotations

from PySide6.QtGui import QColor, QFont, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import QTextEdit

from ..core.tts_engine import TTSEngine
from ..core.word_highlight import (
    HighlightColors,
    WordTimingsBundle,
    build_highlight_segments,
    estimate_word_timings_from_text,
    normalize_timings_to_duration,
    playback_progress,
    uses_painter_overlay,
    word_spans,
)
from .highlight_overlay import HighlightOverlay


class ReadingHighlightController:
    def __init__(self, text_edit: QTextEdit, overlay: HighlightOverlay) -> None:
        self.text_edit = text_edit
        self.overlay = overlay
        self.tts: TTSEngine | None = None
        self.current_text = ""
        self.enabled = True
        self.style = "gradient"
        self.colors = HighlightColors(
            primary=(255, 224, 138),
            secondary=(142, 197, 255),
            accent=(196, 168, 255),
            text=(26, 26, 26),
            text_soft=(68, 68, 68),
        )
        self.spans: list[tuple[int, int]] = []
        self.timings: list[tuple[int, int]] | None = None
        self.timings_estimated = False
        self.playback_rate = 1.0
        self.sync_engine = ""
        self._timings_normalized_for_ms = 0
        self._raw_timings: list[tuple[int, int]] | None = None
        self._reject_high_position = False
        self._scroll_word_index = -1
        self.word_index = -1
        self.blend = -1.0
        self.float_index = -1.0

    def attach_tts(self, tts: TTSEngine) -> None:
        self.tts = tts

    def configure(
        self,
        *,
        enabled: bool,
        style: str,
        colors: HighlightColors,
    ) -> None:
        self.enabled = enabled
        self.style = style
        self.colors = colors
        if not enabled:
            self.clear()

    def set_playback_rate(self, rate: float) -> None:
        from ..core.tts_speed import clamp_playback_rate

        self.playback_rate = clamp_playback_rate(rate)

    def set_timings(self, bundle: WordTimingsBundle | None) -> None:
        if bundle is None:
            self.timings = None
            self.timings_estimated = False
            self._raw_timings = None
            self._timings_normalized_for_ms = 0
            return
        self._raw_timings = list(bundle.timings)
        self.timings = list(bundle.timings)
        self.timings_estimated = bundle.estimated
        self._timings_normalized_for_ms = 0

    def reset_playback_sync(self) -> None:
        """Call when a new audio clip starts (blocks stale player position)."""
        self._reject_high_position = True
        self.word_index = -1
        self.blend = -1.0
        self.float_index = -1.0
        self._scroll_word_index = -1

    def prepare_for_text(self, text: str) -> None:
        self.clear_state()
        self.current_text = text
        self.spans = word_spans(text)
        self._timings_normalized_for_ms = 0
        if self.tts is not None:
            self.sync_engine = self.tts.sync_engine_name()
            self.set_timings(self.tts.word_timings_info_for(text))
        else:
            self.sync_engine = ""
            self.timings = None
            self.timings_estimated = False

    def clear(self) -> None:
        self.clear_state()
        self.current_text = ""
        self.overlay.clear()
        self.text_edit.setExtraSelections([])

    def clear_state(self) -> None:
        self.word_index = -1
        self.blend = -1.0
        self.float_index = -1.0
        self.spans = []
        self.timings = None
        self.timings_estimated = False
        self._timings_normalized_for_ms = 0
        self._raw_timings = None
        self._reject_high_position = False
        self._scroll_word_index = -1

    def refresh(self) -> None:
        if self.float_index >= 0:
            self.apply(self.float_index)

    def update_position(
        self,
        position_ms: int,
        duration_ms: int,
        *,
        playing: bool,
        paused: bool,
    ) -> None:
        if not self.enabled or not playing or paused or not self.spans:
            return
        if duration_ms <= 0:
            return
        if self._reject_high_position:
            if position_ms > 600:
                return
            self._reject_high_position = False
        self._ensure_timings(duration_ms)
        progress = playback_progress(
            position_ms=position_ms,
            duration_ms=duration_ms,
            span_count=len(self.spans),
            timings=self.timings,
            estimated=self.timings_estimated,
            playback_rate=self.playback_rate,
            engine=self.sync_engine,
        )
        if progress.word_index < 0:
            return
        float_index = progress.word_index + progress.blend
        threshold = 0.006 if uses_painter_overlay(self.style) else 0.035
        if (
            abs(float_index - self.float_index) < threshold
            and progress.word_index == self.word_index
        ):
            return
        self.word_index = progress.word_index
        self.blend = progress.blend
        self.float_index = float_index
        self.apply(float_index)

    def apply(self, float_index: float) -> None:
        if not self.enabled or not self.spans:
            self.clear()
            return
        center, segments = build_highlight_segments(
            self.style,
            self.spans,
            float_index,
            len(self.current_text),
            self.colors,
        )
        if not segments and not uses_painter_overlay(self.style):
            self.clear()
            return

        if uses_painter_overlay(self.style):
            self.text_edit.setExtraSelections([])
            self.overlay.set_highlight(
                style=self.style,
                float_index=float_index,
                colors=self.colors,
                spans=self.spans,
                text_length=len(self.current_text),
            )
        else:
            self.overlay.clear()
            selections = []
            for segment in segments:
                bg = self._qcolor_rgba(segment.bg) if segment.bg else None
                fg = self._qcolor_rgba(segment.fg) if segment.fg else None
                underline_color = (
                    self._qcolor_rgba(segment.underline_rgba)
                    if segment.underline_rgba
                    else None
                )
                selections.append(
                    self._selection_for_range(
                        segment.start,
                        segment.end,
                        bg,
                        fg,
                        bold=segment.bold,
                        weight=segment.weight,
                        underline=segment.underline,
                        underline_color=underline_color,
                    )
                )
            self.text_edit.setExtraSelections(selections)

        scroll_index = int(float_index)
        if scroll_index != self._scroll_word_index:
            self._scroll_word_index = scroll_index
            cursor = self.text_edit.textCursor()
            cursor.setPosition(int(center))
            self.text_edit.setTextCursor(cursor)
            self.text_edit.ensureCursorVisible()

    def _ensure_timings(self, duration_ms: int) -> None:
        if duration_ms <= 0:
            return
        source = self._raw_timings or self.timings
        if source:
            from ..core.word_highlight import should_normalize_timings

            if should_normalize_timings(
                source, duration_ms, estimated=self.timings_estimated
            ):
                self.timings = normalize_timings_to_duration(
                    list(source),
                    duration_ms,
                    estimated=self.timings_estimated,
                )
                self._timings_normalized_for_ms = duration_ms
            elif not self.timings:
                self.timings = list(source)
        elif self.current_text:
            self.timings = estimate_word_timings_from_text(
                self.current_text, duration_ms
            )
            self._raw_timings = list(self.timings)
            self.timings_estimated = True
            self._timings_normalized_for_ms = duration_ms

    def _selection_for_range(
        self,
        start: int,
        end: int,
        background: QColor | None = None,
        foreground: QColor | None = None,
        *,
        bold: bool = False,
        weight: int | None = None,
        underline: bool = False,
        underline_color: QColor | None = None,
    ):
        cursor = self.text_edit.textCursor()
        cursor.setPosition(start)
        cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
        fmt = QTextCharFormat()
        if background is not None:
            fmt.setBackground(background)
        if foreground is not None:
            fmt.setForeground(foreground)
        if underline:
            fmt.setFontUnderline(True)
            fmt.setUnderlineStyle(QTextCharFormat.UnderlineStyle.SingleUnderline)
            if underline_color is not None:
                fmt.setUnderlineColor(underline_color)
        if weight is not None:
            fmt.setFontWeight(QFont.Weight(weight))
        elif bold:
            fmt.setFontWeight(QFont.Weight.Bold)
        selection = QTextEdit.ExtraSelection()
        selection.cursor = cursor
        selection.format = fmt
        return selection

    @staticmethod
    def _qcolor_rgba(rgba: tuple[int, int, int, int]) -> QColor:
        color = QColor(rgba[0], rgba[1], rgba[2])
        color.setAlpha(rgba[3])
        return color
