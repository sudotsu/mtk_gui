"""The arm-then-handshake contract for MediaTek preloader connection.

The preloader accepts a handshake only in the few hundred milliseconds right
after it enumerates. These tests pin the two consequences: a phone already on
the bus must not be handshaked (its window is gone), and a freshly enumerated
one must be handshaked without waiting for a human.
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


def test_arming_with_phone_already_attached_does_not_handshake(manager, monkeypatch):
    """A device already on the bus has missed its window; instruct a replug."""
    monkeypatch.setattr(dm, "_usb_device_identity", lambda: (3, 20, 0x2000))
    monkeypatch.setattr(manager, "start_polling", lambda: None)
    began = []
    monkeypatch.setattr(manager, "_begin_handshake", lambda: began.append(True))

    messages = []
    manager.log_message.connect(lambda msg, lvl: messages.append((msg, lvl)))

    manager.connect_device()

    assert began == [], "must not handshake a stale enumeration"
    assert manager.state is DeviceState.DETECTING
    assert manager._stale_usb_identity == (3, 20, 0x2000)
    assert any(
        "plug it back in" in msg and lvl == logging.WARNING
        for msg, lvl in messages
    ), f"expected a replug instruction, got {messages}"


def test_arming_with_no_phone_waits_without_warning(manager, monkeypatch):
    monkeypatch.setattr(dm, "_usb_device_identity", lambda: None)
    monkeypatch.setattr(manager, "start_polling", lambda: None)

    manager.connect_device()

    assert manager.state is DeviceState.DETECTING
    assert manager._stale_usb_identity is None
    assert manager._connect_armed is True


def test_detection_while_armed_handshakes_immediately(manager, monkeypatch):
    """Detection must chain straight into the handshake, with no second click."""
    began = []
    monkeypatch.setattr(manager, "_begin_handshake", lambda: began.append(True))
    manager._connect_armed = True

    manager._on_usb_detected(0x2000, "")

    assert began == [True], "armed detection must handshake at once"


def test_detection_while_not_armed_only_reports(manager, monkeypatch):
    """Passive detection must not start connecting on its own."""
    began = []
    monkeypatch.setattr(manager, "_begin_handshake", lambda: began.append(True))
    manager._connect_armed = False

    manager._on_usb_detected(0x2000, "")

    assert began == []
    assert manager.state is DeviceState.PRELOADER


def test_cancelling_detection_disarms(manager, monkeypatch):
    """A queued detection must not connect after the user cancelled."""
    monkeypatch.setattr(dm, "_usb_device_identity", lambda: None)
    monkeypatch.setattr(manager, "start_polling", lambda: None)
    monkeypatch.setattr(manager, "stop_polling", lambda: None)
    manager.connect_device()
    assert manager._connect_armed is True

    manager.cancel_connection()

    assert manager._connect_armed is False
    assert manager.state is DeviceState.DISCONNECTED


def test_shutdown_disarms(manager):
    manager._connect_armed = True
    manager.begin_shutdown()
    assert manager._connect_armed is False
