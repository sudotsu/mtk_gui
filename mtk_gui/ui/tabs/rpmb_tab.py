"""RPMB tab — read/write/erase RPMB partitions."""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QLineEdit, QPushButton, QFileDialog,
)


class RpmbTab(QWidget):
    def __init__(self, parent=None):
        """Initialize the RPMB interface widget and its controls."""
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        """
        Builds the user interface for RPMB read, write, erase, and authentication controls.
        """
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
        self._erase_btn.setToolTip("Wipe all RPMB data. Only works on xflash/xml-mode devices.")
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
        self._auth_key.setToolTip("32-byte RPMB authentication key in hex. Required for authenticated RPMB access.")
        auth_layout.addWidget(self._auth_key, 1)
        layout.addWidget(auth_group)

        layout.addStretch()

    def _browse_save(self, target):
        """Opens a file-save dialog and assigns the selected output path to the target field.
        
        Parameters:
        	target: The text field that receives the selected file path.
        """
        path, _ = QFileDialog.getSaveFileName(self, "Output File", "", "Binary (*.bin);;All (*)")
        if path:
            target.setText(path)

    def _browse_open(self, target):
        """Select an input binary file and assign its path to the target field.
        
        Parameters:
        	target: The text field that receives the selected file path.
        """
        path, _ = QFileDialog.getOpenFileName(self, "Input File", "", "Binary (*.bin);;All (*)")
        if path:
            target.setText(path)

    @property
    def read_button(self) -> QPushButton:
        """Return the button used to start RPMB read operations.
        
        Returns:
            QPushButton: The RPMB read button.
        """
        return self._read_btn

    @property
    def write_button(self) -> QPushButton:
        """Return the button used to initiate RPMB write operations."""
        return self._write_btn

    @property
    def erase_button(self) -> QPushButton:
        """Return the button used to erase the RPMB partition.
        
        Returns:
            QPushButton: The RPMB erase button.
        """
        return self._erase_btn

    def get_read_params(self) -> dict:
        return {
            "filename": self._read_file.text().strip() or None,
            "sector": self._read_sector.text().strip() or None,
            "sectors": self._read_sectors.text().strip() or None,
        }

    def get_write_params(self) -> dict:
        """Returns write params. Raises ValueError on invalid input."""
        filename = self._write_file.text().strip()
        if not filename:
            raise ValueError("Input file is required for RPMB write.")
        sector_text = self._write_sector.text().strip()
        sectors_text = self._write_sectors.text().strip()
        return {
            "filename": filename,
            "sector": int(sector_text) if sector_text else 0,
            "sectors": int(sectors_text) if sectors_text else None,
        }

    def set_enabled_all(self, enabled: bool):
        """
        Enable or disable all RPMB operation buttons.
        
        Parameters:
        	enabled (bool): Whether the read, write, and erase buttons should be enabled.
        """
        for btn in (self._read_btn, self._write_btn, self._erase_btn):
            btn.setEnabled(enabled)
