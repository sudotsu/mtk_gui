"""Provide safe, observable stdout/stderr for the windowed executable."""
import io
import logging
import sys
import threading
from collections import deque
from typing import Callable, Optional


class BufferedTextStream(io.TextIOBase):
    """Line-buffered text stream whose consumer can be attached after startup."""

    def __init__(self):
        super().__init__()
        self._callback: Optional[Callable[[str], None]] = None
        self._partial = ""
        self._pending = deque(maxlen=500)
        self._lock = threading.Lock()

    @property
    def encoding(self):
        return "utf-8"

    def writable(self):
        return True

    def isatty(self):
        return False

    def write(self, text):
        if text is None:
            return 0
        text = str(text)
        if not text:
            return 0

        ready = []
        with self._lock:
            self._partial += text.replace("\r", "\n")
            while "\n" in self._partial:
                line, self._partial = self._partial.split("\n", 1)
                if line.strip():
                    ready.append(line)
            callback = self._callback
            if callback is None:
                self._pending.extend(ready)

        if callback is not None:
            for line in ready:
                callback(line)
        return len(text)

    def flush(self):
        # Keep partial progress output coalesced until a newline arrives.
        return None

    def attach(self, callback: Callable[[str], None]):
        with self._lock:
            self._callback = callback
            pending = list(self._pending)
            self._pending.clear()
        for line in pending:
            callback(line)

    def detach(self):
        with self._lock:
            self._callback = None


def install_windowed_streams():
    """Replace the `None` streams created by a windowed PyInstaller build."""
    if sys.stdout is None:
        sys.stdout = BufferedTextStream()
    if sys.stderr is None:
        sys.stderr = BufferedTextStream()


def attach_streams(log_callback: Callable[[str, int], None]):
    """Forward captured lines to the GUI log after its Qt signals exist."""
    if isinstance(sys.stdout, BufferedTextStream):
        sys.stdout.attach(lambda line: log_callback(line, logging.INFO))
    if isinstance(sys.stderr, BufferedTextStream):
        sys.stderr.attach(lambda line: log_callback(line, logging.ERROR))


def detach_streams():
    """Release GUI callbacks during shutdown."""
    if isinstance(sys.stdout, BufferedTextStream):
        sys.stdout.detach()
    if isinstance(sys.stderr, BufferedTextStream):
        sys.stderr.detach()
