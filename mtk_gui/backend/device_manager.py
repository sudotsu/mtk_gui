"""Connection state machine and USB polling."""
import logging
import threading
import time
from enum import Enum, auto
from typing import Optional

from PySide6.QtCore import QObject, QTimer, Signal

from mtk_gui.backend.log_interceptor import LogSignalEmitter, GuiSignalProxy
from mtk_gui.backend.mtk_wrapper import MtkWrapper, DeviceInfo
from mtk_gui.backend.worker import Worker
from mtk_gui.constants import USB_POLL_INTERVAL_MS


class DeviceState(Enum):
    DISCONNECTED = auto()
    DETECTING = auto()
    PRELOADER = auto()
    CONNECTING_DA = auto()
    CONNECTED = auto()
    ERROR = auto()


class DeviceManager(QObject):
    """Manages device connection lifecycle."""

    state_changed = Signal(object)            # DeviceState
    device_info_updated = Signal(object)      # DeviceInfo
    log_message = Signal(str, int)            # message, level
    progress_update = Signal(int, int)        # current, total
    status_update = Signal(str)
    _usb_detected = Signal(int)              # PID (internal, thread→main)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._state = DeviceState.DISCONNECTED
        self._wrapper: Optional[MtkWrapper] = None
        self._device_info = DeviceInfo()
        self._workers: list[Worker] = []

        # Log signal bridge
        self._log_emitter = LogSignalEmitter()
        self._log_emitter.log_received.connect(self.log_message)
        self._log_emitter.progress_received.connect(self.progress_update)
        self._log_emitter.status_received.connect(self.status_update)

        # USB poll thread
        self._poll_stop = threading.Event()
        self._poll_thread: Optional[threading.Thread] = None
        self._usb_detected.connect(self._on_usb_detected)

        # Connection settings
        self.preloader_path: Optional[str] = None
        self.da_loader_path: Optional[str] = None
        self.serial_port: Optional[str] = None
        self.iot_mode: bool = False
        self.stock_da: bool = False
        self.work_dir: str = "."

    @property
    def state(self) -> DeviceState:
        """
        Get the device manager's current connection state.
        
        Returns:
            DeviceState: The current device connection state.
        """
        return self._state

    @property
    def device_info(self) -> DeviceInfo:
        """Return information about the currently connected device."""
        return self._device_info

    @property
    def wrapper(self) -> Optional[MtkWrapper]:
        """
        Provide the current MediaTek device wrapper.
        
        Returns:
        	MtkWrapper or None: The active wrapper, or None if no wrapper is configured.
        """
        return self._wrapper

    def _set_state(self, new_state: DeviceState):
        """Update the manager's state and emit a change notification when it changes.
        
        Parameters:
        	new_state (DeviceState): The state to assign to the manager.
        """
        if new_state != self._state:
            self._state = new_state
            self.state_changed.emit(new_state)

    def start_polling(self):
        """Start USB device polling in a background thread."""
        if self._poll_thread and self._poll_thread.is_alive():
            return
        self._poll_stop.clear()
        self._poll_thread = threading.Thread(
            target=self._poll_usb_loop, daemon=True)
        self._poll_thread.start()

    def stop_polling(self):
        """Stop USB device polling."""
        self._poll_stop.set()

    def _poll_usb_loop(self):
        """
        Poll for a configured MediaTek USB preloader device until one is detected or polling is stopped.
        """
        try:
            import usb.core
            from mtk_gui.constants import MTK_USB_VID, MTK_PRELOADER_PIDS
        except ImportError:
            self.log_message.emit(
                "pyusb not available — use manual connect", logging.WARNING)
            return

        interval = USB_POLL_INTERVAL_MS / 1000.0
        while not self._poll_stop.is_set():
            if self._state not in (DeviceState.DISCONNECTED, DeviceState.DETECTING):
                self._poll_stop.wait(interval)
                continue
            try:
                dev = usb.core.find(idVendor=MTK_USB_VID)
                if dev is not None:
                    pid = dev.idProduct
                    if pid in MTK_PRELOADER_PIDS:
                        self._usb_detected.emit(pid)
                        return
            except Exception:
                pass
            self._poll_stop.wait(interval)

    def _on_usb_detected(self, pid: int):
        """Update the device state and log the detected MediaTek USB device.
        
        Parameters:
        	pid (int): Product ID of the detected USB device.
        """
        from mtk_gui.constants import MTK_USB_VID
        self._set_state(DeviceState.PRELOADER)
        self.log_message.emit(
            f"MTK device detected: VID={MTK_USB_VID:#06x} PID={pid:#06x}",
            logging.INFO,
        )

    def connect_device(self):
        """Initiate connection to detected device."""
        if self._state == DeviceState.CONNECTED:
            return

        self._set_state(DeviceState.CONNECTING_DA)

        # Create signal proxy for mtkclient
        proxy = GuiSignalProxy(self._log_emitter)

        self._wrapper = MtkWrapper(
            gui_signal=proxy,
            gui_progress=proxy.progress_callback,
            status_signal=proxy.update_status_text,
        )

        worker = Worker(self._do_connect)
        worker.finished.connect(self._on_connect_finished)
        worker.error.connect(self._on_connect_error)
        self._track_worker(worker)
        worker.start()

    def _do_connect(self, worker=None):
        """
        Initialize the device wrapper and attempt to connect to the device.
        
        Returns:
        	bool: `True` if the connection succeeds, `False` otherwise.
        """
        self._wrapper.init(
            preloader=self.preloader_path,
            loader=self.da_loader_path,
            serial_port=self.serial_port,
            iot=self.iot_mode,
            stock=self.stock_da,
            work_dir=self.work_dir,
        )
        success = self._wrapper.connect(self.work_dir)
        return success

    def _on_connect_finished(self, success):
        """Update the device state and emit connection results after a connection attempt completes.
        
        Parameters:
        	success (bool): Whether the device connection succeeded.
        """
        if success:
            self._device_info = self._wrapper.get_device_info()
            self._set_state(DeviceState.CONNECTED)
            self.device_info_updated.emit(self._device_info)
            self.log_message.emit("Device connected successfully.", logging.INFO)
        else:
            self._set_state(DeviceState.ERROR)
            self.log_message.emit("Connection failed.", logging.ERROR)

    def _on_connect_error(self, msg: str):
        """Set the device state to error and emit the connection error message.
        
        Parameters:
        	msg (str): Description of the connection error.
        """
        self._set_state(DeviceState.ERROR)
        self.log_message.emit(f"Connection error: {msg}", logging.ERROR)

    def disconnect_device(self):
        """Disconnect from device."""
        self._cancel_all_workers()
        if self._wrapper:
            self._wrapper.disconnect()
            self._wrapper = None
        self._device_info = DeviceInfo()
        self._set_state(DeviceState.DISCONNECTED)
        self.device_info_updated.emit(self._device_info)
        self.log_message.emit("Device disconnected.", logging.INFO)
        # Resume polling for next device
        self.start_polling()

    def create_worker(self, func, *args, **kwargs) -> Worker:
        """Create and track a worker for a backend operation."""
        w = Worker(func, *args, **kwargs)
        self._track_worker(w)
        return w

    def _track_worker(self, worker: Worker):
        """Track a worker and remove it from the active worker list when it finishes or reports an error."""
        self._workers.append(worker)
        worker.finished.connect(lambda _: self._untrack_worker(worker))
        worker.error.connect(lambda _: self._untrack_worker(worker))

    def _untrack_worker(self, worker: Worker):
        """Remove a worker from the active worker list."""
        if worker in self._workers:
            self._workers.remove(worker)

    def _cancel_all_workers(self):
        """Cancel all active workers and clear the worker registry."""
        for w in list(self._workers):
            w.cancel()
        self._workers.clear()
