"""Real worker cleanup and controller/web integration, using loopback serial only."""
import json
from queue import Queue
import socket
import threading
from time import monotonic, sleep
from urllib.request import Request, urlopen

import pytest
from werkzeug.serving import make_server

import flaskServer as web
from ProgramModules import Adaptors, SculptureModules
from ProgramModules.Messenger import Messenger
from ProgramModules.Runtime import engineLock, failureEvent
from ProgramModules.SafeModeController import SafeModeController
from ProgramModules.Timers import Timer
import ProgramModules.sharedObjects as app
from SculptureController import ControllerStopped, SculptureController


@pytest.fixture
def controller(monkeypatch):
    monkeypatch.setattr(app, 'safeMode', SafeModeController())
    monkeypatch.setattr(app, 'messenger', Messenger())
    failureEvent.clear()
    web.stopping.clear()
    controller = SculptureController()
    for config in controller.sculptureDefinitions.values():
        for adaptor in config['adaptors'].values():
            adaptor['ports'] = ['loop://']
    monkeypatch.setattr(web, 'sculpture', controller)
    yield controller
    web.stopping.set()
    web.closeStreams()
    controller.stop()
    assert not Timer.activeTimers
    assert not app.safeMode.bindings
    assert not failureEvent.is_set()
    web.stopping.clear()


def test_reload_all_sculptures_stops_old_patterns_inputs_and_manual_off_timers(controller):
    old_workers = []
    old_osc_port = None
    for name in ('aota', 'serpent', 'tympani', 'aota'):
        web.executeCommand(['loadSculpture', name])
        assert all(not worker.is_alive() for worker in old_workers)
        assert controller.dataChannelManager.flush()
        assert app.safeMode.isSet()
        if old_osc_port is not None:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
                probe.bind(('127.0.0.1', old_osc_port))
        for module_id, module in controller.sculptureModules.items():
            for pattern in getattr(module, 'availablePatternNames', []):
                controller.doCommand(['addPattern', module_id, pattern])
        controller.setSafeMode(False)
        controller.doCommand(['setItemState', 'poofers', [0, 0], True])
        controller.addGlobalInput({'type': 'multi', 'subType': 'osc', 'host': '127.0.0.1', 'port': 0})
        osc = controller.globalInputs[next(iter(controller.globalInputs))]
        old_osc_port = osc.server.server.server_address[1]
        sleep(0.25)  # Exercise real pattern callbacks before the next reload.
        json.dumps(controller.getCurrentStateData())
        assert not failureEvent.is_set()
        old_workers = [timer.thread for timer in Timer.activeTimers]
        old_workers += list(controller.dataChannelManager.adaptors.values()) + [osc.server]
        governed_modules = sum(module.safeModeBinding is not None for module in controller.sculptureModules.values())
        assert len(app.safeMode.bindings) == 1 + governed_modules
        assert len(app.messenger.channels['outputChanged']['bindings']) == 1
    assert controller.stop()
    assert all(not worker.is_alive() for worker in old_workers)
    assert app.messenger.channels == {}
    with pytest.raises(ControllerStopped):
        controller.doCommand(['loadSculpture', 'aota'])


@pytest.mark.parametrize('name', ['aota', 'serpent', 'tympani'])
def test_safe_mode_suppresses_controller_outputs_through_shutdown(controller, monkeypatch, name):
    writes = []
    transmit = Adaptors.SerialAdaptor.transmitData
    def record_write(adaptor, data):
        writes.append(data)
        return transmit(adaptor, data)
    monkeypatch.setattr(Adaptors.SerialAdaptor, 'transmitData', record_write)
    controller.loadSculpture(name)
    manager = controller.dataChannelManager
    assert manager.flush()
    # Startup may send only controls explicitly configured to ignore safe mode.
    exempt = set()
    for module in controller.sculptureConfig['modules'].values():
        protocol = module['protocol']
        if protocol.get('ignoreSafeMode'):
            for board, relay in protocol['mapping'].values():
                for value in (0, 1):
                    exempt.add(('!%02X%s%s' % (board, relay, value)).encode('ascii'))
    assert all(packet in exempt for data in writes for packet in data.split(b'.') if packet)
    writes.clear()
    pattern_id = controller.doCommand(['addPattern', 'poofers', 'AllPoof'])
    pattern = controller.sculptureModules['poofers'].patterns[pattern_id]
    instance, index = pattern.inputs.getInputAssignment('poofButton')
    controller.setInputValue(instance, True, index)
    controller.doCommand(['setItemState', 'poofers', [0, 0], True])
    controller.doCommand(['setItemState', 'poofers', [0, 0], False])
    assert manager.flush()
    assert writes == []
    controller.setSafeMode(False)
    controller.doCommand(['setItemState', 'poofers', [0, 0], True])
    assert manager.flush()
    assert writes
    with engineLock, app.safeMode.lock:
        writes.clear()
        controller.setSafeMode(True)
    manager.allOff()
    assert manager.flush()
    assert controller.stop()
    assert writes == []


