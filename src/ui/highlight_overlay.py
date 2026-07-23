"""QPainter overlay for non-text-format highlight effects (gradient, liquid, aurora)."""

from __future__ import annotations

from PySide6.QtCore import Qt, QRect
from PySide6.QtGui import QColor, QLinearGradient, QPainter
from PySide6.QtWidgets import QTextEdit, QWidget

from ..core.word_highlight import (
    HIGHLIGHT_STYLE_AURORA,
    HIGHLIGHT_STYLE_GRADIENT,
    HIGHLIGHT_STYLE_LIQUID,
    HighlightColors,
    _aurora_color,
    _char_frontier,
    flow_highlight_center,
    normalize_highlight_style,
    subtle_gradient_intensity,
)


class HighlightOverlay(QWidget):
    """Transparent layer over QTextEdit — paints gradient/mask effects."""

    def __init__(self, text_edit: QTextEdit) -> None:
        super().__init__(text_edit.viewport())
        self._text_edit = text_edit
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.hide()
        self._style = HIGHLIGHT_STYLE_GRADIENT
        self._float_index = 0.0
        self._colors = HighlightColors(
            primary=(255, 224, 138),
            secondary=(142, 197, 255),
            accent=(196, 168, 255),
            text=(26, 26, 26),
            text_soft=(68, 68, 68),
        )
        self._spans: list[tuple[int, int]] = []
        self._text_length = 0

    def sync_geometry(self) -> None:
        parent = self.parentWidget()
        if parent is not None:
            self.setGeometry(parent.rect())

    def clear(self) -> None:
        self.hide()
        self.update()

    def set_highlight(
        self,
        *,
        style: str,
        float_index: float,
        colors: HighlightColors,
        spans: list[tuple[int, int]],
        text_length: int,
    ) -> None:
        self._style = normalize_highlight_style(style)
        self._float_index = float_index
        self._colors = colors
        self._spans = spans
        self._text_length = text_length
        self.sync_geometry()
        self.show()
        self.raise_()
        self.update()

    def _char_rect(self, position: int) -> QRect | None:
        if position < 0 or position >= self._text_length:
            return None
        cursor = self._text_edit.textCursor()
        cursor.setPosition(position)
        return self._text_edit.cursorRect(cursor)

    def _avg_char_width(self) -> float:
        if not self._spans:
            return 8.0
        total = 0
        count = 0
        for start, end in self._spans[: min(8, len(self._spans))]:
            rect = self._char_rect(start)
            if rect is not None and rect.width() > 0:
                total += rect.width()
                count += 1
        return total / max(1, count)

    def _word_rect(self, start: int, end: int) -> QRect | None:
        rects: list[QRect] = []
        for pos in range(start, min(end, self._text_length)):
            rect = self._char_rect(pos)
            if rect is not None and rect.width() > 0:
                rects.append(rect)
        if not rects:
            return None
        united = rects[0]
        for rect in rects[1:]:
            united = united.united(rect)
        return united

    def _line_key(self, rect: QRect, buckets: dict[int, int]) -> int:
        y = rect.center().y()
        for key in buckets:
            if abs(key - y) <= max(4, rect.height() // 2):
                return key
        buckets[y] = y
        return y

    def _unite_line_band(self, entries: list[tuple[int, QRect]]) -> tuple[float, QRect] | None:
        if not entries:
            return None
        ordered = sorted(entries, key=lambda item: item[0])
        united = QRect(ordered[0][1])
        char_sum = ordered[0][0]
        char_count = 1
        for pos, rect in ordered[1:]:
            if rect.left() > united.right():
                bridge = QRect(
                    united.right(),
                    united.top(),
                    rect.left() - united.right(),
                    united.height(),
                )
                united = united.united(bridge)
            united = united.united(rect)
            char_sum += pos
            char_count += 1
        return char_sum / char_count, united

    def _line_bands_in_zone(
        self, center: float, half_width: float
    ) -> list[tuple[float, QRect]]:
        zone_start = max(0, int(center - half_width))
        zone_end = min(self._text_length, int(center + half_width) + 1)
        line_groups: dict[int, list[tuple[int, QRect]]] = {}
        line_keys: dict[int, int] = {}

        for pos in range(zone_start, zone_end):
            rect = self._char_rect(pos)
            if rect is None or rect.height() <= 0:
                continue
            key = self._line_key(rect, line_keys)
            line_groups.setdefault(key, []).append((pos, rect))

        bands: list[tuple[float, QRect]] = []
        for entries in line_groups.values():
            band = self._unite_line_band(entries)
            if band is not None:
                bands.append(band)
        return bands

    def _paint_gradient(self, painter: QPainter) -> None:
        if not self._spans:
            return
        center = flow_highlight_center(self._spans, self._float_index)
        avg_w = max(6.0, self._avg_char_width())
        half_width = max(18.0, avg_w * 1.8)
        primary = QColor(*self._colors.primary)

        for mid_char, united in self._line_bands_in_zone(center, half_width):
            distance = abs(mid_char - center) / half_width
            intensity = subtle_gradient_intensity(distance)
            if intensity < 0.05:
                continue
            band = united.adjusted(0, 2, 0, -2)
            peak_alpha = int(255 * intensity * 0.26)
            gradient = QLinearGradient(band.left(), 0, band.right(), 0)
            edge_alpha = max(0, int(peak_alpha * 0.15))
            gradient.setColorAt(0.0, QColor(primary.red(), primary.green(), primary.blue(), edge_alpha))
            gradient.setColorAt(0.5, QColor(primary.red(), primary.green(), primary.blue(), peak_alpha))
            gradient.setColorAt(1.0, QColor(primary.red(), primary.green(), primary.blue(), edge_alpha))
            painter.fillRect(band, gradient)

    def _paint_liquid(self, painter: QPainter) -> None:
        if not self._spans:
            return
        frontier = _char_frontier(self._spans, self._float_index)
        frontier_int = int(frontier)
        partial = frontier - frontier_int
        primary = QColor(*self._colors.primary)
        primary.setAlpha(120)
        soft = QColor(*self._colors.primary)
        soft.setAlpha(70)

        for pos in range(0, min(frontier_int, self._text_length)):
            rect = self._char_rect(pos)
            if rect is None:
                continue
            painter.fillRect(rect.adjusted(0, 2, 0, -2), primary)

        if frontier_int < self._text_length:
            rect = self._char_rect(frontier_int)
            if rect is not None and rect.width() > 0:
                filled = QRect(rect)
                filled.setWidth(max(1, int(rect.width() * partial)))
                painter.fillRect(filled.adjusted(0, 2, 0, -2), soft)

    def _paint_aurora(self, painter: QPainter) -> None:
        if not self._spans:
            return
        center = flow_highlight_center(self._spans, self._float_index)
        avg_w = max(6.0, self._avg_char_width())
        half_width = max(36.0, avg_w * 4.5)

        for mid_char, united in self._line_bands_in_zone(center, half_width):
            distance = abs(mid_char - center) / half_width
            intensity = subtle_gradient_intensity(distance)
            if intensity < 0.06:
                continue
            band = united.adjusted(0, 2, 0, -2)
            phase = (mid_char - center) / max(24.0, half_width)
            rgb = _aurora_color(phase, self._colors)
            peak_alpha = int(255 * intensity * 0.34)
            gradient = QLinearGradient(band.left(), 0, band.right(), 0)
            edge_alpha = max(0, int(peak_alpha * 0.12))
            gradient.setColorAt(0.0, QColor(*rgb, edge_alpha))
            gradient.setColorAt(0.5, QColor(*rgb, peak_alpha))
            gradient.setColorAt(1.0, QColor(*rgb, edge_alpha))
            painter.fillRect(band, gradient)

    def paintEvent(self, _event) -> None:
        if not self._spans or self._text_length <= 0:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        painter.setPen(Qt.PenStyle.NoPen)

        if self._style == HIGHLIGHT_STYLE_GRADIENT:
            self._paint_gradient(painter)
        elif self._style == HIGHLIGHT_STYLE_LIQUID:
            self._paint_liquid(painter)
        elif self._style == HIGHLIGHT_STYLE_AURORA:
            self._paint_aurora(painter)
