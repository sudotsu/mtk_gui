"""RPMB tab — read/write/erase RPMB partitions."""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QLineEdit, QPushButton, QFileDialog,
)


class RpmbTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # ── Read RPMB ─────────────────────────────────────
        read_group = QGroupBox("Read RPMB")
        read_layout = QVBoxLayout(read_group)

        r1 = QHBoxLayout()
        r1.addWidget(QLabel("Sector:"))
        self._read_sector = QLineEdit()
        self._read_sector.setPlaceholderText("0")
        r1.addWidget(self._read_sector, 1)
        r1.addWidget(QLabel("Sectors:"))
        self._read_sectors = QLineEdit()
        self._read_sectors.setPlaceholderText("1")
        r1.addWidget(self._read_sectors, 1)
        read_layout.addLayout(r1)

        r2 = QHBoxLayout()
        r2.addWidget(QLabel("Output File:"))
        self._read_file = QLineEdit()
        r2.addWidget(self._read_file, 1)
        rb = QPushButton("Browse")
        rb.setFixedWidth(70)
        rb.clicked.connect(lambda: self._browse_save(self._read_file))
        r2.addWidget(rb)
        self._read_btn = QPushButton("Read")
        self._read_btn.setFixedWidth(80)
        self._read_btn.setEnabled(False)
        r2.addWidget(self._read_btn)
        read_layout.addLayout(r2)
        layout.addWidget(read_group)

        # ── Write RPMB ────────────────────────────────────
        write_group = QGroupBox("Write RPMB")
        write_layout = QVBoxLayout(write_group)

        w1 = QHBoxLayout()
        w1.addWidget(QLabel("Sector:"))
        self._write_sector = QLineEdit()
        self._write_sector.setPlaceholderText("0")
        w1.addWidget(self._write_sector, 1)
        w1.addWidget(QLabel("Sectors:"))
        self._write_sectors = QLineEdit()
        self._write_sectors.setPlaceholderText("1")
        w1.addWidget(self._write_sectors, 1)
        write_layout.addLayout(w1)

        w2 = QHBoxLayout()
        w2.addWidget(QLabel("Input File:"))
        self._write_file = QLineEdit()
        w2.addWidget(self._write_file, 1)
        wb = QPushButton("Browse")
        wb.setFixedWidth(70)
        wb.clicked.connect(lambda: self._browse_open(self._write_file))
        w2.addWidget(wb)
        self._write_btn = QPushButton("Write")
        self._write_btn.setProperty("destructive", True)
        self._write_btn.setFixedWidth(80)
        self._write_btn.setEnabled(False)
        w2.addWidget(self._write_btn)
        write_layout.addLayout(w2)
        layout.addWidget(write_group)

        # ── Erase RPMB ────────────────────────────────────
        erase_group = QGroupBox("Erase RPMB")
        erase_layout = QHBoxLayout(erase_group)
        erase_layout.addStretch()
        self._erase_btn = QPushButton("Erase RPMB")
        self._erase_btn.setProperty("destructive", True)
        self._erase_btn.setEnabled(False)
        erase_layout.addWidget(self._erase_btn)
        layout.addWidget(erase_group)

        # ── Auth ──────────────────────────────────────────
        auth_group = QGroupBox("RPMB Authentication")
        auth_layout = QHBoxLayout(auth_group)
        auth_layout.addWidget(QLabel("Auth Key (32-byte hex):"))
        self._auth_key = QLineEdit()
        self._auth_key.setPlaceholderText("00" * 32)
        auth_layout.addWidget(self._auth_key, 1)
        layout.addWidget(auth_group)

        layout.addStretch()

    def _browse_save(self, target):
        path, _ = QFileDialog.getSaveFileName(self, "Output File", "", "Binary (*.bin);;All (*)")
        if path:
            target.setText(path)

    def _browse_open(self, target):
        path, _ = QFileDialog.getOpenFileName(self, "Input File", "", "Binary (*.bin);;All (*)")
        if path:
            target.setText(path)

    @property
    def read_button(self) -> QPushButton:
        return self._read_btn

    @property
    def write_button(self) -> QPushButton:
        return self._write_btn

    @property
    def erase_button(self) -> QPushButton:
        return self._erase_btn

    def set_enabled_all(self, enabled: bool):
        for btn in (self._read_btn, self._write_btn, self._erase_btn):
            btn.setEnabled(enabled)
