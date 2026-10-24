# Developer notes

See [README.md](README.md) for installation and launch, and [TESTING.md](TESTING.md)
for the byte-comparison procedure, intentional Python 2 differences, test coverage,
and pending Pi checks. Application code keeps its tab indentation; prefer readable
changes and leave `py2/` untouched.

## Typing and extension interfaces

`ProgramModules/Types.py` describes the existing sculpture, module, protocol, and
adaptor JSON using `TypedDict`. Mappings retain their dictionary, one-dimensional,
or two-dimensional list shapes; runtime-added IDs use `NotRequired`. These declarations
do not parse, validate, or rewrite configuration. Dynamic input parameters and mixed
GUI snapshots are left unannotated. A few schema fields and attributes name only their
known container (`dict`, `list`, or `Sequence`); their contents remain untyped.

`ProgramModules/Interfaces.py` defines structural `typing.Protocol` interfaces for
adaptors, protocol encoders, inputs/parameters, patterns, and sculpture modules. Concrete
classes keep their existing inheritance. The `TYPE_CHECKING` declarations in the
implementation modules and package initializers check that supported classes provide
the required methods and types. When adding an implementation, add it to the matching
declaration as well as its existing configuration/registration path, then run
`python -m mypy`. The declarations are not runtime registries or fallback implementations.

Omit annotations where the type would otherwise be `Any`, including input factories,
command dispatch, `InputCollection.__getattr__` (a value or callable), forwarded argument
lists, and heterogeneous input/message data. Do not hide `Any` behind shared aliases.
The recursive settings merge also remains unannotated. Mypy allows missing annotations;
it checks annotated and partially annotated functions, but skips fully unannotated
function bodies. The synchronization decorator preserves argument and result types with
`ParamSpec`, so decorating a method does not erase its signature from the type checker.

`cast` records an existing relationship, such as the mapping shape selected by a protocol
or a manager installed by sculpture loading. It does not convert or validate a value.
Existing `False`/`None` placeholders remain, including inactive pattern callbacks and
input collections; annotations describe those objects when usable and do not add new
runtime guards. Constructor forwarding remains dynamic where the old code used `*args`.

## Adaptors

Adaptors represent the physical data path to the sculpture and handle things
such as connecting and disconnecting of serial ports and sending and receiving
data from the ports. Currently, the only type is SerialAdaptor, which deals
with any connection that works like a serial port. This includes our usual
usb-RS485 serial port setup as well as any type of virtual serial port.

SerialAdaptor does not currently have a receive method, as none of the current
sculpture protocols send data back.

If you are adding a sculpture feature where data is not transmitted over a
serial port, you will need to create a new Adaptor class.  Adaptors are
instantiated by DataChannelManager when the SculptureController.loadSculpture
method is invoked; type(s) and attributes such as port name and baudrate are
specified in 'adaptors' key of the sculpture definition json file.

The checked `Adaptor` interface describes these methods:

 * `connect(self)`: Establish an active connection according to self.configData
   values
 * `updateSerialConnection(self, data)`: Apply port/baud settings and return whether
   the connection opened
 * `transmitData(self, data)`: Write a `bytes` payload and return whether the complete
   payload was accepted by the serial driver. This is not a hardware acknowledgement.
 * `stop(self)`: Close any active connection and prepare for instance to be
   cleaned up
 * `getCurrentStateData(self)`: Return current configuration data and
   connectedness status

## Protocols

These convert sculpture data such as a list of poofer states into a stream of
ascii or binary data ready to be sent to the sculpture. They serve as a
translator between the in-program data formats and the specific type of data
that the microcontrollers on the sculpture understand. Protocols also translate
the mapping used in the program to the mapping used in the sculpture according
to the 'mapping' object in the sculpture's json config file. For example,
poofers in the program are treated as a 2 dimensional row and column
arrangement, but each poofer must map to a specific board and relay number on
the sculpture.

Protocol types that control poofers must check that safe mode is not enabled
before sending any 'on' signals, see FlgRelayProtocol.formatData for example.

Protocols are instantiated by DataChannelManager at sculpture loadup, and are
matched to an adaptor at instantiation per data in the sculpture's config.json
file. Multiple protocols can use one adaptor(for example, on Tympani the LEDs
and sound hammers are on the same physical data bus, but use different
protocols). DataChannelManager associates each module's protocol with its bus writer.

The checked `ProtocolEncoder` interface includes:

* `formatData(self, addr, data)`: Takes an address(already translated to the
   sculpture mapping) and data and does the translation into the sculpture's
   data format as `bytes`. The type of data in addr and data may be different across
   different protocol types as this data varies with the type of thing being
   controlled and the addressing arrangement of the sculpture's hardware.
* `translateAddr(self, addr)`: Translate a logical address to the configured hardware address.
* `formatCommands(self, data)`: Concatenate an iterable of address/value commands as bytes.
* `addresses(self)`: Iterate the mapped logical addresses in module order.
* `allOff(self)`: Encode OFF for those addresses. DataChannelManager decides which
  channels are governed by safe mode; the encoder itself does not deliver the result.


