# Python 3 port verification

Run commands from the repository root with Python 3.11 or newer. Install the test tools
into your chosen Python environment; a virtual environment is optional:

```text
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

In the existing Windows checkout, use `.venv\Scripts\python.exe` in place of `python`
to use the environment already installed. Warnings are errors by default. No test opens
a physical serial port: transports are `loop://` or recording/failing adaptors, and
HTTP/OSC tests bind to localhost on temporary ports.

## What the tests cover

| File | Evidence |
| --- | --- |
| `tests/test_reference.py` | All 75 frozen file hashes; 47 unchanged configuration/GUI files; 59 application scenarios against the saved baseline and a fresh Python 2 run; HeartBeat controls and 360 steps across 42 LEDs with third-party packages disabled. |
| `tests/test_serial.py` | Exact relay/Tympani bytes through loopback; 92 old/new protocol cases with explicit safe-mode suppression differences; silent startup, safe-mode cancellation, Tympani exemption, failed/partial writes, reconnect, queue overflow/age, and bounded shutdown. |
| `tests/test_osc.py` | Actual UDP pulse/toggle/value routing, GUI address lists, bundles/timetags, pulse auto-OFF, cancellation, self-stop, and socket reuse. |
| `tests/test_lifecycle.py` | All sculptures and listed patterns, Chase spacing/reverse, pattern removal, timers, reload, partial initialization, HTTP commands, SSE, and consistent state snapshots. |
| `tests/test_shutdown.py` | Headless boot, SIGINT/SIGTERM handlers, startup/worker failure, final Angel OFF bytes, and joined workers in isolated processes. |

Python 2 is optional for ordinary development. Tests find it via `PYTHON2`, `python2`
on PATH, or `C:/Python27/python.exe`. Legacy dependencies come from `.deps-py2/` or
`PYTHON2PATH` if set; the Python 3 `PYTHONPATH` is never passed to Python 2. See
[legacy setup](deploy/py2/README.md). The two fresh Python 2 comparisons are reported
as skipped when the interpreter is absent; the full-application comparison also needs
the legacy dependencies. A bad explicitly selected interpreter or a failing comparison
is a failure. The saved-baseline comparison always runs.

## Byte comparison and its limits

`deploy/py2/baseline.json` is the reference recorded from the original application.
`tools/record_baseline.py` runs independently under either interpreter, using each
version's controller, Flask routes, modules, inputs, patterns, and protocol encoders.
Only timers and the data-channel manager are replaced externally: clocks advance
manually and a recording transport captures output without hardware.

The same 59 scenarios load Angel, Serpent, and Tympani and exercise manual ON/OFF,
AllPoof, Chase positions, controlled RandomPoof outputs, HeartBeat/FromImage, and
Tympani's input controls and safe-mode exemption. RandomPoof receives explicit output
values, not a shared random seed. Writes are concatenated per bus within each scenario;
write-call boundaries are ignored but byte order within a bus is preserved. The JSON
stores ASCII strings losslessly because the current nonempty protocols are ASCII.
The separate 92-case runner checks every mapped protocol output, representative values,
and both safe-mode states. Ordinary and exempt output must match Python 2 exactly;
governed safe-mode cases must now produce empty output instead of the legacy packets.

This proves the unchanged scenarios produce the same bytes. It does not measure real
timer cadence, physical relay operation, or the new writer's recovery behavior. Live OSC
routing and changed transport/lifecycle behavior have their own tests. Both versions'
Serpent LED protocol emits no bytes; agreement there does not validate an LED protocol.

To keep reviewable captures on Windows without overwriting the saved reference:

```powershell
$py2 = 'C:\Python27\python.exe'
$py3 = '.\.venv\Scripts\python.exe'
New-Item -ItemType Directory -Force artifacts | Out-Null
& $py3 tools/record_baseline.py --root . --output artifacts/new.json
$savedPythonPath = $env:PYTHONPATH
try {
    $env:PYTHONPATH = (Resolve-Path .deps-py2).Path
    & $py2 tools/record_baseline.py --root py2 --output artifacts/old.json
} finally {
    $env:PYTHONPATH = $savedPythonPath
}
& $py3 -c 'import json; from pathlib import Path; old = json.loads(Path("artifacts/old.json").read_text()); new = json.loads(Path("artifacts/new.json").read_text()); assert old == new; print("All", len(old), "scenarios match")'
```

