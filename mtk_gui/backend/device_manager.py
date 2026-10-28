"""Connection state machine and USB polling."""
import logging
import threading
from dataclasses import dataclass
from enum import Enum, auto

from PySide6.QtCore import QObject, Signal

from mtk_gui.backend.diagnostics import LOGGER_NAME as DIAG_LOGGER_NAME
from mtk_gui.backend.log_interceptor import (
    GuiSignalProxy,
    LogSignalEmitter,
    LogSignalHandler,
)
from mtk_gui.backend.mtk_wrapper import DeviceInfo, MtkWrapper
from mtk_gui.backend.port_detection import find_mtk_serial_port
from mtk_gui.backend.stdio_bridge import attach_streams, detach_streams
from mtk_gui.backend.worker import Worker
from mtk_gui.constants import USB_POLL_INTERVAL_MS


class DeviceState(Enum):
    DISCONNECTED = auto()
    DETECTING = auto()
    PRELOADER = auto()
    HANDSHAKING = auto()
    PRELOADER_CONNECTED = auto()
    CONNECTING_DA = auto()
    CONNECTED = auto()
    DA_UNAVAILABLE = auto()
    CANCELLING = auto()
    ERROR = auto()


@dataclass(frozen=True)
class ConnectionOutcome:
    preloader_connected: bool = False
    da_connected: bool = False


