"""Memory tab — peek/poke, memdump, BROM/SRAM dump."""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QLineEdit, QPushButton, QCheckBox, QFileDialog,
)

from mtk_gui.ui.widgets.hex_viewer import HexViewer


class MemoryTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # ── Peek ──────────────────────────────────────────
        peek_group = QGroupBox("Peek (Read Memory)")
        peek_layout = QVBoxLayout(peek_group)

        addr_row = QHBoxLayout()
        addr_row.addWidget(QLabel("Address (hex):"))
        self._peek_addr = QLineEdit()
        self._peek_addr.setPlaceholderText("0x100000")
        addr_row.addWidget(self._peek_addr, 1)
        addr_row.addWidget(QLabel("Length (hex):"))
        self._peek_len = QLineEdit()
        self._peek_len.setPlaceholderText("0x100")
        addr_row.addWidget(self._peek_len, 1)
        peek_layout.addLayout(addr_row)

        opt_row = QHBoxLayout()
        self._peek_regs = QCheckBox("Register mode")
        opt_row.addWidget(self._peek_regs)
        opt_row.addStretch()

        self._peek_btn = QPushButton("Read")
        self._peek_btn.setFixedWidth(80)
        self._peek_btn.setEnabled(False)
        opt_row.addWidget(self._peek_btn)

        self._peek_save_btn = QPushButton("Read to File")
        self._peek_save_btn.setFixedWidth(100)
        self._peek_save_btn.setEnabled(False)
        opt_row.addWidget(self._peek_save_btn)
        peek_layout.addLayout(opt_row)

        self._hex_viewer = HexViewer()
        peek_layout.addWidget(self._hex_viewer, 1)
        layout.addWidget(peek_group, 1)

        # ── Poke ──────────────────────────────────────────
        poke_group = QGroupBox("Poke (Write Memory)")
        poke_layout = QVBoxLayout(poke_group)

        poke_row = QHBoxLayout()
        poke_row.addWidget(QLabel("Address (hex):"))
        self._poke_addr = QLineEdit()
        self._poke_addr.setPlaceholderText("0x100000")
        poke_row.addWidget(self._poke_addr, 1)
        poke_row.addWidget(QLabel("Data (hex):"))
        self._poke_data = QLineEdit()
        self._poke_data.setPlaceholderText("DEADBEEF")
        poke_row.addWidget(self._poke_data, 1)
        poke_layout.addLayout(poke_row)

        poke_btn_row = QHBoxLayout()
        poke_btn_row.addStretch()
        self._poke_btn = QPushButton("Write")
        self._poke_btn.setProperty("destructive", True)
        self._poke_btn.setFixedWidth(80)
        self._poke_btn.setEnabled(False)
        poke_btn_row.addWidget(self._poke_btn)
        poke_layout.addLayout(poke_btn_row)
        layout.addWidget(poke_group)

        # ── Dump buttons ──────────────────────────────────
        dump_group = QGroupBox("Memory Dumps")
        dump_layout = QVBoxLayout(dump_group)

        dir_row = QHBoxLayout()
        dir_row.addWidget(QLabel("Output Dir:"))
        self._dump_dir = QLineEdit(".")
        dir_row.addWidget(self._dump_dir, 1)
        dir_browse = QPushButton("Browse")
        dir_browse.setFixedWidth(70)
        dir_browse.clicked.connect(self._browse_dump_dir)
        dir_row.addWidget(dir_browse)
        dump_layout.addLayout(dir_row)

        btn_row = QHBoxLayout()
        self._brom_btn = QPushButton("Dump BROM")
        self._brom_btn.setEnabled(False)
        btn_row.addWidget(self._brom_btn)
        self._sram_btn = QPushButton("Dump SRAM")
        self._sram_btn.setEnabled(False)
        btn_row.addWidget(self._sram_btn)
        self._dram_btn = QPushButton("Dump DRAM")
        self._dram_btn.setEnabled(False)
        btn_row.addWidget(self._dram_btn)
        self._memdump_btn = QPushButton("Full Memdump")
        self._memdump_btn.setEnabled(False)
        btn_row.addWidget(self._memdump_btn)
        dump_layout.addLayout(btn_row)
        layout.addWidget(dump_group)

    def _browse_dump_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if d:
            self._dump_dir.setText(d)

    # ── Public API ────────────────────────────────────────

    @property
    def peek_button(self) -> QPushButton:
        return self._peek_btn

    @property
    def peek_save_button(self) -> QPushButton:
        return self._peek_save_btn

    @property
    def poke_button(self) -> QPushButton:
        return self._poke_btn

    @property
    def brom_button(self) -> QPushButton:
        return self._brom_btn

    @property
    def sram_button(self) -> QPushButton:
        return self._sram_btn

    @property
    def dram_button(self) -> QPushButton:
        return self._dram_btn

    @property
    def memdump_button(self) -> QPushButton:
        return self._memdump_btn

    @property
    def hex_viewer(self) -> HexViewer:
        return self._hex_viewer

    def get_peek_params(self) -> dict:
        return {
            "addr": int(self._peek_addr.text() or "0", 16),
            "length": int(self._peek_len.text() or "0", 16),
            "registers": self._peek_regs.isChecked(),
        }

    def get_poke_params(self) -> dict:
        return {
            "addr": int(self._poke_addr.text() or "0", 16),
            "data": self._poke_data.text().strip(),
        }

    @property
    def dump_directory(self) -> str:
        return self._dump_dir.text().strip() or "."

    def set_enabled_all(self, enabled: bool):
        for btn in (self._peek_btn, self._peek_save_btn, self._poke_btn,
                     self._brom_btn, self._sram_btn, self._dram_btn, self._memdump_btn):
            btn.setEnabled(enabled)
