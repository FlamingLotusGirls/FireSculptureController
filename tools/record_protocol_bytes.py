"""Record protocol bytes under either interpreter, without serial or scientific dependencies."""
from __future__ import print_function
import json
import os
import sys

root = os.path.abspath(sys.argv[1])
sys.path.insert(0, root)
from ProgramModules import Protocols
import ProgramModules.sharedObjects as app

class Recorder(object):
    def __init__(self): self.frames = []
    def transmitData(self, data):
        if not isinstance(data, str): data = data.decode("ascii")
        self.frames.append(data)
        return True

result = {}
for sculpture in ("aota", "serpent", "tympani"):
    with open(os.path.join(root, "sculptureDefinitions", sculpture + ".json")) as source:
        config = json.load(source)
    for moduleId in sorted(config["modules"]):
        settings = config["modules"][moduleId]["protocol"]
        kind = settings["type"]
        recorder = Recorder()
        protocol = getattr(Protocols, kind[0].upper() + kind[1:] + "Protocol")(recorder, settings)
        mapping = settings["mapping"]
        if isinstance(mapping, dict):
            addresses = sorted(mapping)
        else:
            addresses = [(row, col) for row in range(len(mapping)) for col in range(len(mapping[row]))]
        values = [False, True, "0", "1", 0, 1, 1.0]
        if kind == "tympaniLed": values = [0, 1, 10, 255]
        for safe in (False, True):
            app.safeMode.set(safe)
            for value in values:
                recorder.frames = []
                protocol.send([(address, value) for address in addresses])
                key = "%s/%s/safe=%s/%s:%s" % (sculpture, moduleId, safe, type(value).__name__, value)
                result[key] = "".join(recorder.frames)
print(json.dumps(result, sort_keys=True))
