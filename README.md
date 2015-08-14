# FireSculptureController


Controller framework with the goal of being useful for all FLG and other big
fire sculptures.

## Requirements

Python 2.7 (2.7.6 on Win7 due to greenlet installation issues)

### Python libraries

Sculpture engine:

* pyserial for talking to sculptures over serial


Server for js GUI:

* gevent
* greenlet
* flask


Audio pulse:

* pyaudio


Patterns:

* scipy (LED HeartBeat pattern)


OSC server:

* pyOSC


## Usage

Install libraries, run flaskserver.py, and go to localhost in browser.

Sculpturecontroller.py does everything to do with controlling the sculpture and
is not dependent on the gui or webserver, so could be run some other way too.
