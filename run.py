#!/usr/bin/env python3
"""Entry point for MTK-GUI."""
import sys
import os

from mtk_gui.backend.stdio_bridge import install_windowed_streams

install_windowed_streams()

# Ensure our package dir is first so mtkclient's mtk_gui.py doesn't shadow us
app_dir = os.path.dirname(os.path.abspath(__file__))
if app_dir not in sys.path:
    sys.path.insert(0, app_dir)

# Add mtkclient to path if installed locally (after our dir, so our mtk_gui package wins)
mtkclient_path = os.path.join(os.path.dirname(app_dir), "mtkclient")
if os.path.isdir(mtkclient_path) and mtkclient_path not in sys.path:
    sys.path.append(mtkclient_path)

from mtk_gui.app import main

if __name__ == "__main__":
    main()
