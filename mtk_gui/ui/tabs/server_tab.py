"""Server tab — key server and key generation."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QPushButton, QPlainTextEdit,
)


class ServerTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # ── Key Server ─────────────────────────────────────
        server_group = QGroupBox("Key Server")
        server_layout = QVBoxLayout(server_group)

        desc = QLabel("Runs the mtkclient key exchange server. "
                       "This is a one-shot operation that completes when the key exchange finishes.")
        desc.setWordWrap(True)
        server_layout.addWidget(desc)

        btn_row = QHBoxLayout()
        self._run_btn = QPushButton("Run Key Server")
        self._run_btn.setProperty("success", True)
        self._run_btn.setEnabled(False)
        btn_row.addWidget(self._run_btn)
        btn_row.addStretch()
        server_layout.addLayout(btn_row)

        layout.addWidget(server_group)

        # ── Status ────────────────────────────────────────
        status_group = QGroupBox("Status")
        status_layout = QHBoxLayout(status_group)

        self._status_label = QLabel("Idle")
        self._status_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        status_layout.addWidget(self._status_label)
        status_layout.addStretch()

        layout.addWidget(status_group)

        # ── Server log ────────────────────────────────────
        self._server_log = QPlainTextEdit()
        self._server_log.setReadOnly(True)
        from PySide6.QtGui import QFont
        font = QFont("Consolas", 9)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self._server_log.setFont(font)
        layout.addWidget(self._server_log, 1)

    @property
    def start_button(self) -> QPushButton:
        return self._run_btn

    def set_status(self, running: bool, message: str = ""):
        if running:
            self._status_label.setText(message or "Running...")
            self._status_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #44aa44;")
        else:
            self._status_label.setText(message or "Idle")
            self._status_label.setStyleSheet("font-weight: bold; font-size: 14px;")

    def append_server_log(self, message: str):
        self._server_log.appendPlainText(message)