def test_removing_an_active_pattern_turns_its_outputs_off(controller):
    controller.loadSculpture('aota')
    pattern_id = controller.doCommand(['addPattern', 'poofers', 'AllPoof'])
    module = controller.sculptureModules['poofers']
    pattern = module.patterns[pattern_id]
    controller.setSafeMode(False)
    instance, index = pattern.inputs.getInputAssignment('poofButton')
    controller.setInputValue(instance, True, index)
    assert any(any(row) for row in module.currentOutputState)
    controller.doCommand(['removePattern', 'poofers', pattern_id])
    assert not any(any(row) for row in module.currentOutputState)
    assert not pattern.timer.is_alive()
    assert controller.dataChannelManager.flush()


def test_chase_spacing_and_reverse_with_three_pulses(controller):
    controller.loadSculpture('tympani')
    with engineLock:  # Keep real timer callbacks from advancing this observed step.
        pattern_id = controller.doCommand(['addPattern', 'poofers', 'Chase'])
        pattern = controller.sculptureModules['poofers'].patterns[pattern_id]
        for channel, value in [('numberOn', 1), ('numberPulses', 3)]:
            instance, index = pattern.inputs.getInputAssignment(channel)
            controller.setInputValue(instance, value, index)
        # Fourteen outputs split into three pulses: spacing must be four outputs.
        assert [col for col in range(14) if pattern.getState(0, col)] == [0, 4, 8]
        instance, index = pattern.inputs.getInputAssignment('reverse')
        controller.setInputValue(instance, True, index)
        assert [col for col in range(14) if pattern.getState(0, col)] == [5, 9, 13]


def test_timer_refresh_interval_and_self_stop():
    fired = Queue()
    timer = Timer(False, 1000, lambda: fired.put(monotonic()))
    try:
        timer.changeInterval(50)
        start = monotonic()
        timer.refresh()
        assert fired.get(timeout=1) - start >= 0.035
        assert timer.is_alive()  # A single timer remains available for refresh.
        timer.refresh()
        fired.get(timeout=1)
    finally:
        timer.stop()
    done = threading.Event()
    def stop_self():
        self_timer.stop()
        done.set()
    self_timer = Timer(False, 20, stop_self)
    try:
        assert done.wait(timeout=1)
    finally:
        self_timer.stop()
    assert not self_timer.is_alive()


def test_stopping_timer_waiting_for_controller_lock_does_not_deadlock():
    fired = threading.Event()
    with engineLock:
        timer = Timer(True, 1, fired.set)
        sleep(0.05)
        start = monotonic()
        timer.stop()
        assert monotonic() - start < 1
    assert not fired.is_set()
    assert not timer.is_alive()


def test_partial_module_load_cleans_up_timers_serial_and_bindings(controller, monkeypatch):
    writers = []
    real_factory = Adaptors.SerialAdaptor
    def recording_factory(config):
        adaptor = real_factory(config)
        writers.append(adaptor)
        return adaptor
    def broken_module(config):
        Timer(True, 1000, lambda: None)
        raise RuntimeError('module construction failed')
    monkeypatch.setattr(Adaptors, 'SerialAdaptor', recording_factory)
    monkeypatch.setattr(SculptureModules, 'PooferModule', broken_module)
    with pytest.raises(RuntimeError, match='module construction failed'):
        controller.loadSculpture('aota')
    assert writers and all(adaptor.connection is None for adaptor in writers)
    assert not Timer.activeTimers
    assert not app.safeMode.bindings
    assert controller.sculptureConfig is False


