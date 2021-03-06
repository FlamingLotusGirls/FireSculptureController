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
 * `transmitData(self, data)`: Send the data out to the sculpture and return a
   boolean success value
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
to their output value, more complex types generate audio-responsive pulses,
respond to OSC servers, etc.


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
