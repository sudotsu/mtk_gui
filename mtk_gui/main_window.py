"""Main window — connects backend to UI."""
import logging
import os
from PySide6.QtCore import Qt, QSettings, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QMainWindow, QTabWidget, QSplitter, QWidget, QVBoxLayout,
    QMessageBox, QMenu,
)

from mtk_gui.constants import APP_TITLE, ORG_NAME, APP_NAME, THEME_DARK, THEME_LIGHT, DEFAULT_THEME
from mtk_gui.theme import load_stylesheet
from mtk_gui.backend.device_manager import DeviceManager, DeviceState
from mtk_gui.backend.operation import run_operation
from mtk_gui.ui.widgets.log_panel import LogPanel
from mtk_gui.ui.widgets.progress_panel import ProgressPanel
from mtk_gui.ui.widgets.confirmation_dialog import ConfirmationDialog
from mtk_gui.ui.widgets.dismissable_banner import DismissableBanner

# Tabs
from mtk_gui.ui.tabs.device_tab import DeviceTab
from mtk_gui.ui.tabs.read_tab import ReadTab
from mtk_gui.ui.tabs.write_tab import WriteTab
from mtk_gui.ui.tabs.erase_tab import EraseTab
from mtk_gui.ui.tabs.keys_tab import KeysTab
from mtk_gui.ui.tabs.bootloader_tab import BootloaderTab
from mtk_gui.ui.tabs.memory_tab import MemoryTab
from mtk_gui.ui.tabs.rpmb_tab import RpmbTab
from mtk_gui.ui.tabs.imei_tab import ImeiTab
from mtk_gui.ui.tabs.exploit_tab import ExploitTab
from mtk_gui.ui.tabs.efuse_tab import EfuseTab
from mtk_gui.ui.tabs.server_tab import ServerTab


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.setMinimumSize(900, 650)

        self._settings = QSettings(ORG_NAME, APP_NAME)
        self._current_theme = self._settings.value("theme", DEFAULT_THEME)
        self._plugins = []
        self._last_peek_addr = 0
        self._operation_active = False

        # Backend
        self.device_manager = DeviceManager(self)

        self._setup_ui()
        self._setup_menus()
        self._connect_signals()
        self._restore_geometry()

        # Start USB polling
        self.device_manager.start_polling()

    def _setup_ui(self):
        # Central splitter: tabs on top, log panel on bottom
        splitter = QSplitter(Qt.Orientation.Vertical)

        # Tab widget
        self._tabs = QTabWidget()
        self._tabs.setTabPosition(QTabWidget.TabPosition.North)

        # Create all tabs
        self._device_tab = DeviceTab()
        self._read_tab = ReadTab()
        self._write_tab = WriteTab()
        self._erase_tab = EraseTab()
        self._keys_tab = KeysTab()
        self._bootloader_tab = BootloaderTab()
        self._memory_tab = MemoryTab()
        self._rpmb_tab = RpmbTab()
        self._imei_tab = ImeiTab()
        self._exploit_tab = ExploitTab()
        self._efuse_tab = EfuseTab()
        self._server_tab = ServerTab()

        self._tabs.addTab(self._device_tab, "Device")
        self._tabs.addTab(self._read_tab, "Read")
        self._tabs.addTab(self._write_tab, "Write")
        self._tabs.addTab(self._erase_tab, "Erase")
        self._tabs.addTab(self._keys_tab, "Keys")
        self._tabs.addTab(self._bootloader_tab, "Bootloader")
        self._tabs.addTab(self._memory_tab, "Memory")
        self._tabs.addTab(self._rpmb_tab, "RPMB")
        self._tabs.addTab(self._imei_tab, "IMEI")
        self._tabs.addTab(self._exploit_tab, "Exploit")
        self._tabs.addTab(self._efuse_tab, "eFuse")
        self._tabs.addTab(self._server_tab, "Server")

        top = QWidget()
        top_layout = QVBoxLayout(top)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(4)

        self._connection_notice = DismissableBanner(
            "Connect a device and initialize a compatible Download Agent "
            "before using device-operation tabs.",
            banner_type="warning",
            dismissable=False,
            action_text="Open Device tab",
        )
        self._connection_notice.setVisible(False)
        top_layout.addWidget(self._connection_notice)
        top_layout.addWidget(self._tabs, 1)

        splitter.addWidget(top)

        # Bottom panel: progress + log
        bottom = QWidget()
        bottom_layout = QVBoxLayout(bottom)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.setSpacing(2)

        self._progress_panel = ProgressPanel()
        bottom_layout.addWidget(self._progress_panel)

        self._log_panel = LogPanel()
        bottom_layout.addWidget(self._log_panel)

        splitter.addWidget(bottom)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)

        self.setCentralWidget(splitter)

        # Status bar
        self.statusBar().showMessage("Ready")

    def _setup_menus(self):
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("File")
        file_menu.addAction("Exit", self.close)

        # View menu
        view_menu = menubar.addMenu("View")
        self._theme_action = view_menu.addAction("Toggle Theme", self._toggle_theme)

        # Plugins menu (populated by plugins)
        self._plugins_menu = menubar.addMenu("Plugins")
        self._plugins_menu.addAction("Reload Plugins", self._reload_plugins)
        self._plugins_menu.addSeparator()

        # Help menu
        help_menu = menubar.addMenu("Help")
        help_menu.addAction("mtkclient Documentation", lambda: QDesktopServices.openUrl(
            QUrl("https://github.com/bkerler/mtkclient/blob/main/README.md")))
        help_menu.addAction("MediaTek Exploit Guide", lambda: QDesktopServices.openUrl(
            QUrl("https://github.com/bkerler/mtkclient/wiki")))
        help_menu.addAction("XDA Forums - MTK", lambda: QDesktopServices.openUrl(
            QUrl("https://xdaforums.com/f/mediatek.4292/")))
        help_menu.addSeparator()
        help_menu.addAction("About", self._show_about)

    def _connect_signals(self):
        dm = self.device_manager

        # Connection state
        dm.state_changed.connect(self._on_state_changed)
        dm.device_info_updated.connect(self._on_device_info_updated)

        # Logging
        dm.log_message.connect(self._log_panel.append_log)
        dm.progress_update.connect(self._progress_panel.update_progress)
        dm.status_update.connect(self._progress_panel.set_status)
        dm.status_update.connect(self.statusBar().showMessage)
        dm.operation_activity_changed.connect(self._on_operation_activity_changed)

        # Device tab buttons
        self._device_tab.connect_button.clicked.connect(self._on_connect)
        self._device_tab.disconnect_button.clicked.connect(self._on_disconnect)
        self._connection_notice.action_requested.connect(
            lambda: self._tabs.setCurrentIndex(0))
        self._tabs.currentChanged.connect(self._update_connection_notice)

        # Read tab
        self._read_tab.read_button.clicked.connect(self._on_read)

        # Write tab
        self._write_tab.write_button.clicked.connect(self._on_write)

        # Erase tab
        self._erase_tab.erase_button.clicked.connect(self._on_erase)

        # Keys tab
        self._keys_tab.generate_button.clicked.connect(self._on_generate_keys)

        # Bootloader tab
        self._bootloader_tab.unlock_button.clicked.connect(
            lambda: self._on_seccfg(lock=False))
        self._bootloader_tab.lock_button.clicked.connect(
            lambda: self._on_seccfg(lock=True))
        self._bootloader_tab.vbmeta_button.clicked.connect(self._on_vbmeta)

        # Memory tab
        self._memory_tab.peek_button.clicked.connect(self._on_peek)
        self._memory_tab.peek_save_button.clicked.connect(self._on_peek_to_file)
        self._memory_tab.poke_button.clicked.connect(self._on_poke)
        self._memory_tab.brom_button.clicked.connect(self._on_dump_brom)

        # RPMB tab
        self._rpmb_tab.read_button.clicked.connect(self._on_rpmb_read)
        self._rpmb_tab.write_button.clicked.connect(self._on_rpmb_write)
        self._rpmb_tab.erase_button.clicked.connect(self._on_rpmb_erase)

        # IMEI tab
        self._imei_tab.read_button.clicked.connect(self._on_imei_read)
        self._imei_tab.write_button.clicked.connect(self._on_imei_write)
        self._imei_tab.patch_modem_button.clicked.connect(self._on_patch_modem)
        self._imei_tab.decrypt_button.clicked.connect(self._on_nvitem_decrypt)
        self._imei_tab.encrypt_button.clicked.connect(self._on_nvitem_encrypt)

        # Exploit tab
        self._exploit_tab.crash_button.clicked.connect(self._on_crash)
        self._exploit_tab.brute_button.clicked.connect(self._on_brute)
        self._exploit_tab.payload_button.clicked.connect(self._on_payload)
        self._exploit_tab.stage_button.clicked.connect(self._on_stage2)
        self._exploit_tab.meta_button.clicked.connect(self._on_meta_mode)
        self._exploit_tab.reset_button.clicked.connect(self._on_reset)
        self._exploit_tab.shutdown_button.clicked.connect(self._on_shutdown)

        # Server tab
        self._server_tab.start_button.clicked.connect(self._on_server_start)

        # eFuse tab
        self._efuse_tab.read_button.clicked.connect(self._on_read_efuses)

    # ── Connection handlers ───────────────────────────────

    def _on_connect(self):
        settings = self._device_tab.get_settings()
        dm = self.device_manager
        dm.preloader_path = settings["preloader"]
        dm.da_loader_path = settings["da_loader"]
        dm.serial_port = settings["serial_port"]
        dm.iot_mode = settings["iot"]
        dm.stock_da = settings["stock"]
        dm.work_dir = settings["work_dir"]
        self._progress_panel.start("Connecting...")
        dm.connect_device()

    def _on_disconnect(self):
        state = self.device_manager.state
        if state in (
            DeviceState.DETECTING,
            DeviceState.PRELOADER,
            DeviceState.HANDSHAKING,
            DeviceState.PRELOADER_CONNECTED,
            DeviceState.CONNECTING_DA,
            DeviceState.CANCELLING,
        ):
            self.device_manager.cancel_connection()
            self._progress_panel.set_status("Stopping connection attempt...")
        else:
            self.device_manager.disconnect_device()
            self._progress_panel.reset()

    def _on_state_changed(self, state: DeviceState):
        self._device_tab.update_connection_state(state)
        connected = state == DeviceState.CONNECTED

        # Enable/disable operation tabs
        self._set_operation_controls_enabled(connected and not self._operation_active)
        self._update_connection_notice()

        if state == DeviceState.PRELOADER:
            # Auto-connect when preloader is detected
            self._on_connect()
        elif state == DeviceState.CONNECTED:
            self._progress_panel.finish("Connected")
            self._load_partitions()
        elif state == DeviceState.DA_UNAVAILABLE:
            self._progress_panel.finish("Preloader connected; DA unavailable")
        elif state == DeviceState.DISCONNECTED:
            self._progress_panel.reset()
        elif state == DeviceState.ERROR:
            self._progress_panel.finish("Connection failed")

        # Notify plugins
        for plugin in self._plugins:
            try:
                if connected:
                    plugin.on_device_connected(self.device_manager.device_info.__dict__)
                elif state == DeviceState.DISCONNECTED:
                    plugin.on_device_disconnected()
            except Exception:
                pass

    def _on_device_info_updated(self, info):
        self._device_tab.update_device_info(info)

    def _on_operation_activity_changed(self, active: bool):
        """Prevent overlapping commands from sharing one DA connection."""
        self._operation_active = active
        enabled = self.device_manager.state == DeviceState.CONNECTED and not active
        self._set_operation_controls_enabled(enabled)

    def _set_operation_controls_enabled(self, enabled: bool):
        self._read_tab.read_button.setEnabled(enabled)
        self._write_tab.write_button.setEnabled(enabled)
        self._erase_tab.erase_button.setEnabled(enabled)
        self._keys_tab.generate_button.setEnabled(enabled)
        self._bootloader_tab.unlock_button.setEnabled(enabled)
        self._bootloader_tab.lock_button.setEnabled(enabled)
        self._bootloader_tab.vbmeta_button.setEnabled(enabled)
        self._memory_tab.set_enabled_all(enabled)
        self._rpmb_tab.set_enabled_all(enabled)
        self._imei_tab.set_enabled_all(enabled)
        self._exploit_tab.set_enabled_all(enabled)
        self._efuse_tab.read_button.setEnabled(enabled)
        self._server_tab.start_button.setEnabled(enabled)

    def _update_connection_notice(self, _index=None):
        """Explain disabled operation controls on every non-Device tab."""
        if self._tabs.currentIndex() == 0 or self.device_manager.state == DeviceState.CONNECTED:
            self._connection_notice.setVisible(False)
            return

        state = self.device_manager.state
        if state == DeviceState.DA_UNAVAILABLE:
            message = (
                "Preloader communication succeeded, but no working Download Agent "
                "is available. Storage operations remain disabled."
            )
        elif state in (
            DeviceState.DETECTING,
            DeviceState.PRELOADER,
            DeviceState.HANDSHAKING,
            DeviceState.PRELOADER_CONNECTED,
            DeviceState.CONNECTING_DA,
            DeviceState.CANCELLING,
        ):
            message = (
                "A connection attempt is in progress. Use Stop on the Device tab "
                "to cancel it. Operations unlock only after the Download Agent is online."
            )
        elif state == DeviceState.ERROR:
            message = (
                "The last connection attempt failed. Open the Device tab for the "
                "specific error and retry controls."
            )
        else:
            message = (
                "Connect a device and initialize a compatible Download Agent before "
                "using this operation."
            )

        self._connection_notice.set_message(message)
        self._connection_notice.setVisible(True)

    def _load_partitions(self):
        """Load partition list after connection (off main thread)."""
        wrapper = self.device_manager.wrapper
        if not wrapper:
            return
        self._run_op(
            "Load partitions",
            wrapper.get_partitions,
            on_result=self._on_partitions_loaded,
            on_error=lambda e: self._log_panel.append_log(
            f"Failed to load partitions: {e}", logging.WARNING),
        )

    def _on_partitions_loaded(self, partitions):
        if partitions:
            self._read_tab.partition_list.set_partitions(partitions)
            self._write_tab.set_partitions(partitions)
            self._erase_tab.partition_list.set_partitions(partitions)

    def _on_multi_read_done(self, results):
        if isinstance(results, dict):
            ok = sum(1 for v in results.values() if v)
            total = len(results)
            for name, success in results.items():
                self._log_panel.append_log(
                    f"Read {name}: {'OK' if success else 'FAILED'}",
                    logging.INFO if success else logging.ERROR)
            self._progress_panel.finish(f"Read {ok}/{total} partitions")
        else:
            self._on_op_done("Read partitions", results)

    # ── Operation handlers ────────────────────────────────

    def _on_read(self):
        wrapper = self.device_manager.wrapper
        if not wrapper:
            return
        try:
            params = self._read_tab.get_read_params()
        except ValueError as e:
            QMessageBox.warning(self, "Invalid Input", str(e))
            return

        self._progress_panel.start("Reading...")
        mode = params["mode"]

        if mode == 0:  # Partitions
            if not params.get("partitions"):
                QMessageBox.warning(self, "No Selection", "Select at least one partition.")
                self._progress_panel.reset()
                return
            directory = params["directory"]
            if not directory:
                QMessageBox.warning(self, "No Directory", "Select an output directory.")
                self._progress_panel.reset()
                return
            self._run_op(
                "Read",
                wrapper.read_selected_partitions,
                params["partitions"], directory,
                params["parttype"], params.get("dump_gpt", False),
                on_result=self._on_multi_read_done,
            )
        elif mode == 1:  # Full Flash
            self._run_op("Read flash", wrapper.read_flash, params["filename"], params["parttype"])
        elif mode == 2:  # By Offset
            self._run_op(
                "Read offset",
                wrapper.read_offset, params["offset"], params["length"],
                params["filename"], params["parttype"],
            )
        elif mode == 3:  # By Sector
            self._run_op(
                "Read sectors",
                wrapper.read_sectors, params["start"], params["sectors"],
                params["filename"], params["parttype"],
            )

    def _on_write(self):
        wrapper = self.device_manager.wrapper
        if not wrapper:
            return
        try:
            params = self._write_tab.get_write_params()
        except ValueError as e:
            QMessageBox.warning(self, "Invalid Input", str(e))
            return

        mode = params["mode"]
        if mode == 0:
            targets = ", ".join(params["partitions"])
            warning = (
                f"Overwrite {len(params['partitions'])} partition(s) in "
                f"{params['parttype']} storage: {targets}."
            )
        elif mode == 1:
            warning = (
                f"Overwrite the full {params['parttype']} storage using "
                f"{os.path.basename(params['filenames'][0])}."
            )
        elif mode == 2:
            end = params["offset"] + params["length"] - 1
            warning = (
                f"Overwrite {params['parttype']} storage from "
                f"0x{params['offset']:X} through 0x{end:X} using "
                f"{os.path.basename(params['filename'])}."
            )
        else:
            warning = (
                f"Write matching partition images from {params['directory']} "
                f"to {params['parttype']} storage."
            )

        if not ConfirmationDialog.confirm("Confirm Write", warning, self):
            return

        self._progress_panel.start("Writing...")

        if mode == 0:  # Partitions
            self._run_op(
                "Write",
                wrapper.write_partitions, params["parttype"],
                params["filenames"], params["partitions"],
            )
        elif mode == 1:  # Full Flash
            self._run_op(
                "Write flash",
                wrapper.write_flash, params["filenames"], params["parttype"],
            )
        elif mode == 2:  # By Offset
            self._run_op(
                "Write offset",
                wrapper.write_offset, params["offset"], params["length"],
                params["filename"], params["parttype"],
            )
        elif mode == 3:  # From Directory
            self._run_op(
                "Write dir",
                wrapper.write_from_directory, params["parttype"], params["directory"],
            )

    def _on_erase(self):
        wrapper = self.device_manager.wrapper
        if not wrapper:
            return
        try:
            params = self._erase_tab.get_erase_params()
        except ValueError as e:
            QMessageBox.warning(self, "Invalid Input", str(e))
            return

        if params["mode"] == 0:
            targets = ", ".join(params["partitions"])
            warning = (
                f"Permanently erase {len(params['partitions'])} partition(s) "
                f"from {params['parttype']} storage: {targets}."
            )
        else:
            end = params["sector"] + params["sectors"] - 1
            warning = (
                f"Permanently erase {params['parttype']} sectors "
                f"{params['sector']} through {end}."
            )

        if not ConfirmationDialog.confirm("Confirm Erase", warning, self):
            return

        self._progress_panel.start("Erasing...")

        if params["mode"] == 0:  # Partitions
            self._run_op(
                "Erase",
                wrapper.erase_partitions, params["partitions"], params["parttype"],
            )
        else:  # By Sector
            self._run_op(
                "Erase sectors",
                wrapper.erase_sectors, params["sector"], params["sectors"], params["parttype"],
            )

    def _on_generate_keys(self):
        wrapper = self.device_manager.wrapper
        if not wrapper:
            return
        directory = self._keys_tab.output_directory
        self._progress_panel.start("Generating keys...")
        self._run_op("Keys", wrapper.generate_keys, directory, on_result=self._on_keys_done)

    def _on_keys_done(self, result):
        self._progress_panel.finish("Keys generated")
        self._keys_tab.set_status("Keys saved to hwparam.json")
        # Try to read and display the keys
        directory = self._keys_tab.output_directory
        import json
        hwparam_path = os.path.join(directory, "hwparam.json")
        if os.path.exists(hwparam_path):
            try:
                with open(hwparam_path, "r") as f:
                    keys = json.load(f)
                self._keys_tab.set_keys(keys)
            except Exception:
                pass

    def _on_seccfg(self, lock: bool):
        wrapper = self.device_manager.wrapper
        if not wrapper:
            return
        action = "Lock" if lock else "Unlock"
        if not ConfirmationDialog.confirm(
                f"Confirm {action}",
                f"This will {action.lower()} the bootloader via seccfg.", self):
            return
        critical = self._bootloader_tab.critical_mode
        self._progress_panel.start(f"{action}ing bootloader...")
        self._run_op(
            action,
            wrapper.seccfg_unlock,
            lock,
            critical,
            on_result=lambda r: self._on_op_done(
            f"Bootloader {action.lower()}", r),
        )

    def _on_vbmeta(self):
        wrapper = self.device_manager.wrapper
        if not wrapper:
            return
        if not ConfirmationDialog.confirm(
                "Confirm vbmeta Patch",
                "This will patch vbmeta to disable verified boot.", self):
            return
        mode = self._bootloader_tab.vbmeta_mode
        self._progress_panel.start("Patching vbmeta...")
        self._run_op("vbmeta", wrapper.vbmeta_patch, mode)

    def _on_peek(self):
        wrapper = self.device_manager.wrapper
        if not wrapper:
            return
        try:
            params = self._memory_tab.get_peek_params()
        except ValueError as e:
            QMessageBox.warning(self, "Invalid Input", str(e))
            return
        self._progress_panel.start("Reading memory...")
        self._last_peek_addr = params["addr"]
        self._run_op(
            "Peek",
            wrapper.peek, params["addr"], params["length"], None, params["registers"],
            on_result=self._on_peek_done,
        )

    def _on_peek_to_file(self):
        wrapper = self.device_manager.wrapper
        if not wrapper:
            return
        try:
            params = self._memory_tab.get_peek_params()
        except ValueError as e:
            QMessageBox.warning(self, "Invalid Input", str(e))
            return
        filename = self._memory_tab.choose_peek_output_file()
        if not filename:
            return
        self._progress_panel.start("Reading memory to file...")
        self._run_op(
            "Memory read",
            wrapper.peek, params["addr"], params["length"],
            filename, params["registers"],
        )

    def _on_peek_done(self, data):
        self._progress_panel.finish("Memory read complete")
        if data and isinstance(data, (bytes, bytearray)):
            self._memory_tab.hex_viewer.set_data(data, self._last_peek_addr)

    def _on_poke(self):
        wrapper = self.device_manager.wrapper
        if not wrapper:
            return
        try:
            params = self._memory_tab.get_poke_params()
        except ValueError as e:
            QMessageBox.warning(self, "Invalid Input", str(e))
            return
        if not ConfirmationDialog.confirm(
                "Confirm Memory Write",
                f"Write to address 0x{params['addr']:X}?", self):
            return
        self._progress_panel.start("Writing memory...")
        self._run_op("Poke", wrapper.poke, params["addr"], params["data"])

    def _on_dump_brom(self):
        wrapper = self.device_manager.wrapper
        if not wrapper:
            return
        directory = self._memory_tab.dump_directory
        filename = os.path.join(directory, "brom.bin")
        self._progress_panel.start("Dumping BROM...")
        self._run_op("BROM dump", wrapper.dump_brom, filename)

    def _on_rpmb_read(self):
        wrapper = self.device_manager.wrapper
        if not wrapper:
            return
        params = self._rpmb_tab.get_read_params()
        self._progress_panel.start("Reading RPMB...")
        self._run_op(
            "RPMB read",
            wrapper.read_rpmb, params["filename"],
            params["sector"], params["sectors"],
        )

    def _on_rpmb_write(self):
        wrapper = self.device_manager.wrapper
        if not wrapper:
            return
        try:
            params = self._rpmb_tab.get_write_params()
        except ValueError as e:
            QMessageBox.warning(self, "Invalid Input", str(e))
            return
        if not ConfirmationDialog.confirm(
                "Confirm RPMB Write", "Write to RPMB?", self):
            return
        self._progress_panel.start("Writing RPMB...")
        self._run_op(
            "RPMB write",
            wrapper.write_rpmb, params["filename"],
            params["sector"], params["sectors"],
        )

    def _on_read_efuses(self):
        wrapper = self.device_manager.wrapper
        if not wrapper:
            return
        self._progress_panel.start("Reading eFuses...")
        self._run_op("eFuse read", wrapper.read_efuses, on_result=self._on_efuses_done)

    def _on_efuses_done(self, data):
        self._progress_panel.finish("eFuses read")
        if data and isinstance(data, list):
            self._efuse_tab.set_efuses(data)

    # ── IMEI handlers ────────────────────────────────────

    def _parse_imei_hex_params(self, params: dict):
        """Validate and parse seed/aeskey hex strings. Returns (seed, aeskey) or (None, None)."""
        for field in ("seed", "aeskey"):
            val = params[field]
            if val and (len(val) % 2 != 0 or not all(c in "0123456789abcdefABCDEF" for c in val)):
                QMessageBox.warning(self, "Invalid Hex",
                                    f"{field.title()} must be an even-length hex string.")
                return None, None
        seed = bytes.fromhex(params["seed"]) if params["seed"] else b""
        aeskey = bytes.fromhex(params["aeskey"]) if params["aeskey"] else b"\x00" * 32
        return seed, aeskey

    def _on_imei_read(self):
        wrapper = self.device_manager.wrapper
        if not wrapper:
            return
        params = self._imei_tab.get_imei_params()
        seed, aeskey = self._parse_imei_hex_params(params)
        if seed is None:
            return
        self._progress_panel.start("Reading IMEIs...")
        self._run_op(
            "IMEI read",
            wrapper.read_imei, seed, aeskey,
            on_result=self._on_imei_read_done,
        )

    def _on_imei_read_done(self, result):
        self._progress_panel.finish("IMEI read complete")
        if result and isinstance(result, list):
            imei1 = result[0][0] if len(result) > 0 else ""
            imei2 = result[1][0] if len(result) > 1 else ""
            self._imei_tab.set_imei_display(imei1, imei2)
            for imei, valid in result:
                state = "valid" if valid else "INVALID checksum"
                self._log_panel.append_log(f"IMEI: {imei} ({state})", logging.INFO)
        else:
            self._log_panel.append_log("No IMEIs found on device.", logging.WARNING)

    def _on_imei_write(self):
        wrapper = self.device_manager.wrapper
        if not wrapper:
            return
        params = self._imei_tab.get_imei_params()
        imeis = [i for i in [params["imei1"], params["imei2"]] if i]
        if not imeis:
            QMessageBox.warning(self, "No IMEI", "Enter at least one IMEI.")
            return
        for imei in imeis:
            if not imei.isdigit() or len(imei) != 15:
                QMessageBox.warning(self, "Invalid IMEI",
                                    f"IMEI must be exactly 15 digits: \"{imei}\"")
                return
        if not ConfirmationDialog.confirm(
                "Confirm IMEI Write",
                "This will overwrite IMEI data on the device.", self):
            return
        seed, aeskey = self._parse_imei_hex_params(params)
        if seed is None:
            return
        self._progress_panel.start("Writing IMEIs...")
        self._run_op("IMEI write", wrapper.write_imei, imeis, seed, aeskey, params["product"])

    def _on_patch_modem(self):
        wrapper = self.device_manager.wrapper
        if not wrapper:
            return
        if not ConfirmationDialog.confirm(
                "Confirm Modem Patch",
                "This will patch the modem partition.", self):
            return
        self._progress_panel.start("Patching modem...")
        self._run_op("Modem patch", wrapper.patch_modem)

    def _on_nvitem_decrypt(self):
        wrapper = self.device_manager.wrapper
        if not wrapper:
            return
        filename = self._imei_tab.nv_file
        if not filename:
            QMessageBox.warning(self, "No File", "Select an NV file first.")
            return
        self._progress_panel.start("Decrypting NVItem...")
        self._run_op(
            "NVItem decrypt",
            wrapper.nvitem_crypt, filename, False,
            on_result=lambda r: self._on_nvitem_done("Decrypt", r, filename),
        )

    def _on_nvitem_encrypt(self):
        wrapper = self.device_manager.wrapper
        if not wrapper:
            return
        filename = self._imei_tab.nv_file
        if not filename:
            QMessageBox.warning(self, "No File", "Select an NV file first.")
            return
        self._progress_panel.start("Encrypting NVItem...")
        self._run_op(
            "NVItem encrypt",
            wrapper.nvitem_crypt, filename, True,
            on_result=lambda r: self._on_nvitem_done("Encrypt", r, filename),
        )

    def _on_nvitem_done(self, op: str, result, filename: str):
        self._progress_panel.finish(f"NVItem {op.lower()} complete")
        if result:
            out_path = filename + f".{op.lower()}ed"
            with open(out_path, "wb") as f:
                f.write(result)
            self._log_panel.append_log(f"NVItem {op.lower()}ed → {out_path}", logging.INFO)
        else:
            self._log_panel.append_log(f"NVItem {op.lower()} failed.", logging.ERROR)

    # ── Exploit handlers ─────────────────────────────────

    def _on_crash(self):
        wrapper = self.device_manager.wrapper
        if not wrapper:
            return
        if not ConfirmationDialog.confirm(
                "Confirm Crash",
                "This will crash the preloader to enter BROM mode.", self):
            return
        crash_mode = self._exploit_tab.crash_mode
        self._progress_panel.start(f"Crashing preloader (mode {crash_mode})...")
        self._run_op("Crash", wrapper.crash_preloader, crash_mode)

    def _on_brute(self):
        wrapper = self.device_manager.wrapper
        if not wrapper:
            return
        if not ConfirmationDialog.confirm(
                "Confirm Brute Force",
                "This will iterate all crash modes to reach BROM.", self):
            return
        self._progress_panel.start("Brute forcing (iterating crash modes)...")
        self._run_op("Brute force", wrapper.crash_preloader) # mode=None → iterate all

    def _on_payload(self):
        wrapper = self.device_manager.wrapper
        if not wrapper:
            return
        filename = self._exploit_tab.payload_file
        if not filename:
            QMessageBox.warning(self, "No File", "Select a payload file.")
            return
        self._progress_panel.start("Running payload...")
        self._run_op("Payload", wrapper.run_payload, filename)

    def _on_stage2(self):
        wrapper = self.device_manager.wrapper
        if not wrapper:
            return
        filename = self._exploit_tab.stage_file
        if not filename:
            QMessageBox.warning(self, "No File", "Select a stage2 file.")
            return
        addr = self._exploit_tab.stage_addr
        self._progress_panel.start("Running stage2...")
        self._run_op("Stage2", wrapper.run_stage2, filename, addr)

    def _on_meta_mode(self):
        wrapper = self.device_manager.wrapper
        if not wrapper:
            return
        mode = self._exploit_tab.meta_mode
        self._progress_panel.start(f"Setting meta mode to {mode}...")
        self._run_op("Meta mode", wrapper.set_meta_mode, mode)

    def _on_reset(self):
        wrapper = self.device_manager.wrapper
        if not wrapper:
            return
        self._progress_panel.start("Resetting device...")
        self._run_op("Reset", wrapper.reset_device)

    def _on_shutdown(self):
        wrapper = self.device_manager.wrapper
        if not wrapper:
            return
        self._progress_panel.start("Shutting down device...")
        self._run_op("Shutdown", wrapper.shutdown)

    # ── RPMB erase handler ───────────────────────────────

    def _on_rpmb_erase(self):
        wrapper = self.device_manager.wrapper
        if not wrapper:
            return
        if not ConfirmationDialog.confirm(
                "Confirm RPMB Erase", "This will erase RPMB data.", self):
            return
        self._progress_panel.start("Erasing RPMB...")
        self._run_op("RPMB erase", wrapper.erase_rpmb)

    # ── Server handler ───────────────────────────────────

    def _on_server_start(self):
        wrapper = self.device_manager.wrapper
        if not wrapper:
            return
        self._progress_panel.start("Running key server...")
        self._server_tab.set_status(True, "Key exchange in progress...")
        self._run_op(
            "Key server",
            wrapper.keyserver,
            on_result=self._on_server_done,
            on_error=self._on_server_error,
        )

    def _on_server_done(self, result):
        success = bool(result)
        self._server_tab.set_status(False,
                                    "Complete" if success else "Failed")
        self._progress_panel.finish(
            "Key server complete" if success else "Key server failed")
        self._log_panel.append_log(
            "Key exchange complete." if success else "Key exchange failed.",
            logging.INFO if success else logging.ERROR)

    def _on_server_error(self, error: str):
        self._server_tab.set_status(False, "Error")
        self._on_op_error("Key server", error)

    # ── Button-disable helper ────────────────────────────

    def _run_op(self, name: str, func, *args, on_result=None, on_error=None,
                on_cancelled=None, **kwargs):
        """Start a backend operation with all three terminal signals handled.

        Replaces the former _start_op, which started the thread and then
        returned it for the caller to connect to -- a race that silently
        dropped the result of any fast-failing operation and left the progress
        panel running. run_operation() connects first and starts last.

        Every operation now also has a cancellation handler. Previously
        Worker.cancelled was connected nowhere in the UI, so a cancel left the
        progress panel spinning with no indication it had stopped.

        _start_op also took a `button` argument that it discarded; DeviceManager
        locks the DA controls for the duration, so the parameter was vestigial
        and is gone.
        """
        return run_operation(
            self.device_manager,
            func,
            *args,
            on_result=on_result or (lambda r: self._on_op_done(name, r)),
            on_error=on_error or (lambda e: self._on_op_error(name, e)),
            on_cancelled=on_cancelled or (lambda c: self._on_op_cancelled(name, c)),
            **kwargs,
        )

    # ── Operation result handlers ─────────────────────────

    def _on_op_done(self, name: str, result):
        success = bool(result)
        status = f"{name}: {'OK' if success else 'FAILED'}"
        self._progress_panel.finish(status)
        self._log_panel.append_log(status, logging.INFO if success else logging.ERROR)

    def _on_op_error(self, name: str, error: str):
        self._progress_panel.finish(f"{name}: ERROR")
        # The log keeps everything, including the traceback. The dialog shows
        # only the explanation -- a MtkOperationError already quotes the last
        # lines mtkclient printed, which is the part worth reading.
        self._log_panel.append_log(f"{name} error: {error}", logging.ERROR)
        summary = str(error).split("\nTraceback", 1)[0].strip() or str(error)
        QMessageBox.warning(self, f"{name} Error", summary)

    def _on_op_cancelled(self, name: str, info):
        """Close out a cancelled operation, including one that also failed.

        A cancellation that followed a failure carries the reason with it. On a
        tool that writes flash, "cancelled" alone would hide the fact that the
        device was left in an unknown state.
        """
        if info is not None and getattr(info, "failed", False):
            self._progress_panel.finish(f"{name}: CANCELLED AFTER FAILURE")
            self._log_panel.append_log(
                f"{name}: {info.message}", logging.ERROR)
            if info.traceback:
                self._log_panel.append_log(info.traceback, logging.DEBUG)
            QMessageBox.warning(self, f"{name} Stopped", str(info.message))
        else:
            self._progress_panel.finish(f"{name}: cancelled")
            self._log_panel.append_log(f"{name}: cancelled.", logging.INFO)

    # ── Theme ─────────────────────────────────────────────

    def _toggle_theme(self):
        if self._current_theme == THEME_DARK:
            self._current_theme = THEME_LIGHT
        else:
            self._current_theme = THEME_DARK
        self._apply_theme()
        self._settings.setValue("theme", self._current_theme)

    def apply_initial_theme(self):
        self._apply_theme()

    def _apply_theme(self):
        qss = load_stylesheet(self._current_theme)
        self.setStyleSheet(qss)

    # ── Plugin support ────────────────────────────────────

    def add_plugin_tab(self, widget, title: str):
        self._tabs.addTab(widget, title)

    def add_plugin_menu_item(self, menu_path: str, action):
        parts = menu_path.split("/")
        menu = self._plugins_menu
        for part in parts[:-1]:
            found = None
            for a in menu.actions():
                if a.menu() and a.text() == part:
                    found = a.menu()
                    break
            if found:
                menu = found
            else:
                menu = menu.addMenu(part)
        menu.addAction(parts[-1], action)

    def set_plugins(self, plugins: list):
        self._plugins = plugins

    def _reload_plugins(self):
        self._log_panel.append_log("Plugin reload requires restart.", logging.WARNING)

    # ── Window state ──────────────────────────────────────

    def _restore_geometry(self):
        geo = self._settings.value("geometry")
        if geo:
            self.restoreGeometry(geo)
        state = self._settings.value("windowState")
        if state:
            self.restoreState(state)

    def closeEvent(self, event):
        self._settings.setValue("geometry", self.saveGeometry())
        self._settings.setValue("windowState", self.saveState())
        self.device_manager.begin_shutdown()
        self.device_manager.stop_polling()
        self.device_manager.disconnect_device()
        for plugin in self._plugins:
            try:
                plugin.cleanup()
            except Exception:
                pass
        super().closeEvent(event)

    def _show_about(self):
        QMessageBox.about(self, "About MTK-GUI",
            "MTK-GUI v0.1.0\n\n"
            "Standalone GUI for mtkclient by bkerler.\n"
            "Built with PySide6.\n\n"
            "This tool provides a graphical interface for MediaTek\n"
            "device operations: flash read/write, bootloader unlock,\n"
            "key extraction, IMEI management, and more.\n\n"
            "Requires mtkclient to be installed.\n"
            "License: GPLv3")
