"""Hex display widget for memory peek results."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QPlainTextEdit


class HexViewer(QPlainTextEdit):
    """Displays binary data in hex dump format."""

    BYTES_PER_LINE = 16

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        font = QFont("Consolas", 9)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.setFont(font)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)

    def set_data(self, data: bytes, base_addr: int = 0):
        """
        Display byte data as a fixed-width hexadecimal dump with addresses and ASCII representation.
        
        Parameters:
            data (bytes): Byte sequence to display.
            base_addr (int): Address assigned to the first byte.
        """
        lines = []
        for offset in range(0, len(data), self.BYTES_PER_LINE):
            chunk = data[offset:offset + self.BYTES_PER_LINE]
            addr = base_addr + offset

            hex_parts = []
            for i, b in enumerate(chunk):
                hex_parts.append(f"{b:02X}")
                if i == 7:
                    hex_parts.append("")  # extra space at midpoint

            hex_str = " ".join(hex_parts)
            # Pad to fixed width
            hex_str = hex_str.ljust(3 * self.BYTES_PER_LINE + 1)

            ascii_str = "".join(
                chr(b) if 0x20 <= b < 0x7F else "."
                for b in chunk
            )

            lines.append(f"{addr:08X}  {hex_str} |{ascii_str}|")

        self.setPlainText("\n".join(lines))

    def clear_data(self):
        """Clear the displayed hexadecimal data."""
        self.clear()
