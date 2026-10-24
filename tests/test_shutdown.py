"""Headless startup and shutdown run in isolated processes, never against real ports."""
import json
from pathlib import Path
from queue import Queue
import subprocess
import sys
from threading import Thread
from urllib.request import Request, urlopen

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('mode', ['SIGINT', 'SIGTERM', 'startup-failure', 'worker-failure'])
def test_headless_shutdown_closes_workers_and_writes_off(mode, tmp_path):
    command = [sys.executable, '-W', 'error', str(ROOT / 'tests/helpers/run_controller.py'), mode]
    lines = Queue()
    with subprocess.Popen(command, cwd=tmp_path, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, text=True) as process:
        output = []
        def read_output():
            for line in process.stdout:
                data = json.loads(line)
                output.append(data)
                lines.put(data)
        reader = Thread(target=read_output)
        reader.start()
        try:
            if mode in ('SIGINT', 'SIGTERM'):
                port = lines.get(timeout=5)['port']
                base = 'http://127.0.0.1:%s' % port
                with urlopen(base + '/getData', timeout=2) as response:
                    state = json.load(response)
                assert state['sculptureId'] == 'aota'
                assert state['safeMode'] is True
                for action in [
                    ['addPattern', 'poofers', 'AllPoof'],
                    ['addGlobalInput', {'type': 'multi', 'subType': 'osc', 'host': '127.0.0.1', 'port': 0}],
                    ['setSafeMode', False],
                    ['setItemState', 'poofers', [0, 0], True],
                ]:
                    request = Request(base + '/doCommand', data=json.dumps(action).encode(),
                                      headers={'Content-Type': 'application/json'})
                    with urlopen(request, timeout=2) as response:
                        assert response.status == 200
                process.stdin.write('stop\n')
                process.stdin.flush()
            process.wait(timeout=5)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=3)
            reader.join(timeout=2)
        errors = process.stderr.read()
        expected_exit = 0 if mode in ('SIGINT', 'SIGTERM') else 1
        assert process.returncode == expected_exit, errors
        summary = output[-1]
        assert summary['result'] == expected_exit
        assert summary['safe'] is True
        assert summary['workers'] == []
        assert summary['bindings'] == 0
        config = json.loads((ROOT / 'sculptureDefinitions/aota.json').read_text())
        mapping = config['modules']['poofers']['protocol']['mapping']
        off = ''.join('!%02X%s0.' % (board, relay) for row in mapping for board, relay in row)
        assert summary['last_write'] == off
