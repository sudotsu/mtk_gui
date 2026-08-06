"""Keys tab — hardware key generation and display."""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QLineEdit, QPushButton, QFileDialog, QTableWidget, QTableWidgetItem,
    QHeaderView,
)


class KeysTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # Output directory
        dir_group = QGroupBox("Output")
        dir_layout = QHBoxLayout(dir_group)
        dir_layout.addWidget(QLabel("Directory:"))
        self._dir_input = QLineEdit(".")
        dir_layout.addWidget(self._dir_input, 1)
        browse = QPushButton("Browse")
        browse.setFixedWidth(70)
        browse.clicked.connect(self._browse_dir)
        dir_layout.addWidget(browse)
        layout.addWidget(dir_group)

        # Generate button
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._gen_btn = QPushButton("Generate Keys")
        self._gen_btn.setFixedWidth(140)
        self._gen_btn.setEnabled(False)
        btn_row.addWidget(self._gen_btn)
        layout.addLayout(btn_row)

        # Key table
        self._table = QTableWidget(0, 2)
        self._table.setHorizontalHeaderLabels(["Key", "Value"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        layout.addWidget(self._table, 1)

        # Status
        self._status = QLabel("")
        layout.addWidget(self._status)

    def _browse_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if d:
            self._dir_input.setText(d)

    @property
    def generate_button(self) -> QPushButton:
        return self._gen_btn

    @property
    def output_directory(self) -> str:
        return self._dir_input.text().strip() or "."

    def set_keys(self, keys: dict):
        """Display generated keys in the table."""
        self._table.setRowCount(len(keys))
        for row, (key, value) in enumerate(keys.items()):
            self._table.setItem(row, 0, QTableWidgetItem(str(key)))
            self._table.setItem(row, 1, QTableWidgetItem(str(value)))

    def set_status(self, msg: str):
        self._status.setText(msg)
