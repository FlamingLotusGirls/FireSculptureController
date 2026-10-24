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

## Requirements

Python 2.7 (2.7.6 on Win7 due to greenlet installation issues)

### Python libraries

Sculpture engine:

* pyserial for talking to sculptures over serial


Server for js GUI:

* gevent
* greenlet
* flask


Patterns:

* scipy (LED HeartBeat pattern)


OSC server:

* pyOSC


## Usage

Install libraries, run flaskserver.py, and go to localhost in browser.

Sculpturecontroller.py does everything to do with controlling the sculpture and
is not dependent on the gui or webserver, so could be run some other way too.
