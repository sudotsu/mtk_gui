"""Clean facade over mtkclient API. No Qt dependency."""
import logging
import math
import os
import threading
import time
from dataclasses import dataclass, field
from typing import Optional

from mtkclient.Library.DA.mtk_da_handler import DaHandler
from mtkclient.Library.mtk_class import Mtk
from mtkclient.config.mtk_config import MtkConfig
from mtkclient.Library.DA.mtk_daloader import DAloader

from mtk_gui.backend.windows_usb import select_mtk_usb_backend
from mtk_gui.constants import CONNECTION_TIMEOUT_SECONDS


class ConnectionCancelled(RuntimeError):
    """Raised when the user stops an in-progress connection attempt."""


class ConnectionBusyError(RuntimeError):
    """Raised when another process already owns the selected serial port."""


class ConnectionTimeoutError(RuntimeError):
    """Raised when a detected device does not complete its handshake in time."""


@dataclass
class DeviceInfo:
    chipset: str = ""
    hwcode: str = ""
    hwver: str = ""
    swver: str = ""
    boot_mode: str = ""
    flash_type: str = ""
    flash_size: str = ""
    meid: str = ""
    socid: str = ""
    da_mode: str = ""
    is_brom: bool = False
    target_config: Optional[dict] = None
    extra: dict = field(default_factory=dict)


@dataclass
class PartitionInfo:
    name: str
    sector: int
    sectors: int
    size: int
    fs_type: str = ""


