# Plan: Python 3 port of FireSculptureController, runnable headless on a Raspberry Pi

## Context

The repo is a Python 2.7 control framework for Flaming Lotus Girls fire sculptures
(Flask + gevent web UI, pattern engine, serial output to flame-relay boards and LEDs).
The mandate is to make it Python 3 (with small modernizations) and runnable headless on a
Raspberry Pi. All three sculptures must remain supported and be exercised: Serpent Mother
(`serpent`), Tympani Lambada (`tympani`), and Angel of the Apocalypse (`aota`). Angel is
likely to be the next deployment and has the same readiness requirement as Serpent.
Keep everything except audio in the Python 3 application; preserve the complete original
application, including audio, in `py2/` before conversion.

Decisions already made:

- **Human readability takes priority.** Prefer clear names, straightforward control flow,
  and small, understandable changes over clever abstractions or terse code. Type hints
  and concurrency changes must serve that goal.
- **Implementation and local commits authorized (2026-10-24).** Work on `py3_port`;
  do not push. Keep each completed step reviewable.
- **Keep a runnable, unchanged Python 2 copy in `py2/`.** Switching branches is not the
  recovery path. Preserve the current working application files, not merely `HEAD`, and
  verify a separate Python 2.7 environment can run them (step 0).

- **Remove the audio input unit.** This also removes pyaudio, numpy and PortAudio.
- **Keep OSC.** pyOSC is Python 2-only, so it moves to `python-osc`.
- **Keep all configuration and all patterns,** including ones Serpent doesn't use
  (`RandomPoof`, Tympani LEDs, `InputOnlyModule`) and the stubs (`FromImage`, and the mock
  `SerpentMotherLedProtocol`).
- **Use the `py3_port` branch.** The runnable Python 2
  reference also lives in `py2/` alongside the port; it must not depend on a branch switch.
- **Target Python 3.11+** (`requires-python = ">=3.11"`), which is what Pi OS Bookworm ships.
  Use the available Pi to verify the actual interpreter and dependencies before field
  deployment. `typing.Self`, `NotRequired`, and `StrEnum` are available at this minimum.
- **Add type hints to most functions and methods,** checked by mypy (step 8). The code is
  very dynamic (`getattr` dispatch, `InputCollection.__getattr__`, nested dict configs), so
  the goal is useful coverage, not strict-everywhere.
- **Remove scipy and numpy entirely by stubbing HeartBeat** (step 4). The real heartbeat
  source will be your ECG code with beat recognition, to be piped in later.

**Today's scope (2026-10-24): leave the Serpent LED wire protocol as a stub.**
The active work is steps 0-8. `SerpentMotherLedProtocol` remains a no-op, returning `b""`
in Python 3 and emitting no serial bytes. Step 9 is deferred future work, not a dependency
or completion requirement for today; receiving the spec does not automatically reopen it.
The existing relay and Tympani LED protocols still receive the Python 3 bytes conversion.

## Work plan (reviewable steps; local commits only)

**0. Preserve and run the original Python 2 application before editing it.**
- Copy the current application tree byte-for-byte into `py2/`, retaining its directory
  layout: root Python scripts, `Inputs/` (including audio), `Patterns/`, `ProgramModules/`,
  all three `sculptureDefinitions/`, `config.json`, `jsGui/` with vendored assets,
  `requirements.txt`, and the original documentation. Include current application changes
  even if uncommitted. Exclude `.git/`, the snapshot directory itself, generated caches,
  virtual environments, and this migration-only plan.
- Record and verify a relative-path/file-hash manifest outside `py2/`. Do not modernize,
  repair, reformat, or remove dependencies from the preserved files. Later Python 3 work
  must leave this snapshot unchanged.
- Establish a separate Python 2.7 interpreter and compatible dependencies, including the
  legacy Flask/gevent, pyserial, pyOSC, and audio/scientific dependencies needed by the old
  application. Record working versions and reproducible setup/launch instructions outside
  the snapshot, under `deploy/py2/`. The old unpinned requirements alone are insufficient.
