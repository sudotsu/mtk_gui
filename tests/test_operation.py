"""The dispatch helper's ordering contract."""
import pytest

from mtk_gui.backend.operation import NoDeviceError, require_wrapper, run_operation
from mtk_gui.backend.worker import Worker


class _FakeWorker:
    """Records the order of connect/start calls."""

    def __init__(self, calls):
        self._calls = calls
        self.result_ready = _Sig("result_ready", calls)
        self.error = _Sig("error", calls)
        self.cancelled = _Sig("cancelled", calls)

    def start(self):
        self._calls.append("start")


class _Sig:
    def __init__(self, name, calls):
        self._name = name
        self._calls = calls

    def connect(self, _handler):
        self._calls.append(f"connect:{self._name}")


class _FakeManager:
    def __init__(self, calls, wrapper=None):
        self._calls = calls
        self.wrapper = wrapper

    def create_worker(self, func, *args, **kwargs):
        self._calls.append("create")
        return _FakeWorker(self._calls)


def test_all_handlers_connected_before_start():
    """The race this module exists to remove: start() must come last."""
    calls = []
    run_operation(
        _FakeManager(calls),
        lambda worker=None: None,
        on_result=lambda _r: None,
        on_error=lambda _e: None,
        on_cancelled=lambda _c: None,
    )
    assert calls[-1] == "start", f"start() must be last, got {calls}"
    assert calls.index("connect:result_ready") < calls.index("start")
    assert calls.index("connect:error") < calls.index("start")
    assert calls.index("connect:cancelled") < calls.index("start")


def test_omitted_handlers_are_simply_not_connected():
    calls = []
    run_operation(_FakeManager(calls), lambda worker=None: None,
                  on_result=lambda _r: None)
    assert "connect:error" not in calls
    assert calls[-1] == "start"


def test_require_wrapper_raises_instead_of_returning_none():
    """A missing device must be an error, not a button that does nothing."""
    with pytest.raises(NoDeviceError, match="No device is connected"):
        require_wrapper(_FakeManager([], wrapper=None))


def test_require_wrapper_returns_the_live_wrapper():
    sentinel = object()
    assert require_wrapper(_FakeManager([], wrapper=sentinel)) is sentinel


def test_real_worker_signals_all_reach_handlers(qapp):
    """Against the real Worker, not the fake: a failure reaches on_error."""
    seen = []

    class Manager:
        wrapper = None

        def create_worker(self, func, *args, **kwargs):
            return Worker(func, *args, **kwargs)

    def boom(worker=None):
        raise ValueError("nope")

    w = run_operation(
        Manager(), boom,
        on_result=lambda r: seen.append(("result", r)),
        on_error=lambda e: seen.append(("error", e)),
        on_cancelled=lambda c: seen.append(("cancelled", c)),
    )
    w.wait(2000)
    qapp.processEvents()
    assert [k for k, _ in seen] == ["error"], seen