class DeviceManager(QObject):
    """Manages device connection lifecycle."""

    state_changed = Signal(object)            # DeviceState
    device_info_updated = Signal(object)      # DeviceInfo
    log_message = Signal(str, int)            # message, level
    progress_update = Signal(int, int)        # current, total
    status_update = Signal(str)
    operation_activity_changed = Signal(bool)
    _usb_detected = Signal(int, str)         # PID, VCOM port (internal, thread→main)
    _connection_stage = Signal(object)       # DeviceState (worker→main)
    _preloader_info = Signal(object)         # DeviceInfo (worker→main)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._state = DeviceState.DISCONNECTED
        self._wrapper: MtkWrapper | None = None
        self._device_info = DeviceInfo()
        self._workers: list[Worker] = []
        self._operation_workers: list[Worker] = []
        self._connect_worker: Worker | None = None
        self._shutting_down = False

        # Log signal bridge
        self._log_emitter = LogSignalEmitter()
        self._log_emitter.log_received.connect(self.log_message)
        self._log_emitter.progress_received.connect(self.progress_update)
        self._log_emitter.status_received.connect(self.status_update)
        attach_streams(self.log_message.emit)

        # Route this application's own loggers into the GUI panel. mtkclient's
        # output arrives separately through the stdout tee (it binds its own
        # StreamHandler to sys.stdout at import time), so this handler is
        # attached only to the "mtk_gui" tree to avoid logging every line twice.
        # Without it, failures such as a plugin that will not load are written
        # to a logger nobody is watching.
        self._gui_log_handler = LogSignalHandler(self._log_emitter)
        self._gui_log_handler.setFormatter(logging.Formatter("%(name)s: %(message)s"))
        logging.getLogger(DIAG_LOGGER_NAME).addHandler(self._gui_log_handler)

        # USB poll thread
        self._poll_stop = threading.Event()
        self._poll_thread: threading.Thread | None = None
        self._usb_detected.connect(self._on_usb_detected)
        self._connection_stage.connect(self._set_state)
        self._preloader_info.connect(self._on_preloader_info)
        self._detected_serial_port: str | None = None

        # Connection settings
        self.preloader_path: str | None = None
        self.da_loader_path: str | None = None
        self.serial_port: str | None = None
        self.iot_mode: bool = False
        self.stock_da: bool = False
        self.work_dir: str = "."

    @property
    def state(self) -> DeviceState:
        return self._state

    @property
    def device_info(self) -> DeviceInfo:
        return self._device_info

    @property
    def wrapper(self) -> MtkWrapper | None:
        return self._wrapper

    def _set_state(self, new_state: DeviceState):
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
        """Stop USB device polling and wait for thread to exit."""
        self._poll_stop.set()
        if self._poll_thread and self._poll_thread.is_alive():
            self._poll_thread.join(timeout=2.0)
        self._poll_thread = None

    def _poll_usb_loop(self):
        """Background thread: poll USB until device found or stopped."""
        from mtk_gui.constants import MTK_PRELOADER_PIDS, MTK_USB_VID

        try:
            import usb.core
        except ImportError as err:
            usb = None
            self.log_message.emit(
                f"PyUSB is unavailable ({err}); detection will use serial ports "
                f"only. Install pyusb for USB-level device detection.",
                logging.WARNING,
            )

        last_error = None
        interval = USB_POLL_INTERVAL_MS / 1000.0
        while not self._poll_stop.is_set():
            if self._state not in (DeviceState.DISCONNECTED, DeviceState.DETECTING):
                self._poll_stop.wait(interval)
                continue
            try:
                serial_port = find_mtk_serial_port()
                if serial_port is not None:
                    self._usb_detected.emit(
                        serial_port.pid or 0, serial_port.device)
                    return

                dev = (usb.core.find(idVendor=MTK_USB_VID)
                       if usb is not None else None)
                if dev is not None:
                    pid = dev.idProduct
                    if pid in MTK_PRELOADER_PIDS:
                        self._usb_detected.emit(pid, "")
                        return
            except Exception as err:
                # Enumeration failures here are the most common real-world
                # problem on Linux (missing udev rule, wrong group, device
                # claimed by another process). Logging at DEBUG hid them behind
                # an endless "Detecting..." with no explanation. Surface the
                # first occurrence and each change, but do not repeat an
                # identical message every poll interval.
                message = f"Device detection failed: {err}"
                if message != last_error:
                    last_error = message
                    self.log_message.emit(
                        f"{message} (retrying every "
                        f"{USB_POLL_INTERVAL_MS / 1000.0:g}s; on Linux check "
                        f"udev rules and group membership for USB access)",
                        logging.WARNING,
                    )
            else:
                last_error = None
            self._poll_stop.wait(interval)

    def _on_usb_detected(self, pid: int, serial_port: str):
        """Handle USB detection on the main thread (via signal)."""
        if self._shutting_down:
            return
        from mtk_gui.constants import MTK_USB_VID
        self._detected_serial_port = serial_port or None
        self._set_state(DeviceState.PRELOADER)
        transport = f"; VCOM={serial_port}" if serial_port else ""
        self.log_message.emit(
            f"MTK device detected: VID={MTK_USB_VID:#06x} "
            f"PID={pid:#06x}{transport}",
            logging.INFO,
        )

    def connect_device(self):
        """Initiate connection to detected device."""
        if self._state in (
            DeviceState.DETECTING,
            DeviceState.HANDSHAKING,
            DeviceState.CONNECTING_DA,
            DeviceState.CANCELLING,
            DeviceState.CONNECTED,
        ):
            return

        # An explicitly selected COM port is already a concrete target. In
        # automatic mode, wait until the short-lived MTK USB/VCOM node exists
        # instead of asking mtkclient to fail an empty enumeration immediately.
        if self.serial_port is None and self._state != DeviceState.PRELOADER:
            self._set_state(DeviceState.DETECTING)
            self.start_polling()
            return

        self.stop_polling()
        self._set_state(DeviceState.HANDSHAKING)

        # Create signal proxy for mtkclient
        proxy = GuiSignalProxy(self._log_emitter)

        self._wrapper = MtkWrapper(
            gui_signal=proxy,
            gui_progress=proxy.progress_callback,
            status_signal=proxy.update_status_text,
        )

        worker = Worker(self._do_connect)
        worker.result_ready.connect(self._on_connect_finished)
        worker.error.connect(self._on_connect_error)
        worker.cancelled.connect(self._on_connect_cancelled)
        self._connect_worker = worker
        self._track_worker(worker)
        worker.start()

    def _do_connect(self, worker=None):
        """Run the Preloader and DA connection stages in a worker thread."""
        self._wrapper.init(
            preloader=self.preloader_path,
            loader=self.da_loader_path,
            serial_port=self.serial_port,
            iot=self.iot_mode,
            stock=self.stock_da,
            work_dir=self.work_dir,
        )
        if self._wrapper.transport_backend:
            self.log_message.emit(
                f"USB backend: {self._wrapper.transport_backend}",
                logging.INFO,
            )
        self._connection_stage.emit(DeviceState.HANDSHAKING)
        preloader_connected = self._wrapper.connect_preloader(self.work_dir)
        if not preloader_connected:
            return ConnectionOutcome()

        info = self._wrapper.get_device_info()
        self._preloader_info.emit(info)
        self._connection_stage.emit(DeviceState.PRELOADER_CONNECTED)
        if worker is not None and worker.is_cancelled:
            return ConnectionOutcome(preloader_connected=True)

        self._connection_stage.emit(DeviceState.CONNECTING_DA)
        da_connected = self._wrapper.configure_da()
        return ConnectionOutcome(
            preloader_connected=True,
            da_connected=da_connected,
        )

    def _on_connect_finished(self, outcome: ConnectionOutcome):
        self._connect_worker = None
        if outcome.da_connected:
            self._device_info = self._wrapper.get_device_info()
            self._set_state(DeviceState.CONNECTED)
            self.device_info_updated.emit(self._device_info)
            self.log_message.emit("Device connected successfully.", logging.INFO)
        elif outcome.preloader_connected:
            self._set_state(DeviceState.DA_UNAVAILABLE)
            hwcode = self._device_info.hwcode or "unknown hardware"
            self.log_message.emit(
                f"Preloader handshake complete ({hwcode}), but no working "
                "Download Agent is available. Storage operations are disabled.",
                logging.ERROR,
            )
        else:
            if self._wrapper:
                self._wrapper.disconnect()
                self._wrapper = None
            self._set_state(DeviceState.ERROR)
            self.log_message.emit(
                "Preloader handshake failed. Stop, reconnect the phone, and retry.",
                logging.ERROR,
            )
            self._log_vcom_fallback()

    def _on_connect_error(self, msg: str):
        self._connect_worker = None
        if self._wrapper:
            self._wrapper.disconnect()
            self._wrapper = None
        self._set_state(DeviceState.ERROR)
        summary = msg.splitlines()[0] if msg else "Unknown connection error"
        self.log_message.emit(f"Connection error: {summary}", logging.ERROR)
        self._log_vcom_fallback()

    def _on_connect_cancelled(self):
        self._connect_worker = None
        if self._wrapper:
            self._wrapper.disconnect()
            self._wrapper = None
        self._device_info = DeviceInfo()
        self.device_info_updated.emit(self._device_info)
        self._set_state(DeviceState.DISCONNECTED)
        self.log_message.emit("Connection attempt stopped.", logging.INFO)

    def _on_preloader_info(self, info: DeviceInfo):
        self._device_info = info
        self.device_info_updated.emit(info)

    def cancel_connection(self):
        """Stop a pending detection, handshake, or DA initialization."""
        if self._state == DeviceState.DETECTING:
            self.stop_polling()
            self._set_state(DeviceState.DISCONNECTED)
            self.log_message.emit("Device detection stopped.", logging.INFO)
            return

        if self._state not in (
            DeviceState.PRELOADER,
            DeviceState.HANDSHAKING,
            DeviceState.PRELOADER_CONNECTED,
            DeviceState.CONNECTING_DA,
        ):
            return

        self._set_state(DeviceState.CANCELLING)
        self.log_message.emit("Stopping connection attempt...", logging.INFO)
        if self._connect_worker:
            self._connect_worker.cancel()
        if self._wrapper:
            self._wrapper.request_cancel()

    def _log_vcom_fallback(self):
        """Advertise the real alternate transport when Windows exposed one."""
        if self.serial_port is None and self._detected_serial_port:
            self.log_message.emit(
                f"MediaTek VCOM is available on {self._detected_serial_port}. "
                "Select that Serial Port and retry if direct USB cannot open "
                "the device.",
                logging.WARNING,
            )

    def disconnect_device(self):
        """Disconnect from device."""
        if self._state in (
            DeviceState.DETECTING,
            DeviceState.PRELOADER,
            DeviceState.HANDSHAKING,
            DeviceState.PRELOADER_CONNECTED,
            DeviceState.CONNECTING_DA,
            DeviceState.CANCELLING,
        ):
            self.cancel_connection()
            return

        self._cancel_all_workers()
        if self._wrapper:
            self._wrapper.disconnect()
            self._wrapper = None
        self._device_info = DeviceInfo()
        self._detected_serial_port = None
        self._set_state(DeviceState.DISCONNECTED)
        self.device_info_updated.emit(self._device_info)
        self.log_message.emit("Device disconnected.", logging.INFO)

    def begin_shutdown(self):
        """Called during app close — prevents post-shutdown side effects."""
        self._shutting_down = True
        detach_streams()
        if self._gui_log_handler is not None:
            logging.getLogger(DIAG_LOGGER_NAME).removeHandler(self._gui_log_handler)
            self._gui_log_handler = None

    def create_worker(self, func, *args, **kwargs) -> Worker:
        """Create and track a worker for a backend operation."""
        w = Worker(func, *args, **kwargs)
        was_idle = not self._operation_workers
        self._operation_workers.append(w)
        w.result_ready.connect(lambda _: self._untrack_operation_worker(w))
        w.error.connect(lambda _: self._untrack_operation_worker(w))
        w.cancelled.connect(lambda: self._untrack_operation_worker(w))
        self._track_worker(w)
        if was_idle:
            self.operation_activity_changed.emit(True)
        return w

    def _untrack_operation_worker(self, worker: Worker):
        if worker in self._operation_workers:
            self._operation_workers.remove(worker)
            if not self._operation_workers:
                self.operation_activity_changed.emit(False)

    def _track_worker(self, worker: Worker):
        self._workers.append(worker)
        worker.result_ready.connect(lambda _: self._untrack_worker(worker))
        worker.error.connect(lambda _: self._untrack_worker(worker))
        worker.cancelled.connect(lambda: self._untrack_worker(worker))

    def _untrack_worker(self, worker: Worker):
        if worker in self._workers:
            self._workers.remove(worker)

    def _cancel_all_workers(self):
        if self._wrapper:
            self._wrapper.request_cancel()
        for w in list(self._workers):
            w.cancel()
        # Wait briefly for workers to finish
        for w in list(self._workers):
            w.wait(2000)
        self._workers.clear()
        if self._operation_workers:
            self._operation_workers.clear()
            self.operation_activity_changed.emit(False)
