"""Run identical logical events under Python 2 or 3, without hardware or real clocks."""
from __future__ import print_function
import argparse
import json
import os
import sys

parser = argparse.ArgumentParser()
parser.add_argument("--root", required=True)
parser.add_argument("--output", required=True)
args = parser.parse_args()
root = os.path.abspath(args.root)
output = os.path.abspath(args.output)
sys.path.insert(0, root)
os.chdir(root)

class ManualTimer(object):
    def __init__(self, repeating, interval, function, args=False, stopWhenDone=False):
        self.interval = interval
        self.function = function
        self.args = args
    def stop(self): pass
    def refresh(self): pass
    def changeInterval(self, interval): self.interval = interval
    def is_alive(self): return True
    @classmethod
    def stopAll(cls): pass

import ProgramModules.Timers as timers
timers.Timer = ManualTimer
import ProgramModules.DataChannelManager as channels
import ProgramModules.Protocols as protocols
import ProgramModules.sharedObjects as app

frames = {}
class RecordingAdaptor(object):
    def __init__(self, name): self.name = name
    def transmitData(self, data):
        if not isinstance(data, str): data = data.decode("ascii")
        frames[self.name] = frames.get(self.name, "") + data
        return True

class RecordingManager(object):
    def __init__(self, config):
        self.dataChannels = {}
        for name, module in config["modules"].items():
            kind = module["protocol"]["type"]
            cls = getattr(protocols, kind[0].upper() + kind[1:] + "Protocol")
            self.dataChannels[name] = cls(RecordingAdaptor(module["adaptor"]), module["protocol"])
    def send(self, name, data): return self.dataChannels[name].send(data)
    def stop(self): pass
    def getCurrentStateData(self): return {}
    def allOff(self): pass
    def flush(self, timeout=2): return True

channels.DataChannelManager = RecordingManager
from SculptureController import SculptureController
import flaskServer
controller = flaskServer.sculpture
client = flaskServer.flaskApp.test_client()
response = client.get("/")
assert response.status_code == 200
response.close()
assert client.get("/getData").status_code == 200
results = {}

def record(label, action):
    frames.clear()
    action()
    results[label] = dict(frames)

for sculpture in ("aota", "serpent", "tympani"):
    response = client.post("/doCommand", data=json.dumps(["loadSculpture", sculpture]), content_type="application/json")
    assert response.status_code == 200, response.data
    assert client.get("/getData").status_code == 200
    controller.setSafeMode(False)
    for name in sorted(controller.sculptureModules):
        module = controller.sculptureModules[name]
        prefix = sculpture + "/" + name
        if hasattr(module, "setItemState"):
            record(prefix+"/manual-on", lambda: module.setItemState([0, 0], True))
            record(prefix+"/manual-off", lambda: module.setItemState([0, 0], False))
            for patternName in sorted(module.availablePatternNames):
                if patternName == "Twister":
                    continue  # New pattern; covered separately, not part of the Python 2 baseline.
                instance = module.addPattern(patternName)
                pattern = module.patterns[instance]
                if patternName == "AllPoof":
                    inp, index = pattern.inputs.getInputAssignment("poofButton")
                    record(prefix+"/AllPoof-on", lambda: controller.setInputValue(inp, True, index))
                    record(prefix+"/AllPoof-off", pattern.turnOff)
                elif patternName == "Chase":
                    for position in (0, 1, 3, 7):
                        pattern.position = position
                        record(prefix+"/Chase-"+str(position), module.doUpdates)
                elif patternName == "RandomPoof":
                    inp, indexes = pattern.inputs.getInputAssignment("randomGenerator")
                    generator = app.inputManager.getInputObj(inp)
                    for index in (0, len(indexes)-1):
                        record(prefix+"/RandomPoof-on-"+str(index), lambda: generator.outParams[index].setValue(True))
                        record(prefix+"/RandomPoof-off-"+str(index), lambda: generator.outParams[index].setValue(False))
                else:
                    record(prefix+"/"+patternName, module.doUpdates)
                module.removePattern(instance)
                module.doUpdates()
        else:
            for channel in sorted(module.moduleConfig["inputs"]):
                inp, index = module.inputs.getInputAssignment(channel)
                param = module.moduleConfig["inputs"][channel]
                values = ("1", "0") if param["type"] == "text" else (True, False)
                for value in values:
                    record(prefix+"/"+channel+"/"+str(value), lambda: controller.setInputValue(inp, value, index))
    controller.setSafeMode(True)
    if sculpture == "tympani":
        module = controller.sculptureModules["buttons"]
        inp, index = module.inputs.getInputAssignment("disableA")
        record(sculpture+"/buttons/safe-exempt", lambda: controller.setInputValue(inp, True, index))
    controller.doReset()
with open(output, "w") as stream:
    json.dump(results, stream, indent=2, sort_keys=True)
    stream.write("\n")
print("Recorded %d scenarios across all three sculptures" % len(results))
