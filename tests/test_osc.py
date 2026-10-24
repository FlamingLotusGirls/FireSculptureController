"""Exercise OSC routing and listener lifecycle with local UDP packets."""
from queue import Queue
import threading
from time import monotonic

import pytest
from pythonosc.osc_bundle_builder import IMMEDIATELY, OscBundleBuilder
from pythonosc.osc_message_builder import OscMessageBuilder
from pythonosc.udp_client import SimpleUDPClient

from ProgramModules.InputManager import InputManager
from ProgramModules.Messenger import Messenger
import ProgramModules.sharedObjects as app


@pytest.fixture
def make_input(monkeypatch):
    monkeypatch.setattr(app, "messenger", Messenger())
    manager = InputManager()
    created = []

    def create(**settings):
        params = {"type": "multi", "subType": "osc", "host": "127.0.0.1", "port": 0}
        params.update(settings)
        instance_id = manager.createNewInput(params)
        source = manager.getInputObj(instance_id)
        created.append(source)
        return source

    yield create
    for source in reversed(created):
        source.stop()
        assert not source.server.is_alive()
        assert source.server.server.socket.fileno() == -1
        # Timer joins belong to the later lifecycle phase; keep the test isolated now.
        for output in source.outParams:
            timer = getattr(output, "timer", False)
            if timer:
                timer.thread.join(timeout=1)
                assert not timer.thread.is_alive()


def observe_outputs(source):
    events = Queue()
    for index in range(len(source.outParams)):
        app.messenger.addBinding(
            "output%s_%s" % (source.getId(), index),
            lambda index=index: events.put((index, source.getValue(index))),
        )
    return events


def client_for(source):
    port = source.server.server.server_address[1]
    return SimpleUDPClient("127.0.0.1", port)


def test_udp_routes_each_pulse_toggle_and_value_to_its_configured_output(make_input):
    source = make_input(callbackAddresses={
        "pulse": ["/button/left", "/button/right"],
        "toggle": ["/switch/left", "/switch/right"],
        "value": ["/level/left", "/level/right"],
    })
    events = observe_outputs(source)
    with client_for(source) as client:
        for address, value, index in [
            ("/button/right", 1.0, 1),
            ("/button/left", "1", 0),
        ]:
            client.send_message(address, value)
            assert events.get(timeout=2) == (index, True)
            assert events.get(timeout=2) == (index, False)  # Existing pulse auto-OFF.
        for address, value, index, expected in [
            ("/switch/right", 1.0, 3, True),
            ("/switch/left", 1, 2, True),
            ("/switch/right", 0.0, 3, False),
            ("/level/right", 42.5, 5, 42.5),
            ("/level/left", "17.25", 4, 17.25),
        ]:
            client.send_message(address, value)
            assert events.get(timeout=2) == (index, expected)
    assert [source.getValue(i) for i in range(6)] == [False, False, True, False, 17.25, 42.5]
    assert events.empty()


def test_gui_address_strings_and_string_port_preserve_output_order(make_input):
    source = make_input(
        port="0", pulseAddressString=" /hit/first   /hit/second ",
        toggleAddressString="/enabled", valueAddressString="/level",
    )
    state = source.getCurrentStateData()
    assert type(state["port"]) is int
    assert [output["description"] for output in state["outParams"]] == [
        "Pulse /hit/first", "Pulse /hit/second", "Toggle /enabled", "Value /level",
    ]
    events = observe_outputs(source)
    with client_for(source) as client:
        client.send_message("/level", 32)
        assert events.get(timeout=2) == (3, 32)


def test_empty_gui_address_lists_do_not_restore_default_handlers(make_input):
    source = make_input(pulseAddressString="", toggleAddressString="", valueAddressString="")
    assert source.outParams == []
    assert source.getCurrentStateData()["callbackAddresses"] == {"pulse": [], "toggle": [], "value": []}


def test_default_host_and_addresses_are_available(make_input):
    import Inputs.Osc as osc

    assert osc.inputTypes["osc multi"]["host"] == "0.0.0.0"
    source = make_input(host=osc.inputTypes["osc multi"]["host"])
    assert source.server.server.server_address[0] == "0.0.0.0"
    events = observe_outputs(source)
    with client_for(source) as client:
        client.send_message("/1/value3", 25)
        assert events.get(timeout=2) == (5, 25)


def test_empty_and_unknown_messages_are_ignored_and_bundles_keep_order(make_input):
    source = make_input(callbackAddresses={"pulse": [], "toggle": [], "value": ["/a", "/b"]})
    events = observe_outputs(source)
    with client_for(source) as client:
        client.send_message("/a", [])
        client.send_message("/unknown", 99)
        bundle = OscBundleBuilder(IMMEDIATELY)
        for address, value in [("/b", 12.5), ("/a", 50), ("/b", 60)]:
            message = OscMessageBuilder(address=address)
            message.add_arg(value)
            bundle.add_content(message.build())
        client.send(bundle.build())
        assert [events.get(timeout=2) for _ in range(3)] == [(1, 12.5), (0, 50), (1, 60)]
    assert events.empty()


def test_idle_listener_stops_and_repeatedly_releases_the_same_port(make_input):
    port = 0
    for _ in range(3):
        source = make_input(port=port)
        port = source.server.server.server_address[1]
        start = monotonic()
        source.stop()
        assert monotonic() - start < 1
        assert not source.server.is_alive()
        assert source.server.server.socket.fileno() == -1
        source.stop()  # Repeated cleanup is safe.


def test_stop_waits_for_an_active_callback_before_releasing_the_listener(make_input):
    source = make_input(callbackAddresses={"pulse": [], "toggle": [], "value": ["/value"]})
    entered = threading.Event()
    release = threading.Event()
    stopped = threading.Event()

    def callback():
        entered.set()
        release.wait(timeout=2)

    def stop():
        source.stop()
        stopped.set()

    app.messenger.addBinding("output%s_0" % source.getId(), callback)
    stopper = threading.Thread(target=stop)
    try:
        with client_for(source) as client:
            client.send_message("/value", 1)
            assert entered.wait(timeout=2)
            stopper.start()
            assert not stopped.wait(timeout=0.05)
            release.set()
            assert stopped.wait(timeout=2)
    finally:
        release.set()
        if stopper.ident is not None:
            stopper.join(timeout=2)
    assert not source.server.is_alive()
