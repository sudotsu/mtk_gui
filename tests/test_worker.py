"""The Worker terminal-signal contract.

Worker's docstring promises exactly one of result_ready / error / cancelled.
These tests hold it to that, and in particular hold it to not losing an
exception just because cancellation happened to be requested.
"""
import pytest

from mtk_gui.backend.worker import Cancellation, Worker


def _run(worker):
    """Run the worker body synchronously and collect its terminal signal."""
    seen = []
    worker.result_ready.connect(lambda r: seen.append(("result", r)))
    worker.error.connect(lambda m: seen.append(("error", m)))
    worker.cancelled.connect(lambda c: seen.append(("cancelled", c)))
    worker.run()  # called directly: no thread, signals deliver immediately
    return seen


def test_success_emits_result_only():
    seen = _run(Worker(lambda worker=None: 42))
    assert seen == [("result", 42)]


def test_failure_emits_error_with_traceback():
    def boom(worker=None):
        raise ValueError("disk on fire")

    seen = _run(Worker(boom))
    assert len(seen) == 1
    kind, message = seen[0]
    assert kind == "error"
    assert "disk on fire" in message
    assert "Traceback" in message, "the traceback must survive"


def test_clean_cancel_emits_cancellation_marked_clean():
    def polite(worker=None):
        worker.cancel()
        return None

    seen = _run(Worker(polite))
    assert len(seen) == 1
    kind, info = seen[0]
    assert kind == "cancelled"
    assert isinstance(info, Cancellation)
    assert info.clean is True and info.failed is False


def test_cancel_does_not_swallow_the_exception():
    """Regression: a failure during cancellation reported nothing at all.

    An erase that dies of a USB fault while the user reaches for Disconnect
    used to emit a bare cancelled(), discarding the exception and traceback --
    the one failure path that leaves a partition half-written.
    """
    def fails_while_cancelling(worker=None):
        worker.cancel()
        raise OSError("USB device disappeared")

    seen = _run(Worker(fails_while_cancelling))

    assert len(seen) == 1, "exactly one terminal signal"
    kind, info = seen[0]
    assert kind == "cancelled"
    assert info.failed is True, "must not be reported as a clean cancel"
    assert "USB device disappeared" in info.message
    assert "unknown state" in info.message
    assert info.traceback and "Traceback" in info.traceback


def test_systemexit_during_cancel_also_carries_its_reason():
    """mtkclient aborts with sys.exit(), so SystemExit is a normal failure."""
    def bails(worker=None):
        worker.cancel()
        raise SystemExit(3)

    seen = _run(Worker(bails))
    kind, info = seen[0]
    assert kind == "cancelled"
    assert info.failed is True
    assert "sys.exit(3)" in info.message


def test_systemexit_without_cancel_emits_error():
    def bails(worker=None):
        raise SystemExit(1)

    seen = _run(Worker(bails))
    kind, message = seen[0]
    assert kind == "error"
    assert "sys.exit(1)" in message


@pytest.mark.parametrize("body", [
    lambda worker=None: "ok",
    lambda worker=None: (_ for _ in ()).throw(RuntimeError("x")),
])
def test_exactly_one_terminal_signal(body):
    assert len(_run(Worker(body))) == 1