## Inputs

Inputs take data from various sources and make it into a standardized format
for use by patterns. Currently, every pattern can accept three types of inputs:

 * `pulse`: a boolean state that goes momentarily high to tell the pattern to
   do something,
 * `toggle`: a boolean state that acts as a switch,
 * `value`: a numeric value.

Each input type can have any number of params, which are objects that map to
the knobs and buttons on the GUI. The most simple inputs directly map a param
to their output value; more complex types generate timer pulses,
respond to OSC messages, etc.

The checked `Input` interface covers `setInputValue`, `getValue`, `getId`, `stop`, and
`getCurrentStateData`. `InputParameter` covers the underlying value conversion, get/set,
state, and cleanup methods. These interfaces retain dynamic values because pulse, numeric,
text, and multi-input channels share the same framework.


## Patterns

Patterns are where the states of the things being controlled on the sculpture
are generated. Any number of patterns can be run at once. Patterns are queried
by their parent sculptureModule object for item state on a poofer-by-poofer (or
led-by-led) basis.


## Sculpture Modules

These represent major elements of the sculpture that are controlled by the
program. For example, Tympani has 3 main systems controlled by the program: the
poofers, the sound hammers(called 'clackers' in the config file), and the LEDs
(which are not capable of accepting individual control but are capable of
selecting from a preprogrammed color palette and pattern type). Each of these 3
systems becomes a module instance in the controller program. The modules are
instantiated at startup; type(s), mappings, and which adaptors to use are
loaded from the sculpture's config.json file.

Sculpture modules handle the loading and clearing of patterns, the assignment
of inputs to patterns, the querying of patterns for their current state, the
combining of pattern states into one overall state, and the sending of the
overall state to the sculpture via dataChannelManager protocol/adaptor
pairs. Querying of patterns is done when a pattern requests it or when some
other event, such as safe mode being toggled, brings it about.

## Serial delivery and safe mode

`DataChannelManager.send` returns whether an update was accepted or suppressed by safe mode. Each bus
has one writer thread, a blocking queue, and a record of the latest requested bytes per
output. Queue acceptance is separate from successful serial delivery. Protocol formatting,
safe-mode changes, and writes share a lock; port reconfiguration is serialized with writes.
The adaptor receives only `bytes` and uses `serial_for_url`, including `loop://` for tests.
GUI baud-rate strings are converted to integers. Serial writes have a 250 ms timeout.

During normal operation, accepted packets are written in order. The queue holds at most
128 packets. If it fills, or a packet has waited more than 250 ms, the writer replaces
queued history with the most recently requested state. A short pulse that has already
ended is therefore not replayed later. A still-requested ON can be restored while safe
mode is off. This recovery policy intentionally differs from replaying every old packet.

A failed or partial write closes the connection. The writer retries connection every
250 ms while delivery is pending, then sends the current state rather than the failed
packet's history. An OFF remains in that state record even after the module has updated
its own display/cache, unless safe mode cancels it. No additional pattern update is required to retry it. The writer
also restores current state after an explicit port/baud change. An idle connection is
not actively probed; a disconnect is detected by a write or an explicit reconfiguration.

**Safe mode means no output.** Governed channels send neither ON nor OFF packets on
startup, safe-mode entry, reconnect, or controller shutdown. This includes LED channels.
Entering safe mode invalidates queued commands and discards cached output and pending
OFF requests; suppressed commands are not replayed when safe mode is disabled. The
synchronous protocol send path obeys the same rule. A faulty engine callback is reported
but does not prevent the transport cancellation callback. Safe mode does not turn off
an already active relay or recall bytes already handed to the driver.

**Tympani's exception is retained.** The `buttons` module uses `ignoreSafeMode: true` for
its button-disable controls (`disableA` and `disableR`). Those controls remain operable in
safe mode. They are not forcibly cleared or cancelled with flame commands, including on
a shared bus. Tympani LED controls have no exemption and are suppressed in safe mode.
The Serpent stub continues to emit no bytes.

On manager shutdown, new updates are rejected. If safe mode is enabled, governed output
is cancelled without an OFF packet; otherwise the manager requests relay OFF frames.
Each writer gets up to two seconds to finish remaining permitted delivery, then is woken and joined; the
writer closes its own connection as it exits. An undelivered state is logged and shutdown
returns `False`; an unresponsive writer is an error rather than permission to close a port
underneath it.
Controller shutdown and reload also stop the producers, timers, and OSC listeners before
replacing shared managers; see the lifecycle section below.

Status fields `deliveryPending` and `writerError` distinguish accepted work from completed
writes; `lastError` reports adaptor I/O failure. `connected` means the serial connection is
open, not that the relay hardware acknowledged anything. Bytes already handed to the driver
cannot be recalled. A disconnected bus can receive a pending OFF only after communication
returns and only if safe mode has not cancelled it,
and a partial write may have already affected the hardware. There is no acknowledgement
or exactly-once delivery in these protocols.

Run the focused transport checks from the repository root with Python 3 and pytest:

```text
python -m pytest tests/test_serial.py -q
```

