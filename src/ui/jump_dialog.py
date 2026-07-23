"""Jump to block dialog."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QVBoxLayout,
)

from ..core.i18n import tr


class JumpDialog(QDialog):
    def __init__(
        self,
        db,
        book_id: int,
        total_blocks: int,
        current_block: int,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.selected_block = current_block

        self.setWindowTitle(tr("reading.jump_title"))
        self.setMinimumWidth(320)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(tr("reading.jump_prompt")))

        spin_row = QHBoxLayout()
        self.block_spin = QSpinBox()
        self.block_spin.setRange(1, max(1, total_blocks))
        self.block_spin.setValue(current_block + 1)
        spin_row.addWidget(self.block_spin)
        spin_row.addWidget(QLabel(f"/ {total_blocks}"))
        spin_row.addStretch()
        layout.addLayout(spin_row)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(tr("dialog.ok"))
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(tr("dialog.cancel"))
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _accept(self) -> None:
        self.selected_block = self.block_spin.value() - 1
        self.accept()
