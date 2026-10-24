"""Subprocess harness: real CLI/server/lifecycle, with serial redirected to loop://."""
import _thread
import json
from pathlib import Path
import signal
import sys
from threading import Thread, enumerate as threads

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from ProgramModules import Adaptors
from ProgramModules.Timers import Timer
import ProgramModules.sharedObjects as app

open_serial = Adaptors.serial.serial_for_url
def loop_serial(port, *args, **kwargs):
    return open_serial('loop://', *args, **kwargs)
Adaptors.serial.serial_for_url = loop_serial
writes = []
class RecordingSerialAdaptor(Adaptors.SerialAdaptor):
    def transmitData(self, data):
        success = super().transmitData(data)
        if success:
            writes.append({'data': data.decode('ascii'), 'safe': app.safeMode.isSet()})
        return success
Adaptors.SerialAdaptor = RecordingSerialAdaptor

import flaskServer as web

mode = sys.argv[1]
create_server = web.make_server
def make_server(*args, **kwargs):
    if mode == 'startup-failure':
        raise RuntimeError('injected HTTP startup failure')
    server = create_server(*args, **kwargs)
    print(json.dumps({'port': server.server_port}), flush=True)
    if mode == 'worker-failure':
        def broken_callback():
            raise RuntimeError('injected timer failure')
        Timer(True, 20, broken_callback)
    return server
web.make_server = make_server

if mode in ('SIGINT', 'SIGTERM'):
    def interrupt():
        sys.stdin.readline()
        # Exercise Python's registered handler on Windows without a visible console.
        _thread.interrupt_main(getattr(signal, mode))
    Thread(target=interrupt, name='test-signal').start()

result = web.main(['--host', '127.0.0.1', '--port', '0', '--sculpture', 'aota'])
print(json.dumps({
    'result': result,
    'safe': app.safeMode.isSet(),
    'workers': [thread.name for thread in threads()
                if thread.name.startswith(('timer-', 'serial-', 'osc-', 'http-server'))],
    'bindings': len(app.safeMode.bindings),
    'writes': writes,
}), flush=True)
raise SystemExit(result)
