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

The [Raspberry Pi systemd service](deploy/README.md) uses port 80: open `http://<pi-address>/`.

For this Windows checkout's already-installed test environment, the launch command is:

```powershell
.venv\Scripts\python.exe flaskServer.py --sculpture aota
```

`--host` defaults to `0.0.0.0`; use `--host 127.0.0.1` for this computer only. `--port`
defaults to `8080`, and `--log-level DEBUG` enables detailed logging. Configuration and
GUI paths resolve relative to the source files, so launching by absolute script path
works from another directory too. Keep the source tree and its assets together.

Default serial ports and mappings are in `sculptureDefinitions/*.json`. Choose your
adapter in Main as described below, or configure `loop://` for loopback without hardware.
Missing devices are logged while pending output is retried. OSC uses `python-osc` and
defaults to `0.0.0.0:8000` when an OSC input is created.

## Serial port: one USB Serial adapter

In **Main**, choose an adapter from the **USB adapter** dropdown. **Refresh ports**
rescans devices without opening them. The touchscreen uses an in-page chooser.
Discovery uses pySerial on Linux, macOS, and Windows; it does not shell out to `ls`.
Linux choices prefer `/dev/serial/by-id/` links; macOS uses native `/dev/cu.*` names
and Windows uses COM names. Hardware serial numbers are saved with the selection,
so a uniquely identified adapter can be found after its port name changes. A missing
saved adapter stays visible in the dropdown. Missing or duplicate serial numbers are
labelled **port name only** and require rechecking assignments after reconnecting.

For manual diagnosis:

| Computer | How to check | Port string to use |
| --- | --- | --- |
| Linux / Raspberry Pi | In a terminal, run `ls /dev/ttyUSB*`. | Usually `/dev/ttyUSB0`, as confirmed on this Pi. Use the name listed. |
| macOS | In Terminal, run `ls /dev/cu.*`. Look for the USB serial entry. | The full name, such as `/dev/cu.usbserial-A50285BI`. |
| Windows | Open Device Manager and expand **Ports (COM & LPT)**. Find **USB Serial Port (COMn)**. | The COM name, such as `COM7`. |

Manual defaults can still be set in the intended adaptor's `ports` entry in
`sculptureDefinitions/<sculpture>.json`. For example, on the Pi:

```json
"ports": ["/dev/ttyUSB0"]
```

Copy the actual name from your computer; the strings above are examples. For multiple USB Serial adapters on Linux,
see [What if I have more than one USB Serial adapter? (Linux)](#what-if-i-have-more-than-one-usb-serial-adapter-linux)
at the end.

## Automatically saved settings

USB selections, baud rate, pattern additions/removals, input parameters and bindings,
global inputs, selected rows, and enabled outputs save immediately for each sculpture.
They restore on sculpture reload and application restart. Momentary button presses,
manual output pulses, and Run mode are not restored; startup still enters Safe Mode.

Settings live in `state/<sculptureId>.json` beside the source tree, separately from the
default sculpture definitions. Set `FIRESCULPTURE_STATE_DIR` to choose another directory.
Writes use an atomic file replacement, and unchanged settings are not rewritten. A
save failure is shown in the UI; changes remain active but are not promised to survive
a restart. Back up the state directory to preserve your setup. With the controller
stopped, removing a sculpture's state file returns it to its definition defaults.

The compact status strip above the right-hand log reads the serial writer's connection,
pending-delivery state, and last error every two seconds and after UI commands. In Run,
a disconnected bus used by the sculpture is highlighted. Details appear in the log;
unused buses do not generate Run warnings. “Controller accepted” means the request
was processed, not that hardware received it. “Port connected” means the serial port
is open, not that the sculpture acknowledged or acted on the output.

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
on the Raspberry Pi with Python 3.13.5. Physical relay operation, service startup after
reboot, and the Pi's Python 2 fallback remain unverified. See [headless deployment](deploy/README.md)
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

**3. Save each bus's assignment.** Choose each bus's adapter separately in **Main**;
the selection saves immediately. For default configuration, `flameBus.ports` and
`ledBus.ports` can also be set in the sculpture JSON. Do not put both
USB Serial adapters in each `ports` list: the list contains alternatives for one bus.
Label the cables to match. If a USB Serial adapter is replaced, update its saved path.

### Refreshing the control panel

The ↻ button beside Safe/Run reloads controls from the controller. Use it to
pick up pattern or input changes made in another browser. State notifications and
stream reconnections no longer rebuild the panel, so trigger controls stay in place
when operating All Poof or Chase. Live output indicators, Safe/Run status, and USB
connection status still update. Adding or removing patterns in this browser still
refreshes the panel automatically.


### Chase on duration

Poofer Chase has an **On duration** control beside **Trigger next step in sequence**,
with **ms, 0 = direct follow** below the control.
Leave it at **0** for the original behavior. To fire one poofer every second for
half a second, set **Poofers** to **1**, the **Trigger next step in sequence**
interval to **1000 ms**, and **On duration** to **500 ms**.

A positive duration applies to each poofer selected by a step, independently of
when the next step starts. Longer durations can overlap steps. Selecting a poofer
again before it turns off restarts its on-duration. The last step's poofers finish
their duration even when the sequence ends. Changes to duration apply to subsequent
steps; zero switches back to the original behavior. The setting saves with the pattern.