def test_partial_serial_initialization_closes_open_ports(controller, monkeypatch):
    adaptors = []
    real_factory = Adaptors.SerialAdaptor
    def recording_factory(config):
        adaptor = real_factory(config)
        adaptors.append(adaptor)
        return adaptor
    monkeypatch.setattr(Adaptors, 'SerialAdaptor', recording_factory)
    controller.sculptureDefinitions['aota']['modules']['poofers']['protocol']['type'] = 'missing'
    with pytest.raises(AttributeError):
        controller.loadSculpture('aota')
    assert adaptors and all(adaptor.connection is None for adaptor in adaptors)
    assert not app.safeMode.bindings


def test_http_load_state_sse_and_file_paths(controller, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    assert set(SculptureController().sculptureDefinitions) == {'aota', 'serpent', 'tympani'}
    with web.flaskApp.test_client() as client:
        with client.get('/') as page:
            assert page.status_code == 200
        assert client.post('/doCommand', json=[]).status_code == 400
        assert client.post('/doCommand', json=['loadSculpture', 'aota']).status_code == 200
        assert client.post('/doCommand', json=['addPattern', 'poofers', 'AllPoof']).status_code == 200
        assert client.get('/getData').json['safeMode'] is True
        response = client.get('/dataStream', buffered=False)
        try:
            stream = iter(response.response)
            assert next(stream) == b': connected\n\n'
            assert client.post('/doCommand', json=['setSafeMode', False]).status_code == 200
            assert client.post('/doCommand', json=['setItemState', 'poofers', [0, 0], True]).status_code == 200
            event = json.loads(next(stream).decode().removeprefix('data: '))
            assert event['outputChanged'][0]['moduleId'] == 'poofers'
        finally:
            response.close()
        assert web.serverSentEventStreams == []
        web.stopping.set()
        assert client.post('/doCommand', json=['setSafeMode', False]).status_code == 503


def test_threaded_http_serves_commands_while_sse_is_open(controller):
    web.executeCommand(['loadSculpture', 'aota'])  # Same helper used for --sculpture.
    server = make_server('127.0.0.1', 0, web.flaskApp, threaded=True)
    thread = threading.Thread(target=server.serve_forever, kwargs={'poll_interval': 0.05})
    thread.start()
    base = 'http://127.0.0.1:%s' % server.server_port
    try:
        with urlopen(base + '/dataStream', timeout=2) as stream:
            assert stream.readline() == b': connected\n'
            assert stream.readline() == b'\n'
            for command in [['setSafeMode', False], ['setItemState', 'poofers', [0, 0], True]]:
                request = Request(base + '/doCommand', data=json.dumps(command).encode(),
                                  headers={'Content-Type': 'application/json'})
                with urlopen(request, timeout=2) as response:
                    assert response.status == 200
            event = json.loads(stream.readline().decode().removeprefix('data: '))
            assert event['outputChanged'][0]['data'][0] == [[0, 0], True]
            with urlopen(base + '/getData', timeout=2) as response:
                assert json.load(response)['sculptureId'] == 'aota'
    finally:
        web.closeStreams()
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()
    assert not thread.is_alive()


def test_http_state_waits_for_a_whole_timer_callback(controller):
    controller.loadSculpture('aota')
    controller.setSafeMode(False)
    module = controller.sculptureModules['poofers']
    entered = threading.Event()
    release = threading.Event()
    finished = threading.Event()
    states = Queue()
    def update_outputs():
        module.setItemState([0, 0], True)
        entered.set()
        release.wait(timeout=2)
        module.setItemState([0, 1], True)
    def read_state():
        with web.flaskApp.test_client() as client:
            states.put(client.get('/getData').json)
        finished.set()
    timer = Timer(False, 10, update_outputs, stopWhenDone=True)
    reader = threading.Thread(target=read_state)
    try:
        assert entered.wait(timeout=2)
        reader.start()
        assert not finished.wait(timeout=0.05)
        release.set()
        assert finished.wait(timeout=2)
        assert states.get()['modules']['poofers']['currentOutputState'][0][:2] == [True, True]
    finally:
        release.set()
        timer.stop()
        if reader.ident is not None:
            reader.join(timeout=2)