Tests use `loop://` and controlled fake adaptors. The original/protocol comparison uses
`PYTHON2` if set, otherwise `python2` on PATH or `C:/Python27/python.exe` on Windows. It is
skipped if no Python 2 interpreter is available; the remaining transport checks still run.
The separate 59-scenario full-application comparison now passes on Python 3.11 and 3.13
against a fresh run of the preserved Python 2 application. It uses manual timers and a
recording transport; it checks packet contents, not physical timing or relay operation.

## OSC input

The active application uses `python-osc`. The GUI's Host, Port, and three address-list
fields are unchanged. A new listener defaults to `0.0.0.0:8000` (all IPv4 interfaces);
set Host to `127.0.0.1` for local-only operation. The port accepts the GUI's integer or
text value. `sendOscTest.py` sends one `/1/button1` pulse to `127.0.0.1:8000` using
`SimpleUDPClient`; run it with `python sendOscTest.py` while the listener is running.

Outputs retain their configured order: pulse addresses, then toggle addresses, then
value addresses. Each address is registered with its own output index. This corrects the
old address parser, which sent normal addresses to output zero. GUI address strings are
split on whitespace; submitting empty lists now leaves them empty instead of restoring
the default addresses. The `callbackAddresses` dictionary remains supported.

Messages use their first argument. Pulse ON values retain the existing interpretation
(`1`, `1.0`, `True`, `"1"`, `"true"`, or `"True"`); other values mean OFF. Existing pulse
auto-OFF timing, toggle conversion, and numeric input bounds are retained. Messages with
no arguments and unregistered addresses are ignored. Immediate bundles run in order.

One blocking server handles callbacks sequentially on its own thread. `stop()` calls
`shutdown()` from the caller's thread, then joins the listener; the listener closes its
socket on exit. An idle listener checks shutdown every 50 ms and needs no incoming packet
to stop. Repeated stops are supported, and the port can be reused after stopping.

Future bundle timetags retain their scheduling behavior while running, but stopping
cancels their wait and discards the pending messages. Shutdown still waits for an active
callback to finish. If an OSC callback stops its own input, shutdown is requested on a
helper thread and the listener exits after that callback returns; it never joins itself.
An external stop waits for the listener and pulse timers to finish before returning.

Run `python -m pytest tests/test_osc.py -q` for local UDP routing, pulse auto-OFF, GUI
configuration, bundle ordering, and listener shutdown/rebind checks. These checks use
ephemeral ports and do not contact sculpture hardware.

## Controller lifecycle

The application has one controller per process. HTTP commands, state snapshots, timer
callbacks, and OSC callbacks share the reentrant lock in `ProgramModules/Runtime.py`.
State returned to the web server is copied before releasing that lock, so JSON encoding
cannot observe a partly updated pattern or module. The serial writer retains its separate
safe-mode lock; lock order is controller, safe mode, then adaptor. It never calls back
into the controller.

Reload holds the controller lock, enables silent safe mode, and stops old modules, inputs,
timers, and serial writers before installing new managers. Timer and OSC workers waiting
for the controller lock can cancel that wait, preventing shutdown from joining a worker
that is waiting for the lock shutdown holds. Old safe-mode bindings and messenger
subscriptions are removed. Per-output manual OFF timers are now owned by the module and
stopped on reload; partial construction also releases any workers or ports it created.
Removing an active pattern now immediately recomputes outputs, so its last ON state does
not remain cached until another update.

The existing timer countdown, refresh, and changeInterval behavior is retained. A new
timer skips its first interval; refresh consumes that skipped step and waits one full
interval. Changing the interval affects the next wait. Single timers remain refreshable
unless stopWhenDone is set. Stopping joins the timer, except when it stops itself. Reset
or reload from inside a timer/OSC callback is rejected; use the normal controller command
path after the callback returns so managers cannot be replaced beneath that callback.

The web server uses Werkzeug's threaded server and standard-library queues for SSE.
Both GUI loading and `--sculpture` loading use the same output-stream binding helper.
SSE connections send an initial comment and periodic keepalive comments, remove their
queues when closed, and are woken during shutdown. Debug mode and the reloader are off.

SIGINT/Ctrl+C and SIGTERM request shutdown through an event. New web commands are then
rejected, producers stop, governed OFF is attempted, and connections close. Unexpected
HTTP command, worker-callback, or server exceptions request the same cleanup and a nonzero
exit. Failed serial delivery also yields a nonzero exit so systemd can restart in safe
mode. There is no overall hard deadline for arbitrary application callbacks: shutdown
waits for a running callback to finish; the serial delivery wait is bounded as described
above. The service template has a 15-second stop timeout; a forced process kill cannot
establish that hardware received OFF.

Run `python -m pytest -q` for the current suite; warnings are errors in `pyproject.toml`.
Tests exercise all three
sculptures with real timers, loopback serial, local OSC and HTTP, SSE, reload, partial
startup failures, and worker cleanup. Windows subprocess checks use Python's interrupt
mechanism to exercise registered SIGINT/SIGTERM handlers; Linux signal delivery, systemd,
Pi timing, and physical hardware still require on-device verification.
