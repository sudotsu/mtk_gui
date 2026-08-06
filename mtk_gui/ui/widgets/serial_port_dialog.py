"""Serial port selection dialog."""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton,
)


class SerialPortDialog(QDialog):
    """Dialog for selecting a serial port."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Serial Port")
        self.setMinimumWidth(300)
        self._selected_port = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Available serial ports:"))

        self._combo = QComboBox()
        self._refresh_ports()
        layout.addWidget(self._combo)

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._refresh_ports)
        btn_row.addWidget(refresh_btn)

        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self._accept)
        btn_row.addWidget(ok_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        layout.addLayout(btn_row)

    def _refresh_ports(self):
        self._combo.clear()
        self._combo.addItem("(auto-detect)", None)
        try:
            import serial.tools.list_ports
            for port in serial.tools.list_ports.comports():
                self._combo.addItem(f"{port.device} - {port.description}", port.device)
        except ImportError:
            pass

    def _accept(self):
        self._selected_port = self._combo.currentData()
        self.accept()

    @property
    def selected_port(self):
        return self._selected_port
