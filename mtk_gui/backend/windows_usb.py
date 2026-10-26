"""Windows USB backend selection for MediaTek filter-driver devices."""
import os
import sys
from typing import Optional

from mtk_gui.constants import MTK_USB_VID


def select_mtk_usb_backend(mtk) -> Optional[str]:
    """Use libusb0 when its filter can see the live MTK device.

    MediaTek's Windows VCOM packages can expose the same device through a
    libusb-win32 upper filter.  On Windows build 26200, UsbDk enumeration is
    broken and libusb1 can enumerate such a node but fail when opening its
    configuration.  Selecting libusb0 only when it can already enumerate the
    target preserves normal WinUSB/libusb1 behavior on other driver stacks.
    """
    if os.name != "nt" or getattr(mtk, "serialportname", None) is not None:
        return None

    cdc = getattr(getattr(mtk, "port", None), "cdc", None)
    if cdc is None or not hasattr(cdc, "backend"):
        return None

    try:
        import usb.backend.libusb0
        import usb.core

        bundled = os.path.join(getattr(sys, "_MEIPASS", ""), "libusb0.dll")
        if os.path.isfile(bundled):
            backend = usb.backend.libusb0.get_backend(
                find_library=lambda _: bundled)
        else:
            backend = usb.backend.libusb0.get_backend()
        if backend is None:
            return None
        device = usb.core.find(idVendor=MTK_USB_VID, backend=backend)
        if device is None:
            return None
    except Exception:
        return None

    cdc.backend = backend
    return "libusb0 (MediaTek upper-filter device)"
