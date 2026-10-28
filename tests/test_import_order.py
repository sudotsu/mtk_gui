"""Pins the load-bearing import order in mtk_gui/app.py.

mtkclient's LogBase metaclass runs logging.config.dictConfig() at class
definition time, installing a StreamHandler bound to whatever sys.stdout is at
that moment. If our tee is installed after the first mtkclient import, that
handler holds the *original* stdout and none of mtkclient's log output ever
reaches the GUI log panel. That was the state of the code before Phase 0, and
it is silent when broken, so it gets a test.

Runs in a subprocess because the assertion is about import-time side effects.
"""
import subprocess
import sys
import textwrap

CHECK = textwrap.dedent(
    """
    import logging, sys
    import mtk_gui.app  # noqa: F401  - imported for its side effects
    from mtk_gui.backend.stdio_bridge import BufferedTextStream

    assert isinstance(sys.stdout, BufferedTextStream), "tee not installed on stdout"
    assert isinstance(sys.stderr, BufferedTextStream), "tee not installed on stderr"

    # mtkclient must have bound its StreamHandler to our tee, not the original.
    streams = [
        getattr(h, "stream", None)
        for h in logging.getLogger().handlers
        if isinstance(h, logging.StreamHandler)
    ]
    assert streams, "mtkclient installed no root StreamHandler; assumption changed"
    assert any(isinstance(s, BufferedTextStream) for s in streams), (
        "mtkclient's log handler is bound to a stream that is not our tee; "
        "install_windowed_streams() ran too late in mtk_gui/app.py"
    )
    print("OK")
    """
)


def test_mtkclient_logging_is_bound_to_our_stream():
    result = subprocess.run(
        [sys.executable, "-c", CHECK],
        capture_output=True,
        text=True,
        env={"QT_QPA_PLATFORM": "offscreen", "PATH": "/usr/bin:/bin"},
    )
    assert result.returncode == 0, result.stderr
    assert "OK" in result.stdout
