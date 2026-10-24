# FireSculptureController


Controller framework with the goal of being useful for all FLG and other big
fire sculptures.

## Migration status

The root application now runs on Python 3.11+. Pi and physical-hardware checks are still
pending. The unchanged original remains runnable from `py2/`; see
[the Python 2 launcher and setup](deploy/py2/README.md).

Serial protocols now produce bytes. `loop://` can replace a port name for testing without
hardware. The serial writer blocks when idle, retries current state after delivery
failures, and reports pending delivery/errors in adaptor status. See
[serial delivery and safe mode](dev-notes.md#serial-delivery-and-safe-mode) for the exact
behavior and limits.

HeartBeat remains selectable with its existing controls, but its waveform is an inert
placeholder: all LEDs stay black. The active application no longer needs SciPy or NumPy.

OSC now uses `python-osc`. Its configurable listener defaults to `0.0.0.0:8000`, and
each configured address controls its own output. See [OSC input](dev-notes.md#osc-input)
for routing, shutdown behavior, and the local test sender.

## Requirements

Python 3.11 or newer, with the packages in `requirements.txt` installed in your chosen
Python environment. No virtual environment is required by the application.

### Python libraries

Sculpture engine:

* pyserial for talking to sculptures over serial


Server for js GUI:

* flask


OSC server:

* python-osc


## Usage

From the repository root:

```text
python flaskServer.py --sculpture aota --port 8080
```

Open `http://localhost:8080`. Use `aota`, `serpent`, or `tympani` for `--sculpture`, or
omit it to choose in the GUI. Startup and sculpture loads begin in safe mode and request
OFF for governed relays. The default web host is `0.0.0.0`; `--host 127.0.0.1` restricts
it to this computer. `--log-level DEBUG` enables detailed logging.

The server uses threaded Flask/Werkzeug with debug mode and the reloader off. Ctrl+C and
SIGTERM stop inputs, timers, OSC, and serial writers. See [headless deployment](deploy/README.md)
for the systemd template and [lifecycle details](dev-notes.md#controller-lifecycle) for
cleanup and delivery limits. Configuration and GUI paths are relative to the source files,
so an absolute script path also works from another directory.

SculptureController.py does everything to do with controlling the sculpture and
is not dependent on the gui or webserver, so could be run some other way too.
