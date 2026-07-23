"""Prevent accidental wheel changes on combo/spin boxes while scrolling."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject
from PySide6.QtWidgets import QComboBox, QSpinBox, QWidget


class _WheelGuardFilter(QObject):
    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.Wheel and not obj.hasFocus():
            event.ignore()
            return True
        return False


def disable_wheel_unless_focused(root: QWidget) -> None:
    """Block wheel events on spin/combo boxes until the user clicks them."""
    for widget in (*root.findChildren(QComboBox), *root.findChildren(QSpinBox)):
        guard = _WheelGuardFilter(widget)
        widget.installEventFilter(guard)
        widget._wheel_guard = guard  # keep reference alive
