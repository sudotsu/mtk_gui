"""QThread-based worker for running backend operations off the GUI thread."""
import threading
import traceback
from PySide6.QtCore import QThread, Signal


class Worker(QThread):
    """Runs a callable in a background thread, emitting progress and result signals.

    Guarantees exactly one terminal signal is emitted: result_ready, error, or
    cancelled.

    ``result_ready`` is deliberately NOT named ``finished``: ``QThread`` already
    defines a ``finished`` signal that fires once the thread has actually exited.
    A same-named signal here shadowed it and was emitted from inside ``run()``
    while the thread was still alive, so anything connecting to ``finished``
    expecting thread termination got the result instead.
    """

    progress = Signal(int, int)       # current, total
    log_message = Signal(str, int)    # message, level
    status_text = Signal(str)
    result_ready = Signal(object)     # result (any)
    error = Signal(str)               # error message
    cancelled = Signal()              # emitted if cancelled before result

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
        self._cancel_event = threading.Event()

    def cancel(self):
        """Request cooperative cancellation of the worker."""
        self._cancel_event.set()

    @property
    def is_cancelled(self):
        """Return whether the worker has been cancelled.
        
        Returns:
        	bool: `True` if cancellation has been requested, `False` otherwise.
        """
        return self._cancel_event.is_set()

    def run(self):
        """Execute the worker function and emit its result or an error message."""
        try:
            result = self._func(*self._args, worker=self, **self._kwargs)
            if self.is_cancelled:
                self.cancelled.emit()
            else:
                self.result_ready.emit(result)
        except SystemExit as e:
            if self.is_cancelled:
                self.cancelled.emit()
            else:
                self.error.emit(f"Operation aborted (sys.exit({e.code})).")
        except Exception as e:
            if self.is_cancelled:
                self.cancelled.emit()
            else:
                tb = traceback.format_exc()
                self.error.emit(f"{e}\n{tb}")
