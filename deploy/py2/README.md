# Preserved Python 2 controller

`py2/` is the unchanged application copied before conversion. `snapshot.json` records
SHA-256 hashes of all 75 original files. The copy includes audio, original dependencies,
all three sculptures, and the GUI. Do not edit these files.

From the repository root on Windows, using the installed Python 2.7.18:

```powershell
$py2 = 'C:\Python27\python.exe'
& $py2 -m pip install --target .deps-py2 -r deploy/py2/requirements.txt
& $py2 deploy/py2/run.py --port 8080
```

Dependencies are local to this repository, separate from Python 3. The launcher changes
to `py2/`, as required by the original relative paths. Only one version should own the
physical serial ports at a time. No branch switch is needed.

To record the original bytes without hardware or real timer threads:

```powershell
$env:PYTHONPATH = (Resolve-Path .deps-py2).Path
& $py2 tools/record_baseline.py --root py2 --output deploy/py2/baseline.json
```

The runner uses the original controller, modules, inputs, patterns, protocols, and Flask
routes. It substitutes manual timers and a recording transport outside the snapshot.
The trace compares logical output events; actual timing is checked separately on the Pi.
