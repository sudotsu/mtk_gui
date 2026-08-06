"""QApplication setup, theme init, entry point."""
import os
import sys

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from mtk_gui.constants import APP_NAME, ORG_NAME
from mtk_gui.main_window import MainWindow
from mtk_gui.plugins.loader import load_plugins


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
