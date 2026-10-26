"""Abstract base class for MTK-GUI plugins."""
from abc import ABC, abstractmethod


class PluginContext:
    """Provides plugin access to the application."""

    def __init__(self, app):
        """Initialize the plugin context with an application reference.
        
        Parameters:
        	app: The application instance used to access plugin services.
        """
        self._app = app

    def add_tab(self, widget, title: str, icon=None):
        """Add a tab to the main window's tab widget."""
        self._app.main_window.add_plugin_tab(widget, title)

    def add_menu_item(self, menu_path: str, action):
        """Adds an action to the specified plugin menu path.
        
        Parameters:
        	menu_path (str): Menu path for the action, such as ``"Plugins/My Action"``.
        	action: Action to add to the menu.
        """
        self._app.main_window.add_plugin_menu_item(menu_path, action)

    def get_backend(self):
        """Get the DeviceManager instance."""
        return self._app.main_window.device_manager

    def get_device_info(self) -> dict:
        """Return selected information for the currently connected device.
        
        Returns:
        	dict: A mapping containing the device chipset, hardware code, flash type,
        	flash size, MEID, and SoC ID, or an empty dictionary when device
        	information is unavailable.
        """
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
        """
        Emit a message through the plugin backend.
        
        Parameters:
            message (str): The message to emit.
            level (int): The log severity, using 10 for debug, 20 for info, 30 for warning, or 40 for error.
        """
        dm = self.get_backend()
        if dm:
            dm.log_message.emit(message, level)

    def create_worker(self, func, *args):
        """Create a tracked worker for executing a function.
        
        Parameters:
        	func: The function to execute.
        	*args: Positional arguments passed to the function.
        
        Returns:
        	Worker: The created worker.
        """
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
        """
        Handle notification that a device has connected.
        
        Parameters:
            device_info (dict): Information about the connected device.
        """
        pass

    def on_device_disconnected(self) -> None:
        """Called when a device disconnects."""
        pass

    def cleanup(self) -> None:
        """Releases plugin resources when the application exits."""
        pass
