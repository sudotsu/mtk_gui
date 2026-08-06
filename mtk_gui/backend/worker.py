"""QThread-based worker for running backend operations off the GUI thread."""
import traceback
from PySide6.QtCore import QThread, Signal


class OperationAborted(Exception):
    """Raised when a library call hits sys.exit() (monkey-patched)."""


class Worker(QThread):
    """Runs a callable in a background thread, emitting progress and result signals."""

    progress = Signal(int, int)       # current, total
    log_message = Signal(str, int)    # message, level
    status_text = Signal(str)
    finished = Signal(object)         # result (any)
    error = Signal(str)               # error message

    def __init__(self, func, *args, **kwargs):
        super().__init__()
        self._func = func
        self._args = args
        self._kwargs = kwargs
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    @property
    def is_cancelled(self):
        return self._cancelled

    def run(self):
        try:
            result = self._func(*self._args, worker=self, **self._kwargs)
            if not self._cancelled:
                self.finished.emit(result)
        except OperationAborted:
            self.error.emit("Operation aborted by library.")
        except Exception as e:
            tb = traceback.format_exc()
            self.error.emit(f"{e}\n{tb}")
