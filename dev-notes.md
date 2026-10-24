# Major object types

## Adaptors

Adaptors represent the physical data path to the sculpture and handle things
such as connecting and disconnecting of serial ports and sending and recieving
data from the ports. Currently, the only type is SerialAdaptor, which deals
with any connection that works like a serial port. This includes our usual
usb-RS485 serial port setup as well as any type of virtual serial port.

SerialAdaptor does not currently have a method for recieving data, as none of
our scultures currently send data back. But we may in the future need to create
a SerialAdaptor.recieveData method if we do want to recieve data.

If you are adding a sculpture feature where data is not transmitted over a
serial port, you will need to create a new Adaptor class.  Adaptors are
instantiated by DataChannelManager when the SculptureController.loadSculpture
method is invoked; type(s) and attributes such as port name and baudrate are
specified in 'adaptors' key of the sculpture definition json file.

Methods needed:

 * `connect(self)`: Establish an active connection according to self.configData
   values
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
that the microconrtollers on the sculpture understand. Protocols also translate
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
protocols). A protocol instance matched with an adaptor instance is

Methods needed:

* `formatData(self, addr, data)`: Takes an address(already translated to the
   sculpture mapping) and data and does the translation into the sculpture's
   data format. The type of data in addr and data may be different across
   different protocol types as this data varies with the type of thing being
   controlled and the addressing arangement of the sculpture's hardware.


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

`DataChannelManager.send` returns whether an update was accepted by the writer. Each bus
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
its own display/cache. No additional pattern update is required to retry it. The writer
also restores current state after an explicit port/baud change. An idle connection is
not actively probed; a disconnect is detected by a write or an explicit reconfiguration.

**New behavior:** loading a sculpture in safe mode, enabling safe mode, or reconnecting
while safe sends OFF for every mapped relay output governed by safe mode, even if the
software already believes it is off. These are the existing individual relay commands
(`!0110.` for board 1, relay 1), not a new broadcast command. Pending governed commands
are invalidated by generation, and OFF frames take priority over queued traffic. A faulty
engine callback is reported but does not prevent the transport safe-mode callback.

**Tympani's exception is retained.** The `buttons` module uses `ignoreSafeMode: true` for
its button-disable controls (`disableA` and `disableR`). Those controls remain operable in
safe mode. They are not forcibly cleared or cancelled with flame commands, including on
a shared bus. Neither Tympani LED controls nor the empty Serpent LED stub are included in
relay all-OFF handling. The Serpent stub continues to emit no bytes.

On manager shutdown, new updates are rejected, governed OFF frames are requested, and
each writer gets up to two seconds to finish delivery. It is then woken and joined; the
writer closes its own connection as it exits. An undelivered state is logged and shutdown
returns `False`; an unresponsive writer is an error rather than permission to close a port
underneath it.
Broader timer, process-signal, and controller-reload cleanup remains in step 6.

Status fields `deliveryPending` and `writerError` distinguish accepted work from completed
writes; `lastError` reports adaptor I/O failure. `connected` means the serial connection is
open, not that the relay hardware acknowledged anything. Bytes already handed to the driver
cannot be recalled. A disconnected bus cannot receive OFF until communication returns,
and a partial write may have already affected the hardware. There is no acknowledgement
or exactly-once delivery in these protocols.

Run the focused transport checks from the repository root with Python 3 and pytest:

```text
python -m pytest tests/test_serial.py -q
```

Tests use `loop://` and controlled fake adaptors. The original/protocol comparison uses
`PYTHON2` if set, otherwise `python2` on PATH or `C:/Python27/python.exe` on Windows. It is
skipped if no Python 2 interpreter is available; the remaining transport checks still run.
The 59-scenario full-application comparison remains separate and awaits completion of the
Python 3 dependency/server changes.

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

Shutdown waits for an active callback to finish. Future bundle timetags retain their
existing scheduling behavior and can also delay shutdown; this is not a hard shutdown
deadline. Calling `stop()` from an OSC callback raises an explicit error instead of
deadlocking. Broader callback coordination and timer cleanup remain in step 6.

Run `python -m pytest tests/test_osc.py -q` for local UDP routing, pulse auto-OFF, GUI
configuration, bundle ordering, and listener shutdown/rebind checks. These checks use
ephemeral ports and do not contact sculpture hardware.
