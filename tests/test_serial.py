"""Transport tests use loop:// and controlled failures; never physical ports."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
from time import monotonic, sleep

import pytest

from ProgramModules.Adaptors import SerialAdaptor
from ProgramModules.DataChannelManager import AdaptorThread, DataChannelManager
from ProgramModules.Protocols import FlgRelayProtocol
from ProgramModules.SafeModeController import SafeModeController
import ProgramModules.sharedObjects as app

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def safe_mode(monkeypatch):
    monkeypatch.setattr(app, "safeMode", SafeModeController())


def config_for(name):
    config = json.loads((ROOT / "sculptureDefinitions" / (name + ".json")).read_text())
    for adaptor in config["adaptors"].values():
        adaptor["ports"] = ["loop://"]
    return config


def read_exact(adaptor, count):
    result = b""
    deadline = monotonic() + 2
    while len(result) < count and monotonic() < deadline:
        result += adaptor.connection.read(count - len(result))
    assert len(result) == count
    return result


@pytest.mark.parametrize("name", ["aota", "serpent", "tympani"])
def test_initial_safe_mode_sends_every_governed_relay_off(name):
    config = config_for(name)
    manager = DataChannelManager(config)
    try:
        assert manager.flush()
        expected = {bus: b"" for bus in config["adaptors"]}
        for module in config["modules"].values():
            protocol = module["protocol"]
            if protocol["type"] == "flgRelay" and not protocol.get("ignoreSafeMode"):
                for row in protocol["mapping"]:
                    for board, relay in row:
                        expected[module["adaptor"]] += ("!%02X%s0." % (board, relay)).encode("ascii")
        for bus, data in expected.items():
            adaptor = manager.adaptors[bus].adaptor
            assert read_exact(adaptor, len(data)) == data
            assert adaptor.connection.in_waiting == 0
    finally:
        assert manager.stop()
    assert all(not writer.is_alive() for writer in manager.adaptors.values())
    assert app.safeMode.bindings == []


def test_loopback_exact_bytes_and_baud_update():
    manager = DataChannelManager(config_for("tympani"))
    try:
        assert manager.flush()
        for writer in manager.adaptors.values():
            writer.adaptor.connection.reset_input_buffer()
        app.safeMode.set(False)
        assert manager.send("poofers", [([0, 0], True), ([0, 0], False)])
        assert manager.send("leds", [("colorList", "9"), ("flash", True)])
        assert manager.flush()
        assert read_exact(manager.adaptors["flameBus"].adaptor, 12) == b"!0311.!0310."
        assert read_exact(manager.adaptors["ledBus"].adaptor, 16) == b"!140109.!140301."
        assert manager.updateSerialConnection("flameBus", {"baudrate": "38400"})
        assert manager.flush()
        state = manager.getCurrentStateData()["flameBus"]
        assert state["baudrate"] == 38400
        assert state["connected"]
        assert not state["deliveryPending"]
        assert state["writerError"] is None
    finally:
        manager.stop()


def test_safe_mode_cancels_queued_on_but_keeps_tympani_exemption():
    manager = DataChannelManager(config_for("tympani"))
    try:
        assert manager.flush()
        writer = manager.adaptors["flameBus"]
        writer.adaptor.connection.reset_input_buffer()
        # Hold the same lock the writer uses, making the transition deterministic.
        with app.safeMode.lock:
            app.safeMode.set(False)
            manager.send("poofers", [([0, 0], True)])
            manager.send("buttons", [("disableA", True)])
            app.safeMode.set(True)
            manager.send("poofers", [([0, 1], True)])
        assert manager.flush()
        data = writer.adaptor.connection.read(writer.adaptor.connection.in_waiting)
        packets = [packet + b"." for packet in data.split(b".") if packet]
        assert b"!0311." not in packets
        assert b"!0321." not in packets
        assert b"!0471." in packets  # Button-disable control remains exempt.
        assert packets[0] == b"!0310."
        assert b"!0320." in packets
    finally:
        manager.stop()


class FailingAdaptor:
    """Failure is controlled by events; accepted bytes are captured without hardware."""
    def __init__(self):
        self.configData = {"adaptorId": "fake"}
        self.frames = []
        self.fail = False
        self.failed = threading.Event()
        self.reconnectAllowed = threading.Event()
        self.reconnectAllowed.set()
        self.closed = False
        self.connectCount = 0
    def transmitData(self, data):
        assert isinstance(data, bytes)
        if self.fail:
            self.failed.set()
            return False
        self.frames.append(data)
        return True
    def connect(self):
        self.connectCount += 1
        if not self.reconnectAllowed.is_set():
            return False
        self.fail = False
        return True
    def stop(self): self.closed = True
    def getCurrentStateData(self): return {"connected": not self.fail}


def make_writer(adaptor):
    writer = AdaptorThread(adaptor)
    protocol = FlgRelayProtocol(None, {"mapping": [[[1, 1], [1, 2]]]})
    writer.registerChannel("flame", protocol)
    writer.start()
    return writer


def test_failed_off_retries_without_another_module_update():
    adaptor = FailingAdaptor()
    writer = make_writer(adaptor)
    try:
        app.safeMode.set(False)
        writer.send("flame", [([0, 0], True)])
        assert writer.flush()
        adaptor.reconnectAllowed.clear()
        adaptor.fail = True
        writer.send("flame", [([0, 0], False)])
        assert adaptor.failed.wait(1)
        assert not writer.flush(0.05)
        assert writer.getCurrentStateData()["deliveryPending"]
        adaptor.reconnectAllowed.set()
        assert writer.flush()
        assert adaptor.frames[-1] == b"!0110.!0120."
        assert not writer.getCurrentStateData()["deliveryPending"]
    finally:
        writer.stop()


def test_reconnect_discards_obsolete_on_history_and_resends_off_while_safe():
    adaptor = FailingAdaptor()
    writer = make_writer(adaptor)
    binding = app.safeMode.addBinding(writer.allOff)
    try:
        app.safeMode.set(False)
        adaptor.reconnectAllowed.clear()
        adaptor.fail = True
        writer.send("flame", [([0, 0], True)])
        assert adaptor.failed.wait(1)
        writer.send("flame", [([0, 0], False)])
        app.safeMode.set(True)
        adaptor.reconnectAllowed.set()
        assert writer.flush()
        assert adaptor.frames == [b"!0110.!0120."]
    finally:
        app.safeMode.removeBinding(binding)
        writer.stop()


def test_overflow_and_old_backlog_resynchronize_current_state(monkeypatch):
    for queue_limit, max_age in [(2, 10), (128, -1)]:
        monkeypatch.setattr(AdaptorThread, "QUEUE_LIMIT", queue_limit)
        monkeypatch.setattr(AdaptorThread, "MAX_QUEUE_AGE", max_age)
        adaptor = FailingAdaptor()
        writer = make_writer(adaptor)
        try:
            app.safeMode.set(False)
            with app.safeMode.lock:
                for value in [True, False, True, False]:
                    writer.send("flame", [([0, 0], value)])
            assert writer.flush()
            assert adaptor.frames == [b"!0110.!0120."]
        finally:
            writer.stop()


def test_idle_writer_blocks_and_shutdown_closes_after_join():
    adaptor = FailingAdaptor()
    writer = make_writer(adaptor)
    assert writer.flush()
    sleep(0.1)
    assert adaptor.frames == []
    assert adaptor.connectCount == 0
    assert writer.stop()
    assert not writer.is_alive()
    assert adaptor.closed
    assert writer.send("flame", [([0, 0], True)]) is False


def test_failed_shutdown_is_bounded_and_reports_undelivered_state():
    adaptor = FailingAdaptor()
    writer = make_writer(adaptor)
    adaptor.fail = True
    adaptor.reconnectAllowed.clear()
    writer.allOff()
    start = monotonic()
    assert writer.stop(timeout=0.1) is False
    assert monotonic() - start < 1
    assert adaptor.closed
    assert not writer.is_alive()


def test_serial_rejects_text_and_does_not_reopen_after_stop():
    adaptor = SerialAdaptor({"adaptorId": "loop", "ports": ["loop://"], "baudrate": 19200})
    try:
        with pytest.raises(TypeError):
            adaptor.transmitData("!0111.")
        assert adaptor.transmitData(b"!0111.")
        assert read_exact(adaptor, 6) == b"!0111."
    finally:
        adaptor.stop()
    assert not adaptor.connect()
    assert not adaptor.transmitData(b"!0111.")


def test_protocol_bytes_match_unchanged_python2_for_all_mapped_outputs():
    py2 = os.environ.get("PYTHON2") or shutil.which("python2")
    if not py2 and Path("C:/Python27/python.exe").exists():
        py2 = "C:/Python27/python.exe"
    if not py2:
        pytest.skip("Set PYTHON2 to run the original interpreter comparison")
    script = str(ROOT / "tools/record_protocol_bytes.py")
    old = subprocess.check_output([py2, script, str(ROOT / "py2")], text=True)
    new = subprocess.check_output([sys.executable, script, str(ROOT)], text=True)
    old_data, new_data = json.loads(old), json.loads(new)
    assert len(old_data) == 92
    assert new_data == old_data


def test_faulty_engine_callback_cannot_prevent_transport_safe_mode():
    def broken_callback():
        raise RuntimeError("engine callback failed")
    app.safeMode.addBinding(broken_callback)
    manager = DataChannelManager(config_for("aota"))
    try:
        assert manager.flush()
        adaptor = manager.adaptors["flameBus"].adaptor
        adaptor.connection.reset_input_buffer()
        with app.safeMode.lock:
            app.safeMode.set(False)
            manager.send("poofers", [([0, 0], True)])
            with pytest.raises(RuntimeError, match="engine callback failed"):
                app.safeMode.set(True)
        assert manager.flush()
        data = adaptor.connection.read(adaptor.connection.in_waiting)
        assert b"!0111." not in data
        assert data.startswith(b"!0110.")
    finally:
        manager.stop()


def test_partial_serial_write_is_failure_and_connection_closes():
    adaptor = SerialAdaptor({"adaptorId": "loop", "ports": ["loop://"], "baudrate": 19200})
    connection = adaptor.connection
    try:
        connection.write = lambda data: len(data) - 1
        assert adaptor.transmitData(b"!0110.") is False
        assert adaptor.connection is None
        assert not connection.is_open
        assert "Incomplete" in adaptor.lastError
    finally:
        adaptor.stop()


def test_synchronous_protocol_reports_failure_without_retaining_stale_on():
    adaptor = FailingAdaptor()
    protocol = FlgRelayProtocol(adaptor, {"mapping": [[[1, 1]]]})
    app.safeMode.set(False)
    adaptor.fail = True
    assert protocol.send([([0, 0], True)]) is False
    assert protocol.dataCache == b""
    app.safeMode.set(True)
    adaptor.fail = False
    assert protocol.send([([0, 0], False)]) is True
    assert adaptor.frames == [b"!0110."]


def test_serpent_stub_never_enqueues_bytes():
    manager = DataChannelManager(config_for("serpent"))
    try:
        assert manager.flush()
        adaptor = manager.adaptors["flameBus"].adaptor
        adaptor.connection.reset_input_buffer()
        app.safeMode.set(False)
        assert manager.send("leds", [([0, 0], (255, 0, 0)), ([0, 41], (0, 0, 0))])
        assert manager.flush()
        assert adaptor.connection.in_waiting == 0
    finally:
        manager.stop()
