"""Statistics view — blocks-based progress and browsable calendar."""

from __future__ import annotations

import calendar
from datetime import date
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QFileDialog,
    QVBoxLayout,
    QWidget,
)

from ..core.database import Database
from ..core.i18n import month_name, tr, weekday_labels
from ..core.reading_stats import estimate_reading_minutes, format_reading_duration
from .stats_chart import StatsChartWidget


class DayStatsDialog(QDialog):
    def __init__(
        self, day_date: str, stats: dict, parent=None
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("stats.day_title", date=day_date))
        self.setMinimumWidth(340)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(24, 24, 24, 24)

        blocks = stats["blocks"]
        words = stats["words"]
        seconds = stats.get("seconds", 0)
        goal_type = stats.get("goal_type", "blocks")
        layout.addWidget(QLabel(tr("stats.day_blocks", n=blocks)))
        layout.addWidget(QLabel(tr("stats.day_words", n=words)))
        if seconds > 0:
            layout.addWidget(
                QLabel(tr("stats.day_time_actual", time=format_reading_duration(seconds)))
            )
        else:
            minutes = estimate_reading_minutes(blocks, words)
            if minutes > 0:
                layout.addWidget(QLabel(tr("stats.day_time_estimated", n=minutes)))
        if goal_type == "time":
            goal_minutes = int(stats.get("goal_minutes", 15))
            layout.addWidget(QLabel(tr("stats.day_goal_time", n=goal_minutes)))
            if stats["goal_met"]:
                status = QLabel(
                    tr(
                        "stats.day_goal_reached_time",
                        time=format_reading_duration(seconds),
                        goal=format_reading_duration(goal_minutes * 60),
                    )
                )
                status.setObjectName("goalComplete")
            else:
                status = QLabel(
                    tr(
                        "stats.day_goal_not_time",
                        time=format_reading_duration(seconds),
                        goal=format_reading_duration(goal_minutes * 60),
                    )
                )
                status.setStyleSheet("color: #888;")
        else:
            goal_blocks = int(stats.get("goal_blocks", 10))
            layout.addWidget(QLabel(tr("stats.day_goal", n=goal_blocks)))
            if stats["goal_met"]:
                status = QLabel(
                    tr("stats.day_goal_reached", blocks=blocks, goal=goal_blocks)
                )
                status.setObjectName("goalComplete")
            else:
                status = QLabel(
                    tr("stats.day_goal_not", blocks=blocks, goal=goal_blocks)
                )
                status.setStyleSheet("color: #888;")
        layout.addWidget(status)

        close_btn = QPushButton(tr("dialog.close"))
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)


