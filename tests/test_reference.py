"""Compare the port with the frozen reference, using external clocks and transport."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "deploy" / "py2"


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def current_trace(tmp_path_factory):
    output = tmp_path_factory.mktemp("reference") / "python3.json"
    subprocess.run(
        [sys.executable, "-W", "error", str(ROOT / "tools/record_baseline.py"),
         "--root", str(ROOT), "--output", str(output)],
        check=True, capture_output=True, text=True, timeout=30,
    )
    return read_json(output)


def test_all_preserved_python2_files_retain_their_original_bytes():
    manifest = read_json(REFERENCE / "snapshot.json")
    assert len(manifest) == 75
    for name, expected_hash in manifest.items():
        data = (ROOT / "py2" / name).read_bytes()
        assert hashlib.sha256(data).hexdigest() == expected_hash, name


def test_active_configuration_and_gui_match_except_serpent_pi_port():
    manifest = read_json(REFERENCE / "snapshot.json")
    unchanged = [name for name in manifest
                 if name == "config.json" or name.startswith(("sculptureDefinitions/", "jsGui/"))]
    assert len(unchanged) == 47
    for name in unchanged:
        current = (ROOT / name).read_bytes()
        original = (ROOT / "py2" / name).read_bytes()
        if name == "sculptureDefinitions/serpent.json":
            # The Pi deployment changes only Serpent's flame-bus port.
            expected = json.loads(original)
            expected["adaptors"]["flameBus"]["ports"] = ["/dev/ttyUSB0"]
            assert json.loads(current) == expected, name
            continue
        path = Path(name)
        if path.suffix in {'.json', '.htm', '.html', '.js', '.css', '.md', '.txt'} or path.name == 'LICENSE':
            # Git checks out LF on Linux; the frozen Windows snapshot retains CRLF.
            current = current.replace(b'\r\n', b'\n')
            original = original.replace(b'\r\n', b'\n')
        assert current == original, name


def test_application_bytes_match_the_saved_python2_baseline(current_trace):
    expected = read_json(REFERENCE / "baseline.json")
    assert len(expected) == 59
    assert {name.split("/")[0] for name in expected} == {"aota", "serpent", "tympani"}
    assert current_trace == expected


def test_application_bytes_match_a_fresh_python2_run(
    current_trace, python2, python2_environment, tmp_path,
):
    probe = subprocess.run(
        [python2, "-c", "import flask, gevent, serial, OSC, scipy, pyaudio"],
        env=python2_environment, capture_output=True, text=True, timeout=30,
    )
    if probe.returncode:
        pytest.skip("Python 2 dependencies unavailable; see deploy/py2/README.md. "
                    + probe.stderr.strip())
    output = tmp_path / "python2.json"
    subprocess.run(
        [python2, str(ROOT / "tools/record_baseline.py"),
         "--root", str(ROOT / "py2"), "--output", str(output)],
        env=python2_environment, check=True, capture_output=True, text=True, timeout=30,
    )
    assert read_json(output) == current_trace


def test_heartbeat_controls_and_black_output_without_third_party_packages():
    # -S disables site-packages entirely; HeartBeat must work with the standard library.
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    subprocess.run(
        [sys.executable, "-S", "-W", "error", str(ROOT / "tests/helpers/check_heartbeat.py")],
        env=environment, check=True, capture_output=True, text=True, timeout=30,
    )
