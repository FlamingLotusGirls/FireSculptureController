# FireSculptureController


Controller framework with the goal of being useful for all FLG and other big
fire sculptures.

## Migration status

The root application is being ported in stages and is not yet a complete Python 3 GUI
release. The unchanged original remains runnable from `py2/`; see
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

Python 2.7 (2.7.6 on Win7 due to greenlet installation issues)

### Python libraries

Sculpture engine:

* pyserial for talking to sculptures over serial


Server for js GUI:

* gevent
* greenlet
* flask


OSC server:

* python-osc


## Usage

Install libraries, run flaskserver.py, and go to localhost in browser.

Sculpturecontroller.py does everything to do with controlling the sculpture and
is not dependent on the gui or webserver, so could be run some other way too.