class StatsView(QWidget):
    CAL_CELL_HEIGHT = 38
    CAL_MAX_WIDTH = 560

    def __init__(self, db: Database, parent=None) -> None:
        super().__init__(parent)
        self.db = db
        self._card_labels: dict[str, QLabel] = {}
        self._legend_labels: list[QLabel] = []
        today = date.today()
        self._view_year = today.year
        self._view_month = today.month
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        outer.addWidget(scroll)

        content = QWidget()
        scroll.setWidget(content)

        layout = QVBoxLayout(content)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        self.title_label = QLabel()
        self.title_label.setObjectName("titleLabel")
        layout.addWidget(self.title_label)

        self.subtitle_label = QLabel()
        self.subtitle_label.setObjectName("statLabel")
        layout.addWidget(self.subtitle_label)

        stats_row = QHBoxLayout()
        stats_row.setSpacing(12)

        self.today_blocks_card = self._make_stat_card("stats.today_blocks")
        self.today_words_card = self._make_stat_card("stats.today_words")
        self.today_time_card = self._make_stat_card("stats.today_time")
        self.books_card = self._make_stat_card("stats.books_done")
        self.streak_card = self._make_stat_card("stats.streak")
        self.total_card = self._make_stat_card("stats.total_blocks")

        for card in [
            self.today_blocks_card,
            self.today_words_card,
            self.today_time_card,
            self.books_card,
            self.streak_card,
            self.total_card,
        ]:
            card.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
            )
            stats_row.addWidget(card, stretch=1)

        layout.addLayout(stats_row)

        chart_frame = QFrame()
        chart_frame.setObjectName("card")
        chart_layout = QVBoxLayout(chart_frame)
        chart_layout.setContentsMargins(16, 16, 16, 16)
        chart_header = QHBoxLayout()
        self.chart_title = QLabel()
        self.chart_title.setObjectName("statLabel")
        chart_header.addWidget(self.chart_title)
        chart_header.addStretch()
        self.chart_period_combo = QComboBox()
        for key in ("week", "month", "year"):
            self.chart_period_combo.addItem(tr(f"stats.chart.{key}"), key)
        self.chart_period_combo.currentIndexChanged.connect(self._refresh_chart)
        chart_header.addWidget(self.chart_period_combo)
        self.chart_metric_combo = QComboBox()
        for key in ("blocks", "time"):
            self.chart_metric_combo.addItem(tr(f"stats.chart.metric.{key}"), key)
        self.chart_metric_combo.currentIndexChanged.connect(self._refresh_chart)
        chart_header.addWidget(self.chart_metric_combo)
        chart_layout.addLayout(chart_header)
        self.period_total_label = QLabel()
        self.period_total_label.setObjectName("statLabel")
        chart_layout.addWidget(self.period_total_label)
        self.stats_chart = StatsChartWidget()
        chart_layout.addWidget(self.stats_chart)
        export_row = QHBoxLayout()
        export_row.addStretch()
        self.export_csv_btn = QPushButton()
        self.export_csv_btn.setObjectName("secondaryBtn")
        self.export_csv_btn.clicked.connect(self._export_csv)
        export_row.addWidget(self.export_csv_btn)
        chart_layout.addLayout(export_row)
        layout.addWidget(chart_frame)

        cal_frame = QFrame()
        cal_frame.setObjectName("card")
        cal_frame.setMaximumWidth(self.CAL_MAX_WIDTH)
        cal_layout = QVBoxLayout(cal_frame)
        cal_layout.setContentsMargins(12, 12, 12, 12)
        cal_layout.setSpacing(6)

        nav_row = QHBoxLayout()
        nav_row.setSpacing(8)
        self.prev_month_btn = QPushButton("◀")
        self.prev_month_btn.setObjectName("calNavBtn")
        self.prev_month_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.prev_month_btn.clicked.connect(self._prev_month)
        nav_row.addWidget(self.prev_month_btn)

        self.cal_title = QLabel()
        self.cal_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cal_title.setStyleSheet("font-size: 14px; font-weight: 600;")
        nav_row.addWidget(self.cal_title, stretch=1)

        self.next_month_btn = QPushButton("▶")
        self.next_month_btn.setObjectName("calNavBtn")
        self.next_month_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.next_month_btn.clicked.connect(self._next_month)
        nav_row.addWidget(self.next_month_btn)

        cal_layout.addLayout(nav_row)

        today_row = QHBoxLayout()
        today_row.addStretch()
        self.today_btn = QPushButton()
        self.today_btn.setObjectName("calTodayBtn")
        self.today_btn.clicked.connect(self._go_today)
        today_row.addWidget(self.today_btn)
        today_row.addStretch()
        cal_layout.addLayout(today_row)

        self.cal_hint = QLabel()
        self.cal_hint.setObjectName("statLabel")
        cal_layout.addWidget(self.cal_hint)

        self.cal_grid = QGridLayout()
        self.cal_grid.setSpacing(3)
        self.cal_grid.setContentsMargins(0, 0, 0, 0)
        for col in range(7):
            self.cal_grid.setColumnStretch(col, 1)
            self.cal_grid.setColumnMinimumWidth(col, 32)
        cal_layout.addLayout(self.cal_grid)

        legend = QHBoxLayout()
        legend.setSpacing(12)
        for key in ("stats.legend_done", "stats.legend_partial", "stats.legend_none"):
            lbl = QLabel()
            lbl.setWordWrap(True)
            lbl.setStyleSheet("font-size: 10px; color: #888;")
            self._legend_labels.append(lbl)
            legend.addWidget(lbl, stretch=1)
        cal_layout.addLayout(legend)

        cal_row = QHBoxLayout()
        cal_row.addStretch(1)
        cal_row.addWidget(cal_frame, stretch=0, alignment=Qt.AlignmentFlag.AlignTop)
        cal_row.addStretch(1)
        layout.addLayout(cal_row)

    def _make_stat_card(self, label_key: str) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 16, 16, 16)

        value_label = QLabel("0")
        value_label.setObjectName("statValue")
        card_layout.addWidget(value_label)

        name_label = QLabel()
        name_label.setObjectName("statLabel")
        card_layout.addWidget(name_label)
        self._card_labels[label_key] = name_label

        card.value_label = value_label
        return card

    def retranslate(self) -> None:
        self.title_label.setText(tr("stats.title"))
        self.subtitle_label.setText(tr("stats.subtitle"))
        self.cal_hint.setText(tr("stats.cal_hint"))
        self.today_btn.setText(tr("stats.cal_today"))
        self.chart_title.setText(tr("stats.chart_title"))
        for i, key in enumerate(("week", "month", "year")):
            self.chart_period_combo.setItemText(i, tr(f"stats.chart.{key}"))
        for i, key in enumerate(("blocks", "time")):
            self.chart_metric_combo.setItemText(i, tr(f"stats.chart.metric.{key}"))
        self.export_csv_btn.setText(tr("stats.export_csv"))
        for key, lbl in self._card_labels.items():
            lbl.setText(tr(key))
        legend_keys = (
            "stats.legend_done_time"
            if self.db.get_daily_goal_settings().get("daily_goal_type") == "time"
            else "stats.legend_done",
            "stats.legend_partial",
            "stats.legend_none",
        )
        for lbl, key in zip(self._legend_labels, legend_keys):
            lbl.setText(tr(key))
        self._update_calendar_header()
        self.refresh()

    def refresh(self) -> None:
        stats = self.db.get_statistics()
        goal_type = stats.get("daily_goal_type", "blocks")

        if goal_type == "time":
            self._card_labels["stats.today_blocks"].setText(tr("stats.today_goal_time"))
            today = stats["today_seconds"]
            goal = stats["daily_goal_minutes"] * 60
            today_label = format_reading_duration(today)
            goal_label = format_reading_duration(goal)
            if stats["goal_met_today"]:
                self.today_blocks_card.value_label.setText(f"{today_label}/{goal_label} ✓")
            else:
                self.today_blocks_card.value_label.setText(f"{today_label}/{goal_label}")
        else:
            self._card_labels["stats.today_blocks"].setText(tr("stats.today_blocks"))
            goal = stats["daily_goal_blocks"]
            today = stats["today_blocks"]
            if stats["goal_met_today"]:
                self.today_blocks_card.value_label.setText(f"{today}/{goal} ✓")
            else:
                self.today_blocks_card.value_label.setText(f"{today}/{goal}")

        self.today_words_card.value_label.setText(
            self._format_words(stats["today_words"])
        )
        self.today_time_card.value_label.setText(
            format_reading_duration(stats.get("today_seconds", 0))
        )
        self.books_card.value_label.setText(str(stats["books_completed"]))
        self.streak_card.value_label.setText(
            f"{stats['current_streak']} {tr('stats.days_unit')}"
        )
        self.total_card.value_label.setText(str(stats["total_blocks"]))

        self._refresh_chart()

        self._update_calendar()

    def _refresh_chart(self) -> None:
        goal_settings = self.db.get_daily_goal_settings()
        goal_type = goal_settings.get("daily_goal_type", "blocks")
        if goal_type == "time":
            goal_value = int(goal_settings.get("daily_goal_minutes", "15")) * 60
        else:
            goal_value = int(goal_settings.get("daily_goal_blocks", "10"))
        period = self.chart_period_combo.currentData() or "week"
        metric = self.chart_metric_combo.currentData() or "blocks"
        if period == "month":
            rows = self.db.get_monthly_stats(12)
            title_key = (
                "stats.chart_title_month_time"
                if metric == "time"
                else "stats.chart_title_month"
            )
        elif period == "year":
            rows = self.db.get_yearly_stats(5)
            title_key = (
                "stats.chart_title_year_time"
                if metric == "time"
                else "stats.chart_title_year"
            )
        else:
            rows = self.db.get_recent_daily_stats(7)
            title_key = (
                "stats.chart_title_time"
                if metric == "time"
                else "stats.chart_title"
            )
        self.chart_title.setText(tr(title_key))
        self.stats_chart.set_data(rows, goal_value, period, metric, goal_type)
        total_seconds = sum(int(row.get("seconds", 0) or 0) for row in rows)
        total_blocks = sum(int(row.get("blocks", 0) or 0) for row in rows)
        if metric == "time":
            self.period_total_label.setText(
                tr(
                    "stats.period_time_total",
                    time=format_reading_duration(total_seconds),
                )
            )
        else:
            self.period_total_label.setText(
                tr("stats.period_blocks_total", n=total_blocks)
            )

    def _export_csv(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            tr("stats.export_csv"),
            "reading_stats.csv",
            "CSV (*.csv)",
        )
        if not path:
            return
        try:
            Path(path).write_text(self.db.export_stats_csv(), encoding="utf-8")
            QMessageBox.information(
                self, tr("stats.export_csv"), tr("stats.export_csv_ok", path=path)
            )
        except Exception as exc:
            QMessageBox.critical(
                self, tr("stats.export_csv"), tr("stats.export_csv_failed", error=exc)
            )

    def _update_calendar_header(self) -> None:
        self.cal_title.setText(
            f"{month_name(self._view_month)} {self._view_year}"
        )

    def _prev_month(self) -> None:
        if self._view_month == 1:
            self._view_month = 12
            self._view_year -= 1
        else:
            self._view_month -= 1
        self._update_calendar()

    def _next_month(self) -> None:
        today = date.today()
        if (
            self._view_year > today.year
            or (
                self._view_year == today.year
                and self._view_month >= today.month
            )
        ):
            return
        if self._view_month == 12:
            self._view_month = 1
            self._view_year += 1
        else:
            self._view_month += 1
        self._update_calendar()

    def _go_today(self) -> None:
        today = date.today()
        self._view_year = today.year
        self._view_month = today.month
        self._update_calendar()

    def _can_go_next(self) -> bool:
        today = date.today()
        if self._view_year < today.year:
            return True
        if self._view_year == today.year and self._view_month < today.month:
            return True
        return False

    @staticmethod
    def _format_words(words: int) -> str:
        if words >= 1000:
            return f"{words // 1000:,}k".replace(",", " ")
        return str(words)

    def _day_object_name(self, status: str, is_future: bool) -> str:
        if is_future:
            return "calDayFuture"
        if status == "completed":
            return "calDayDone"
        if status == "partial":
            return "calDayPartial"
        return "calDayEmpty"

    def _update_calendar(self) -> None:
        while self.cal_grid.count():
            item = self.cal_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self._update_calendar_header()
        self.next_month_btn.setEnabled(self._can_go_next())

        today = date.today()
        goal_settings = self.db.get_daily_goal_settings()
        goal_type = goal_settings.get("daily_goal_type", "blocks")
        if goal_type == "time":
            goal_value = int(goal_settings.get("daily_goal_minutes", "15")) * 60
            goal_label = format_reading_duration(goal_value)
        else:
            goal_value = int(goal_settings.get("daily_goal_blocks", "10"))
            goal_label = str(goal_value)
        month_data = self.db.get_calendar_month(self._view_year, self._view_month)

        for col, day_name in enumerate(weekday_labels()):
            lbl = QLabel(day_name)
            lbl.setObjectName("statLabel")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setFixedHeight(18)
            lbl.setStyleSheet("font-size: 10px; font-weight: 600; color: #666;")
            self.cal_grid.addWidget(lbl, 0, col)

        weeks = calendar.Calendar(firstweekday=0).monthdayscalendar(
            self._view_year, self._view_month
        )

        for row_idx, week in enumerate(weeks, start=1):
            self.cal_grid.setRowMinimumHeight(row_idx, self.CAL_CELL_HEIGHT)
            for col_idx, day in enumerate(week):
                if day == 0:
                    spacer = QWidget()
                    spacer.setFixedHeight(self.CAL_CELL_HEIGHT)
                    spacer.setSizePolicy(
                        QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
                    )
                    self.cal_grid.addWidget(spacer, row_idx, col_idx)
                    continue

                day_key = str(day)
                info = month_data.get(day_key)
                blocks = int(info["blocks"]) if info else 0
                seconds = int(info.get("seconds", 0)) if info else 0
                status = str(info["status"]) if info else "missed"

                is_future = date(self._view_year, self._view_month, day) > today
                is_today = (
                    self._view_year == today.year
                    and self._view_month == today.month
                    and day == today.day
                )

                if is_future:
                    btn = QPushButton(str(day))
                    btn.setObjectName("calDayFuture")
                    btn.setEnabled(False)
                else:
                    btn = QPushButton(str(day))
                    btn.setObjectName(self._day_object_name(status, False))
                    btn.setCursor(Qt.CursorShape.PointingHandCursor)
                    day_date = f"{self._view_year}-{self._view_month:02d}-{day:02d}"
                    btn.clicked.connect(
                        lambda checked=False, d=day_date: self._show_day(d)
                    )
                    tip = (
                        tr(
                            "stats.cal_day_tip_time",
                            time=format_reading_duration(seconds),
                            goal=goal_label,
                            blocks=blocks,
                        )
                        if goal_type == "time"
                        else tr(
                            "stats.cal_day_tip",
                            blocks=blocks,
                            goal=goal_label,
                            time=format_reading_duration(seconds),
                        )
                    )
                    if status == "completed":
                        tip += " ✓"
                    btn.setToolTip(tip)

                btn.setSizePolicy(
                    QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
                )
                btn.setFixedHeight(self.CAL_CELL_HEIGHT)
                btn.setMinimumWidth(28)
                btn.setMaximumHeight(self.CAL_CELL_HEIGHT)

                if is_today:
                    btn.setProperty("today", True)
                    btn.style().unpolish(btn)
                    btn.style().polish(btn)

                self.cal_grid.addWidget(btn, row_idx, col_idx)

    def _show_day(self, day_date: str) -> None:
        stats = self.db.get_day_stats(day_date)
        if not stats:
            QMessageBox.information(
                self,
                tr("stats.day_title", date=day_date),
                tr("stats.day_empty"),
            )
            return
        DayStatsDialog(day_date, stats, self.window()).exec()
