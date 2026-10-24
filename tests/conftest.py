"""Locate the optional Python 2 reference without mixing its packages into Python 3."""
import os
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def python2():
    executable = os.environ.get("PYTHON2") or shutil.which("python2")
    if not executable and Path("C:/Python27/python.exe").is_file():
        executable = "C:/Python27/python.exe"
    if not executable:
        pytest.skip("Set PYTHON2 to run the preserved Python 2 reference")
    return executable


@pytest.fixture(scope="session")
def python2_environment(python2):
    environment = os.environ.copy()
    environment.pop("PYTHONHOME", None)
    # Never inherit the Python 3 runner's PYTHONPATH into the legacy interpreter.
    environment["PYTHONPATH"] = os.environ.get("PYTHON2PATH", str(ROOT / ".deps-py2"))
    subprocess.run(
        [python2, "-c", "import sys; assert sys.version_info[:2] == (2, 7)"],
        env=environment, check=True, capture_output=True, text=True, timeout=10,
    )
    return environment
