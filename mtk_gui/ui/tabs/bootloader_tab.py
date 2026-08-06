"""Bootloader tab — seccfg lock/unlock, vbmeta patch."""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QPushButton, QCheckBox, QComboBox,
)


class BootloaderTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        """
        Build the controls for bootloader state changes and vbmeta patching.
        """
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # ── Bootloader unlock/lock ────────────────────────
        bl_group = QGroupBox("Bootloader Lock State")
        bl_layout = QVBoxLayout(bl_group)

        self._critical_check = QCheckBox("Critical mode (use with caution)")
        bl_layout.addWidget(self._critical_check)

        btn_row = QHBoxLayout()
        self._unlock_btn = QPushButton("Unlock Bootloader")
        self._unlock_btn.setProperty("destructive", True)
        self._unlock_btn.setEnabled(False)
        btn_row.addWidget(self._unlock_btn)

        self._lock_btn = QPushButton("Lock Bootloader")
        self._lock_btn.setProperty("destructive", True)
        self._lock_btn.setEnabled(False)
        btn_row.addWidget(self._lock_btn)

        btn_row.addStretch()
        bl_layout.addLayout(btn_row)
        layout.addWidget(bl_group)

        # ── vbmeta patch ──────────────────────────────────
        vb_group = QGroupBox("vbmeta Patch")
        vb_layout = QVBoxLayout(vb_group)

        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("Patch Mode:"))
        self._vbmeta_mode = QComboBox()
        self._vbmeta_mode.addItem("Disable verity + verify", 3)
        self._vbmeta_mode.addItem("Disable verity only", 1)
        self._vbmeta_mode.addItem("Disable verify only", 2)
        mode_row.addWidget(self._vbmeta_mode, 1)
        vb_layout.addLayout(mode_row)

        vb_btn_row = QHBoxLayout()
        self._vbmeta_btn = QPushButton("Patch vbmeta")
        self._vbmeta_btn.setProperty("destructive", True)
        self._vbmeta_btn.setEnabled(False)
        vb_btn_row.addWidget(self._vbmeta_btn)
        vb_btn_row.addStretch()
        vb_layout.addLayout(vb_btn_row)

        layout.addWidget(vb_group)
        layout.addStretch()

    @property
    def unlock_button(self) -> QPushButton:
        """Provide the button used to unlock the bootloader.
        
        Returns:
            QPushButton: The bootloader unlock button.
        """
        return self._unlock_btn

    @property
    def lock_button(self) -> QPushButton:
        """Provides the button used to lock the bootloader.
        
        Returns:
            QPushButton: The bootloader lock button.
        """
        return self._lock_btn

    @property
    def vbmeta_button(self) -> QPushButton:
        """Return the button used to patch vbmeta."""
        return self._vbmeta_btn

    @property
    def critical_mode(self) -> bool:
        """Return whether critical mode is enabled."""
        return self._critical_check.isChecked()

    @property
    def vbmeta_mode(self) -> int:
        """Get the selected vbmeta patch mode.
        
        Returns:
        	int: The selected vbmeta patch mode.
        """
        return self._vbmeta_mode.currentData()
