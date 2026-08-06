"""Device connection and info tab (landing page)."""
import logging
from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox,
    QLabel, QLineEdit, QPushButton, QCheckBox, QComboBox, QFileDialog,
)

from mtk_gui.theme.colors import Colors


class StatusLed(QLabel):
    """Colored status indicator dot."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(16, 16)
        self.set_color(Colors.LED_DISCONNECTED)

    def set_color(self, color: str):
        """Set the indicator's background color."""
        self.setStyleSheet(
            f"background-color: {color}; border-radius: 8px; border: 1px solid #555;"
        )


class DeviceTab(QWidget):
    """Device connection settings and info display."""

    def __init__(self, parent=None):
        """Initialize the device tab and build its user interface."""
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        """
        Set up the device tab's status display, device information fields, and connection settings controls.
        """
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # ── Status section ────────────────────────────────
        status_group = QGroupBox("Connection Status")
        status_layout = QHBoxLayout(status_group)

        self._status_led = StatusLed()
        status_layout.addWidget(self._status_led)

        self._status_label = QLabel("Disconnected")
        self._status_label.setProperty("heading", True)
        status_layout.addWidget(self._status_label)
        status_layout.addStretch()

        self._connect_btn = QPushButton("Connect")
        self._connect_btn.setFixedWidth(100)
        status_layout.addWidget(self._connect_btn)

        self._disconnect_btn = QPushButton("Disconnect")
        self._disconnect_btn.setFixedWidth(100)
        self._disconnect_btn.setEnabled(False)
        status_layout.addWidget(self._disconnect_btn)

        layout.addWidget(status_group)

        # ── Device info section ───────────────────────────
        info_group = QGroupBox("Device Information")
        info_grid = QGridLayout(info_group)
        info_grid.setColumnStretch(1, 1)
        info_grid.setColumnStretch(3, 1)

        self._info_fields = {}
        fields = [
            ("Chipset:", "chipset", 0, 0),
            ("Boot Mode:", "boot_mode", 0, 2),
            ("HW Code:", "hwcode", 1, 0),
            ("HW Ver:", "hwver", 1, 2),
            ("SW Ver:", "swver", 2, 0),
            ("DA Mode:", "da_mode", 2, 2),
            ("Flash Type:", "flash_type", 3, 0),
            ("Flash Size:", "flash_size", 3, 2),
            ("MEID:", "meid", 4, 0),
            ("SoC ID:", "socid", 5, 0),
        ]

        for label_text, key, row, col in fields:
            label = QLabel(label_text)
            label.setStyleSheet("font-weight: bold;")
            info_grid.addWidget(label, row, col)

            value = QLineEdit()
            value.setReadOnly(True)
            value.setPlaceholderText("—")
            colspan = 3 if col == 0 and key in ("meid", "socid") else 1
            info_grid.addWidget(value, row, col + 1, 1, colspan)
            self._info_fields[key] = value

        layout.addWidget(info_group)

        # ── Connection settings section ───────────────────
        settings_group = QGroupBox("Connection Settings")
        settings_grid = QGridLayout(settings_group)
        settings_grid.setColumnStretch(1, 1)

        # DA loader path
        settings_grid.addWidget(QLabel("DA Loader:"), 0, 0)
        self._da_loader_input = QLineEdit()
        self._da_loader_input.setPlaceholderText("(auto-detect)")
        settings_grid.addWidget(self._da_loader_input, 0, 1)
        da_browse = QPushButton("Browse")
        da_browse.setFixedWidth(70)
        da_browse.clicked.connect(lambda: self._browse_file(self._da_loader_input))
        settings_grid.addWidget(da_browse, 0, 2)

        # Preloader path
        settings_grid.addWidget(QLabel("Preloader:"), 1, 0)
        self._preloader_input = QLineEdit()
        self._preloader_input.setPlaceholderText("(optional)")
        settings_grid.addWidget(self._preloader_input, 1, 1)
        pl_browse = QPushButton("Browse")
        pl_browse.setFixedWidth(70)
        pl_browse.clicked.connect(lambda: self._browse_file(self._preloader_input))
        settings_grid.addWidget(pl_browse, 1, 2)

        # Serial port
        settings_grid.addWidget(QLabel("Serial Port:"), 2, 0)
        self._serial_combo = QComboBox()
        self._serial_combo.addItem("(auto-detect)", None)
        self._serial_combo.setEditable(True)
        settings_grid.addWidget(self._serial_combo, 2, 1, 1, 2)

        # Working directory
        settings_grid.addWidget(QLabel("Working Dir:"), 3, 0)
        self._workdir_input = QLineEdit(".")
        settings_grid.addWidget(self._workdir_input, 3, 1)
        wd_browse = QPushButton("Browse")
        wd_browse.setFixedWidth(70)
        wd_browse.clicked.connect(self._browse_workdir)
        settings_grid.addWidget(wd_browse, 3, 2)

        # Checkboxes
        cb_row = QHBoxLayout()
        self._iot_check = QCheckBox("IoT Mode")
        cb_row.addWidget(self._iot_check)
        self._stock_check = QCheckBox("Stock DA")
        cb_row.addWidget(self._stock_check)
        cb_row.addStretch()
        settings_grid.addLayout(cb_row, 4, 0, 1, 3)

        layout.addWidget(settings_group)
        layout.addStretch()

    def _browse_file(self, target: QLineEdit):
        """Open a file chooser and populate the target field with the selected binary file path.
        
        Parameters:
        	target (QLineEdit): Field to update with the selected file path.
        """
        path, _ = QFileDialog.getOpenFileName(self, "Select File", "", "Binary (*.bin);;All (*)")
        if path:
            target.setText(path)

    def _browse_workdir(self):
        """Selects a working directory and updates the working-directory field when a directory is chosen."""
        d = QFileDialog.getExistingDirectory(self, "Select Working Directory")
        if d:
            self._workdir_input.setText(d)

    # ── Public API ────────────────────────────────────────

    @property
    def connect_button(self) -> QPushButton:
        """Provide access to the device connection button.
        
        Returns:
            QPushButton: The device connection button.
        """
        return self._connect_btn

    @property
    def disconnect_button(self) -> QPushButton:
        """Return the button used to disconnect from the device."""
        return self._disconnect_btn

    def get_settings(self) -> dict:
        """
        Return the configured device connection settings.
        
        Returns:
            dict: Settings containing normalized loader and preloader paths, the selected
                serial port, working directory, and IoT and Stock DA mode flags.
        """
        serial = self._serial_combo.currentData()
        if serial is None and self._serial_combo.currentText() != "(auto-detect)":
            serial = self._serial_combo.currentText()
        return {
            "da_loader": self._da_loader_input.text().strip() or None,
            "preloader": self._preloader_input.text().strip() or None,
            "serial_port": serial,
            "work_dir": self._workdir_input.text().strip() or ".",
            "iot": self._iot_check.isChecked(),
            "stock": self._stock_check.isChecked(),
        }

    @Slot(object)
    def update_device_info(self, info):
        """
        Update the displayed device information from a device-information object.
        
        Parameters:
            info: Object containing the device chipset, hardware, software, boot, flash, MEID, and SoC details.
        """
        mapping = {
            "chipset": info.chipset,
            "hwcode": info.hwcode,
            "hwver": info.hwver,
            "swver": info.swver,
            "boot_mode": info.boot_mode,
            "da_mode": info.da_mode,
            "flash_type": info.flash_type,
            "flash_size": info.flash_size,
            "meid": info.meid,
            "socid": info.socid,
        }
        for key, value in mapping.items():
            if key in self._info_fields:
                self._info_fields[key].setText(str(value) if value else "")

    @Slot(object)
    def update_connection_state(self, state):
        """
        Update the connection status display and button availability for a device state.
        
        Parameters:
            state: The current device connection state.
        """
        from mtk_gui.backend.device_manager import DeviceState
        state_map = {
            DeviceState.DISCONNECTED: ("Disconnected", Colors.LED_DISCONNECTED),
            DeviceState.DETECTING: ("Detecting...", Colors.LED_DETECTING),
            DeviceState.PRELOADER: ("Preloader detected", Colors.LED_CONNECTING),
            DeviceState.CONNECTING_DA: ("Connecting DA...", Colors.LED_CONNECTING),
            DeviceState.CONNECTED: ("Connected", Colors.LED_CONNECTED),
            DeviceState.ERROR: ("Error", Colors.LED_DISCONNECTED),
        }
        label, color = state_map.get(state, ("Unknown", Colors.LED_DISCONNECTED))
        self._status_label.setText(label)
        self._status_led.set_color(color)

        connected = state == DeviceState.CONNECTED
        self._connect_btn.setEnabled(not connected)
        self._disconnect_btn.setEnabled(connected)
