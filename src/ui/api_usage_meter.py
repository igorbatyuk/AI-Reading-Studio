"""Colored API quota meter for Settings → API tab."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QProgressBar, QVBoxLayout, QWidget

from ..core.i18n import tr


def usage_status_level(*, percent: int, remaining: int) -> str:
    """Return ok | warn | critical for quota display."""
    if remaining <= 0 or percent >= 100:
        return "critical"
    if percent >= 85:
        return "critical"
    if percent >= 65:
        return "warn"
    return "ok"


class ApiUsageMeter(QWidget):
    """Progress bar + green/yellow/red status chip for monthly API limits."""

    _STATUS_OBJECTS = {
        "ok": "statusValueOk",
        "warn": "statusValueWorking",
        "critical": "statusValueError",
    }
    _BAR_OBJECTS = {
        "ok": "apiUsageBarOk",
        "warn": "apiUsageBarWarn",
        "critical": "apiUsageBarCritical",
    }

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        header = QHBoxLayout()
        self._status_label = QLabel()
        self._status_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self._percent_label = QLabel()
        self._percent_label.setObjectName("hintLabel")
        self._percent_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        header.addStretch()
        header.addWidget(self._status_label)
        header.addWidget(self._percent_label)
        layout.addLayout(header)

        self._bar = QProgressBar()
        self._bar.setFixedHeight(10)
        self._bar.setTextVisible(False)
        self._bar.setRange(0, 100)
        layout.addWidget(self._bar)

        self._detail_label = QLabel()
        self._detail_label.setObjectName("hintLabel")
        self._detail_label.setWordWrap(True)
        self._detail_label.setMinimumWidth(320)
        layout.addWidget(self._detail_label)

    def set_usage(
        self,
        *,
        used: int,
        limit: int,
        remaining: int,
        percent: int,
        detail: str,
    ) -> None:
        level = usage_status_level(percent=percent, remaining=remaining)
        status_key = f"settings.api_usage.status.{level}"
        self._status_label.setText(tr(status_key))
        self._status_label.setObjectName(self._STATUS_OBJECTS[level])
        self._status_label.style().unpolish(self._status_label)
        self._status_label.style().polish(self._status_label)

        pct = min(100, max(0, int(percent)))
        self._percent_label.setText(f"{pct}%")
        self._bar.setValue(pct)
        self._bar.setObjectName(self._BAR_OBJECTS[level])
        self._bar.style().unpolish(self._bar)
        self._bar.style().polish(self._bar)
        self._detail_label.setText(detail)
