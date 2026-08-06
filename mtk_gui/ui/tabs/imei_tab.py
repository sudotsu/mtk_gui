"""IMEI tab — read/write IMEI, NVItem, modem patch."""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QLineEdit, QPushButton, QFileDialog,
)


class ImeiTab(QWidget):
    def __init__(self, parent=None):
        """Initialize the IMEI operation interface and its controls."""
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        """Build the widget layout and initialize its IMEI, modem, and NVItem controls."""
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # ── Read IMEI ─────────────────────────────────────
        read_group = QGroupBox("Read IMEI")
        read_layout = QVBoxLayout(read_group)

        r1 = QHBoxLayout()
        r1.addWidget(QLabel("Seed:"))
        self._seed_input = QLineEdit()
        self._seed_input.setPlaceholderText("(optional)")
        self._seed_input.setToolTip("Optional encryption seed for NVItem IMEI data. Usually not needed.")
        r1.addWidget(self._seed_input, 1)
        r1.addWidget(QLabel("AES Key:"))
        self._aeskey_input = QLineEdit()
        self._aeskey_input.setPlaceholderText("(optional)")
        self._aeskey_input.setToolTip("Optional AES key for NVItem decryption. Leave empty for default.")
        r1.addWidget(self._aeskey_input, 1)
        read_layout.addLayout(r1)

        r2 = QHBoxLayout()
        self._read_btn = QPushButton("Read IMEIs")
        self._read_btn.setFixedWidth(120)
        self._read_btn.setEnabled(False)
        r2.addWidget(self._read_btn)
        r2.addStretch()
        read_layout.addLayout(r2)

        # IMEI display
        self._imei_display = QLabel("IMEI1: —\nIMEI2: —")
        self._imei_display.setStyleSheet("font-family: Consolas; font-size: 14px; padding: 8px;")
        read_layout.addWidget(self._imei_display)
        layout.addWidget(read_group)

        # ── Write IMEI ────────────────────────────────────
        write_group = QGroupBox("Write IMEI")
        write_layout = QVBoxLayout(write_group)

        w1 = QHBoxLayout()
        w1.addWidget(QLabel("IMEI 1:"))
        self._imei1_input = QLineEdit()
        self._imei1_input.setPlaceholderText("15-digit IMEI")
        self._imei1_input.setMaxLength(15)
        w1.addWidget(self._imei1_input, 1)
        w1.addWidget(QLabel("IMEI 2:"))
        self._imei2_input = QLineEdit()
        self._imei2_input.setPlaceholderText("15-digit IMEI (optional)")
        self._imei2_input.setMaxLength(15)
        w1.addWidget(self._imei2_input, 1)
        write_layout.addLayout(w1)

        w2 = QHBoxLayout()
        w2.addWidget(QLabel("Product:"))
        self._product_input = QLineEdit()
        self._product_input.setPlaceholderText("(optional)")
        self._product_input.setToolTip("Device product name for CSSD record. Only needed for IMEI write with CSSD.")
        w2.addWidget(self._product_input, 1)
        self._write_btn = QPushButton("Write IMEIs")
        self._write_btn.setProperty("destructive", True)
        self._write_btn.setFixedWidth(120)
        self._write_btn.setEnabled(False)
        w2.addWidget(self._write_btn)
        write_layout.addLayout(w2)
        layout.addWidget(write_group)

        # ── Modem patch ───────────────────────────────────
        modem_group = QGroupBox("Modem")
        modem_layout = QHBoxLayout(modem_group)
        self._patch_modem_btn = QPushButton("Patch Modem")
        self._patch_modem_btn.setToolTip("Patch the modem partition to allow custom IMEI values.")
        self._patch_modem_btn.setProperty("destructive", True)
        self._patch_modem_btn.setEnabled(False)
        modem_layout.addWidget(self._patch_modem_btn)
        modem_layout.addStretch()
        layout.addWidget(modem_group)

        # ── NVItem ────────────────────────────────────────
        nv_group = QGroupBox("NVItem")
        nv_layout = QVBoxLayout(nv_group)
        nv1 = QHBoxLayout()
        nv1.addWidget(QLabel("NV File:"))
        self._nv_file = QLineEdit()
        self._nv_file.setToolTip("Select an NVItem binary file to encrypt or decrypt offline.")
        nv1.addWidget(self._nv_file, 1)
        nv_browse = QPushButton("Browse")
        nv_browse.setFixedWidth(70)
        nv_browse.clicked.connect(self._browse_nv)
        nv1.addWidget(nv_browse)
        nv_layout.addLayout(nv1)

        nv2 = QHBoxLayout()
        self._decrypt_btn = QPushButton("Decrypt")
        self._decrypt_btn.setEnabled(False)
        nv2.addWidget(self._decrypt_btn)
        self._encrypt_btn = QPushButton("Encrypt")
        self._encrypt_btn.setEnabled(False)
        nv2.addWidget(self._encrypt_btn)
        nv2.addStretch()
        nv_layout.addLayout(nv2)
        layout.addWidget(nv_group)

        layout.addStretch()

    def _browse_nv(self):
        """Open a file picker and update the NV file path when a file is selected."""
        path, _ = QFileDialog.getOpenFileName(self, "Select NV File", "", "All (*)")
        if path:
            self._nv_file.setText(path)

    @property
    def read_button(self) -> QPushButton:
        """Return the button used to initiate IMEI reading.
        
        Returns:
        	QPushButton: The IMEI read button.
        """
        return self._read_btn

    @property
    def write_button(self) -> QPushButton:
        """Return the button used to write IMEI values."""
        return self._write_btn

    @property
    def patch_modem_button(self) -> QPushButton:
        """Provides access to the modem patch action button.
        
        Returns:
            QPushButton: The modem patch button.
        """
        return self._patch_modem_btn

    def set_imei_display(self, imei1: str, imei2: str = ""):
        """Update the IMEI display with the primary and optional secondary IMEI values.
        
        Parameters:
        	imei1 (str): The primary IMEI value.
        	imei2 (str): The optional secondary IMEI value.
        """
        text = f"IMEI1: {imei1 or '—'}"
        if imei2:
            text += f"\nIMEI2: {imei2}"
        self._imei_display.setText(text)

    @property
    def decrypt_button(self) -> QPushButton:
        """Return the button used to decrypt NV files.
        
        Returns:
            QPushButton: The NV file decryption button.
        """
        return self._decrypt_btn

    @property
    def encrypt_button(self) -> QPushButton:
        """Return the NV item encryption button."""
        return self._encrypt_btn

    @property
    def nv_file(self) -> str:
        """Return the selected NV file path with surrounding whitespace removed."""
        return self._nv_file.text().strip()

    def get_imei_params(self) -> dict:
        """
        Collect the configured IMEI operation parameters.
        
        Returns:
        	dict: A dictionary containing trimmed values for IMEI1, IMEI2, seed, AES key, and product.
        """
        return {
            "imei1": self._imei1_input.text().strip(),
            "imei2": self._imei2_input.text().strip(),
            "seed": self._seed_input.text().strip(),
            "aeskey": self._aeskey_input.text().strip(),
            "product": self._product_input.text().strip(),
        }

    def set_enabled_all(self, enabled: bool):
        """Enable or disable all IMEI, modem, and NV file operation buttons.
        
        Parameters:
            enabled (bool): Whether the operation buttons should be enabled.
        """
        for btn in (self._read_btn, self._write_btn, self._patch_modem_btn,
                     self._decrypt_btn, self._encrypt_btn):
            btn.setEnabled(enabled)