class MtkWrapper:
    """Wraps mtkclient init/connect and all DA operations.

    All methods catch SystemExit (which mtkclient raises via sys.exit)
    and convert it to a controlled failure. Connection guards are installed on
    this wrapper's mtkclient instance only; package-global behavior is untouched.
    """

    def __init__(self, gui_signal=None, gui_progress=None, status_signal=None):
        self.mtk: Optional[Mtk] = None
        self.da_handler: Optional[DaHandler] = None
        self.config: Optional[MtkConfig] = None
        self._gui_signal = gui_signal
        self._gui_progress = gui_progress
        self._status_signal = status_signal
        self.transport_backend: Optional[str] = None
        self._cancel_event = threading.Event()
        self._connect_deadline: Optional[float] = None

    def init(self, preloader: str = None, loader: str = None,
             serial_port: str = None, iot: bool = False,
             stock: bool = False, work_dir: str = ".") -> Mtk:
        """Initialize MtkConfig and Mtk instance."""
        loglevel = logging.INFO
        self.config = MtkConfig(
            loglevel=loglevel,
            gui=self._gui_signal,
            guiprogress=self._gui_progress,
            update_status_text=self._status_signal,
        )
        self.config.loader = loader
        self.config.iot = iot
        self.config.stock = stock
        self.config.hwparam_path = work_dir

        if preloader and os.path.exists(preloader):
            self.config.preloader_filename = preloader
            with open(preloader, "rb") as f:
                self.config.preloader = f.read()

        self.mtk = Mtk(config=self.config, loglevel=loglevel, serialportname=serial_port)
        self.transport_backend = select_mtk_usb_backend(self.mtk)
        self._install_connection_guards()
        return self.mtk

    def connect_preloader(self, work_dir: str = ".") -> bool:
        """Complete the Preloader handshake without requiring a working DA."""
        if self.mtk is None:
            return False
        self._connect_deadline = time.monotonic() + CONNECTION_TIMEOUT_SECONDS
        try:
            self.da_handler = DaHandler(self.mtk, logging.INFO)
            mtk = self.da_handler.connect(self.mtk, work_dir)
            if mtk is None:
                return False
            self.mtk = mtk
            return True
        except SystemExit:
            return False

    def configure_da(self) -> bool:
        """Select, upload, and initialize the Download Agent."""
        if self.mtk is None or self.da_handler is None:
            return False
        self._raise_if_cancelled_or_timed_out(check_timeout=False)
        try:
            mtk = self.da_handler.configure_da(self.mtk)
            if mtk is None:
                return False
            self.mtk = mtk
            return True
        except SystemExit:
            return False

    def connect(self, work_dir: str = ".") -> bool:
        """Connect through Preloader and then initialize a DA."""
        return self.connect_preloader(work_dir) and self.configure_da()

    def request_cancel(self):
        """Interrupt a pending connection and release its device handle."""
        self._cancel_event.set()
        self._close_port()

    def disconnect(self):
        """Clean up connection state."""
        self.request_cancel()
        self.da_handler = None
        self.mtk = None
        self.config = None

    def _close_port(self):
        if self.mtk is None:
            return
        try:
            self.mtk.port.close()
        except Exception:
            pass

    def _raise_if_cancelled_or_timed_out(self, check_timeout: bool = True):
        if self._cancel_event.is_set():
            raise ConnectionCancelled("Connection attempt stopped by user.")
        if (
            check_timeout
            and self._connect_deadline is not None
            and time.monotonic() >= self._connect_deadline
        ):
            raise ConnectionTimeoutError(
                f"The Preloader handshake did not complete within "
                f"{CONNECTION_TIMEOUT_SECONDS} seconds."
            )

    @staticmethod
    def _is_port_busy_error(error: Exception) -> bool:
        message = str(error).lower()
        return (
            getattr(error, "winerror", None) == 170
            or "resource is in use" in message
            or "winerror 170" in message
        )

    def _install_connection_guards(self):
        """Bound mtkclient's retry loops and make them cooperatively stoppable."""
        if self.mtk is None:
            return

        port = self.mtk.port
        guarded_io = {}
        for name in (
            "usbread",
            "usbwrite",
            "usbreadwrite",
            "echo",
            "rbyte",
            "rword",
            "rdword",
        ):
            original = getattr(port, name, None)
            if original is None:
                continue

            def make_guarded_io(io_func):
                def call(*args, **kwargs):
                    self._raise_if_cancelled_or_timed_out(check_timeout=False)
                    result = io_func(*args, **kwargs)
                    self._raise_if_cancelled_or_timed_out(check_timeout=False)
                    return result

                return call

            guarded_io[name] = make_guarded_io(original)
            setattr(port, name, guarded_io[name])

        # mtkclient copies these callables into the Preloader, DAloader, and
        # DAconfig during construction. Replacing Port.usbread alone therefore
        # does not affect the XML DA loop that waits for CMD:START. Rebind all
        # already-created consumers so closing the port makes the very next I/O
        # boundary raise ConnectionCancelled instead of spinning on b"".
        cached_consumers = [
            getattr(self.mtk, "preloader", None),
            getattr(self.mtk, "daloader", None),
            getattr(getattr(self.mtk, "daloader", None), "daconfig", None),
        ]
        for consumer in cached_consumers:
            if consumer is None:
                continue
            for name, guarded in guarded_io.items():
                if hasattr(consumer, name):
                    setattr(consumer, name, guarded)

        original_handshake = port.handshake
        original_serial_handshake = port.serial_handshake

        def guarded_wait_for_device(max_attempts=300, interval=2, wait=True):
            self._raise_if_cancelled_or_timed_out()
            try:
                port.cdc.connected = port.cdc.connect()
            except Exception as error:
                if self._is_port_busy_error(error):
                    port_name = getattr(port.cdc, "portname", None) or "The selected port"
                    raise ConnectionBusyError(
                        f"{port_name} is already in use by another application. "
                        "Close the other phone tool and retry."
                    ) from error
                port.warning(f"Device enumeration failed: {error}")
                port.cdc.connected = False
            return bool(port.cdc.connected)

        def guarded_handshake(maxtries=None, loop=0):
            self._raise_if_cancelled_or_timed_out()
            return original_handshake(maxtries=1, loop=loop)

        def bounded_run_serial_handshake():
            """Run one bounded serial handshake instead of retrying forever."""
            cdc = port.cdc
            start_command = b"\xa0\x0a\x50\x05"
            byte_index = 0
            failed_cycles = 0

            while byte_index < len(start_command) and failed_cycles < 8:
                self._raise_if_cancelled_or_timed_out()
                value = start_command[byte_index]
                try:
                    wrote = cdc.write(bytes([value]))
                    response = cdc.read(1, timeout=20) if wrote else b""
                except Exception:
                    response = b""

                if len(response) == 1 and response[0] == (~value & 0xFF):
                    byte_index += 1
                    continue

                byte_index = 0
                failed_cycles += 1

            if byte_index == len(start_command):
                port.info("Device detected :)")
                return True
            return False

        def guarded_serial_handshake(maxtries=None, loop=0):
            self._raise_if_cancelled_or_timed_out()
            return original_serial_handshake(maxtries=1, loop=loop)

        port.wait_for_device = guarded_wait_for_device
        port.handshake = guarded_handshake
        port.run_serial_handshake = bounded_run_serial_handshake
        port.serial_handshake = guarded_serial_handshake

    def get_device_info(self) -> DeviceInfo:
        """Gather device info from current connection."""
        info = DeviceInfo()
        if self.mtk is None or self.config is None:
            return info

        info.hwcode = hex(self.config.hwcode) if self.config.hwcode else ""
        info.hwver = hex(self.config.hwver) if self.config.hwver else ""
        info.swver = hex(self.config.swver) if self.config.swver else ""
        info.is_brom = self.config.is_brom
        info.boot_mode = "BROM" if self.config.is_brom else "Preloader"
        info.chipset = f"MT{self.config.hwcode:04X}" if self.config.hwcode else "Unknown"

        if self.config.meid:
            info.meid = self.config.meid.hex() if isinstance(self.config.meid, (bytes, bytearray)) else str(self.config.meid)
        if self.config.socid:
            info.socid = self.config.socid.hex() if isinstance(self.config.socid, (bytes, bytearray)) else str(self.config.socid)

        if hasattr(self.mtk, 'daloader') and self.mtk.daloader is not None:
            dl = self.mtk.daloader
            if hasattr(dl, 'daconfig') and dl.daconfig is not None:
                storage = dl.daconfig.storage
                if storage:
                    info.flash_type = getattr(storage, 'flashtype', '')
                    flash_size = getattr(storage, 'flashsize', 0)
                    if flash_size:
                        info.flash_size = self._format_size(flash_size)

        if self.config.target_config:
            info.target_config = self.config.target_config

        return info

    def get_partitions(self, worker=None) -> list:
        """Get list of partitions from GPT."""
        partitions = []
        if self.da_handler is None:
            return partitions
        try:
            gpt = self.mtk.daloader.get_gpt()
            if gpt is None:
                return partitions
            gpt_data, gpt_guid = gpt
            for partition in gpt_data:
                p = PartitionInfo(
                    name=partition.name,
                    sector=partition.sector,
                    sectors=partition.sectors,
                    size=partition.sectors * self.config.SECTOR_SIZE_IN_BYTES,
                )
                partitions.append(p)
        except (SystemExit, Exception):
            pass
        return partitions

    # ── Flash read operations ─────────────────────────────

    def read_partition(self, partition_name: str, filename: str,
                       parttype: str = "user", worker=None) -> bool:
        """Read a single partition to file."""
        if self.da_handler is None:
            return False
        try:
            return self.da_handler.da_read(
                partition_name, parttype, filename, display=True
            )
        except SystemExit:
            return False

    def read_selected_partitions(self, partitions: list, directory: str,
                                  parttype: str = "user",
                                  dump_gpt: bool = False, worker=None) -> dict:
        """Read multiple partitions sequentially in a single worker.
        Returns dict of {name: success_bool}.
        """
        if self.da_handler is None:
            return {}
        results = {}
        try:
            if dump_gpt:
                self.da_handler.da_gpt(directory, display=True)
        except SystemExit:
            pass
        for name in partitions:
            filename = os.path.join(directory, f"{name}.bin")
            try:
                results[name] = bool(self.da_handler.da_read(
                    name, parttype, filename, display=True))
            except SystemExit:
                results[name] = False
        return results

    def read_partitions(self, directory: str, parttype: str = "user",
                        skip: list = None, worker=None) -> bool:
        """Read all partitions to directory."""
        if self.da_handler is None:
            return False
        try:
            return self.da_handler.da_rl(directory, parttype, skip or [], display=True)
        except SystemExit:
            return False

    def read_flash(self, filename: str, parttype: str = "user",
                   offset: int = None, length: int = None, worker=None) -> bool:
        """Read full flash or offset range to file."""
        if self.da_handler is None:
            return False
        try:
            return self.da_handler.da_rf(filename, parttype, offset, length, display=True)
        except SystemExit:
            return False

    def read_sectors(self, start: int, sectors: int, filename: str,
                     parttype: str = "user", worker=None) -> bool:
        """Read by sector range."""
        if self.da_handler is None:
            return False
        try:
            return self.da_handler.da_rs(start, sectors, filename, parttype, display=True)
        except SystemExit:
            return False

    def read_offset(self, start: int, length: int, filename: str,
                    parttype: str = "user", worker=None) -> bool:
        """Read by byte offset range."""
        if self.da_handler is None:
            return False
        try:
            return self.da_handler.da_ro(start, length, filename, parttype, display=True)
        except SystemExit:
            return False

    # ── Flash write operations ────────────────────────────

    def write_partitions(self, parttype: str, filenames: list,
                         partitions: list, worker=None) -> bool:
        """Write files to named partitions."""
        if self.da_handler is None:
            return False
        try:
            return self.da_handler.da_write(parttype, filenames, partitions)
        except SystemExit:
            return False

    def write_flash(self, filenames: list, parttype: str = "user", worker=None) -> bool:
        """Write full flash image(s)."""
        if self.da_handler is None:
            return False
        try:
            return self.da_handler.da_wf(filenames, parttype)
        except SystemExit:
            return False

    def write_from_directory(self, parttype: str, directory: str, worker=None) -> bool:
        """Write all matching partition files from directory."""
        if self.da_handler is None:
            return False
        try:
            return self.da_handler.da_wl(parttype, directory)
        except SystemExit:
            return False

    def write_offset(self, start: int, length: int, filename: str,
                     parttype: str = "user", worker=None) -> bool:
        """Write to a byte offset."""
        if self.da_handler is None:
            return False
        try:
            return self.da_handler.da_wo(start, length, filename, parttype)
        except SystemExit:
            return False

    # ── Erase operations ──────────────────────────────────

    def erase_partitions(self, partitions: list, parttype: str = "user", worker=None) -> bool:
        """Erase named partitions."""
        if self.da_handler is None:
            return False
        try:
            return self.da_handler.da_erase(partitions, parttype)
        except SystemExit:
            return False

    def erase_sectors(self, sector: int, sectors: int,
                      parttype: str = "user", worker=None) -> bool:
        """Erase by sector range."""
        if self.da_handler is None:
            return False
        try:
            return self.da_handler.da_ess(sector, sectors, parttype)
        except SystemExit:
            return False

    # ── Security operations ───────────────────────────────

    def generate_keys(self, directory: str = ".", worker=None) -> bool:
        """Generate hardware keys."""
        if self.mtk is None or not hasattr(self.mtk, 'daloader'):
            return False
        try:
            self.config.hwparam_path = directory
            return self.mtk.daloader.keys()
        except SystemExit:
            return False

    def seccfg_unlock(self, lock: bool = False, critical: bool = False, worker=None) -> bool:
        """Lock or unlock bootloader via seccfg."""
        if self.mtk is None or not hasattr(self.mtk, 'daloader'):
            return False
        try:
            lockflag = "lock" if lock else "unlock"
            return self.mtk.daloader.seccfg(lockflag, critical)
        except SystemExit:
            return False

    def vbmeta_patch(self, vbmode: int = 3, worker=None) -> bool:
        """Patch vbmeta for verified boot bypass."""
        if self.da_handler is None:
            return False
        try:
            return self.da_handler.da_vbmeta(vbmode, display=True)
        except SystemExit:
            return False

    # ── Memory operations ─────────────────────────────────

    def peek(self, addr: int, length: int, filename: Optional[str] = None,
             registers: bool = False, worker=None):
        """Read memory at address, returning bytes or writing them to a file."""
        if self.mtk is None or not hasattr(self.mtk, "daloader"):
            return None
        try:
            remaining = length
            position = 0
            chunks = []
            output = open(filename, "wb") if filename else None
            try:
                while remaining > 0:
                    if worker is not None and worker.is_cancelled:
                        raise ConnectionCancelled("Memory read stopped by user.")
                    request_size = min(remaining, 0x20000)
                    data = self.mtk.daloader.peek(
                        addr=addr + position,
                        length=request_size,
                        registers=registers,
                    )
                    if not data:
                        raise RuntimeError(
                            f"Memory read returned no data at 0x{addr + position:X}."
                        )
                    if output is not None:
                        output.write(data)
                    else:
                        chunks.append(bytes(data))
                    position += len(data)
                    remaining -= len(data)
            finally:
                if output is not None:
                    output.close()
            return True if filename else b"".join(chunks)
        except SystemExit:
            return None

    def poke(self, addr: int, data: str, filename: str = "", worker=None) -> bool:
        """Write memory at address."""
        if self.da_handler is None:
            return False
        try:
            return self.da_handler.da_poke(addr, data, filename)
        except SystemExit:
            return False

    def dump_brom(self, filename: str, worker=None) -> bool:
        """Dump BROM."""
        if self.da_handler is None:
            return False
        try:
            return self.da_handler.da_brom(filename)
        except SystemExit:
            return False

    # ── RPMB operations ───────────────────────────────────

    def read_rpmb(self, filename: str = None, sector: str = None,
                  sectors: str = None, worker=None):
        """Read RPMB."""
        if self.mtk is None or not hasattr(self.mtk, 'daloader'):
            return None
        try:
            return self.mtk.daloader.read_rpmb(filename, sector, sectors)
        except SystemExit:
            return None

    def write_rpmb(self, filename: str = None, sector: int = 0,
                   sectors: int = None, worker=None) -> bool:
        """Write RPMB."""
        if self.mtk is None or not hasattr(self.mtk, 'daloader'):
            return False
        try:
            return self.mtk.daloader.write_rpmb(filename, sector, sectors)
        except SystemExit:
            return False

    def erase_rpmb(self, sector: int = 0, sectors: int = None, worker=None) -> bool:
        """Erase RPMB."""
        if self.mtk is None or not hasattr(self.mtk, 'daloader'):
            return False
        try:
            return self.mtk.daloader.erase_rpmb(sector, sectors)
        except SystemExit:
            return False

    def auth_rpmb(self, rpmbkey: bytes = None, worker=None) -> bool:
        """Authenticate RPMB with key."""
        if self.mtk is None or not hasattr(self.mtk, 'daloader'):
            return False
        try:
            return self.mtk.daloader.auth_rpmb(rpmbkey)
        except SystemExit:
            return False

    # ── eFuse ─────────────────────────────────────────────

    def read_efuses(self, worker=None):
        """Read eFuse values."""
        if self.da_handler is None:
            return None
        try:
            return self.da_handler.da_efuse()
        except SystemExit:
            return None

    # ── GPT ───────────────────────────────────────────────

    def dump_gpt(self, directory: str, worker=None) -> bool:
        """Dump GPT to directory."""
        if self.da_handler is None:
            return False
        try:
            return self.da_handler.da_gpt(directory, display=True)
        except SystemExit:
            return False

    # ── IMEI ──────────────────────────────────────────────

    def read_imei(self, seed: bytes = b"", aeskey: bytes = b"\x00" * 32,
                  worker=None) -> list:
        """Read IMEI(s) from nvdata partition. Returns list of (imei, valid) tuples."""
        if self.da_handler is None:
            return []
        try:
            from mtkclient.Library.utils import find_binary
            from mtkclient.Library.mtk_crypto import decode_imei, calc_checksum, is_luhn_valid

            nvdata = self.da_handler.da_read_partition(partitionname="nvdata")
            if not nvdata or nvdata == b"":
                return []

            pos = find_binary(nvdata, b"\x4C\x44\x49\x00\x10\xEF\x0A\x00\x0A")
            if pos == -1:
                return []

            nvitem_data = nvdata[pos:pos + 0x180]
            result = self.mtk.daloader.nvitem(
                data=nvitem_data, encrypt=False,
                otp=self.mtk.config.get_otp(),
                seed=seed, aeskey=aeskey, display=False,
            )
            if result is None:
                return []

            imeis = []
            for i in range(len(result) // 0x20):
                data = bytearray(result[i * 0x20:i * 0x20 + 0x20])
                if data[:0xA] == b"\xFF" * 0xA:
                    continue
                csum = calc_checksum(data, 0xA)
                if csum == data[0xA:0xA + 8]:
                    imei = decode_imei(data[:0xA])
                    valid = is_luhn_valid(imei)
                    imeis.append((imei, valid))
            return imeis
        except SystemExit:
            return []

    def write_imei(self, imeis: list, seed: bytes = b"",
                   aeskey: bytes = b"\x00" * 32, product: str = "",
                   worker=None) -> bool:
        """Write IMEI(s) to nvdata partition. imeis: list of IMEI strings."""
        if self.da_handler is None or not imeis:
            return False
        try:
            from mtkclient.Library.utils import find_binary
            from mtkclient.Library.mtk_crypto import (
                encode_imei, calc_checksum, make_luhn_checksum,
            )

            fixed = []
            for imei_str in imeis:
                pre = imei_str[:14] + "0"
                fixed.append(pre[:14] + str(make_luhn_checksum(pre)))

            nvdata = bytearray(
                self.da_handler.da_read_partition(partitionname="nvdata")
            )
            if not nvdata or nvdata == b"":
                return False

            pos = 0
            while pos != -1:
                pos = nvdata.find(b"\x4C\x44\x49\x00\x10\xEF\x0A\x00\x0A", pos + 1)
                if pos != -1:
                    old_nvitem_data = nvdata[pos:pos + 0x180]
                    nvitem_data = bytearray()
                    x = 0
                    for imei in fixed:
                        data = encode_imei(imei) + b"\x00\x00"
                        csum = calc_checksum(data, 0xA)
                        nvitem_data.extend(data + csum + b"\x00" * 0xE)
                        x += 1
                    for _ in range(10 - x):
                        data = b"\xFF" * 0xA
                        csum = calc_checksum(data, 0xA)
                        nvitem_data.extend(data + csum + b"\x00" * 0xE)

                    header = old_nvitem_data[:0x40]
                    result = self.mtk.daloader.nvitem(
                        data=header + nvitem_data, encrypt=True,
                        otp=self.mtk.config.get_otp(),
                        seed=seed, aeskey=aeskey, display=False,
                    )
                    nvdata[pos:pos + 0x180] = header + result

            return self.da_handler.da_write_partition(
                partitionname="nvdata", data=bytes(nvdata)
            )
        except SystemExit:
            return False

    def nvitem_crypt(self, filename: str, encrypt: bool = False,
                     worker=None):
        """Encrypt or decrypt an NVItem file. Returns processed bytes or None."""
        if self.mtk is None or not hasattr(self.mtk, 'daloader'):
            return None
        try:
            with open(filename, "rb") as rf:
                data = rf.read()
            return self.mtk.daloader.nvitem(
                data=data, encrypt=encrypt,
                otp=self.mtk.config.get_otp(),
                seed=b"", aeskey=b"\x00" * 32, display=False,
            )
        except SystemExit:
            return None

    # ── Exploit ───────────────────────────────────────────

    def crash_preloader(self, mode: int = None, worker=None) -> bool:
        """Crash preloader/DA to get into BROM mode. mode=None iterates all modes."""
        if self.mtk is None:
            return False
        try:
            self.mtk.crasher(mode=mode)
            return True
        except SystemExit:
            return False

    def run_payload(self, filename: str, worker=None) -> bool:
        """Load and run a payload binary via boot_to."""
        if self.mtk is None or not hasattr(self.mtk, 'daloader'):
            return False
        try:
            with open(filename, "rb") as f:
                data = f.read()
            return self.mtk.daloader.boot_to(addr=0x200000, data=data)
        except SystemExit:
            return False

    def run_stage2(self, filename: str, addr: int = 0x200000, worker=None) -> bool:
        """Load stage2 payload at address."""
        if self.mtk is None or not hasattr(self.mtk, 'daloader'):
            return False
        try:
            with open(filename, "rb") as f:
                data = f.read()
            return self.mtk.daloader.boot_to(addr=addr, data=data)
        except SystemExit:
            return False

    def set_meta_mode(self, porttype: str = "off", worker=None) -> bool:
        """Set meta mode (off/usb/uart)."""
        if self.mtk is None or not hasattr(self.mtk, 'daloader'):
            return False
        try:
            return self.mtk.daloader.setmetamode(porttype)
        except SystemExit:
            return False

    def shutdown(self, worker=None) -> bool:
        """Shutdown device."""
        if self.mtk is None or not hasattr(self.mtk, 'daloader'):
            return False
        try:
            return self.mtk.daloader.shutdown()
        except SystemExit:
            return False

    def reset_device(self, worker=None) -> bool:
        """Reset/reboot device."""
        if self.mtk is None or not hasattr(self.mtk, 'daloader'):
            return False
        try:
            return self.mtk.daloader.shutdown(
                bootmode=self.mtk.daloader.ShutDownModes.HOME_SCREEN
            )
        except SystemExit:
            return False

    def keyserver(self, worker=None) -> bool:
        """Run key server."""
        if self.mtk is None or not hasattr(self.mtk, 'daloader'):
            return False
        try:
            return self.mtk.daloader.keyserver()
        except SystemExit:
            return False

    def patch_modem(self, worker=None) -> bool:
        """Patch modem partition."""
        if self.da_handler is None:
            return False
        try:
            return self.da_handler.da_patch_modem()
        except SystemExit:
            return False

    # ── Helpers ───────────────────────────────────────────

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        """Format bytes to human-readable string."""
        if size_bytes <= 0:
            return "0 B"
        units = ("B", "KB", "MB", "GB", "TB")
        i = int(math.floor(math.log(size_bytes, 1024)))
        i = min(i, len(units) - 1)
        p = math.pow(1024, i)
        s = round(size_bytes / p, 2)
        return f"{s} {units[i]}"
