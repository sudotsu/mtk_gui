"""QApplication setup, theme init, entry point."""
import os
import sys

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from mtk_gui.constants import APP_NAME, ORG_NAME
from mtk_gui.main_window import MainWindow
from mtk_gui.plugins.loader import load_plugins


def get_plugin_dirs() -> list:
    """Return plugin search directories."""
    dirs = []
    # App-local plugins dir
    app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    dirs.append(os.path.join(app_dir, "plugins"))
    # User config plugins dir
    if sys.platform == "win32":
        config_dir = os.path.join(os.environ.get("APPDATA", ""), "mtk-gui", "plugins")
    else:
        config_dir = os.path.join(os.path.expanduser("~"), ".config", "mtk-gui", "plugins")
    dirs.append(config_dir)
    return dirs


def main():
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
