"""eFuse tab — read eFuse values."""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView,
)


class EfuseTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        btn_row = QHBoxLayout()
        self._read_btn = QPushButton("Read eFuses")
        self._read_btn.setFixedWidth(140)
        self._read_btn.setEnabled(False)
        btn_row.addWidget(self._read_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self._table = QTableWidget(0, 3)
        self._table.setHorizontalHeaderLabels(["Index", "Address", "Value"])
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self._table, 1)

    @property
    def read_button(self) -> QPushButton:
        return self._read_btn

    def set_efuses(self, efuse_data: list):
        """Set eFuse table. Each item: (index, address, value)."""
        self._table.setRowCount(len(efuse_data))
        for row, (idx, addr, val) in enumerate(efuse_data):
            self._table.setItem(row, 0, QTableWidgetItem(str(idx)))
            self._table.setItem(row, 1, QTableWidgetItem(f"0x{addr:08X}" if isinstance(addr, int) else str(addr)))
            self._table.setItem(row, 2, QTableWidgetItem(f"0x{val:08X}" if isinstance(val, int) else str(val)))
