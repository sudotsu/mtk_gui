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
    stream.attach_callback(seen.append)
    stream.write("50%\r100%\n")
    assert seen == ["50%", "100%"]


def test_blank_lines_are_dropped():
    stream = BufferedTextStream(None)
    seen = []
    stream.attach_callback(seen.append)
    stream.write("a\n\n   \nb\n")
    assert seen == ["a", "b"]


def test_output_before_attach_is_replayed():
    stream = BufferedTextStream(None)
    stream.write("early\n")
    seen = []
    stream.attach_callback(seen.append)
    assert seen == ["early"]


def test_dropped_startup_lines_are_reported_not_silent():
    """The old 500-line buffer discarded overflow with no trace."""
    stream = BufferedTextStream(None)
    overflow = stream._pending.maxlen + 5
    for i in range(overflow):
        stream.write(f"line{i}\n")
    seen = []
    stream.attach_callback(seen.append)
    assert "dropped from the startup buffer" in seen[0]
    assert seen[-1] == f"line{overflow - 1}"


def test_trailing_text_without_newline_is_flushed_on_detach():
    """mtkclient prints prompts with no trailing newline; they used to vanish."""
    stream = BufferedTextStream(None)
    seen = []
    stream.attach_callback(seen.append)
    stream.write("Waiting for device...")
    assert seen == []
    stream.detach_callback()
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

    stream.attach_callback(dead)
    stream.write("still fine\n")  # must not raise


def test_broken_passthrough_is_dropped_not_fatal():
    class Broken(io.StringIO):
        def write(self, _text):
            raise ValueError("console is gone")

    stream = BufferedTextStream(Broken())
    stream.write("x\n")  # must not raise
    assert stream._passthrough is None


def test_ansi_escapes_stripped_from_captured_lines():
    """mtkclient's colour codes must not reach the log file or GUI panel."""
    sink = io.StringIO()
    stream = BufferedTextStream(sink)
    captured = []
    stream.attach_callback(captured.append)

    stream.write("\x1b[31mStatus: Handshake failed, retrying...\x1b[0m\n")

    assert captured == ["Status: Handshake failed, retrying..."]


def test_ansi_escapes_preserved_on_passthrough():
    """The terminal keeps its colours; only the captured copy is stripped."""
    sink = io.StringIO()
    stream = BufferedTextStream(sink)
    stream.attach_callback(lambda _: None)

    coloured = "\x1b[31mred\x1b[0m\n"
    stream.write(coloured)

    assert sink.getvalue() == coloured


def test_line_of_only_ansi_codes_is_dropped():
    """A line that is nothing but escapes becomes blank and is discarded."""
    stream = BufferedTextStream(io.StringIO())
    captured = []
    stream.attach_callback(captured.append)

    stream.write("\x1b[2J\x1b[H\n")

    assert captured == []


def test_ansi_stripped_from_trailing_partial_line():
    """drain_partial() strips too, or a crash's last line arrives corrupted."""
    stream = BufferedTextStream(io.StringIO())
    captured = []
    stream.attach_callback(captured.append)

    stream.write("\x1b[31mno trailing newline")
    stream.drain_partial()

    assert captured == ["no trailing newline"]


def test_detach_refuses_to_release_the_buffer():
    """mtkclient's import-time stdout replacement must not disturb the tee.

    Regression test for a silent failure: detach() used to clear the GUI
    callback, so importing mtkclient severed the log panel and only the
    accident of DeviceManager constructing later restored it.
    """
    stream = BufferedTextStream(io.StringIO())
    captured = []
    stream.attach_callback(captured.append)

    # Exactly what mtkclient/Library/utils.py does, guard included.
    try:
        io.TextIOWrapper(stream.detach(), encoding="utf-8")
    except (io.UnsupportedOperation, AttributeError):
        pass

    stream.write("still wired\n")
    assert captured == ["still wired"], "GUI callback was severed by detach()"


def test_printing_from_inside_a_sink_does_not_recurse():
    """A sink that prints must not blow the stack.

    attach_streams() wires the GUI callback to a Qt signal; any handler on it
    that writes to stdout re-enters write(). Without a guard that recurses
    until RecursionError, which in a flashing tool means a hang mid-operation.
    """
    stream = BufferedTextStream(io.StringIO())
    seen = []

    def chatty(line):
        seen.append(line)
        stream.write("sink noise\n")  # re-enters write()

    stream.attach_callback(chatty)
    stream.write("original\n")

    assert seen == ["original"], f"expected no recursion, got {seen}"


def test_reentrant_write_still_reaches_the_real_stream():
    """The nested text is not lost -- it just is not fanned back out."""
    sink = io.StringIO()
    stream = BufferedTextStream(sink)

    def chatty(_line):
        stream.write("nested\n")

    stream.attach_callback(chatty)
    stream.write("outer\n")

    assert "outer" in sink.getvalue()
    assert "nested" in sink.getvalue()
