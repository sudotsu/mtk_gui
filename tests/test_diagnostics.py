"""Diagnostics setup, and the two ways it used to misbehave.

Both of these were found by Codex review on PR #3, and both were reproduced
before being fixed.
"""
import builtins
import logging

import pytest

from mtk_gui.backend import diagnostics
from mtk_gui.backend.diagnostics import CAPTURED_LOGGER_NAME


@pytest.fixture
def isolated_log_dir(tmp_path, monkeypatch):
    """Point the log directory at tmp_path and undo handler changes after."""
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    app_logger = logging.getLogger(diagnostics.LOGGER_NAME)
    before = list(app_logger.handlers)
    propagate = app_logger.propagate
    yield tmp_path
    for h in list(app_logger.handlers):
        if h not in before:
            app_logger.removeHandler(h)
            h.close()
    app_logger.propagate = propagate


def test_install_survives_an_unopenable_fault_log(isolated_log_dir, monkeypatch):
    """Startup must not abort because a crash log could not be opened.

    faulthandler's default target is sys.stderr, which by this point is the
    stdio tee and has no file descriptor, so enabling it there raises
    io.UnsupportedOperation -- which is not an OSError-shaped failure the
    caller was catching, so it propagated and killed startup.
    """
    real_open = builtins.open

    def refuse_fault_log(path, *args, **kwargs):
        if "mtk-gui-fault.log" in str(path):
            raise PermissionError(13, "Permission denied")
        return real_open(path, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", refuse_fault_log)

    path = diagnostics.install()

    assert path is not None, "startup must still get a log file"


def test_captured_records_are_distinguishable_by_logger_name():
    """The filter in DeviceManager keys off this name, so pin it."""
    assert CAPTURED_LOGGER_NAME == "mtk_gui.captured"
    assert CAPTURED_LOGGER_NAME.startswith(diagnostics.LOGGER_NAME + ".")


def test_captured_lines_reach_the_gui_exactly_once(qapp, isolated_log_dir):
    """Regression: every mtkclient line used to appear twice in the GUI.

    attach_streams() delivers each captured line to the GUI directly. The same
    lines are also logged under mtk_gui.captured so they reach the log file,
    and those records propagate to the handler DeviceManager puts on the
    "mtk_gui" parent -- so the GUI received one bare copy and one prefixed
    "mtk_gui.captured:".
    """
    from mtk_gui.backend.device_manager import DeviceManager

    diagnostics.install()
    manager = DeviceManager()
    try:
        seen = []
        manager.log_message.connect(lambda msg, _lvl: seen.append(msg))

        logging.getLogger(CAPTURED_LOGGER_NAME).info("MARKER-UNIQUE")
        qapp.processEvents()

        hits = [m for m in seen if "MARKER-UNIQUE" in m]
        assert len(hits) == 0, (
            f"captured records must not reach the GUI via the logging "
            f"handler at all; got {hits}"
        )
    finally:
        manager.begin_shutdown()
        manager.stop_polling()


def test_application_log_records_still_reach_the_gui(qapp, isolated_log_dir):
    """The filter must not silence the app's own loggers, which it exists for."""
    from mtk_gui.backend.device_manager import DeviceManager

    diagnostics.install()
    manager = DeviceManager()
    try:
        seen = []
        manager.log_message.connect(lambda msg, _lvl: seen.append(msg))

        logging.getLogger(f"{diagnostics.LOGGER_NAME}.plugins").warning(
            "PLUGIN-MARKER")
        qapp.processEvents()

        assert any("PLUGIN-MARKER" in m for m in seen), (
            f"app loggers must still reach the GUI; got {seen}")
    finally:
        manager.begin_shutdown()
        manager.stop_polling()
