"""Exercise desktop and touchscreen UI in Cog, using only simulated USB ports.

Run from the repo with the app dependencies on PYTHONPATH and cog/dbus-run-session
installed. This never contacts the live server or opens a physical serial port.
"""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
from threading import Event, Thread

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

SCRIPT = r'''
window.EventSource = function() {};
function assert(value, message) { if (!value) throw Error(message); }
function waitFor(check) {
    return new Promise(function(resolve, reject) {
        var attempts = 0;
        var timer = setInterval(function() {
            if (check()) { clearInterval(timer); resolve(); }
            else if (++attempts > 200) { clearInterval(timer); reject(Error('Timed out: ' + check)); }
        }, 50);
    });
}
function choosePort(path) {
    var select = $('#flameBusPorts');
    if (isTouchDisplay) {
        select.next('.serialPortTouchChoices').click();
        $('#dialog .inputSelectorChoice').filter(function() { return $(this).text().indexOf(path) >= 0; }).first().click();
    } else { select.val(JSON.stringify([path])).trigger('change'); }
}
async function runChecks() {
    await waitFor(function() { return $('#flameBusPorts option').length > 2; });
    var path = '/dev/serial/by-id/usb-FTDI_A50285BI-if00-port0';
    choosePort(path);
    await waitFor(function() { return $('#logDiv').text().indexOf('Controller accepted: updateSerialConnection') >= 0; });
    reloadData();
    await waitFor(function() { return allSculptureData.adaptors.flameBus.ports[0] == path; });
    assert($('#flameBusPorts option:selected').text().indexOf('by-id') >= 0, 'by-id label missing');
    if (isTouchDisplay) {
        $('#poofers_patternChoices').click();
        $('#dialog .patternChoice').filter(function() { return $(this).text().indexOf('Chase') >= 0; }).first().click();
    } else { $('#poofers_patternChoices').val('Chase').trigger('change'); }
    await waitFor(function() { return Object.keys(allSculptureData.modules.poofers.patterns).length == 1; });
    var pattern = allSculptureData.modules.poofers.patterns[Object.keys(allSculptureData.modules.poofers.patterns)[0]];
    doCommand(['setInputValue', pattern.inputs.numberOn.inputInstanceId, 4, pattern.inputs.numberOn.outParamIndex]);
    await waitFor(function() { return $('#logDiv').text().indexOf('Controller accepted: setInputValue') >= 0; });
    var saved = await (await fetch('/test/saved')).json();
    assert(saved.adaptors.flameBus.ports[0] == path, 'USB selection not saved');
    assert(saved.modules.poofers.patterns[0].type == 'Chase', 'Pattern not saved');
    await fetch('/test/restart', {method: 'POST'});
    reloadData();
    await waitFor(function() { return allSculptureData.safeMode && Object.keys(allSculptureData.modules.poofers.patterns).length == 1; });
    var state = await (await fetch('/getData')).json();
    pattern = state.modules.poofers.patterns[Object.keys(state.modules.poofers.patterns)[0]];
    assert(state.inputs[pattern.inputs.numberOn.inputInstanceId].inParams[pattern.inputs.numberOn.outParamIndex].currentValue == 4, 'Pattern value lost on restart');
    doCommand(['updateSerialConnection', 'flameBus', {ports: ['/missing/usb-adapter']}]);
    await waitFor(function() { return $('#connectionStatus').text().indexOf('Disconnected') >= 0; });
    $('#safeModeOff').click();
    await waitFor(function() { return $('#connectionStatus').hasClass('connectionWarning'); });
    assert($('#logDiv').text().indexOf('simulated missing port') >= 0, 'Backend error missing from log');
    assert($('#logDiv').text().indexOf('Command sent:') < 0, 'Log claims hardware delivery');
    reloadData();
    await waitFor(function() { return $('#flameBusPorts option:selected').text().indexOf('not detected') >= 0; });
    choosePort(path);
    await waitFor(function() { return $('#connectionStatus').text().indexOf('Port connected') >= 0 && !$('#connectionStatus').hasClass('connectionWarning'); });
    assert($('#connectionStatus')[0].getBoundingClientRect().height < 90, 'Status strip takes too much room');
    return {touch: isTouchDisplay, checks: 'USB selection, by-id labels, autosave, pattern restore, Run warning, backend error, recovery, compact strip'};
}
window.addEventListener('load', async function() {
    try {
        var result = await runChecks();
        await fetch('/test/report', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({pass: true, result: result})});
    } catch (error) {
        await fetch('/test/report', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({pass: false, error: String(error.stack || error)})});
    }
});
'''


