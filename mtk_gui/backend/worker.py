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
        """
        Initialize a worker for executing a callable with the supplied arguments.
        
        Parameters:
            func (callable): Function to execute in the worker thread.
            *args: Positional arguments passed to the function.
            **kwargs: Keyword arguments passed to the function.
        """
        super().__init__()
        self._func = func
        self._args = args
        self._kwargs = kwargs
        self._cancelled = False

    def cancel(self):
        """Mark the worker as cancelled."""
        self._cancelled = True

    @property
    def is_cancelled(self):
        """Return whether the worker has been cancelled.
        
        Returns:
        	bool: `True` if cancellation has been requested, `False` otherwise.
        """
        return self._cancelled

    def run(self):
        """Execute the worker function and emit its result or an error message."""
        try:
            result = self._func(*self._args, worker=self, **self._kwargs)
            if not self._cancelled:
                self.finished.emit(result)
        except OperationAborted:
            self.error.emit("Operation aborted by library.")
        except Exception as e:
            tb = traceback.format_exc()
            self.error.emit(f"{e}\n{tb}")
