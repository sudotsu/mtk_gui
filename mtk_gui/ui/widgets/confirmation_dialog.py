"""Confirmation dialog requiring the user to type YES for destructive operations."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QLineEdit, QHBoxLayout, QPushButton,
)


class ConfirmationDialog(QDialog):
    """Shows a warning and requires typing 'YES' to confirm destructive ops."""

    def __init__(self, title: str, message: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(400)
        self.setModal(True)
        self._confirmed = False
        self._setup_ui(message)

    def _setup_ui(self, message: str):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Warning icon + message
        warn_label = QLabel(f"WARNING: {message}")
        warn_label.setWordWrap(True)
        warn_label.setStyleSheet("color: #cc4444; font-weight: bold; font-size: 14px;")
        layout.addWidget(warn_label)

        hint = QLabel("Type YES to confirm:")
        layout.addWidget(hint)

        self._input = QLineEdit()
        self._input.setPlaceholderText("Type YES")
        self._input.textChanged.connect(self._on_text_changed)
        self._input.returnPressed.connect(self._try_accept)
        layout.addWidget(self._input)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(self._cancel_btn)

        self._confirm_btn = QPushButton("Confirm")
        self._confirm_btn.setEnabled(False)
        self._confirm_btn.setProperty("destructive", True)
        self._confirm_btn.clicked.connect(self._try_accept)
        btn_row.addWidget(self._confirm_btn)

        layout.addLayout(btn_row)

    def _on_text_changed(self, text: str):
        self._confirm_btn.setEnabled(text.strip().upper() == "YES")

    def _try_accept(self):
        if self._input.text().strip().upper() == "YES":
            self._confirmed = True
            self.accept()

    @property
    def confirmed(self) -> bool:
        return self._confirmed

    @staticmethod
    def confirm(title: str, message: str, parent=None) -> bool:
        """Convenience method. Returns True if confirmed."""
        dialog = ConfirmationDialog(title, message, parent)
        dialog.exec()
        return dialog.confirmed