`artifacts/`, `.deps-py2/`, and `.venv*/` are ignored local files. The committed baseline
and snapshot manifest are reference inputs, not outputs to regenerate during testing.

## Intentional differences from Python 2

| Change | Expected behavior and verification |
| --- | --- |
| Audio removed from the active application | No audio input or PyAudio dependency; original audio remains in `py2/`. |
| HeartBeat waveform stubbed | Controls and renderer remain, but every LED stays black; exercised without SciPy/NumPy or any third-party packages. |
| Serpent LED wire stub retained | Returns `b""` and sends no data; the real protocol is deferred. FromImage remains a stub too. |
| OSC routing corrected | Each configured address reaches its own output. Empty GUI address lists remain empty; the default host is `0.0.0.0`. Tested with real local UDP. |
| Numeric portability fixes | GUI numeric text-list bounds are converted before constraining; zero is a valid bound. RandomPulse supplies integer bounds. Recorded under step 2; no separate regression files for these two fixes. |
| Silent safe mode | No governed output, including OFF, at startup, safe-mode entry, reconnect, or controller shutdown. Pending and cached output is discarded. Tympani's `ignoreSafeMode` button controls remain exempt. The 92 protocol cases compare ordinary/exempt bytes exactly and require empty output for governed safe-mode cases. |
| Delivery recovery | Failed OFF remains pending while safe mode is off; safe-mode entry cancels it. Failed, full, or expired queues restore permitted current state instead of replaying stale ON history. Serial tests exercise these paths. |
| Lifecycle cleanup | Reload/shutdown stop workers and release sockets/bindings. Removing a pattern recomputes output immediately. Future OSC waits can be cancelled on stop. |
| Logging and headless launch | Console logging, boot-time sculpture selection, threaded HTTP/SSE, and orderly shutdown replace the old server behavior. Missing serial devices are reported; governed output is not retried in safe mode. |

See [delivery and safe-mode details](dev-notes.md#serial-delivery-and-safe-mode) for the
limits: queue acceptance is not successful delivery, a driver write is not a hardware
acknowledgement, and disconnected hardware cannot receive OFF until the connection returns.

## Static checks and protected source

Compile only the active application and supporting checks:

```text
python -W error -m compileall -q SculptureController.py flaskServer.py sendOscTest.py Inputs Patterns ProgramModules tests tools
python -W error -c "import SculptureController"
```

Do not run `compileall .` or repository-wide source transformations over `py2/`.
Pytest discovery and mypy targets are explicit in `pyproject.toml`; setuptools discovery
and `MANIFEST.in` exclude the legacy tree and local environments. Deployment uses the
source checkout, not a wheel. Keep `config.json`, `sculptureDefinitions/`, and `jsGui/`
alongside the root scripts.

Run the type checker separately:

```text
python -m mypy
```

The configuration targets Python 3.11 and the 26 active source files. Missing annotations
are allowed where no useful type is known; fully unannotated function bodies are not
checked. There are no blanket error suppressions. Configuration schemas and structural
interfaces are in `ProgramModules/Types.py` and `ProgramModules/Interfaces.py`; supported implementations
are checked through `TYPE_CHECKING` declarations. See
[typing boundaries](dev-notes.md#typing-and-extension-interfaces) for deliberate dynamic
values and the steps for adding an implementation. Mypy does not validate JSON at runtime.

## Recorded verification and remaining field checks

Step 7, step 8, and the safe-mode correction results are recorded in [the migration plan](PLAN_python3.md). The Windows checks
use Python 3.13.17 and Python 3.11.15, with Python 2.7.18 for the fresh reference. The
3.11 run uses the same installed runtime/pytest packages via `PYTHONPATH`; it is not a
separate clean dependency installation. Requirements are pinned to the verified local
environment; installation on the Pi still needs validation.

Windows shutdown tests invoke the registered handlers through Python's interrupt
mechanism. Actual Linux signal delivery and systemd behavior remain unverified.

On the available Pi, exercise **all three** configurations with actual timers and serial
I/O: GUI controls and patterns, numeric text-list inputs, RandomPoof, safe-mode entry,
silent startup, disconnect/reconnect, reload, Ctrl+C, and service stop/restart/reboot. Compare
captured bytes and inspect pulse durations/cadence separately. Capture through a suitable
paired adaptor or the sculpture bus with relay loads unpowered; keep the gas side off
for these checks. Record which physical paths were tested. Independently launch the
preserved Python 2 fallback after installation and rerun the snapshot checks.
