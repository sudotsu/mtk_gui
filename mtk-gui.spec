# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for MTK-GUI."""
import os
import sys
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

block_cipher = None

# Collect all mtkclient submodules — many are loaded dynamically
mtkclient_hiddenimports = collect_submodules('mtkclient')
usb_hiddenimports = collect_submodules('usb')

# Collect mtkclient data files (DA loaders, configs, etc.)
mtkclient_datas = collect_data_files('mtkclient')

a = Analysis(
    ['run.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('mtk_gui/theme/*.qss', 'mtk_gui/theme'),
        ('plugins', 'plugins'),
    ] + mtkclient_datas,
    hiddenimports=mtkclient_hiddenimports + usb_hiddenimports + [
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='mtk-gui',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # windowed app, no console
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='mtk-gui',
)
