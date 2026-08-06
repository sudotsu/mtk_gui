"""Bridge mtkclient's logging to Qt signals."""
import logging
from PySide6.QtCore import QObject, Signal


class LogSignalEmitter(QObject):
    """Emits Qt signals when log records arrive."""
    log_received = Signal(str, int)        # message, level
    progress_received = Signal(int, int)   # current, total
    status_received = Signal(str)


class LogSignalHandler(logging.Handler):
    """logging.Handler that forwards records to a LogSignalEmitter."""

    def __init__(self, emitter: LogSignalEmitter):
        super().__init__()
        self.emitter = emitter

    def emit(self, record: logging.LogRecord):
        try:
            msg = self.format(record)
            self.emitter.log_received.emit(msg, record.levelno)
        except RuntimeError:
            pass  # Qt object deleted


class GuiSignalProxy(QObject):
    """Drop-in replacement for mtkclient's gui/guiprogress/update_status_text signals.

    MtkConfig expects:
      - gui: object with .emit(str) for log lines
      - guiprogress: callable(current, total)
      - update_status_text: object with .emit(str) for status bar
    """
    sendToLogSignal = Signal(str)
    sendUpdateSignal = Signal()
    update_status_text = Signal(str)

    def __init__(self, emitter: LogSignalEmitter):
        super().__init__()
        self.emitter = emitter
        self.sendToLogSignal.connect(self._on_log)
        self.update_status_text.connect(self._on_status)

    def _on_log(self, msg: str):
        self.emitter.log_received.emit(msg, logging.INFO)

    def _on_status(self, msg: str):
        self.emitter.status_received.emit(msg)

    def emit(self, msg: str):
        """Direct emit — mtkclient's logsetup() calls gui.emit(string)."""
        self.sendToLogSignal.emit(msg)

    def progress_callback(self, current: int, total: int):
        self.emitter.progress_received.emit(current, total)
