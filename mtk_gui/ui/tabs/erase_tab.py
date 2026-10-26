"""Erase tab — partition/sector erase operations."""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QComboBox, QLineEdit, QPushButton,
    QStackedWidget, QRadioButton, QButtonGroup,
)

from mtk_gui.ui.widgets.dismissable_banner import DismissableBanner
from mtk_gui.ui.widgets.partition_list import PartitionList
from mtk_gui.constants import PART_TYPES


class EraseTab(QWidget):
    def __init__(self, parent=None):
        """
        Initialize the erase control widget and its user interface.
        
        Parameters:
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        """Builds the widget layout and initializes its partition and sector erase controls."""
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # Warning
        warn = DismissableBanner(
            "WARNING: Erasing partitions is irreversible. Data will be permanently lost.",
            banner_type="danger",
            settings_key="banner/erase_warning",
        )
        layout.addWidget(warn)

        # Mode selector
        mode_group = QGroupBox("Erase Mode")
        mode_layout = QHBoxLayout(mode_group)

        self._mode_group = QButtonGroup(self)
        for i, name in enumerate(["Partitions", "By Sector"]):
            rb = QRadioButton(name)
            if i == 0:
                rb.setChecked(True)
            self._mode_group.addButton(rb, i)
            mode_layout.addWidget(rb)
        mode_layout.addStretch()

        mode_layout.addWidget(QLabel("Part Type:"))
        self._parttype_combo = QComboBox()
        self._parttype_combo.addItems(PART_TYPES)
        self._parttype_combo.setToolTip("Usually 'user'. Only change if you know the target storage region.")
        mode_layout.addWidget(self._parttype_combo)

        layout.addWidget(mode_group)

        # Stacked content
        self._stack = QStackedWidget()

        # Page 0: Partitions
        part_page = QWidget()
        part_layout = QVBoxLayout(part_page)
        self._partition_list = PartitionList()
        part_layout.addWidget(self._partition_list)
        self._stack.addWidget(part_page)

        # Page 1: By Sector
        sector_page = QWidget()
        sector_layout = QVBoxLayout(sector_page)
        sg = QHBoxLayout()
        sg.addWidget(QLabel("Start Sector:"))
        self._sector_start = QLineEdit()
        self._sector_start.setPlaceholderText("0")
        sg.addWidget(self._sector_start, 1)
        sg.addWidget(QLabel("Sector Count:"))
        self._sector_count = QLineEdit()
        self._sector_count.setPlaceholderText("1")
        sg.addWidget(self._sector_count, 1)
        sector_layout.addLayout(sg)
        sector_layout.addStretch()
        self._stack.addWidget(sector_page)

        layout.addWidget(self._stack, 1)
        self._mode_group.idClicked.connect(self._stack.setCurrentIndex)

        # Erase button
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._erase_btn = QPushButton("Erase")
        self._erase_btn.setToolTip("Permanently destroys data. Cannot be undone.")
        self._erase_btn.setFixedWidth(120)
        self._erase_btn.setProperty("destructive", True)
        self._erase_btn.setEnabled(False)
        btn_row.addWidget(self._erase_btn)
        layout.addLayout(btn_row)

    @property
    def erase_button(self) -> QPushButton:
        """Return the button used to initiate the erase operation.
        
        Returns:
            QPushButton: The erase button.
        """
        return self._erase_btn

    @property
    def partition_list(self) -> PartitionList:
        """Provide access to the partition selection widget.
        
        Returns:
        	PartitionList: The partition list widget used by the tab.
        """
        return self._partition_list

    def get_erase_params(self) -> dict:
        """
        Collect the parameters selected for the current erase mode.
        
        Returns:
        	dict: A dictionary containing the erase mode and partition type, plus either the selected partitions or the starting sector and sector count. Empty sector fields are represented as zero.
        """
        mode = self._mode_group.checkedId()
        params = {"mode": mode, "parttype": self._parttype_combo.currentText()}
        if mode == 0:
            params["partitions"] = self._partition_list.get_selected()
            if not params["partitions"]:
                raise ValueError("Select at least one partition to erase.")
        else:
            start_text = self._sector_start.text().strip()
            count_text = self._sector_count.text().strip()
            if not start_text or not count_text:
                raise ValueError("Start sector and sector count are required.")
            params["sector"] = int(start_text)
            params["sectors"] = int(count_text)
            if params["sector"] < 0:
                raise ValueError("Start sector cannot be negative.")
            if params["sectors"] <= 0:
                raise ValueError("Sector count must be greater than zero.")
        return params
