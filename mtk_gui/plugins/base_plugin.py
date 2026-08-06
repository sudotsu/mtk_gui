"""Abstract base class for MTK-GUI plugins."""
from abc import ABC, abstractmethod


class PluginContext:
    """Provides plugin access to the application."""

    def __init__(self, app):
        self._app = app

    def add_tab(self, widget, title: str, icon=None):
        """Add a tab to the main window's tab widget."""
        self._app.main_window.add_plugin_tab(widget, title)

    def add_menu_item(self, menu_path: str, action):
        """Add a menu item. menu_path: 'Plugins/My Action'."""
        self._app.main_window.add_plugin_menu_item(menu_path, action)

    def get_backend(self):
        """Get the DeviceManager instance."""
        return self._app.main_window.device_manager

    def get_device_info(self) -> dict:
        """Get current device info as a dict."""
        dm = self.get_backend()
        if dm and dm.device_info:
            info = dm.device_info
            return {
                "chipset": info.chipset,
                "hwcode": info.hwcode,
                "flash_type": info.flash_type,
                "flash_size": info.flash_size,
                "meid": info.meid,
                "socid": info.socid,
            }
        return {}

    def log(self, message: str, level: int = 20):
        """Log a message (level: 10=DEBUG, 20=INFO, 30=WARNING, 40=ERROR)."""
        dm = self.get_backend()
        if dm:
            dm.log_message.emit(message, level)

    def create_worker(self, func, *args):
        """Create a tracked Worker thread."""
        from mtk_gui.backend.worker import Worker
        dm = self.get_backend()
        return dm.create_worker(func, *args)


class MtkPlugin(ABC):
    """Base class for MTK-GUI plugins."""

    name: str = "Unnamed Plugin"
    version: str = "0.1.0"
    author: str = "Unknown"
    description: str = ""

    @abstractmethod
    def register(self, ctx: PluginContext) -> None:
        """Called when the plugin is loaded. Use ctx to add tabs, menus, etc."""
        ...

    def on_device_connected(self, device_info: dict) -> None:
        """Called when a device connects."""
        pass

    def on_device_disconnected(self) -> None:
        """Called when a device disconnects."""
        pass

    def cleanup(self) -> None:
        """Called when the application exits."""
        pass
