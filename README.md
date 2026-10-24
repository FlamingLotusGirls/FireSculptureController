# FireSculptureController

Python 3 controller and browser GUI for Flaming Lotus Girls fire sculptures.

| Sculpture ID | Sculpture |
| --- | --- |
| `aota` | Angel of the Apocalypse |
| `serpent` | Serpent Mother |
| `tympani` | Tympani Lambada |

## Install and run

Use Python 3.11 or newer. From the repository root, install the pinned dependencies
into your chosen Python environment and start the controller:

```text
python -m pip install -r requirements.txt
python flaskServer.py --sculpture aota
```

Open **http://localhost:8080**. Omit `--sculpture` to choose in the GUI. Ctrl+C stops the
controller. The application does not require a virtual environment.

For this Windows checkout's already-installed test environment, the launch command is:

```powershell
.venv\Scripts\python.exe flaskServer.py --sculpture aota
```

`--host` defaults to `0.0.0.0`; use `--host 127.0.0.1` for this computer only. `--port`
defaults to `8080`, and `--log-level DEBUG` enables detailed logging. Configuration and
GUI paths resolve relative to the source files, so launching by absolute script path
works from another directory too. Keep the source tree and its assets together.

Serial ports and mappings are in `sculptureDefinitions/*.json`. The preserved Linux
port names will not open on Windows; select the actual port in the GUI, or use `loop://`
for serial loopback without hardware. Missing devices are logged while pending output
is retried. OSC uses `python-osc` and defaults to `0.0.0.0:8000` when an OSC input is created.

## Safe mode and shutdown

Startup and sculpture loads begin in safe mode. Loading, enabling safe mode, and
reconnecting while safe request OFF for every governed relay, even if its cached state
already says OFF. Tympani's `ignoreSafeMode` button-disable controls retain their exemption.

The serial writer blocks when idle, retries current state after failed delivery, and
reports pending delivery/errors in adaptor status. Ctrl+C and SIGTERM stop inputs,
timers, OSC, and serial workers after attempting OFF delivery. A successful write is
not a hardware acknowledgement; disconnected hardware cannot receive OFF until the
connection returns. See [delivery and lifecycle details](dev-notes.md#serial-delivery-and-safe-mode).

## Current scope

HeartBeat remains selectable with its controls and renderer, but its stubbed waveform
keeps all LEDs black. The Serpent LED wire protocol still emits no bytes. FromImage
remains a stub. Audio is removed from the active application. The Python 3 dependencies
are Flask/Werkzeug, pyserial, and python-osc; gevent, PyAudio, SciPy, and NumPy are not needed.

The root application has automated checks on Windows with Python 3.11 and 3.13. Pi,
physical hardware, and systemd checks remain pending. See [headless deployment](deploy/README.md)
for the service template and [testing](TESTING.md) for the old/new byte comparisons,
intentional differences, and remaining field checks.

## Original Python 2 version

The exact original, including audio, remains in `py2/`. It runs without switching branches:

```powershell
C:\Python27\python.exe deploy/py2/run.py --port 8080
```

See [Python 2 setup](deploy/py2/README.md) for its separate dependencies. Stop the other
controller first; only one version should own the web and physical serial ports.

## Development

```text
python -m pip install -r requirements-dev.txt
python -m pytest -q
python -m mypy
```

The tests use recording transports, serial loopback, and local HTTP/UDP. The frozen
Python 2 snapshot is excluded from Python 3 test discovery and type checking. Mypy
checks the annotated active application and its configuration/interface definitions;
runtime-selected input values and commands retain their documented dynamic boundaries.

`SculptureController.py` can also run without the web server. See
[developer notes](dev-notes.md) for the input, pattern, protocol, and adaptor interfaces,
and [the migration plan](PLAN_python3.md) for progress and deferred work.
