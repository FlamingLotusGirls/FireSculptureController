
import OSC
c = OSC.OSCClient()
c.connect(("127.0.0.2", 8000))
bundle = OSC.OSCBundle()
bundle.append({'addr' : '/1/button1', 'args' : ['1']})
bundle.setAddress('/1/button1')
c.send(bundle)
