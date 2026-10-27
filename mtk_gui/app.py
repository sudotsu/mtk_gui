"""QApplication setup, theme init, entry point."""
import logging
import os
import sys

# ---------------------------------------------------------------------------
# Import order is load-bearing and must not be "tidied".
#
# mtkclient's LogBase metaclass calls logging.config.dictConfig() at class
# definition time, installing a StreamHandler bound to whatever sys.stdout is
# at that moment. Our tee has to be in place first or mtkclient's output never
# reaches the GUI. mtkclient is imported transitively by mtk_gui.main_window,
# so install_windowed_streams() must run above that import.
#
# tests/test_import_order.py pins this.
# ---------------------------------------------------------------------------
from mtk_gui.backend.stdio_bridge import install_windowed_streams

install_windowed_streams()

from mtk_gui.backend import diagnostics

diagnostics.install()

from PySide6.QtCore import Qt

# PySide6 6.8+ creates binding types lazily, on first attribute access. Because
# MainWindow overrides closeEvent(), the QCloseEvent wrapper type is created for
# the first time *during* window teardown, and doing so segfaulted inside
# Shiboken::ObjectType::introduceWrapperType on 6.12.0 (2026-10-26). Importing
# the name here forces that type into existence at startup instead, so the lazy
# path never runs during close. Keep this import even though it looks unused.
from PySide6.QtGui import QCloseEvent  # noqa: F401
from PySide6.QtWidgets import QApplication

from mtk_gui.constants import APP_NAME, ORG_NAME
from mtk_gui.main_window import MainWindow
from mtk_gui.plugins.loader import load_plugins

logger = logging.getLogger("mtk_gui.app")


def get_plugin_dirs() -> list:
    """
    Provide the application-local and user configuration directories used to search for plugins.

    Returns:
        list[str]: Plugin search directory paths.
    """
    dirs = []
    # App-local plugins dir
    app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    dirs.append(os.path.join(app_dir, "plugins"))
    # User config plugins dir
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        if appdata and os.path.isabs(appdata):
            dirs.append(os.path.join(appdata, "mtk-gui", "plugins"))
    else:
        config_dir = os.path.join(os.path.expanduser("~"), ".config", "mtk-gui", "plugins")
        if os.path.isabs(config_dir):
            dirs.append(config_dir)
    return dirs


def main():
    """
    Initialize the application, load plugins, display the main window, and start the Qt event loop.
    """
    path = diagnostics.log_path()
    if path:
        logger.info("MTK-GUI starting; log file: %s", path)

    QApplication.setOrganizationName(ORG_NAME)
    QApplication.setApplicationName(APP_NAME)

    app = QApplication(sys.argv)

    # High DPI support
    app.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    window = MainWindow()
    window.apply_initial_theme()

    # Load plugins
    class AppContext:
        main_window = window

    plugins = load_plugins(AppContext(), get_plugin_dirs())
    window.set_plugins(plugins)

    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
