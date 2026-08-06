# MTK-GUI

A standalone GUI for [mtkclient](https://github.com/bkerler/mtkclient) — the open-source MediaTek reverse engineering tool.

## Why this exists

mtkclient ships with `mtk_gui.py`, a 717-line single-file GUI that's effectively unmaintained. It works for basic operations but is fragile, hard to extend, and freezes during USB operations because everything runs on the main thread.

MTK-GUI is a ground-up replacement built with PySide6. It's modular (12 tabs, each in its own file), runs all device I/O on background threads, and has a plugin system for extensibility.

## Features

- **12 operation tabs**: Device, Read, Write, Erase, Keys, Bootloader, Memory, RPMB, IMEI, Exploit, eFuse, Server
- **Non-blocking UI**: USB polling, partition loading, and all device operations run on background threads
- **Input validation**: Hex fields, IMEI digits, file paths — validated before reaching the backend
- **Destructive operation safety**: Confirmation dialogs with type-to-confirm for writes, erases, bootloader changes
- **Button-disable during operations**: Prevents concurrent conflicting operations on the same device session
- **Dark/light theme**: Toggle from the View menu, persisted across sessions
- **Plugin system**: Drop `.py` files in the `plugins/` directory to add tabs, menu items, or hooks
- **Dismissable warning banners**: Erase and Write tabs warn about destructive operations; dismiss persists
- **Tooltips**: Hover help explaining why settings exist and when to use them

## Requirements

- Python 3.9+
- [mtkclient](https://github.com/bkerler/mtkclient) installed and on `sys.path`
- PySide6 >= 6.5
- pyusb (for automatic device detection)

## Installation

```bash
# Clone this repo
git clone https://github.com/sudotsu/mtk_gui.git
cd mtk_gui

# Install dependencies
pip install PySide6 mtkclient

# Run
python run.py
```

## Building the executable

```bash
pip install pyinstaller
pyinstaller mtk-gui.spec --noconfirm
```

The standalone executable will be at `dist/mtk-gui/mtk-gui.exe`. The entire `dist/mtk-gui/` folder is distributable.

## Project structure

```
mtk_gui/
├── app.py                  # QApplication entry point
├── main_window.py          # Signal wiring, operation handlers
├── constants.py            # App metadata, USB IDs, part types
├── backend/
│   ├── device_manager.py   # Connection state machine, threaded USB poll
│   ├── log_interceptor.py  # GuiSignalProxy for mtkclient logging bridge
│   ├── mtk_wrapper.py      # Clean facade over mtkclient DA operations
│   └── worker.py           # QThread worker with cancel support
├── ui/
│   ├── tabs/               # 12 tab widgets (one file each)
│   └── widgets/            # Reusable widgets (log panel, hex viewer, etc.)
├── plugins/                # Plugin base class and loader
└── theme/                  # QSS dark/light stylesheets
```

## Plugins

Create a Python file in `plugins/` that subclasses `MtkPlugin`:

```python
from mtk_gui.plugins.base_plugin import MtkPlugin

class MyPlugin(MtkPlugin):
    name = "My Plugin"
    version = "1.0"

    def register(self, ctx):
        ctx.add_menu_item("My Plugin/Do Thing", self.do_thing)

    def do_thing(self):
        print("Plugin action")
```

Plugins are loaded at startup from the app-local `plugins/` directory and from the user config directory (`%APPDATA%/mtk-gui/plugins` on Windows, `~/.config/mtk-gui/plugins` on Linux).

## License

GPLv3 — same as mtkclient.
