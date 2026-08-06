"""Example MTK-GUI plugin demonstrating the plugin API."""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton

from mtk_gui.plugins.base_plugin import MtkPlugin, PluginContext


class ExamplePlugin(MtkPlugin):
    name = "Example Plugin"
    version = "0.1.0"
    author = "MTK-GUI"
    description = "Demonstrates the plugin API with a simple tab."

    def __init__(self):
        """Initialize the plugin with no registered context or widget."""
        self._ctx = None
        self._widget = None

    def register(self, ctx: PluginContext) -> None:
        """Register the plugin with the application context and add its example tab."""
        self._ctx = ctx

        self._widget = QWidget()
        layout = QVBoxLayout(self._widget)
        layout.addWidget(QLabel("This is an example plugin tab."))
        layout.addWidget(QLabel("Plugins can add tabs, menu items, and interact with the backend."))

        info_btn = QPushButton("Show Device Info")
        info_btn.clicked.connect(self._show_info)
        layout.addWidget(info_btn)

        log_btn = QPushButton("Log a Message")
        log_btn.clicked.connect(lambda: ctx.log("Hello from Example Plugin!"))
        layout.addWidget(log_btn)

        layout.addStretch()

        ctx.add_tab(self._widget, "Example")

    def _show_info(self):
        """Log the connected device chipset or indicate that no device is connected."""
        info = self._ctx.get_device_info()
        if info.get("chipset"):
            self._ctx.log(f"Connected device: {info['chipset']}")
        else:
            self._ctx.log("No device connected.")

    def on_device_connected(self, device_info: dict) -> None:
        """
        Log a message when a device connects.
        
        Parameters:
            device_info (dict): Device information, including an optional ``chipset`` value.
        """
        self._ctx.log(f"[Example Plugin] Device connected: {device_info.get('chipset', '?')}")

    def on_device_disconnected(self) -> None:
        self._ctx.log("[Example Plugin] Device disconnected.")
