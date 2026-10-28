"""How connection starts, and why it starts immediately.

The MediaTek preloader accepts a handshake only in the few hundred
milliseconds after it enumerates. USB_POLL_INTERVAL_MS is 2000ms, so any
flow that waits for the poller to notice a device and *then* handshakes
misses the window essentially every time -- which is what the real-hardware
logs showed, endlessly. mtkclient retries the handshake internally, and that
retry loop is what actually catches the window, so connect starts it at once.
"""
import logging

import pytest

from mtk_gui.backend import device_manager as dm
from mtk_gui.backend.device_manager import DeviceManager, DeviceState

pytestmark = pytest.mark.usefixtures("qapp")


@pytest.fixture
def manager(qapp):
    m = DeviceManager()
    yield m
    m.begin_shutdown()
    m.stop_polling()


def test_connect_starts_the_handshake_immediately(manager, monkeypatch):
    """The whole fix: no waiting for detection before handshaking."""
    monkeypatch.setattr(dm, "_usb_device_identity", lambda: None)
    began = []
    monkeypatch.setattr(manager, "_begin_handshake", lambda: began.append(True))

    manager.connect_device()

    assert began == [True], "handshake must start on connect, not on detection"


def test_attached_device_is_told_to_reconnect(manager, monkeypatch):
    """A device already on the bus has missed its window; say so plainly."""
    monkeypatch.setattr(dm, "_usb_device_identity", lambda: (3, 20, 0x2000))
    monkeypatch.setattr(manager, "_begin_handshake", lambda: None)
    messages = []
    manager.log_message.connect(lambda msg, lvl: messages.append((msg, lvl)))

    manager.connect_device()

    assert any(
        "plug it back in" in msg and lvl == logging.WARNING
        for msg, lvl in messages
    ), f"expected a reconnect instruction, got {messages}"


def test_no_device_waits_without_a_warning(manager, monkeypatch):
    monkeypatch.setattr(dm, "_usb_device_identity", lambda: None)
    monkeypatch.setattr(manager, "_begin_handshake", lambda: None)
    messages = []
    manager.log_message.connect(lambda msg, lvl: messages.append((msg, lvl)))

    manager.connect_device()

    assert all(lvl != logging.WARNING for _m, lvl in messages)
    assert any("Connect the phone now" in m for m, _l in messages)


@pytest.mark.parametrize("state", [
    DeviceState.HANDSHAKING,
    DeviceState.CONNECTING_DA,
    DeviceState.CANCELLING,
    DeviceState.CONNECTED,
])
def test_connect_is_ignored_while_already_busy(manager, monkeypatch, state):
    """Re-entry must not stack a second handshake on a live one."""
    monkeypatch.setattr(dm, "_usb_device_identity", lambda: None)
    began = []
    monkeypatch.setattr(manager, "_begin_handshake", lambda: began.append(True))
    manager._state = state

    manager.connect_device()

    assert began == []


def test_explicit_serial_port_also_handshakes(manager, monkeypatch):
    monkeypatch.setattr(dm, "_usb_device_identity", lambda: None)
    began = []
    monkeypatch.setattr(manager, "_begin_handshake", lambda: began.append(True))
    manager.serial_port = "/dev/ttyACM0"

    manager.connect_device()

    assert began == [True]
