"""Behaviour of the stdout/stderr tee that carries mtkclient output to the GUI."""
import io
import logging

import pytest

from mtk_gui.backend import stdio_bridge
from mtk_gui.backend.stdio_bridge import BufferedTextStream


@pytest.fixture(autouse=True)
def _clear_sinks():
    """Keep module-level sinks from leaking between tests."""
    with stdio_bridge._sink_lock:
        saved = list(stdio_bridge._line_sinks)
        stdio_bridge._line_sinks.clear()
    yield
    with stdio_bridge._sink_lock:
        stdio_bridge._line_sinks[:] = saved


def test_passthrough_receives_text_verbatim():
    """The real terminal must still see carriage returns, or progress bars break."""
    sink = io.StringIO()
    stream = BufferedTextStream(sink)
    stream.write("50%\r100%\n")
    assert sink.getvalue() == "50%\r100%\n"


def test_gui_sees_carriage_returns_as_separate_lines():
    stream = BufferedTextStream(None)
    seen = []
    stream.attach(seen.append)
    stream.write("50%\r100%\n")
    assert seen == ["50%", "100%"]


def test_blank_lines_are_dropped():
    stream = BufferedTextStream(None)
    seen = []
    stream.attach(seen.append)
    stream.write("a\n\n   \nb\n")
    assert seen == ["a", "b"]


def test_output_before_attach_is_replayed():
    stream = BufferedTextStream(None)
    stream.write("early\n")
    seen = []
    stream.attach(seen.append)
    assert seen == ["early"]


def test_dropped_startup_lines_are_reported_not_silent():
    """The old 500-line buffer discarded overflow with no trace."""
    stream = BufferedTextStream(None)
    overflow = stream._pending.maxlen + 5
    for i in range(overflow):
        stream.write(f"line{i}\n")
    seen = []
    stream.attach(seen.append)
    assert "dropped from the startup buffer" in seen[0]
    assert seen[-1] == f"line{overflow - 1}"


def test_trailing_text_without_newline_is_flushed_on_detach():
    """mtkclient prints prompts with no trailing newline; they used to vanish."""
    stream = BufferedTextStream(None)
    seen = []
    stream.attach(seen.append)
    stream.write("Waiting for device...")
    assert seen == []
    stream.detach()
    assert seen == ["Waiting for device..."]


def test_line_sinks_receive_lines_with_no_gui_attached():
    stream = BufferedTextStream(None, logging.ERROR)
    captured = []
    stdio_bridge.add_line_sink(lambda line, level: captured.append((line, level)))
    stream.write("boom\n")
    assert captured == [("boom", logging.ERROR)]


def test_dead_gui_receiver_does_not_break_printing():
    """A deleted QObject raises RuntimeError; print() must not propagate it."""
    stream = BufferedTextStream(None)

    def dead(_line):
        raise RuntimeError("Internal C++ object already deleted")

    stream.attach(dead)
    stream.write("still fine\n")  # must not raise


def test_broken_passthrough_is_dropped_not_fatal():
    class Broken(io.StringIO):
        def write(self, _text):
            raise ValueError("console is gone")

    stream = BufferedTextStream(Broken())
    stream.write("x\n")  # must not raise
    assert stream._passthrough is None
