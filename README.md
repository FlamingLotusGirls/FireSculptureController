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

Serial ports and mappings are in `sculptureDefinitions/*.json`. Set the port for your
computer as described below, or use `loop://` for serial loopback without hardware.
Missing devices are logged while pending output is retried. OSC uses `python-osc` and
defaults to `0.0.0.0:8000` when an OSC input is created.

## Serial port: one USB Serial adapter

With one FTDI USB Serial adapter, check its port name and use that name directly:

| Computer | How to check | Port string to use |
| --- | --- | --- |
| Linux / Raspberry Pi | In a terminal, run `ls /dev/ttyUSB*`. | Usually `/dev/ttyUSB0`, as confirmed on this Pi. Use the name listed. |
| macOS | In Terminal, run `ls /dev/cu.*`. Look for the USB serial entry. | The full name, such as `/dev/cu.usbserial-A50285BI`. |
| Windows | Open Device Manager and expand **Ports (COM & LPT)**. Find **USB Serial Port (COMn)**. | The COM name, such as `COM7`. |

Enter the port string in the GUI's serial port field. To retain it after a restart,
set the intended adaptor's `ports` entry in `sculptureDefinitions/<sculpture>.json`.
For example, on the Pi:

```json
"ports": ["/dev/ttyUSB0"]
```

The Mac and Windows strings go in the same field. Copy the actual name from your
computer; the strings above are examples. For multiple USB Serial adapters on Linux,
see [What if I have more than one USB Serial adapter? (Linux)](#what-if-i-have-more-than-one-usb-serial-adapter-linux)
at the end.

## Safe mode and shutdown

Startup and sculpture loads begin in safe mode. Safe mode sends no output for governed
channels: no ON, OFF, startup, reconnect, or shutdown packets. Pending commands and cached
state are discarded when entering safe mode. Tympani's `ignoreSafeMode` button-disable
controls retain their exemption. Safe mode does not turn off an already active relay.

The serial writer blocks when idle, retries current state after failed delivery, and
reports pending delivery/errors in adaptor status. Ctrl+C and SIGTERM stop inputs,
timers, OSC, and serial workers after entering safe mode and cancelling governed output.
While safe mode is off, failed OFF delivery is retried; entering safe mode cancels that
retry too. A successful write is not a hardware acknowledgement.
See [delivery and lifecycle details](dev-notes.md#serial-delivery-and-safe-mode).

## Current scope

HeartBeat remains selectable with its controls and renderer, but its stubbed waveform
keeps all LEDs black. The Serpent LED wire protocol still emits no bytes. FromImage
remains a stub. Audio is removed from the active application. The Python 3 dependencies
are Flask/Werkzeug, pyserial, and python-osc; gevent, PyAudio, SciPy, and NumPy are not needed.

The root application has automated checks on Windows with Python 3.11 and 3.13, and
on the Raspberry Pi with Python 3.13.5. Physical relay operation, systemd, and the Pi's Python 2
fallback remain unverified. See [headless deployment](deploy/README.md)
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

The default tests use recording transports, serial loopback, and local HTTP/UDP.
[Real USB Serial checks](TESTING.md#real-usb-serial-checks) require an explicit port option.
The frozen Python 2 snapshot is excluded from Python 3 test discovery and type checking. Mypy
checks the annotated active application and its configuration/interface definitions;
runtime-selected input values and commands retain their documented dynamic boundaries.

`SculptureController.py` can also run without the web server. See
[developer notes](dev-notes.md) for the input, pattern, protocol, and adaptor interfaces,
and [the migration plan](PLAN_python3.md) for progress and deferred work.

## What if I have more than one USB Serial adapter? (Linux)

These steps apply to Linux, including Raspberry Pi. Each physical bus needs its own
USB Serial adapter assignment. Tympani uses two:

| Adaptor in `sculptureDefinitions/tympani.json` | Connected equipment |
| --- | --- |
| `flameBus` | Poofers and button-disable controls |
| `ledBus` | Clackers and LEDs |

**1. Identify and label each USB Serial adapter.** With the controller stopped, connect
one USB Serial adapter at a time and note which bus it serves. Get hardware details
with pyserial installed in the Python environment used to run the controller:

```sh
python3 -m serial.tools.list_ports -v
```

For the current Pi test installation, run
`PYTHONPATH="$PWD/artifacts/py3-deps" python3 -m serial.tools.list_ports -v` from the
repository root. These commands list device information without opening the serial port.

An FTDI entry includes a hardware ID such as:

```text
USB VID:PID=0403:6001 SER=A50285BI LOCATION=1-1.2
```

`0403:6001` identifies the vendor and product; identical USB Serial adapters can share
those values. The `SER=` value identifies the individual USB Serial adapter. Record it
beside the bus name.

**2. Find the persistent device path.** List the device links:

```sh
ls -l /dev/serial/by-id/
```

Use the full path containing the USB Serial adapter's serial number, for example:

```json
"ports": ["/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A50285BI-if00-port0"]
```

Copy the actual path listed for your USB Serial adapter. That path follows it if its
`/dev/ttyUSB` number changes. If serial numbers are missing or duplicated, use explicit
port names and recheck the assignments when reconnecting.

**3. Save each bus's assignment.** Set `flameBus.ports` and `ledBus.ports` separately in
the sculpture JSON, using the path for each bus's USB Serial adapter. Do not put both
USB Serial adapters in each `ports` list: the list contains alternatives for one bus.
Label the cables to match. If a USB Serial adapter is replaced, update its saved path.
