"""Edit book tags dialog."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QLineEdit,
    QVBoxLayout,
)

from ..core.i18n import tr


class TagsDialog(QDialog):
    def __init__(self, book_title: str, current_tags: list[str], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("library.tags_title"))
        self.setMinimumWidth(380)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(tr("library.tags_for", title=book_title)))
        layout.addWidget(QLabel(tr("library.tags_hint")))

        self.tags_edit = QLineEdit(", ".join(current_tags))
        layout.addWidget(self.tags_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Save).setText(tr("dialog.save"))
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(tr("dialog.cancel"))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def tags(self) -> list[str]:
        raw = self.tags_edit.text()
        return [part.strip() for part in raw.split(",") if part.strip()]
