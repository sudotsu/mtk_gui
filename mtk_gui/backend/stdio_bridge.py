"""Provide safe, observable stdout/stderr for the GUI and the windowed executable.

This bridge is the transport that carries mtkclient's output into the GUI log
panel. mtkclient's ``LogBase`` metaclass runs ``logging.config.dictConfig`` at
class-definition time with a handler bound to ``ext://sys.stdout``, so the
stream object installed here must already be in place before any mtkclient
module is imported. See ``mtk_gui/app.py`` for the install site and the import
ordering that depends on it.
"""
import io
import logging
import sys
import threading
from collections import deque
from collections.abc import Callable

# Sinks that receive every captured line regardless of GUI attachment, so that
# output survives a crash that takes the log panel with it.
_line_sinks: list[Callable[[str, int], None]] = []
_sink_lock = threading.Lock()


def add_line_sink(sink: Callable[[str, int], None]):
    """Register a consumer for every captured line, as (message, level)."""
    with _sink_lock:
        _line_sinks.append(sink)


def _emit_to_sinks(line: str, level: int):
    with _sink_lock:
        sinks = list(_line_sinks)
    for sink in sinks:
        try:
            sink(line, level)
        except Exception:
            pass


class BufferedTextStream(io.TextIOBase):
    """Line-buffered tee: forwards to the real stream and to the GUI.

    Writes reach ``passthrough`` unmodified so terminal behaviour (including
    carriage-return progress bars) is preserved. A separate line-split copy,
    with ``\\r`` normalised to ``\\n``, goes to the GUI callback and to any
    registered line sink.
    """

    def __init__(self, passthrough=None, level: int = logging.INFO):
        super().__init__()
        self._passthrough = passthrough
        self._level = level
        self._callback: Callable[[str], None] | None = None
        self._partial = ""
        self._pending = deque(maxlen=2000)
        self._dropped = 0
        self._lock = threading.Lock()

    @property
    def encoding(self):
        return getattr(self._passthrough, "encoding", None) or "utf-8"

    def writable(self):
        return True

    def isatty(self):
        try:
            return bool(self._passthrough and self._passthrough.isatty())
        except Exception:
            return False

    def write(self, text):
        if text is None:
            return 0
        text = str(text)
        if not text:
            return 0

        self._write_passthrough(text)

        ready = []
        with self._lock:
            self._partial += text.replace("\r", "\n")
            while "\n" in self._partial:
                line, self._partial = self._partial.split("\n", 1)
                if line.strip():
                    ready.append(line)
            callback = self._callback
            if callback is None:
                for line in ready:
                    if len(self._pending) == self._pending.maxlen:
                        self._dropped += 1
                    self._pending.append(line)

        for line in ready:
            _emit_to_sinks(line, self._level)
        if callback is not None:
            self._deliver(callback, ready)
        return len(text)

    def _write_passthrough(self, text: str):
        if self._passthrough is None:
            return
        try:
            self._passthrough.write(text)
            self._passthrough.flush()
        except Exception:
            self._passthrough = None

    @staticmethod
    def _deliver(callback: Callable[[str], None], lines):
        """Push lines to the GUI, tolerating a destroyed Qt receiver.

        The callback runs outside the lock to avoid deadlocking against a GUI
        thread that is itself printing, which means ``detach()`` can race an
        in-flight delivery during shutdown. Swallowing the resulting error is
        deliberate: the alternative is an exception raised out of an arbitrary
        ``print()`` on a worker thread.
        """
        for line in lines:
            try:
                callback(line)
            except Exception:
                return

    def flush(self):
        if self._passthrough is not None:
            try:
                self._passthrough.flush()
            except Exception:
                self._passthrough = None
        return

    def drain_partial(self):
        """Emit any trailing text that was never terminated by a newline."""
        with self._lock:
            line, self._partial = self._partial, ""
            callback = self._callback
        if not line.strip():
            return
        _emit_to_sinks(line, self._level)
        if callback is not None:
            self._deliver(callback, [line])

    def attach(self, callback: Callable[[str], None]):
        with self._lock:
            self._callback = callback
            pending = list(self._pending)
            dropped = self._dropped
            self._pending.clear()
            self._dropped = 0
        if dropped:
            pending.insert(
                0, f"[{dropped} earlier line(s) dropped from the startup buffer]")
        self._deliver(callback, pending)

    def detach(self):
        self.drain_partial()
        with self._lock:
            self._callback = None


def install_windowed_streams():
    """Install the tee on stdout/stderr.

    Must run before any mtkclient import: mtkclient binds a logging
    StreamHandler to ``sys.stdout`` at import time, so a stream installed after
    that is bypassed entirely. Safe to call more than once.
    """
    if not isinstance(sys.stdout, BufferedTextStream):
        sys.stdout = BufferedTextStream(sys.stdout, logging.INFO)
    if not isinstance(sys.stderr, BufferedTextStream):
        sys.stderr = BufferedTextStream(sys.stderr, logging.ERROR)


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
