"""Bar charts for reading statistics."""

from __future__ import annotations

from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget

from ..core.i18n import month_name, tr
from ..core.reading_stats import chart_bar_label, format_reading_duration


class StatsChartWidget(QWidget):
    PERIOD_WEEK = "week"
    PERIOD_MONTH = "month"
    PERIOD_YEAR = "year"
    METRIC_BLOCKS = "blocks"
    METRIC_TIME = "time"

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._data: list[dict] = []
        self._goal = 10
        self._goal_type = "blocks"
        self._period = self.PERIOD_WEEK
        self._metric = self.METRIC_BLOCKS
        self.setMinimumHeight(140)
        self.setMaximumHeight(200)

    def set_data(
        self,
        rows: list[dict],
        goal_value: int,
        period: str = "week",
        metric: str = "blocks",
        goal_type: str = "blocks",
    ) -> None:
        self._data = rows
        self._goal = max(1, goal_value)
        self._goal_type = goal_type if goal_type in ("blocks", "time") else "blocks"
        self._period = period if period in (
            self.PERIOD_WEEK,
            self.PERIOD_MONTH,
            self.PERIOD_YEAR,
        ) else self.PERIOD_WEEK
        self._metric = metric if metric in (
            self.METRIC_BLOCKS,
            self.METRIC_TIME,
        ) else self.METRIC_BLOCKS
        self.update()

    def _row_value(self, row: dict) -> int:
        if self._metric == self.METRIC_TIME:
            return int(row.get("seconds", 0) or 0)
        return int(row.get("blocks", 0) or 0)

    def _value_label(self, value: int) -> str:
        if self._metric == self.METRIC_TIME:
            if value <= 0:
                return ""
            return format_reading_duration(value)
        return str(value) if value > 0 else ""

    def _show_goal_line(self) -> bool:
        return self._metric == self._goal_type

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        if not self._data:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        margin = 28
        chart_h = h - margin - 24
        bar_w = max(10, (w - margin * 2) // max(len(self._data), 1) - 6)

        if self._metric == self.METRIC_TIME:
            max_val = max(
                max(self._goal, 60) if self._show_goal_line() else 60,
                max((self._row_value(d) for d in self._data), default=60),
            )
        else:
            max_val = max(
                self._goal if self._show_goal_line() else 1,
                max((self._row_value(d) for d in self._data), default=1),
            )

        if self._show_goal_line():
            painter.setPen(QPen(QColor("#888")))
            goal_y = margin + chart_h - int(self._goal / max_val * chart_h)
            painter.drawLine(margin, goal_y, w - margin, goal_y)
            painter.setFont(QFont("Segoe UI", 8))
            painter.drawText(4, goal_y + 4, tr("stats.chart_goal"))

        for i, row in enumerate(self._data):
            value = self._row_value(row)
            bar_h = int(value / max_val * chart_h) if max_val else 0
            x = margin + i * (bar_w + 6)
            y = margin + chart_h - bar_h

            if self._show_goal_line() and value >= self._goal:
                color = QColor("#4a7c59")
            elif value > 0:
                color = QColor("#c4a035")
            else:
                color = QColor("#ccc")

            painter.fillRect(x, y, bar_w, bar_h, color)
            painter.setPen(QPen(QColor("#666")))
            label = chart_bar_label(
                row["date"],
                self._period,
                month_name_fn=month_name,
            )
            painter.drawText(x, h - 8, label)
            value_label = self._value_label(value)
            if value_label:
                painter.drawText(x, max(margin, y - 4), value_label)

        painter.end()


# Backward-compatible alias
WeekChartWidget = StatsChartWidget
