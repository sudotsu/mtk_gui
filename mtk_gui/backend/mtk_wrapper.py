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
        """Initialize the wrapper with optional GUI and status callbacks."""
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
            """
            Intercept a system-exit request by raising an operation-aborted exception.
            
            Parameters:
                code: The requested exit status.
            
            Raises:
                OperationAborted: Always raised with the requested exit status.
            """
            raise OperationAborted(f"sys.exit({code}) intercepted")
        sys.exit = patched_exit

    def _restore_sys_exit(self):
        """Restore the original ``sys.exit`` implementation."""
        sys.exit = self._original_exit

    def init(self, preloader: str = None, loader: str = None,
             serial_port: str = None, iot: bool = False,
             stock: bool = False, work_dir: str = ".") -> Mtk:
        """
             Initialize the MediaTek client with the specified connection and loader settings.
             
             Parameters:
                 preloader (str): Optional path to a preloader file.
                 loader (str): Optional download agent path.
                 serial_port (str): Optional serial port name.
                 iot (bool): Whether to enable IoT mode.
                 stock (bool): Whether to use stock device settings.
                 work_dir (str): Directory used for hardware parameter data.
             
             Returns:
                 Mtk: The initialized MediaTek client.
             """
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
        """
        Connect to the device through the Download Agent.
        
        Parameters:
            work_dir (str): Directory used for connection-related files.
        
        Returns:
            bool: `True` if the connection and DA configuration succeed, `False` otherwise.
        """
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
        """
        Gather information about the connected device.
        
        Returns:
        	DeviceInfo: Device metadata, or an empty instance when no device is initialized.
        """
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
        """Retrieve partition metadata from the device's GPT.
        
        Returns:
            list: Partition information, or an empty list when GPT data is unavailable.
        """
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
        """
                       Read a partition from the connected device into a file.
                       
                       Parameters:
                           partition_name (str): Name of the partition to read.
                           filename (str): Destination file path.
                           parttype (str): Partition type used for the read operation.
                           worker: Optional worker associated with the operation.
                       
                       Returns:
                           bool: `True` if the partition is read successfully, `False` otherwise.
                       """
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
        """
                        Read selected device partitions into a directory.
                        
                        Parameters:
                        	directory (str): Destination directory for the partition images.
                        	parttype (str): Partition type to read.
                        	skip (list): Partition names to exclude.
                        	worker: Optional worker used by the underlying read operation.
                        
                        Returns:
                        	bool: `True` if the operation succeeds, `False` if the device is unavailable or the operation is aborted.
                        """
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
        """Read flash data or a specified range to a file.
                   
                   Parameters:
                       parttype (str): Flash region to read.
                       offset (int): Starting byte offset, when reading a range.
                       length (int): Number of bytes to read, when reading a range.
                   
                   Returns:
                       bool: `True` if the read succeeds, `False` otherwise.
                   """
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
        """
                     Read a sector range from the connected device into a file.
                     
                     Parameters:
                     	start (int): Starting sector.
                     	sectors (int): Number of sectors to read.
                     	filename (str): Destination file path.
                     	parttype (str): Partition type containing the sectors.
                     
                     Returns:
                     	bool: `true` if the read succeeds, `false` otherwise.
                     """
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
        """
                    Read a byte range from the device into a file.
                    
                    Parameters:
                    	start (int): The starting byte offset.
                    	length (int): The number of bytes to read.
                    	filename (str): The destination file path.
                    	parttype (str): The partition type containing the byte range.
                    
                    Returns:
                    	bool: `True` if the read succeeds, `False` if no device connection is available or the operation is aborted.
                    """
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
        """
                         Write files to the specified device partitions.
                         
                         Parameters:
                             parttype (str): Partition type used for the write operation.
                             filenames (list): Files containing the data to write.
                             partitions (list): Target partition names.
                             worker: Optional worker associated with the operation.
                         
                         Returns:
                             bool: `True` if the write succeeds, `False` if no device connection is available or the operation is aborted.
                         """
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
        """Write one or more full flash images to the device.
        
        Parameters:
            filenames (list): Flash image files to write.
            parttype (str): Partition type targeted by the images.
        
        Returns:
            bool: `True` if the write operation succeeds, `False` otherwise.
        """
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
        """
        Write matching partition image files from a directory to the device.
        
        Parameters:
            parttype (str): Partition type used to select the files.
            directory (str): Directory containing the partition files.
        
        Returns:
            bool: `True` if the write operation succeeds, `False` otherwise.
        """
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
        """
                     Write data from a file to a device at a byte offset.
                     
                     Parameters:
                         start (int): Starting byte offset.
                         length (int): Number of bytes to write.
                         filename (str): Path to the input file.
                         parttype (str): Partition type containing the offset.
                         worker: Optional progress worker.
                     
                     Returns:
                         bool: `True` if the write succeeds, `False` if no device connection is available or the operation is aborted.
                     """
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
        """
        Erase the specified partitions on the connected device.
        
        Parameters:
        	partitions (list): Names of the partitions to erase.
        	parttype (str): Partition type containing the named partitions.
        
        Returns:
        	bool: `True` if the erase operation succeeds, `False` otherwise.
        """
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
        """Erase a range of sectors on the specified partition type.
                      
                      Parameters:
                          sector (int): The starting sector.
                          sectors (int): The number of sectors to erase.
                          parttype (str): The partition type containing the sectors.
                          worker: An optional operation worker.
                      
                      Returns:
                          bool: `True` if the erase operation succeeds, `False` otherwise.
                      """
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
        """Generate hardware keys in the specified directory.
        
        Parameters:
        	directory (str): Directory where the generated hardware keys are stored.
        	worker: Optional worker used by the key-generation operation.
        
        Returns:
        	bool: `True` if key generation succeeds, `False` otherwise.
        """
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
        """Set the device's secure configuration to lock or unlock mode.
        
        Parameters:
            lock (bool): Whether to lock the bootloader; otherwise, unlock it.
            critical (bool): Whether to apply the operation to critical partitions.
        
        Returns:
            bool: `True` if the operation succeeds, `False` if the device is unavailable or the operation is aborted.
        """
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
        """
        Patch verified boot metadata using the specified mode.
        
        Parameters:
        	vbmode (int): Verified boot patch mode.
        
        Returns:
        	bool: `True` if the patch succeeds, `False` otherwise.
        """
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
        """
             Read a region of device memory.
             
             Parameters:
                 addr (int): Starting memory address.
                 length (int): Number of bytes to read.
                 filename (str): Optional file path for saving the data.
                 registers (bool): Whether to include register data.
             
             Returns:
                 bytes or None: The memory contents, or `None` if the device is unavailable or the operation is aborted.
             """
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
        """
        Write data to a device memory address.
        
        Parameters:
            addr (int): Memory address to write.
            data (str): Data to write.
            filename (str): Optional file containing the data.
        
        Returns:
            bool: `True` if the write succeeds, `False` otherwise.
        """
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
        """Dump the device's Boot ROM contents to a file.
        
        Parameters:
            filename (str): Path of the output file.
            worker: Optional worker used by the underlying dump operation.
        
        Returns:
            bool: `True` if the dump succeeds, `False` if the device is unavailable or the operation is aborted.
        """
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
        """
                  Read data from RPMB storage.
                  
                  Parameters:
                      filename (str, optional): Destination file for the RPMB data.
                      sector (str, optional): Starting RPMB sector.
                      sectors (str, optional): Number of sectors to read.
                  
                  Returns:
                      The result of the RPMB read operation, or `None` if the device is unavailable or the operation is aborted.
                  """
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
        """
                   Write data to RPMB storage.
                   
                   Parameters:
                       filename (str): Path to the file containing data to write.
                       sector (int): Starting RPMB sector.
                       sectors (int): Number of sectors to write.
                   
                   Returns:
                       bool: `True` if the write succeeds, `False` otherwise.
                   """
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
        """
        Read the device's eFuse values.
        
        Parameters:
            worker: Optional worker context used by the eFuse operation.
        
        Returns:
            The eFuse values, or `None` if the device is unavailable or the operation is aborted.
        """
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
        """
        Dump the device's GPT data to a directory.
        
        Parameters:
        	directory (str): Destination directory for the GPT data.
        	worker: Optional worker associated with the operation.
        
        Returns:
        	bool: `True` if the GPT data is dumped successfully, `False` otherwise.
        """
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
        """
        Erase a range of sectors from RPMB storage.
        
        Parameters:
        	sector (int): The first sector to erase.
        	sectors (int): The number of sectors to erase.
        
        Returns:
        	bool: `True` if the operation succeeds, `False` otherwise.
        """
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
        """
        Authenticate the device's RPMB using the supplied key.
        
        Parameters:
            rpmbkey (bytes): Key used to authenticate RPMB access.
        
        Returns:
            bool: `true` if authentication succeeds, `false` otherwise.
        """
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
        """
                  Read IMEI values from the device's `nvdata` partition.
                  
                  Parameters:
                      seed (bytes): Seed used to process the NVItem data.
                      aeskey (bytes): AES key used to process the NVItem data.
                      worker: Optional worker context for the operation.
                  
                  Returns:
                      list: Tuples containing each decoded IMEI and whether its check digit is valid.
                  """
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
        """
                   Write IMEI values to the device's `nvdata` partition.
                   
                   Parameters:
                   	imeis (list): IMEI strings to write.
                   	seed (bytes): Optional encryption seed.
                   	aeskey (bytes): Optional AES key.
                   	product (str): Optional product identifier.
                   	worker: Optional worker context for the operation.
                   
                   Returns:
                   	bool: `True` if the `nvdata` partition is updated successfully, `False` otherwise.
                   """
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
        """
                     Encrypt or decrypt the contents of an NVItem file.
                     
                     Parameters:
                     	filename (str): Path to the NVItem file.
                     	encrypt (bool): Whether to encrypt the file contents; otherwise, decrypt them.
                     	worker: Optional worker context for the operation.
                     
                     Returns:
                     	bytes: The processed NVItem data, or `None` if the operation is unavailable or aborted.
                     """
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
        """
        Crash the preloader to enter BROM mode.
        
        Parameters:
        	mode (int, optional): Crash mode to use. If omitted, the operation selects the available modes.
        	worker: Optional worker context for the operation.
        
        Returns:
        	`True` if the preloader crash succeeds, `False` otherwise.
        """
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
        """
        Load and execute a payload binary on the connected device.
        
        Parameters:
            filename (str): Path to the payload binary.
        
        Returns:
            bool: `True` if the payload is loaded successfully, `False` otherwise.
        """
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
        """
        Load a stage 2 payload into device memory.
        
        Parameters:
            filename (str): Path to the stage 2 payload.
            addr (int): Device memory address at which to load the payload.
        
        Returns:
            bool: `true` if the payload loads successfully, `false` otherwise.
        """
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
        """
        Set the device's meta mode.
        
        Parameters:
            porttype (str): Meta mode to configure, such as ``"off"``, ``"usb"``, or ``"uart"``.
        
        Returns:
            bool: ``True`` if the mode was configured successfully, ``False`` otherwise.
        """
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
        """Powers down the connected device.
        
        Parameters:
            worker: Optional operation worker passed to the device shutdown handler.
        
        Returns:
            `True` if the shutdown operation succeeds, `False` otherwise.
        """
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
        """
        Patch the modem partition on the connected device.
        
        Parameters:
            worker: Optional worker context used by the modem patching operation.
        
        Returns:
            `True` if patching succeeds, `False` if no device handler is available or the operation is aborted.
        """
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
