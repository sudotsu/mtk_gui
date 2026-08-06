"""Clean facade over mtkclient API. No Qt dependency."""
import logging
import os
import sys
from dataclasses import dataclass, field
from typing import Optional

from mtkclient.Library.DA.mtk_da_handler import DaHandler
from mtkclient.Library.mtk_class import Mtk
from mtkclient.config.mtk_config import MtkConfig
from mtkclient.Library.DA.mtk_daloader import DAloader


class OperationAborted(Exception):
    """Raised instead of sys.exit() inside library code."""


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
    """Wraps mtkclient init/connect and all DA operations."""

    def __init__(self, gui_signal=None, gui_progress=None, status_signal=None):
        self.mtk: Optional[Mtk] = None
        self.da_handler: Optional[DaHandler] = None
        self.config: Optional[MtkConfig] = None
        self._gui_signal = gui_signal
        self._gui_progress = gui_progress
        self._status_signal = status_signal
        self._original_exit = sys.exit

    def _patch_sys_exit(self):
        """Monkey-patch sys.exit() to raise OperationAborted instead."""
        def patched_exit(code=0):
            raise OperationAborted(f"sys.exit({code}) intercepted")
        sys.exit = patched_exit

    def _restore_sys_exit(self):
        sys.exit = self._original_exit

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
        return self.mtk

    def connect(self, work_dir: str = ".") -> bool:
        """Connect to device via DA. Returns True on success."""
        if self.mtk is None:
            return False
        self._patch_sys_exit()
        try:
            self.da_handler = DaHandler(self.mtk, logging.INFO)
            mtk = self.da_handler.connect(self.mtk, work_dir)
            if mtk is None:
                return False
            self.mtk = mtk
            self.mtk = self.da_handler.configure_da(self.mtk)
            return True
        except OperationAborted:
            return False
        finally:
            self._restore_sys_exit()

    def disconnect(self):
        """Clean up connection state."""
        self.da_handler = None
        self.mtk = None
        self.config = None

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
        except Exception:
            pass
        return partitions

    # ── Flash read operations ─────────────────────────────

    def read_partition(self, partition_name: str, filename: str,
                       parttype: str = "user", worker=None) -> bool:
        """Read a single partition to file."""
        if self.da_handler is None:
            return False
        self._patch_sys_exit()
        try:
            return self.da_handler.da_read(
                partition_name, parttype, filename, display=True
            )
        except OperationAborted:
            return False
        finally:
            self._restore_sys_exit()

    def read_partitions(self, directory: str, parttype: str = "user",
                        skip: list = None, worker=None) -> bool:
        """Read all partitions to directory."""
        if self.da_handler is None:
            return False
        self._patch_sys_exit()
        try:
            return self.da_handler.da_rl(directory, parttype, skip or [], display=True)
        except OperationAborted:
            return False
        finally:
            self._restore_sys_exit()

    def read_flash(self, filename: str, parttype: str = "user",
                   offset: int = None, length: int = None, worker=None) -> bool:
        """Read full flash or offset range to file."""
        if self.da_handler is None:
            return False
        self._patch_sys_exit()
        try:
            return self.da_handler.da_rf(filename, parttype, offset, length, display=True)
        except OperationAborted:
            return False
        finally:
            self._restore_sys_exit()

    def read_sectors(self, start: int, sectors: int, filename: str,
                     parttype: str = "user", worker=None) -> bool:
        """Read by sector range."""
        if self.da_handler is None:
            return False
        self._patch_sys_exit()
        try:
            return self.da_handler.da_rs(start, sectors, filename, parttype, display=True)
        except OperationAborted:
            return False
        finally:
            self._restore_sys_exit()

    def read_offset(self, start: int, length: int, filename: str,
                    parttype: str = "user", worker=None) -> bool:
        """Read by byte offset range."""
        if self.da_handler is None:
            return False
        self._patch_sys_exit()
        try:
            return self.da_handler.da_ro(start, length, filename, parttype, display=True)
        except OperationAborted:
            return False
        finally:
            self._restore_sys_exit()

    # ── Flash write operations ────────────────────────────

    def write_partitions(self, parttype: str, filenames: list,
                         partitions: list, worker=None) -> bool:
        """Write files to named partitions."""
        if self.da_handler is None:
            return False
        self._patch_sys_exit()
        try:
            return self.da_handler.da_write(parttype, filenames, partitions)
        except OperationAborted:
            return False
        finally:
            self._restore_sys_exit()

    def write_flash(self, filenames: list, parttype: str = "user", worker=None) -> bool:
        """Write full flash image(s)."""
        if self.da_handler is None:
            return False
        self._patch_sys_exit()
        try:
            return self.da_handler.da_wf(filenames, parttype)
        except OperationAborted:
            return False
        finally:
            self._restore_sys_exit()

    def write_from_directory(self, parttype: str, directory: str, worker=None) -> bool:
        """Write all matching partition files from directory."""
        if self.da_handler is None:
            return False
        self._patch_sys_exit()
        try:
            return self.da_handler.da_wl(parttype, directory)
        except OperationAborted:
            return False
        finally:
            self._restore_sys_exit()

    def write_offset(self, start: int, length: int, filename: str,
                     parttype: str = "user", worker=None) -> bool:
        """Write to a byte offset."""
        if self.da_handler is None:
            return False
        self._patch_sys_exit()
        try:
            return self.da_handler.da_wo(start, length, filename, parttype)
        except OperationAborted:
            return False
        finally:
            self._restore_sys_exit()

    # ── Erase operations ──────────────────────────────────

    def erase_partitions(self, partitions: list, parttype: str = "user", worker=None) -> bool:
        """Erase named partitions."""
        if self.da_handler is None:
            return False
        self._patch_sys_exit()
        try:
            return self.da_handler.da_erase(partitions, parttype)
        except OperationAborted:
            return False
        finally:
            self._restore_sys_exit()

    def erase_sectors(self, sector: int, sectors: int,
                      parttype: str = "user", worker=None) -> bool:
        """Erase by sector range."""
        if self.da_handler is None:
            return False
        self._patch_sys_exit()
        try:
            return self.da_handler.da_ess(sector, sectors, parttype)
        except OperationAborted:
            return False
        finally:
            self._restore_sys_exit()

    # ── Security operations ───────────────────────────────

    def generate_keys(self, directory: str = ".", worker=None) -> bool:
        """Generate hardware keys."""
        if self.mtk is None or not hasattr(self.mtk, 'daloader'):
            return False
        self._patch_sys_exit()
        try:
            self.config.hwparam_path = directory
            return self.mtk.daloader.keys()
        except OperationAborted:
            return False
        finally:
            self._restore_sys_exit()

    def seccfg_unlock(self, lock: bool = False, critical: bool = False, worker=None) -> bool:
        """Lock or unlock bootloader via seccfg."""
        if self.mtk is None or not hasattr(self.mtk, 'daloader'):
            return False
        self._patch_sys_exit()
        try:
            lockflag = "lock" if lock else "unlock"
            return self.mtk.daloader.seccfg(lockflag, critical)
        except OperationAborted:
            return False
        finally:
            self._restore_sys_exit()

    def vbmeta_patch(self, vbmode: int = 3, worker=None) -> bool:
        """Patch vbmeta for verified boot bypass."""
        if self.da_handler is None:
            return False
        self._patch_sys_exit()
        try:
            return self.da_handler.da_vbmeta(vbmode, display=True)
        except OperationAborted:
            return False
        finally:
            self._restore_sys_exit()

    # ── Memory operations ─────────────────────────────────

    def peek(self, addr: int, length: int, filename: str = "",
             registers: bool = False, worker=None):
        """Read memory at address."""
        if self.da_handler is None:
            return None
        self._patch_sys_exit()
        try:
            return self.da_handler.da_peek(addr, length, filename, registers)
        except OperationAborted:
            return None
        finally:
            self._restore_sys_exit()

    def poke(self, addr: int, data: str, filename: str = "", worker=None) -> bool:
        """Write memory at address."""
        if self.da_handler is None:
            return False
        self._patch_sys_exit()
        try:
            return self.da_handler.da_poke(addr, data, filename)
        except OperationAborted:
            return False
        finally:
            self._restore_sys_exit()

    def dump_brom(self, filename: str, worker=None) -> bool:
        """Dump BROM."""
        if self.da_handler is None:
            return False
        self._patch_sys_exit()
        try:
            return self.da_handler.da_brom(filename)
        except OperationAborted:
            return False
        finally:
            self._restore_sys_exit()

    # ── RPMB operations ───────────────────────────────────

    def read_rpmb(self, filename: str = None, sector: str = None,
                  sectors: str = None, worker=None):
        """Read RPMB."""
        if self.mtk is None or not hasattr(self.mtk, 'daloader'):
            return None
        self._patch_sys_exit()
        try:
            return self.mtk.daloader.read_rpmb(filename, sector, sectors)
        except OperationAborted:
            return None
        finally:
            self._restore_sys_exit()

    def write_rpmb(self, filename: str = None, sector: int = 0,
                   sectors: int = None, worker=None) -> bool:
        """Write RPMB."""
        if self.mtk is None or not hasattr(self.mtk, 'daloader'):
            return False
        self._patch_sys_exit()
        try:
            return self.mtk.daloader.write_rpmb(filename, sector, sectors)
        except OperationAborted:
            return False
        finally:
            self._restore_sys_exit()

    # ── eFuse ─────────────────────────────────────────────

    def read_efuses(self, worker=None):
        """Read eFuse values."""
        if self.da_handler is None:
            return None
        self._patch_sys_exit()
        try:
            return self.da_handler.da_efuse()
        except OperationAborted:
            return None
        finally:
            self._restore_sys_exit()

    # ── GPT ───────────────────────────────────────────────

    def dump_gpt(self, directory: str, worker=None) -> bool:
        """Dump GPT to directory."""
        if self.da_handler is None:
            return False
        self._patch_sys_exit()
        try:
            return self.da_handler.da_gpt(directory, display=True)
        except OperationAborted:
            return False
        finally:
            self._restore_sys_exit()

    def erase_rpmb(self, sector: int = 0, sectors: int = None, worker=None) -> bool:
        """Erase RPMB."""
        if self.mtk is None or not hasattr(self.mtk, 'daloader'):
            return False
        self._patch_sys_exit()
        try:
            return self.mtk.daloader.erase_rpmb(sector, sectors)
        except OperationAborted:
            return False
        finally:
            self._restore_sys_exit()

    def auth_rpmb(self, rpmbkey: bytes = None, worker=None) -> bool:
        """Authenticate RPMB with key."""
        if self.mtk is None or not hasattr(self.mtk, 'daloader'):
            return False
        self._patch_sys_exit()
        try:
            return self.mtk.daloader.auth_rpmb(rpmbkey)
        except OperationAborted:
            return False
        finally:
            self._restore_sys_exit()

    # ── IMEI ──────────────────────────────────────────────

    def read_imei(self, seed: bytes = b"", aeskey: bytes = b"" * 32,
                  worker=None) -> list:
        """Read IMEI(s) from nvdata partition. Returns list of (imei, valid) tuples."""
        if self.da_handler is None:
            return []
        self._patch_sys_exit()
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
        except OperationAborted:
            return []
        finally:
            self._restore_sys_exit()

    def write_imei(self, imeis: list, seed: bytes = b"",
                   aeskey: bytes = b"" * 32, product: str = "",
                   worker=None) -> bool:
        """Write IMEI(s) to nvdata partition. imeis: list of IMEI strings."""
        if self.da_handler is None or not imeis:
            return False
        self._patch_sys_exit()
        try:
            from mtkclient.Library.utils import find_binary
            from mtkclient.Library.mtk_crypto import (
                encode_imei, calc_checksum, make_luhn_checksum,
            )

            # Fix checksums
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
        except OperationAborted:
            return False
        finally:
            self._restore_sys_exit()

    def nvitem_crypt(self, filename: str, encrypt: bool = False,
                     worker=None):
        """Encrypt or decrypt an NVItem file. Returns processed bytes or None."""
        if self.mtk is None or not hasattr(self.mtk, 'daloader'):
            return None
        self._patch_sys_exit()
        try:
            with open(filename, "rb") as rf:
                data = rf.read()
            return self.mtk.daloader.nvitem(
                data=data, encrypt=encrypt,
                otp=self.mtk.config.get_otp(),
                seed=b"", aeskey=b"" * 32, display=False,
            )
        except OperationAborted:
            return None
        finally:
            self._restore_sys_exit()

    # ── Exploit ───────────────────────────────────────────

    def crash_preloader(self, mode: int = None, worker=None) -> bool:
        """Crash preloader/DA to get into BROM mode. mode=None iterates all modes."""
        if self.mtk is None:
            return False
        self._patch_sys_exit()
        try:
            self.mtk.crasher(mode=mode)
            return True
        except OperationAborted:
            return False
        finally:
            self._restore_sys_exit()

    def run_payload(self, filename: str, worker=None) -> bool:
        """Load and run a payload binary via boot_to."""
        if self.mtk is None or not hasattr(self.mtk, 'daloader'):
            return False
        self._patch_sys_exit()
        try:
            with open(filename, "rb") as f:
                data = f.read()
            return self.mtk.daloader.boot_to(addr=0x200000, data=data)
        except OperationAborted:
            return False
        finally:
            self._restore_sys_exit()

    def run_stage2(self, filename: str, addr: int = 0x200000, worker=None) -> bool:
        """Load stage2 payload at address."""
        if self.mtk is None or not hasattr(self.mtk, 'daloader'):
            return False
        self._patch_sys_exit()
        try:
            with open(filename, "rb") as f:
                data = f.read()
            return self.mtk.daloader.boot_to(addr=addr, data=data)
        except OperationAborted:
            return False
        finally:
            self._restore_sys_exit()

    def set_meta_mode(self, porttype: str = "off", worker=None) -> bool:
        """Set meta mode (off/usb/uart)."""
        if self.mtk is None or not hasattr(self.mtk, 'daloader'):
            return False
        self._patch_sys_exit()
        try:
            return self.mtk.daloader.setmetamode(porttype)
        except OperationAborted:
            return False
        finally:
            self._restore_sys_exit()

    def shutdown(self, worker=None) -> bool:
        """Shutdown device."""
        if self.mtk is None or not hasattr(self.mtk, 'daloader'):
            return False
        self._patch_sys_exit()
        try:
            return self.mtk.daloader.shutdown()
        except OperationAborted:
            return False
        finally:
            self._restore_sys_exit()

    def reset_device(self, worker=None) -> bool:
        """Reset/reboot device."""
        if self.mtk is None or not hasattr(self.mtk, 'daloader'):
            return False
        self._patch_sys_exit()
        try:
            return self.mtk.daloader.shutdown(
                bootmode=self.mtk.daloader.ShutDownModes.HOME_SCREEN
            )
        except OperationAborted:
            return False
        finally:
            self._restore_sys_exit()

    def keyserver(self, worker=None) -> bool:
        """Run key server."""
        if self.mtk is None or not hasattr(self.mtk, 'daloader'):
            return False
        self._patch_sys_exit()
        try:
            return self.mtk.daloader.keyserver()
        except OperationAborted:
            return False
        finally:
            self._restore_sys_exit()

    def patch_modem(self, worker=None) -> bool:
        """Patch modem partition."""
        if self.da_handler is None:
            return False
        self._patch_sys_exit()
        try:
            return self.da_handler.da_patch_modem()
        except OperationAborted:
            return False
        finally:
            self._restore_sys_exit()

    # ── Helpers ───────────────────────────────────────────

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        """Format bytes to human-readable string."""
        if size_bytes <= 0:
            return "0 B"
        units = ("B", "KB", "MB", "GB", "TB")
        import math
        i = int(math.floor(math.log(size_bytes, 1024)))
        i = min(i, len(units) - 1)
        p = math.pow(1024, i)
        s = round(size_bytes / p, 2)
        return f"{s} {units[i]}"
