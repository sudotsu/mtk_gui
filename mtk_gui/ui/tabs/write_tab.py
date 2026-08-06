"""Write tab — partition/flash/offset/directory write operations."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QComboBox, QLineEdit, QPushButton, QFileDialog,
    QStackedWidget, QRadioButton, QButtonGroup, QTreeWidget,
    QTreeWidgetItem, QHeaderView,
)

from mtk_gui.constants import PART_TYPES


class WriteTab(QWidget):
    def __init__(self, parent=None):
        """Initialize the write-configuration widget and its user interface."""
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        """Build the widget layout and controls for selecting flash-write modes and parameters."""
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # Warning banner
        warn = QLabel("WARNING: Writing to flash is destructive. Ensure you have backups.")
        warn.setStyleSheet(
            "background-color: #442200; color: #ffaa44; padding: 6px; "
            "border: 1px solid #cc8844; border-radius: 3px; font-weight: bold;"
        )
        warn.setWordWrap(True)
        layout.addWidget(warn)

        # ── Mode selector ─────────────────────────────────
        mode_group = QGroupBox("Write Mode")
        mode_layout = QHBoxLayout(mode_group)

        self._mode_group = QButtonGroup(self)
        modes = ["Partitions", "Full Flash", "By Offset", "From Directory"]
        for i, name in enumerate(modes):
            rb = QRadioButton(name)
            if i == 0:
                rb.setChecked(True)
            self._mode_group.addButton(rb, i)
            mode_layout.addWidget(rb)
        mode_layout.addStretch()

        mode_layout.addWidget(QLabel("Part Type:"))
        self._parttype_combo = QComboBox()
        self._parttype_combo.addItems(PART_TYPES)
        mode_layout.addWidget(self._parttype_combo)

        layout.addWidget(mode_group)

        # ── Stacked content ───────────────────────────────
        self._stack = QStackedWidget()

        # Page 0: Partitions with per-partition file selectors
        part_page = QWidget()
        part_layout = QVBoxLayout(part_page)

        self._part_tree = QTreeWidget()
        self._part_tree.setHeaderLabels(["Partition", "File"])
        self._part_tree.setRootIsDecorated(False)
        header = self._part_tree.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._part_tree.itemDoubleClicked.connect(self._on_part_file_select)
        part_layout.addWidget(self._part_tree)

        gpt_row = QHBoxLayout()
        gpt_row.addWidget(QLabel("GPT File (optional):"))
        self._gpt_file_input = QLineEdit()
        gpt_row.addWidget(self._gpt_file_input, 1)
        gpt_browse = QPushButton("Browse")
        gpt_browse.setFixedWidth(70)
        gpt_browse.clicked.connect(lambda: self._browse_open(self._gpt_file_input))
        gpt_row.addWidget(gpt_browse)
        part_layout.addLayout(gpt_row)

        self._stack.addWidget(part_page)

        # Page 1: Full Flash
        flash_page = QWidget()
        flash_layout = QVBoxLayout(flash_page)
        fr = QHBoxLayout()
        fr.addWidget(QLabel("Flash Image:"))
        self._flash_file_input = QLineEdit()
        fr.addWidget(self._flash_file_input, 1)
        fb = QPushButton("Browse")
        fb.setFixedWidth(70)
        fb.clicked.connect(lambda: self._browse_open(self._flash_file_input))
        fr.addWidget(fb)
        flash_layout.addLayout(fr)
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
        of_row.addWidget(QLabel("Input File:"))
        self._offset_file_input = QLineEdit()
        of_row.addWidget(self._offset_file_input, 1)
        ob = QPushButton("Browse")
        ob.setFixedWidth(70)
        ob.clicked.connect(lambda: self._browse_open(self._offset_file_input))
        of_row.addWidget(ob)
        offset_layout.addLayout(of_row)
        offset_layout.addStretch()
        self._stack.addWidget(offset_page)

        # Page 3: From Directory
        dir_page = QWidget()
        dir_layout = QVBoxLayout(dir_page)
        dr = QHBoxLayout()
        dr.addWidget(QLabel("Source Directory:"))
        self._dir_input = QLineEdit()
        dr.addWidget(self._dir_input, 1)
        db = QPushButton("Browse")
        db.setFixedWidth(70)
        db.clicked.connect(lambda: self._browse_dir(self._dir_input))
        dr.addWidget(db)
        dir_layout.addLayout(dr)
        dir_layout.addStretch()
        self._stack.addWidget(dir_page)

        layout.addWidget(self._stack, 1)
        self._mode_group.idClicked.connect(self._stack.setCurrentIndex)

        # ── Write button ──────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._write_btn = QPushButton("Write")
        self._write_btn.setFixedWidth(120)
        self._write_btn.setProperty("destructive", True)
        self._write_btn.setEnabled(False)
        btn_row.addWidget(self._write_btn)
        layout.addLayout(btn_row)

    def _browse_open(self, target: QLineEdit):
        """
        Select a binary file and place its path in the target input field.
        
        Parameters:
        	target (QLineEdit): Input field to receive the selected file path.
        """
        path, _ = QFileDialog.getOpenFileName(self, "Select File", "", "Binary (*.bin);;All (*)")
        if path:
            target.setText(path)

    def _browse_dir(self, target: QLineEdit):
        """Selects a directory and writes its path to the target input field.
        
        Parameters:
        	target (QLineEdit): Input field to receive the selected directory path.
        """
        d = QFileDialog.getExistingDirectory(self, "Select Directory")
        if d:
            target.setText(d)

    def _on_part_file_select(self, item: QTreeWidgetItem, column: int):
        """Selects a binary file for the partition represented by the activated tree item.
        
        Parameters:
        	item (QTreeWidgetItem): Partition item whose file path is updated.
        	column (int): Activated tree column.
        
        Returns:
        	None
        """
        if column == 1:
            path, _ = QFileDialog.getOpenFileName(self, f"Select file for {item.text(0)}", "", "Binary (*.bin);;All (*)")
            if path:
                item.setText(1, path)

    # ── Public API ────────────────────────────────────────

    @property
    def write_button(self) -> QPushButton:
        """Return the destructive write button."""
        return self._write_btn

    def set_partitions(self, partitions: list):
        """
        Replace the partition list displayed in the widget.
        
        Parameters:
        	partitions (list): Partition objects whose names populate the partition tree.
        """
        self._part_tree.clear()
        for p in partitions:
            item = QTreeWidgetItem([p.name, ""])
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
            self._part_tree.addTopLevelItem(item)

    def get_mode(self) -> int:
        """
        Get the selected flash-write mode.
        
        Returns:
        	int: The identifier of the selected mode.
        """
        return self._mode_group.checkedId()

    def get_parttype(self) -> str:
        """Return the selected partition type.
        
        Returns:
        	str: The currently selected partition type.
        """
        return self._parttype_combo.currentText()

    def get_write_params(self) -> dict:
        """
        Collect the configured parameters for the selected flash-write mode.
        
        Returns:
        	dict: A dictionary containing the selected mode, partition type, and mode-specific write parameters.
        """
        mode = self.get_mode()
        params = {"mode": mode, "parttype": self.get_parttype()}
        if mode == 0:
            partitions, filenames = [], []
            for i in range(self._part_tree.topLevelItemCount()):
                item = self._part_tree.topLevelItem(i)
                if item.text(1):
                    partitions.append(item.text(0))
                    filenames.append(item.text(1))
            params["partitions"] = partitions
            params["filenames"] = filenames
            params["gpt_file"] = self._gpt_file_input.text() or None
        elif mode == 1:
            params["filenames"] = [self._flash_file_input.text()]
        elif mode == 2:
            params["offset"] = int(self._offset_input.text() or "0", 16)
            params["length"] = int(self._offset_len_input.text() or "0", 16)
            params["filename"] = self._offset_file_input.text()
        elif mode == 3:
            params["directory"] = self._dir_input.text()
        return params
