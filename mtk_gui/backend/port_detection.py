"""Serial-port discovery helpers for MediaTek devices."""
from dataclasses import dataclass
from typing import Iterable, Optional

from mtk_gui.constants import MTK_PRELOADER_PIDS, MTK_USB_VID


@dataclass(frozen=True)
class SerialPortInfo:
    """The serial-port fields the GUI needs, detached from pyserial objects."""

    device: str
    description: str
    vid: Optional[int]
    pid: Optional[int]


def list_serial_ports() -> list[SerialPortInfo]:
    """Return the serial ports currently reported by pyserial."""
    try:
        from serial.tools import list_ports
    except ImportError:
        return []

    return [
        SerialPortInfo(
            device=port.device,
            description=port.description or port.device,
            vid=port.vid,
            pid=port.pid,
        )
        for port in list_ports.comports()
    ]


def find_mtk_serial_port(
    ports: Optional[Iterable[SerialPortInfo]] = None,
) -> Optional[SerialPortInfo]:
    """Find a live MediaTek BROM, Preloader, or DA VCOM port."""
    candidates = list_serial_ports() if ports is None else ports
    for port in candidates:
        if port.vid == MTK_USB_VID and port.pid in MTK_PRELOADER_PIDS:
            return port
    return None
