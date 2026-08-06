"""Read tab — partition/flash/offset/sector read operations."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QComboBox, QLineEdit, QPushButton, QFileDialog, QCheckBox,
    QStackedWidget, QRadioButton, QButtonGroup,
)

from mtk_gui.ui.widgets.partition_list import PartitionList
from mtk_gui.constants import PART_TYPES


class ReadTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # ── Mode selector ─────────────────────────────────
        mode_group = QGroupBox("Read Mode")
        mode_layout = QHBoxLayout(mode_group)

        self._mode_group = QButtonGroup(self)
        modes = ["Partitions", "Full Flash", "By Offset", "By Sector"]
        for i, name in enumerate(modes):
            rb = QRadioButton(name)
            if i == 0:
                rb.setChecked(True)
            self._mode_group.addButton(rb, i)
            mode_layout.addWidget(rb)
        mode_layout.addStretch()

        # Part type
        mode_layout.addWidget(QLabel("Part Type:"))
        self._parttype_combo = QComboBox()
        self._parttype_combo.addItems(PART_TYPES)
        mode_layout.addWidget(self._parttype_combo)

        layout.addWidget(mode_group)

        # ── Stacked content ───────────────────────────────
        self._stack = QStackedWidget()

        # Page 0: Partitions
        part_page = QWidget()
        part_layout = QVBoxLayout(part_page)
        self._partition_list = PartitionList()
        part_layout.addWidget(self._partition_list)

        self._dump_gpt_check = QCheckBox("Also dump GPT")
        part_layout.addWidget(self._dump_gpt_check)

        dir_row = QHBoxLayout()
        dir_row.addWidget(QLabel("Output Directory:"))
        self._part_dir_input = QLineEdit()
        self._part_dir_input.setPlaceholderText("Select output directory...")
        dir_row.addWidget(self._part_dir_input, 1)
        part_dir_btn = QPushButton("Browse")
        part_dir_btn.setFixedWidth(70)
        part_dir_btn.clicked.connect(lambda: self._browse_dir(self._part_dir_input))
        dir_row.addWidget(part_dir_btn)
        part_layout.addLayout(dir_row)

        self._stack.addWidget(part_page)

        # Page 1: Full Flash
        flash_page = QWidget()
        flash_layout = QVBoxLayout(flash_page)
        file_row = QHBoxLayout()
        file_row.addWidget(QLabel("Output File:"))
        self._flash_file_input = QLineEdit()
        self._flash_file_input.setPlaceholderText("Select output file...")
        file_row.addWidget(self._flash_file_input, 1)
        flash_browse = QPushButton("Browse")
        flash_browse.setFixedWidth(70)
        flash_browse.clicked.connect(lambda: self._browse_save(self._flash_file_input))
        file_row.addWidget(flash_browse)
        flash_layout.addLayout(file_row)
        flash_layout.addStretch()
        self._stack.addWidget(flash_page)

        # Page 2: By Offset
        offset_page = QWidget()
        offset_layout = QVBoxLayout(offset_page)
        og = QHBoxLayout()
        og.addWidget(QLabel("Offset (hex):"))
        self._offset_input = QLineEdit()
        self._offset_input.setPlaceholderText("0x0")
        og.addWidget(self._offset_input, 1)
        og.addWidget(QLabel("Length (hex):"))
        self._offset_len_input = QLineEdit()
        self._offset_len_input.setPlaceholderText("0x1000")
        og.addWidget(self._offset_len_input, 1)
        offset_layout.addLayout(og)

        of_row = QHBoxLayout()
        of_row.addWidget(QLabel("Output File:"))
        self._offset_file_input = QLineEdit()
        of_row.addWidget(self._offset_file_input, 1)
        off_browse = QPushButton("Browse")
        off_browse.setFixedWidth(70)
        off_browse.clicked.connect(lambda: self._browse_save(self._offset_file_input))
        of_row.addWidget(off_browse)
        offset_layout.addLayout(of_row)
        offset_layout.addStretch()
        self._stack.addWidget(offset_page)

        # Page 3: By Sector
        sector_page = QWidget()
        sector_layout = QVBoxLayout(sector_page)
        sg = QHBoxLayout()
        sg.addWidget(QLabel("Start Sector:"))
        self._sector_start_input = QLineEdit()
        self._sector_start_input.setPlaceholderText("0")
        sg.addWidget(self._sector_start_input, 1)
        sg.addWidget(QLabel("Sector Count:"))
        self._sector_count_input = QLineEdit()
        self._sector_count_input.setPlaceholderText("1")
        sg.addWidget(self._sector_count_input, 1)
        sector_layout.addLayout(sg)

        sf_row = QHBoxLayout()
        sf_row.addWidget(QLabel("Output File:"))
        self._sector_file_input = QLineEdit()
        sf_row.addWidget(self._sector_file_input, 1)
        sec_browse = QPushButton("Browse")
        sec_browse.setFixedWidth(70)
        sec_browse.clicked.connect(lambda: self._browse_save(self._sector_file_input))
        sf_row.addWidget(sec_browse)
        sector_layout.addLayout(sf_row)
        sector_layout.addStretch()
        self._stack.addWidget(sector_page)

        layout.addWidget(self._stack, 1)

        # Wire mode selector to stack
        self._mode_group.idClicked.connect(self._stack.setCurrentIndex)

        # ── Read button ───────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._read_btn = QPushButton("Read")
        self._read_btn.setFixedWidth(120)
        self._read_btn.setEnabled(False)
        btn_row.addWidget(self._read_btn)
        layout.addLayout(btn_row)

    def _browse_dir(self, target: QLineEdit):
        d = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if d:
            target.setText(d)

    def _browse_save(self, target: QLineEdit):
        path, _ = QFileDialog.getSaveFileName(self, "Select Output File", "", "Binary (*.bin);;All (*)")
        if path:
            target.setText(path)

    # ── Public API ────────────────────────────────────────

    @property
    def read_button(self) -> QPushButton:
        return self._read_btn

    @property
    def partition_list(self) -> PartitionList:
        return self._partition_list

    def get_mode(self) -> int:
        return self._mode_group.checkedId()

    def get_parttype(self) -> str:
        return self._parttype_combo.currentText()

    def get_read_params(self) -> dict:
        mode = self.get_mode()
        params = {"mode": mode, "parttype": self.get_parttype()}
        if mode == 0:
            params["partitions"] = self._partition_list.get_selected()
            params["directory"] = self._part_dir_input.text()
            params["dump_gpt"] = self._dump_gpt_check.isChecked()
        elif mode == 1:
            params["filename"] = self._flash_file_input.text()
        elif mode == 2:
            params["offset"] = int(self._offset_input.text() or "0", 16)
            params["length"] = int(self._offset_len_input.text() or "0", 16)
            params["filename"] = self._offset_file_input.text()
        elif mode == 3:
            params["start"] = int(self._sector_start_input.text() or "0")
            params["sectors"] = int(self._sector_count_input.text() or "0")
            params["filename"] = self._sector_file_input.text()
        return params
