"""Filterable log viewer with search and export."""
import logging
from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QColor, QTextCharFormat
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPlainTextEdit,
    QLineEdit, QComboBox, QPushButton, QFileDialog,
)


class LogPanel(QWidget):
    """Log viewer with level filtering, search, and export."""

    LEVEL_COLORS = {
        logging.DEBUG: "#888888",
        logging.INFO: "#d4d4d4",
        logging.WARNING: "#cc8844",
        logging.ERROR: "#cc4444",
        logging.CRITICAL: "#ff4444",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._all_messages = []
        self._min_level = logging.DEBUG
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        # Toolbar
        toolbar = QHBoxLayout()
        toolbar.setSpacing(4)

        self._search = QLineEdit()
        self._search.setPlaceholderText("Search logs...")
        self._search.textChanged.connect(self._apply_filter)
        toolbar.addWidget(self._search, 1)

        self._level_filter = QComboBox()
        self._level_filter.addItems(["All", "Debug", "Info", "Warning", "Error"])
        self._level_filter.currentIndexChanged.connect(self._on_level_changed)
        toolbar.addWidget(self._level_filter)

        clear_btn = QPushButton("Clear")
        clear_btn.setFixedWidth(60)
        clear_btn.clicked.connect(self.clear)
        toolbar.addWidget(clear_btn)

        export_btn = QPushButton("Export")
        export_btn.setFixedWidth(60)
        export_btn.clicked.connect(self._export)
        toolbar.addWidget(export_btn)

        layout.addLayout(toolbar)

        # Log display
        self._log_view = QPlainTextEdit()
        self._log_view.setReadOnly(True)
        self._log_view.setMaximumBlockCount(10000)
        self._log_view.setFont(self._monospace_font())
        layout.addWidget(self._log_view)

    @staticmethod
    def _monospace_font():
        from PySide6.QtGui import QFont
        font = QFont("Consolas", 9)
        font.setStyleHint(QFont.StyleHint.Monospace)
        return font

    @Slot(str, int)
    def append_log(self, message: str, level: int = logging.INFO):
        """Add a log message."""
        self._all_messages.append((message, level))
        if level >= self._min_level and self._matches_search(message):
            self._append_colored(message, level)

    def _append_colored(self, message: str, level: int):
        color = self.LEVEL_COLORS.get(level, "#d4d4d4")
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        cursor = self._log_view.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText(message + "\n", fmt)
        self._log_view.setTextCursor(cursor)
        self._log_view.ensureCursorVisible()

    def _on_level_changed(self, index: int):
        levels = [logging.DEBUG, logging.DEBUG, logging.INFO, logging.WARNING, logging.ERROR]
        self._min_level = levels[index]
        self._apply_filter()

    def _matches_search(self, message: str) -> bool:
        query = self._search.text().strip().lower()
        if not query:
            return True
        return query in message.lower()

    def _apply_filter(self):
        self._log_view.clear()
        for msg, level in self._all_messages:
            if level >= self._min_level and self._matches_search(msg):
                self._append_colored(msg, level)

    def clear(self):
        self._all_messages.clear()
        self._log_view.clear()

    def _export(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export Log", "mtk_log.txt", "Text (*.txt)")
        if path:
            with open(path, "w", encoding="utf-8") as f:
                for msg, _ in self._all_messages:
                    f.write(msg + "\n")