def main():
    with tempfile.TemporaryDirectory(prefix='firesculpture-gui-') as directory:
        root = Path(directory)
        os.environ['FIRESCULPTURE_STATE_DIR'] = str(root / 'settings')
        import flaskServer as web
        import SculptureController as controller_module
        from ProgramModules import Adaptors, SerialPorts
        from serial import SerialException
        from werkzeug.serving import make_server

        identity = {'serialNumber': 'A50285BI', 'vid': 0x0403, 'pid': 0x6001, 'interface': None}
        port = '/dev/serial/by-id/usb-FTDI_A50285BI-if00-port0'
        discovered = [{'device': '/dev/ttyUSB0', 'port': port, 'identity': identity,
                       'label': 'FTDI — A50285BI — ' + port},
                      {'device': '/dev/ttyUSB1', 'port': '/dev/serial/by-id/usb-spare',
                       'identity': dict(identity, serialNumber='SPARE'), 'label': 'Spare adapter'}]
        SerialPorts.discoverSerialPorts = lambda: discovered
        controller_module.discoverSerialPorts = lambda: discovered
        open_serial = Adaptors.serial.serial_for_url

        def simulated_serial(device, *args, **kwargs):
            if device not in ('loop://', port, '/dev/serial/by-id/usb-spare'):
                raise SerialException('simulated missing port: ' + device)
            return open_serial('loop://', *args, **kwargs)

        Adaptors.serial.serial_for_url = simulated_serial

        def reset():
            web.sculpture.stop()
            web.sculpture = controller_module.SculptureController()
            for definition in web.sculpture.sculptureDefinitions.values():
                for adaptor in definition['adaptors'].values():
                    adaptor['ports'] = ['loop://']
            web.executeCommand(['loadSculpture', 'serpent'])

        web.flaskApp.view_functions['jsGui'] = lambda: web.Response(
            (ROOT / 'jsGui/index.htm').read_text().replace('</head>', '<script src="/test/script.js"></script></head>'),
            mimetype='text/html')
        web.flaskApp.add_url_rule('/test/script.js', 'testScript', lambda: web.Response(SCRIPT, mimetype='application/javascript'))
        done = Event()
        reports = []

        def report():
            reports.append(web.request.get_json())
            done.set()
            return web.jsonify({})

        def restart():
            reset()
            return web.jsonify({})

        web.flaskApp.add_url_rule('/test/report', 'testReport', report, methods=['POST'])
        web.flaskApp.add_url_rule('/test/restart', 'testRestart', restart, methods=['POST'])
        web.flaskApp.add_url_rule('/test/saved', 'testSaved', lambda: web.jsonify(web.sculpture.settingsStore.load('serpent')))
        server = make_server('127.0.0.1', 0, web.flaskApp, threaded=True)
        thread = Thread(target=server.serve_forever, kwargs={'poll_interval': 0.05})
        thread.start()
        try:
            for mode, query in [('desktop', ''), ('touch', '?display=touch')]:
                web.sculpture.settingsStore._path('serpent').unlink(missing_ok=True)
                reset()
                done.clear()
                environment = os.environ.copy()
                for key in ('DISPLAY', 'WAYLAND_DISPLAY', 'DBUS_SESSION_BUS_ADDRESS'):
                    environment.pop(key, None)
                runtime = root / mode
                runtime.mkdir(mode=0o700)
                environment.update(XDG_RUNTIME_DIR=str(runtime), XDG_CACHE_HOME=str(runtime / 'cache'), XDG_DATA_HOME=str(runtime / 'data'))
                with (runtime / 'browser.log').open('w') as log:
                    browser = subprocess.Popen(['dbus-run-session', '--', 'cog', '--platform=headless',
                        '--webprocess-failure=exit', 'http://127.0.0.1:%s/%s' % (server.server_port, query)],
                        env=environment, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
                    try:
                        if not done.wait(30):
                            raise AssertionError('Browser timed out: ' + (runtime / 'browser.log').read_text())
                        print(json.dumps(reports[-1]), flush=True)
                        assert reports[-1]['pass'], reports[-1]
                    finally:
                        os.killpg(browser.pid, signal.SIGTERM)
                        browser.wait(timeout=5)
        finally:
            web.closeStreams()
            server.shutdown()
            thread.join(timeout=2)
            server.server_close()
            web.sculpture.stop()


if __name__ == '__main__':
    main()
