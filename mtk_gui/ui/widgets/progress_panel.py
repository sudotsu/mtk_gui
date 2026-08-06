"""Dual progress bars with ETA and speed display."""
import time
from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QProgressBar, QLabel


class ProgressPanel(QWidget):
    """Shows operation and overall progress with ETA/speed."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._start_time = 0
        self._last_update = 0
        self._last_bytes = 0
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        # Operation progress
        self._op_bar = QProgressBar()
        self._op_bar.setTextVisible(True)
        self._op_bar.setFormat("%p%")
        layout.addWidget(self._op_bar)

        # Info row
        info_row = QHBoxLayout()
        info_row.setSpacing(12)

        self._status_label = QLabel("Idle")
        info_row.addWidget(self._status_label, 1)

        self._speed_label = QLabel("")
        self._speed_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        info_row.addWidget(self._speed_label)

        self._eta_label = QLabel("")
        self._eta_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._eta_label.setMinimumWidth(80)
        info_row.addWidget(self._eta_label)

        layout.addLayout(info_row)

    def start(self, status: str = "Working..."):
        """Reset and start progress tracking."""
        self._start_time = time.time()
        self._last_update = self._start_time
        self._last_bytes = 0
        self._op_bar.setValue(0)
        self._status_label.setText(status)
        self._speed_label.setText("")
        self._eta_label.setText("")

    @Slot(int, int)
    def update_progress(self, current: int, total: int):
        """Update progress bar and compute ETA/speed."""
        if total <= 0:
            self._op_bar.setRange(0, 0)  # indeterminate
            return

        self._op_bar.setRange(0, total)
        self._op_bar.setValue(current)

        now = time.time()
        elapsed = now - self._start_time

        # Speed (bytes/sec over last interval)
        dt = now - self._last_update
        if dt >= 0.5:
            delta_bytes = current - self._last_bytes
            if delta_bytes > 0 and dt > 0:
                speed = delta_bytes / dt
                self._speed_label.setText(self._format_speed(speed))
            self._last_update = now
            self._last_bytes = current

        # ETA
        if current > 0 and elapsed > 0:
            remaining = (elapsed / current) * (total - current)
            self._eta_label.setText(f"ETA: {self._format_time(remaining)}")

    @Slot(str)
    def set_status(self, text: str):
        self._status_label.setText(text)

    def finish(self, status: str = "Done"):
        """Mark operation complete."""
        self._op_bar.setValue(self._op_bar.maximum() or 100)
        self._status_label.setText(status)
        self._speed_label.setText("")
        elapsed = time.time() - self._start_time
        self._eta_label.setText(f"Took: {self._format_time(elapsed)}")

    def reset(self):
        """Reset to idle state."""
        self._op_bar.setRange(0, 100)
        self._op_bar.setValue(0)
        self._status_label.setText("Idle")
        self._speed_label.setText("")
        self._eta_label.setText("")

    @staticmethod
    def _format_speed(bps: float) -> str:
        if bps >= 1024 * 1024:
            return f"{bps / (1024*1024):.1f} MB/s"
        if bps >= 1024:
            return f"{bps / 1024:.1f} KB/s"
        return f"{bps:.0f} B/s"

    @staticmethod
    def _format_time(seconds: float) -> str:
        s = int(seconds)
        if s >= 3600:
            return f"{s // 3600}h {(s % 3600) // 60}m {s % 60}s"
        if s >= 60:
            return f"{s // 60}m {s % 60}s"
        return f"{s}s"
