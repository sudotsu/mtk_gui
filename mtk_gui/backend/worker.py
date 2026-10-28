"""QThread-based worker for running backend operations off the GUI thread."""
import threading
import traceback
from dataclasses import dataclass

from PySide6.QtCore import QThread, Signal


@dataclass(frozen=True)
class Cancellation:
    """Why a worker stopped, when cancellation was requested.

    Cancellation and failure are not mutually exclusive: an erase can die of a
    USB fault at the same moment the user reaches for Disconnect. Reporting
    only "cancelled" in that case loses the reason the device is now in an
    unknown state, which on a flashing tool is the one thing the user most
    needs to know.
    """

    clean: bool                      # True when nothing failed
    message: str = "Cancelled."
    traceback: str | None = None

    @property
    def failed(self) -> bool:
        return not self.clean


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
    cancelled = Signal(object)        # Cancellation

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
        """Execute the worker function and emit exactly one terminal signal."""
        try:
            result = self._func(*self._args, worker=self, **self._kwargs)
        except SystemExit as e:
            self._emit_failure(
                f"Operation aborted (sys.exit({e.code})).",
                traceback.format_exc(),
            )
        except Exception as e:
            self._emit_failure(f"{e}", traceback.format_exc())
        else:
            if self.is_cancelled:
                self.cancelled.emit(Cancellation(clean=True))
            else:
                self.result_ready.emit(result)

    def _emit_failure(self, message: str, tb: str):
        """Report a failure, preserving it even when cancellation was requested.

        The previous implementation discarded the exception and its traceback
        whenever ``is_cancelled`` was set, emitting a bare ``cancelled``. An
        operation that died while the user was reaching for Disconnect
        therefore reported nothing, anywhere -- no message, no traceback, no
        log line. That is the failure path most likely to matter, because it
        is the one that leaves a partition half-written.
        """
        if self.is_cancelled:
            self.cancelled.emit(Cancellation(
                clean=False,
                message=(
                    "Cancelled after a failure, so the device may be in an "
                    f"unknown state: {message}"
                ),
                traceback=tb,
            ))
        else:
            self.error.emit(f"{message}\n{tb}")
