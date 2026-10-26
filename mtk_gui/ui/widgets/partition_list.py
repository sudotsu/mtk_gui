"""Reusable checkbox list with partition sizes."""
import math
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTreeWidget, QTreeWidgetItem,
    QPushButton, QHeaderView,
)


class PartitionList(QWidget):
    """Partition list with checkboxes, name, and size columns."""

    selection_changed = Signal(list)  # list of partition names

    def __init__(self, parent=None):
        super().__init__(parent)
        self._partitions = []
        self._setup_ui()

    def _setup_ui(self):
        """Builds the widget layout with partition controls and a checkable partition tree."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(4)

        select_all = QPushButton("Select All")
        select_all.setFixedWidth(80)
        select_all.clicked.connect(self._select_all)
        btn_row.addWidget(select_all)

        deselect_all = QPushButton("Deselect All")
        deselect_all.setFixedWidth(90)
        deselect_all.clicked.connect(self._deselect_all)
        btn_row.addWidget(deselect_all)

        btn_row.addStretch()
        layout.addLayout(btn_row)

        # Tree widget
        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(["Partition", "Size", "Sectors"])
        self._tree.setRootIsDecorated(False)
        self._tree.setAlternatingRowColors(True)

        header = self._tree.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)

        self._tree.itemChanged.connect(self._on_item_changed)
        layout.addWidget(self._tree)

    def set_partitions(self, partitions: list):
        """
        Replace the displayed partition entries with the provided partitions.
        
        Parameters:
        	partitions (list): Partition objects with `name`, `size`, and `sectors` attributes.
        """
        self._tree.blockSignals(True)
        self._tree.clear()
        self._partitions = partitions

        for p in partitions:
            item = QTreeWidgetItem()
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(0, Qt.CheckState.Unchecked)
            item.setText(0, p.name)
            item.setText(1, self._format_size(p.size))
            item.setText(2, str(p.sectors))
            item.setData(0, Qt.ItemDataRole.UserRole, p.name)
            self._tree.addTopLevelItem(item)

        self._tree.blockSignals(False)

    def get_selected(self) -> list:
        """Return list of selected partition names."""
        selected = []
        for i in range(self._tree.topLevelItemCount()):
            item = self._tree.topLevelItem(i)
            if item.checkState(0) == Qt.CheckState.Checked:
                selected.append(item.data(0, Qt.ItemDataRole.UserRole))
        return selected

    def _select_all(self):
        """Select all partitions and emit the updated selection."""
        self._tree.blockSignals(True)
        for i in range(self._tree.topLevelItemCount()):
            self._tree.topLevelItem(i).setCheckState(0, Qt.CheckState.Checked)
        self._tree.blockSignals(False)
        self.selection_changed.emit(self.get_selected())

    def _deselect_all(self):
        """
        Deselect all partitions and emit the updated selection.
        """
        self._tree.blockSignals(True)
        for i in range(self._tree.topLevelItemCount()):
            self._tree.topLevelItem(i).setCheckState(0, Qt.CheckState.Unchecked)
        self._tree.blockSignals(False)
        self.selection_changed.emit(self.get_selected())

    def _on_item_changed(self, item, column):
        if column == 0:
            self.selection_changed.emit(self.get_selected())

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        """
        Format a byte count using a binary size unit.
        
        Parameters:
            size_bytes (int): The size in bytes.
        
        Returns:
            str: The rounded size with a unit from bytes through terabytes, or "0 B" for nonpositive values.
        """
        if size_bytes <= 0:
            return "0 B"
        units = ("B", "KB", "MB", "GB", "TB")
        i = min(int(math.floor(math.log(size_bytes, 1024))), len(units) - 1)
        p = math.pow(1024, i)
        s = round(size_bytes / p, 2)
        return f"{s} {units[i]}"