- Launch the original with `py2/` as its working directory, verify the GUI and all three
  sculpture configurations using a recording transport, and establish the byte-comparison
  baseline before conversion. Test tooling may substitute hardware and clocks externally;
  it must not edit the preserved source or use the Python 3 implementation as its oracle.
- Keep Python 2 and Python 3 imports, dependency environments, and launch commands separate.
  Run one controller at a time against a physical port. Verify the original can still be
  launched after the port is present, without checking out another branch.

**1. Remove audio from the Python 3 application only — completed 2026-10-24.**

Removed the active audio implementation, registration, dependencies, and documentation
references. Verified all 59 existing byte scenarios match the Python 2 baseline and all
75 preserved snapshot files retain their original hashes. No Python 3 syntax conversion
in this step; the verification runner still uses Python 2.7.

Original checklist:
Delete [Inputs/Audio.py](Inputs/Audio.py). Then edit these places:
- [Inputs/__init__.py](Inputs/__init__.py): drop the `Audio` import and its `inputTypes` entry.
- [SculptureController.py:28](SculptureController.py#L28): drop `['pulse','audio']` from the
  `availableGlobalInputs` list.
- [requirements.txt](requirements.txt) and [README.md](README.md): drop pyaudio and numpy.
- The audio mentions in docstrings and in the `flaskServer.py` testing comments.

The GUI has no audio-specific code, so `jsGui/` is untouched.

**2. Python 3 portability changes — completed 2026-10-24.**

Converted syntax, package-relative imports, JSON key views, integer division, and exception
handling; added UTF-8 context-managed config reads and fixed the explicit output-index key.
Corrected random-pulse integer bounds and GUI numeric text-list bounds before constraining
values. Preserved tab indentation and the original `py2/` files.

Verification: the active application compiles on Python 3.11 and 3.13. Controller import,
configuration loading, and state JSON passed on 3.13. Numeric-input and random-pulse
behavior passed on both versions with manual timers. All 59 serial scenarios still match
the saved baseline when the active application runs under Python 2.7; all 75 snapshot
hashes match. Full Python 3 GUI/serial operation awaits the later dependency, server, and
bytes steps. No new dedicated test files were added for the two reproduced portability bugs.

Original checklist (active application only, excluding `py2/`):
- `print` statement → `logger` calls (`Adaptors.py:17` is a per-frame debug print;
  `flaskServer.py:108,112` are startup/error messages). `except X, e` → `except X as e`.
- Implicit relative imports → package-relative imports. About 15 sites:
  `Inputs/__init__.py`, `Inputs/{Basic,Osc,InputBase}.py`, `Patterns/__init__.py`,
  `ProgramModules/{Adaptors,DataChannelManager,sharedObjects}.py`.
- `.iteritems()` → `.items()`. `.keys()` handed to JSON → `list(...)`, at
  [SculptureController.py:98](SculptureController.py#L98) and
  [Messenger.py:72](ProgramModules/Messenger.py#L72). Plain membership tests such as
  `in x.keys()` can stay.
- `/` → `//` where Python 2 integer division was intended:
  [Poof.py](Patterns/Poof.py) `Chase.getState` (`spacing`), [LED.py:163](Patterns/LED.py#L163).
  **Chase is a silent behaviour change if missed.**
- `except StandardError` in [SculptureModules.py](ProgramModules/SculptureModules.py)
  `addPattern`. The block also leaves `newInstanceId` unbound on error, so simplify it.
- `e.message` → `str(e)`. `Event.isSet()` → `is_set()`. Wrap `open()` calls in `with`.
- Latent bug at [InputManager.py:42](ProgramModules/InputManager.py#L42): `outParamIndex` is an
  undefined name on a currently dead path. Fix it to the string key.
- Fix the reproduced random-pulse failure in [Inputs/Basic.py](Inputs/Basic.py): rarity
  and duration inputs currently produce floats, but `random.randint()` requires integer
  bounds on Python 3.12+. Give these integer-valued parameters integer types and normalize
  bounds before calling `randint`, including values supplied by reassigned inputs.
- Fix the reproduced numeric-string failure in [Inputs/IoParams.py](Inputs/IoParams.py):
  the GUI sends basic-multi minimums, maximums, and defaults as text lists. Normalize numeric
  bounds before the first `constrain()` call, preserving the explicit `False` sentinel for
  an absent bound and treating numeric zero as a valid bound. Calling `int(...)` and then
  discarding its result is not conversion. This can be fixed server-side without GUI edits.
- These two reproduced errors belong in the portability checklist; no separate dedicated
  regression tests are required for them. Exercise the affected controls and RandomPoof
  in the application checks below.
- Leave the tab indentation alone in this step (see simplification S7).

**3. Serial bytes, loopback, and blocking writer — completed 2026-10-24.**

Converted protocol output and serial writes to bytes, added `serial_for_url` support and
integer baud-rate updates, and replaced the spinning writer with a bounded blocking
queue. Failed delivery, full queues, and expired backlog restore current output state;
failed OFF commands retry without another module update. Safe-mode transitions cancel
queued governed relay commands and prioritize all-OFF while retaining Tympani's exempt
controls. Serial shutdown is bounded, and the writer owns closing its connection.
Delivery semantics and limits are documented in `dev-notes.md`.

Verification: 16 focused transport checks pass with warnings treated as errors on Python
3.11.15 and 3.13.17, using `loop://` and controlled failures. The unchanged Python 2
protocols and Python 3 protocols produce identical bytes across 92 cases covering all
mapped outputs in all three sculptures, both safe-mode states, and representative values.
The Serpent LED protocol remains empty. All 75 preserved snapshot hashes match; sculpture
configurations and GUI assets remain unchanged. The 59-scenario full-application comparison
still awaits the later dependency/server changes; physical serial and Pi checks are pending.
Focused transport tests were brought forward from step 7 to verify this delivery change.

Original checklist:
This is the Python 3 serial/network type issue. See the boundary table below. It is the
riskiest change in the port, because `serial.write()` needs `bytes` and the current bare
`except:` in `SerialAdaptor.transmitData` would swallow the `TypeError` and only log
"failure sending data". Nothing would crash and nothing would reach the relays.
- Make the data path `bytes` end to end, not encode-at-the-edge. `ProtocolBase.dataCache`
  becomes `b""`, and every `formatData` returns `bytes`. `FlgRelayProtocol` and
  `TympaniLedProtocol` do `.encode("ascii")` on their existing format strings. The adaptor
  receives only `bytes`. Queue entries retain the channel and cancellation generation
  alongside each bytes payload so safe-mode transitions can invalidate pending flame
  commands without discarding exempt controls on the same bus. A future Serpent LED
  protocol may be binary and will produce `bytes` natively.
- Open ports with `serial.serial_for_url(...)`, which accepts normal device names and also
  `loop://`. The app can then run on a laptop with no hardware, and tests can read back the exact bytes.
- Coerce `baudrate` to `int` in `updateSerialConnection` (the GUI sends a string).
- Replace the busy-wait `AdaptorThread` in
  [DataChannelManager.py](ProgramModules/DataChannelManager.py) with a blocking `queue.Queue`.
  The current loop spins a core at 100% and races on `self.data +=`.
- Make queue acceptance distinct from a successful serial write. A failed OFF must remain
  pending or be regenerated during reconnect; advancing `currentOutputState` must not
  suppress its retry. On reconnect, resynchronize current required state rather than
  replaying obsolete ON commands. Surface delivery failures in the log/status.
- Coordinate safe-mode changes and writes: invalidate unsent ON commands for non-exempt
  relay channels and prioritize their OFF frames. Prevent a concurrent producer from
  enqueueing an old-generation ON after invalidation. Preserve ordering within each bus
  and define a bounded backlog policy so delayed flame actions are not replayed later.
- **Documented behavior change: all-OFF in safe mode.** On sculpture load with safe mode
  enabled, on enabling safe mode, and on reconnect while safe, explicitly send OFF for
  every mapped relay output governed by safe mode, even if cached state already says OFF.
  This is a set of existing per-address OFF commands, not a new broadcast wire command.
- **Keep Tympani's `ignoreSafeMode` behavior.** Its button-disable channel intentionally
  bypasses safe-mode gating. Exempt channels are not forcibly cleared or filtered by the
  new all-OFF behavior, including when they share a serial adaptor with flame outputs.
- Document the boundary: unsent application commands can be cancelled; bytes already
  handed to the driver or hardware cannot be recalled. A successful write is not a relay
  acknowledgement, and a disconnected bus cannot deliver OFF until communication returns.
- Set a finite serial write timeout. Stop producers, finish the required OFF attempt with
  a bounded wait, wake and join the writer, then close the port. Serialize port changes
  with writes; closing the connection must not race a writer that reconnects it.

**4. Stub HeartBeat's waveform; remove scipy and numpy.**
[LED.py:289-294](Patterns/LED.py#L289) is the only scipy use: a *fixed* waveform (`daub(10)`
resampled to 50 points, twice), and `signal.wavelets` was removed from current SciPy, so the
pattern can't import on a fresh install anyway. Per your direction, the heartbeat will come
from your ECG code with beat recognition, so:
- Keep the `HeartBeat` class, its `inputParams` (so the GUI and config still list it), and
  every method signature and call site (`triggerStep`, `triggerSequence`,
  `_update_heart_position`, `getState`, etc.).
- Keep the pure-Python render half (`LED`, `LEDGrid`, distance falloff, color), which has
  no dependencies and is what a real beat will drive.
- Replace only the waveform source: `_compute_heart_values` returns a flat placeholder, so the
  pattern is inert (`getState` gives `(0, 0, 0)`), with a `TODO` and a log line saying it is a stub.
- Remove the `scipy` and `signal` imports. Nothing else in the tree uses numpy or scipy.

*Pipe-through hook, not built now:* a beat is a **pulse**, and the input system already has
pulse inputs. A beat recognizer could send an OSC `/heart/beat` message, which the OSC input
(kept) turns into a pulse that `triggerStep` can bind to, with no further plumbing.

**5. OSC: pyOSC → python-osc.**
Rewrite the server thread in [Inputs/Osc.py](Inputs/Osc.py) onto
`pythonosc.dispatcher.Dispatcher` and `BlockingOSCUDPServer`. `serve_forever()` runs in the
thread. Stop it from another thread with `shutdown()`, close its socket with
`server_close()`, and join the thread. Stopping must work without an incoming packet and
release the port for the next load. The current `handle_request()` loop cannot do that.
The `setupParamsNeeded` GUI contract and the public `OscMultiInput` stay.
Two fixes ride along:
- `getOutputIndexFromAddress` references an undefined `outputTypes` and effectively always
  returns index 0. Replace it by binding each address to its out-param index when
  registering handlers.
- The default host `127.0.0.2` can't be reached from a phone. Make it configurable, with
  `0.0.0.0` as the headless default.

Port [sendOscTest.py](sendOscTest.py) to `SimpleUDPClient`.

**6. Web server and headless launch** (see simplification S1 for the gevent decision).
- `gevent.wsgi` → `gevent.pywsgi` at minimum.
- Make `debug` False, add `--host` (default `0.0.0.0`) and `--log-level`.
- Add `--sculpture <id>` to load a sculpture at boot. Today someone must click one in the
  browser. The SSE bindings added inside the `doCommand` route move into a shared helper so
  boot-time loading wires them too. Safe mode stays on at boot, with the explicit
  non-exempt relay all-OFF behavior from step 3.
- Resolve `config.json` and `sculptureDefinitions/` relative to the file, not the current
  directory, so systemd can launch it from anywhere.
- Add `deploy/firesculpture.service`, a systemd unit running as a user in the `dialout`
  group. It restarts on failure and logs to journald.
- Add orderly SIGTERM, Ctrl+C, and exception cleanup. Stop incoming commands and pattern
  producers, request safe mode/all-OFF, complete the bounded serial shutdown, and release
  resources. A restart starts in safe mode; it does not establish that hardware received OFF.
- Make sculpture reset/reload clean up old safe-mode bindings, messenger subscriptions,
  OSC sockets, and timer threads, including the per-item auto-OFF timers. Wait for callbacks
  to finish before replacing shared managers; never join a thread from its own callback.
  Keep existing timer refresh/changeInterval semantics rather than replacing the timer
  framework. Serialize controller mutations from concurrent HTTP requests and callbacks.

**7. Tests, requirements, docs.**
- Pin `requirements.txt` to `flask`, `pyserial`, `python-osc`, plus `gevent` only if S1 isn't
  taken. No scipy, numpy or pyaudio.
- Add `pyproject.toml` (`requires-python`, pytest and mypy config) and `requirements-dev.txt`
  (pytest, mypy, `types-pyserial`).
- Rewrite [README.md](README.md) (Python 3, install, running headless, systemd, all three
  sculptures, and how to launch the preserved Python 2 version) and fix [dev-notes.md](dev-notes.md).
  Explain when all-OFF is sent, the delivery limits, and Tympani's retained `ignoreSafeMode`
  exception. Record intentional differences from Python 2 beside the comparison results.
- Exclude `py2/` and its environment from Python 3 compilation, pytest discovery, mypy,
  packaging, and automatic source transformations. The separate baseline runner invokes
  Python 2 explicitly. Verify snapshot hashes after the port.
- Add `tests/` with pytest. Details are in Verification below. Tests land *before* the
  typing pass so they guard it.

**8. Type hints and mypy.** A separate reviewable step after the port, so the type changes
are not tangled with the porting diff. Keep annotations readable.
- Annotate arguments and returns on essentially all functions and methods in
  `ProgramModules/`, `Inputs/`, `Patterns/`, `SculptureController.py` and `flaskServer.py`.
- Model the JSON schemas with `TypedDict` (sculpture definition, adaptor config, protocol
  config with its `mapping`, module config). The runtime JSON stays as-is, so no behaviour
  change.
- Turn the "Methods needed" lists in [dev-notes.md](dev-notes.md) into `typing.Protocol`
  classes for adaptors, protocols and inputs, so a new adaptor or protocol that forgets a
  method fails the type check.
- Honest limits: `InputCollection.__getattr__` (returns a value *or* a bound method
  depending on the channel), the `getattr(Inputs, className)` factories and the
  `getattr(self, functionName)` command dispatch stay `Any`, each with a one-line comment.
- mypy runs non-strict at first. `disallow_untyped_defs = true` is turned on per package as
  each is finished. mypy also flags undefined names, which would have caught the
  `outParamIndex` and `outputTypes` bugs found during planning.
- Hints are annotation-only, with no runtime effect.

## Deferred future work — outside today's scope

**9. Serpent Mother LED protocol.** Keep the stub for today's work. Resume this step only
when explicitly requested and the spec is available. The following notes are retained
for that future work:
- **Wire format:** framing, ASCII or binary, per-pixel RGB layout, header/terminator.
  Implement `SerpentMotherLedProtocol.formatData` ([Protocols.py](ProgramModules/Protocols.py))
  to return `bytes`.
- **Serial settings and bus:** baud and port, and whether the LEDs really share a bus with
  the flame relays. [serpent.json](sculptureDefinitions/serpent.json) currently puts both on
  `flameBus` and leaves `ledBus` unused, which is a safety-relevant question. The config is
  updated to match the doc.
- **Hardware match:** confirm the spec (from another sculpture) describes Serpent's LED
  controller, not a different board.
- **Pixel mapping:** the current logical grid is 1×42; its addresses cover seven boards
  with six outputs each. Confirm how those addresses map to actual LED strip/pixel indices
  from the spec; do not assume a physical 7×6 grid. Express the result in `mapping`.
- **Update model:** the engine sends changes only, as deltas
  ([SculptureModules.py](ProgramModules/SculptureModules.py) `doUpdates`). If the controller
  wants steady full frames, add a full-frame send path for this module. The module-type
  question also lands here: `serpent.json` declares the LEDs as `"Poofer"`, while an unused
  `LEDModule` exists.
- **Tests:** golden-bytes tests built from any examples in the spec, run against `loop://`.
  Hardware check only after the loopback passes.

## Where Python 3's `str` / `bytes` split bites (serial and network)

| Boundary | Python 2 behaviour | Python 3 | Plan |
|---|---|---|---|
| **Serial write** ([Adaptors.py](ProgramModules/Adaptors.py), `connection.write`) | `str` was bytes, so `"!0111."` just worked | `write()` needs `bytes`. A `str` raises `TypeError`, which the bare `except:` hides. | **Step 3:** protocols return `bytes`, the whole path is typed `bytes`, and a loopback test asserts the exact bytes. |
| Serial read | Not implemented (no sculpture sends data back) | Would be `bytes` | Type `receiveData -> bytes` in the adaptor `Protocol`, still unimplemented. |
| HTTP request body (`request.data` in [flaskServer.py](flaskServer.py)) | `str` | `bytes`. `json.loads` accepts bytes on 3.6+, so it works, but use `request.get_json(force=True)`. | Step 6. |
| SSE stream (`/dataStream`) | `str` | `str`; Flask encodes it as UTF-8 | Nothing to change beyond simplifying the encoder (S5). |
| **OSC (UDP)** ([Osc.py](Inputs/Osc.py)) | pyOSC gives `str` args | `python-osc` handles the byte-level packet encoding itself. Arguments arrive as `int`/`float`/`str`/`bool`, and TouchOSC-style apps send floats like `1.0`. | Step 5. The existing `in ['1', 1, 'true', 'True']` check still matches `1.0` because `1.0 == 1`. |
| JSON files (`json.load(open(...))`) | bytes decoded implicitly | Text mode, locale-dependent encoding | Open with `encoding="utf-8"` inside a `with`. |

## Simplifications on the table

S2, S3, S4, and S6 are already part of the agreed plan. Other recommendations remain
pick-or-skip choices; the queue and launch changes include the lifecycle and safety
requirements above.

| # | Simplification | Gain | Risk / cost | Recommendation |
|---|---|---|---|---|
| S1 | **Drop gevent and greenlet.** Use Flask's threaded server and `queue.Queue` for the SSE stream. | Removes the only heavy, compiled dependency (the README already complains about greenlet on Win7). It also fixes a real bug: SSE queues are gevent `Queue`s fed from plain OS threads (timers, serial), which isn't thread-safe unless `monkey.patch_all()` is used, and it isn't. | Werkzeug's server is "dev grade", but it's fine for a LAN-only controller with a handful of browsers. Each open SSE tab holds a thread. | **Yes.** The fallback is `gevent.pywsgi` plus `monkey.patch_all()`. |
| S2 | **Stub HeartBeat's waveform and drop scipy/numpy** (step 4, per your direction). | No scipy/numpy install on the Pi (large wheels), faster startup (the code comment admits the import is slow), and the pattern imports on current Python. | HeartBeat is inert until the ECG beat source is wired in. The GUI entry and calls remain. | **Yes**, per your direction. |
| S3 | **Blocking-queue serial writer** (step 3). | Frees a full CPU core on the Pi and removes a data race. | Write timing, cancellation, failure recovery, and shutdown need the explicit behavior in step 3. | **Yes**, it's already in the plan. |
| S4 | **`serial_for_url` / `loop://` dev mode** (step 3). | Develop and test on a laptop with no hardware, and assert exact relay bytes. | None. | **Yes**, it's already in the plan. |
| S5 | **Simplify the SSE encoder** in `flaskServer.py`. | `ServerSentEvent` builds a dict keyed by its own values (`None` appears twice), which works by luck. It reduces to `f"data: {payload}\n\n"`. | None. | **Yes.** |
| S6 | **Auto-load the sculpture at boot** (`--sculpture`). | Headless with no browser click needed. | Safe mode starts enabled and sends non-exempt relay OFF frames; delivery still depends on the serial connection. | **Yes**, it's already in the plan. |
| S7 | **Re-indent tabs to 4 spaces.** | PEP 8, and removes the tab/space mix in four files. | A whole-file diff that destroys `git blame` and hides the real port changes. | **No** in this branch. If wanted, do it as a single mechanical last commit. |
| S8 | **Replace the hand-rolled `Timer`** ([Timers.py](ProgramModules/Timers.py)) with `threading.Timer` or asyncio. | Less custom code. | It has `refresh` / `changeInterval` semantics that patterns depend on, and no tests protect them. | **No replacement.** Preserve timing semantics; make the shutdown fixes required in step 6. |
| S9 | **Dataclasses, asyncio, f-strings/pathlib sweep.** (Type hints are now *in* the plan, as step 8.) | Looks modern. | Large diff, no behaviour gain. | **No**, except f-strings and pathlib in code I'm already touching. |
| S10 | **Remove dead code** (`LEDModule` is used by no config, `Image` stubs, `SculptureController.methodList` reflection). | Less to read. | You asked to keep the stubs and patterns, and `LEDModule` is probably where the Serpent LEDs should go once the spec lands. | **No.** Keep, per your direction. |
| S11 | **Vendored jQuery 1.10 / jQuery UI** in `jsGui/lib`. | Newer libs. | Risks breaking the GUI for no headless benefit. | **No.** The assets are already served locally, which is good for offline operation. |

## Things to flag (not fixing now)

- **Serpent LED output stays a no-op throughout today's work.** `SerpentMotherLedProtocol.formatData`
  returns `""` today. In `serpent.json` the `leds` module is declared
  `"moduleType": "Poofer"` (not `LED`) and sits on `flameBus`, the same bus as the flame
  relays, while `ledBus` is unused. HeartBeat's `getState` returns an RGB tuple, which the
  boolean-style `PooferModule` passes through. These questions remain deferred with step 9;
  do not change the LED bus, mapping, or module type today.
- `SculptureController.getCurrentStateData` shallow-copies the config and then overwrites
  entries in the shared `modules` dict. It's harmless today and left alone.
- Input instance IDs now follow dict insertion order (Python 3.7+), so they become
  deterministic. The GUI only uses them as opaque IDs.

## Critical files

[flaskServer.py](flaskServer.py), [SculptureController.py](SculptureController.py),
[ProgramModules/Adaptors.py](ProgramModules/Adaptors.py),
[ProgramModules/DataChannelManager.py](ProgramModules/DataChannelManager.py),
[ProgramModules/Protocols.py](ProgramModules/Protocols.py),
[ProgramModules/SculptureModules.py](ProgramModules/SculptureModules.py),
[ProgramModules/Messenger.py](ProgramModules/Messenger.py),
[Inputs/Osc.py](Inputs/Osc.py), [Inputs/__init__.py](Inputs/__init__.py),
[Patterns/Poof.py](Patterns/Poof.py), [Patterns/LED.py](Patterns/LED.py),
[requirements.txt](requirements.txt), [README.md](README.md).
`sculptureDefinitions/*.json`, `config.json`, and `jsGui/` stay unchanged in today's work.
Spec-driven Serpent LED configuration changes are deferred with step 9. `py2/` always
retains the originals.

## Verification

Prioritize evidence that the controller works on the available Pi before the field trip.
The core regression check is old/new serial-byte comparison for all three sculptures;
keep additional tests focused on behavior and failure paths, not one test per mechanical fix.

1. **Runnable original and byte comparison.** Use the step 0 Python 2.7 environment and
   unchanged `py2/` snapshot alongside the Python 3 application, in separate processes.
   - Load identical configurations for `serpent`, `tympani`, and `aota`. A recording adaptor
     replaces physical serial access externally in both runners.
   - Replay the same operator actions and logical input events, including pattern controls,
     manual outputs, OSC-derived events, safe-mode changes, and Tympani's InputOnly controls.
     Drive timer callbacks in a controlled sequence and supply the same recorded random
     choices rather than assuming a shared random seed gives identical behavior.
   - Capture raw bytes per adaptor/bus and compare exact packet contents and meaningful
     ordering. Concatenate writes when comparing: different write-call boundaries are not
     wire-format differences. Make event and module execution order explicit in the harness
     so Python 2 dictionary iteration does not introduce irrelevant ordering differences.
   - Relay board 1, channel 1, ON must be `!0111.` and OFF `!0110.` (no spaces); include
     Tympani LED packets as well as relay packets. Preserve each sculpture's mappings.
   - Record intentional differences explicitly: removal of audio, the inert HeartBeat
     waveform, corrected OSC routing and portability bugs, new all-OFF frames, and corrected
     failure/lifecycle behavior. Compare unchanged behavior exactly; verify changed behavior
     against its stated requirement. Do not treat Python 2 bugs as required compatibility.
   - For today's work, verify Serpent LED output remains empty in both versions, including
     when LED patterns run. No real Serpent LED wire-protocol or hardware validation is
     required today. Future step 9 needs spec-derived expected bytes because the old mock
     cannot provide an oracle.

2. **Static checks on the Python 3 application only.** Compile the root application scripts
   and `Inputs/`, `Patterns/`, and `ProgramModules/` explicitly, never `compileall .` across
   `py2/`. Check `python -W error -c "import SculptureController"` on 3.11 and the newest
   available Python. After step 8, mypy must pass with the legacy snapshot excluded.

3. **Focused automated checks (`tests/`, pytest, no hardware).**
   - Load all three definitions, instantiate every module and listed pattern, and exercise
     representative behavior rather than stopping at construction. Check Chase's integer
     spacing and that stubbed HeartBeat produces `(0, 0, 0)` without scientific dependencies.
   - Read exact relay and Tympani LED bytes back through `loop://`.
   - Check safe-mode entry and initial load produce OFF for every non-exempt mapped relay.
     Exercise `setItemState`, AllPoof, and a queued ON crossing a safe-mode transition;
     separately verify Tympani's `ignoreSafeMode` controls retain their original behavior.
   - With a controllable failing adaptor, check failed OFF delivery, reconnect/state
     resynchronization, cancellation of stale ON commands, and bounded writer shutdown.
   - Check repeated sculpture loads, timer cleanup, and OSC stop/restart without incoming
     traffic leave no old callbacks, threads, or occupied sockets behind.
   - Flask test client: `/getData`, `/doCommand loadSculpture`, `addPattern`, and an SSE
     message after an output change. Send actual OSC UDP messages and check pulse, toggle,
     and value routing, including per-address mapping.

4. **Interactive checks on the laptop and available Pi.**
   - Run each of `serpent`, `tympani`, and `aota`; use the GUI to exercise the available
     patterns and module controls. In particular, run RandomPoof on Tympani and create a
     basic multi-input using the GUI's numeric text lists to exercise the portability fixes.
   - Run actual timers and serial I/O on the Pi, compare captured packets with the baseline,
     and inspect cadence and pulse durations separately from deterministic byte equivalence.
     Check safe-mode transitions, initial OFF frames, unplug/reconnect, repeated loads,
     Ctrl+C, and service stop/restart. Confirm no spinning writer CPU.
   - Install the service, reboot, and browse to `http://<pi>:8080` from another machine.
     Confirm safe mode is enabled and the expected OFF commands are emitted at boot.
   - Capture serial output using a suitable paired-adaptor setup or the sculpture bus with
     relay loads unpowered. Test real poofers only with the propane/gas side off during
     these checks. Record which configurations and hardware paths were actually exercised;
     software byte equivalence does not establish physical relay operation.
   - Recheck the `py2/` manifest and independently launch the original after the port is
     installed, so the preserved version is an exercised fallback, not just archived source.
