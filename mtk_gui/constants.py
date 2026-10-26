"""Application constants."""

APP_NAME = "MTK-GUI"
APP_VERSION = "0.1.0"
APP_TITLE = f"{APP_NAME} v{APP_VERSION}"
ORG_NAME = "mtk-gui"

# MediaTek USB IDs
MTK_USB_VID = 0x0E8D
MTK_PRELOADER_PIDS = [0x0003, 0x2000, 0x2001, 0x20FF]
MTK_DA_PIDS = [0x2000, 0x2001]

# USB polling interval (ms)
USB_POLL_INTERVAL_MS = 2000

# A detected Preloader/VCOM device should either handshake or return control to
# the user promptly.  mtkclient's internal retry budget is intentionally much
# larger because it is also used by command-line workflows that wait for a
# cable insertion.
CONNECTION_TIMEOUT_SECONDS = 30

# Default paths
DEFAULT_DA_LOADER = None
DEFAULT_PRELOADER = None
DEFAULT_WORK_DIR = "."

# Partition types
PART_TYPES = ["user", "boot1", "boot2", "rpmb"]

# Theme names
THEME_DARK = "dark"
THEME_LIGHT = "light"
DEFAULT_THEME = THEME_DARK
