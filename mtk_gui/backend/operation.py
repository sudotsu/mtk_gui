"""Single dispatch path for backend operations.

Two bugs motivated this module, both structural rather than local.

**The start/connect race.** The previous helper created a worker, called
``start()``, and returned it for the caller to connect signals to. A worker
that failed quickly -- a missing file, a disconnected device -- could emit its
terminal signal before the caller's ``connect()`` ran, so the result was
delivered to nobody and the progress panel span forever. Connecting before
starting removes the window entirely rather than making it smaller.

**The unhandled cancellation.** ``Worker.cancelled`` was connected nowhere in
the UI, so every cancel left the progress panel running. Routing all three
terminal signals through one function makes forgetting one impossible.
"""
from collections.abc import Callable

from mtk_gui.backend.worker import Cancellation, Worker


class NoDeviceError(RuntimeError):
    """Raised when an operation is requested with no device connected."""


def require_wrapper(device_manager):
    """Return the live MtkWrapper, or raise rather than return silently.

    Call sites used to read ``wrapper = dm.wrapper`` and ``return`` when it was
    falsey, which turned "no device" into a button that did nothing at all with
    no message anywhere.
    """
    wrapper = device_manager.wrapper
    if wrapper is None:
        raise NoDeviceError(
            "No device is connected. Connect a device before starting an "
            "operation."
        )
    return wrapper


def run_operation(
    device_manager,
    func: Callable,
    *args,
    on_result: Callable[[object], None] | None = None,
    on_error: Callable[[str], None] | None = None,
    on_cancelled: Callable[[Cancellation], None] | None = None,
    **kwargs,
) -> Worker:
    """Create a worker, connect every terminal signal, then start it.

    The ordering is the contract: nothing is started until all three handlers
    are attached. ``on_cancelled`` is as mandatory in practice as the other
    two, because a cancel that nothing handles leaves the UI mid-operation.
    """
    worker = device_manager.create_worker(func, *args, **kwargs)
    if on_result is not None:
        worker.result_ready.connect(on_result)
    if on_error is not None:
        worker.error.connect(on_error)
    if on_cancelled is not None:
        worker.cancelled.connect(on_cancelled)
    worker.start()
    return worker
