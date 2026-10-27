"""Crash and log diagnostics: a file log, faulthandler, and an excepthook.

Installed once at startup from ``mtk_gui.app``. The point is that when this
application dies — including by segfault inside the Qt bindings, which has
happened — there is something on disk afterwards to read. The GUI log panel
lives in a QTextEdit and dies with the process.
"""
import faulthandler
import logging
import os
import sys
import traceback
from logging.handlers import RotatingFileHandler

from mtk_gui.backend.stdio_bridge import add_line_sink

LOGGER_NAME = "mtk_gui"
_LOG_FILENAME = "mtk-gui.log"
_MAX_BYTES = 2 * 1024 * 1024
_BACKUP_COUNT = 3

_log_path: str | None = None
_fault_log = None


def log_directory() -> str:
    """Return the per-user directory the log file lives in."""
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    elif sys.platform == "darwin":
        base = os.path.join(os.path.expanduser("~"), "Library", "Logs")
    else:
        base = os.environ.get("XDG_STATE_HOME") or os.path.join(
            os.path.expanduser("~"), ".local", "state")
    return os.path.join(base, "mtk-gui")


def log_path() -> str | None:
    """Return the active log file path, or None if logging is not installed."""
    return _log_path


def install(level: int = logging.INFO) -> str | None:
    """Install the file log, faulthandler, and excepthook. Returns the log path.

    Returns None if the log file could not be opened; the application must stay
    usable on a read-only or full home directory.
    """
    # Module-level state is the point: this is a process-wide, install-once
    # side effect, and the faulthandler file must outlive this call.
    global _log_path, _fault_log  # noqa: PLW0603

    if _log_path is not None:
        return _log_path

    directory = log_directory()
    try:
        os.makedirs(directory, exist_ok=True)
        path = os.path.join(directory, _LOG_FILENAME)
        handler = RotatingFileHandler(
            path, maxBytes=_MAX_BYTES, backupCount=_BACKUP_COUNT, encoding="utf-8")
    except OSError as err:
        # No log file is survivable; failing to start because of one is not.
        print(f"mtk-gui: could not open log file in {directory}: {err}",
              file=sys.stderr)
        return None

    handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)-8s %(name)s: %(message)s"))

    # Our own loggers do not propagate: mtkclient reconfigures the root logger
    # via dictConfig at import time, and anything that reaches root is already
    # being captured through the stdout tee. Propagating would double every line.
    app_logger = logging.getLogger(LOGGER_NAME)
    app_logger.setLevel(level)
    app_logger.addHandler(handler)
    app_logger.propagate = False

    # Everything the stdout/stderr tee captures — which is where mtkclient's own
    # logging lands — also goes to the file.
    captured = logging.getLogger(f"{LOGGER_NAME}.captured")
    add_line_sink(lambda line, lvl: captured.log(lvl, line))

    _log_path = path

    try:
        # Deliberately not a context manager: faulthandler writes to this file
        # at crash time, so it has to stay open for the life of the process.
        _fault_log = open(  # noqa: SIM115
            os.path.join(directory, "mtk-gui-fault.log"),
            "a", buffering=1, encoding="utf-8")
        faulthandler.enable(file=_fault_log, all_threads=True)
    except OSError:
        faulthandler.enable(all_threads=True)

    _install_excepthook(app_logger)
    return path


def _install_excepthook(logger: logging.Logger):
    previous = sys.excepthook

    def hook(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            previous(exc_type, exc_value, exc_tb)
            return
        text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        logger.critical("Unhandled exception:\n%s", text)
        _show_crash_dialog(text)
        previous(exc_type, exc_value, exc_tb)

    sys.excepthook = hook


def _show_crash_dialog(text: str):
    """Show the traceback if a GUI exists, rather than dying silently."""
    try:
        from PySide6.QtWidgets import QApplication, QMessageBox
    except Exception:
        return
    if QApplication.instance() is None:
        return
    try:
        box = QMessageBox()
        box.setIcon(QMessageBox.Icon.Critical)
        box.setWindowTitle("MTK-GUI - unexpected error")
        box.setText("An unexpected error occurred.")
        where = _log_path or "(no log file)"
        box.setInformativeText(f"Details were written to:\n{where}")
        box.setDetailedText(text)
        box.exec()
    except Exception:
        pass
