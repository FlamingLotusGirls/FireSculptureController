#!/usr/bin/env python3
"""Run the local touchscreen browser without importing the controller."""
from __future__ import annotations

import array
from contextlib import contextmanager
import fcntl
import glob
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import termios
from threading import Event, Thread
import time
import tty
from urllib.error import URLError
from urllib.request import ProxyHandler, build_opener

URL = 'http://127.0.0.1/?display=touch'
COG_COMMAND = [
    '/usr/bin/dbus-run-session', '--', '/usr/bin/cog',
    '--platform=drm', '--platform-params=renderer=gles',
    '--webprocess-failure=exit', URL,
]


def physical_keyboard_connected(
        sys_input: Path = Path('/sys/class/input'),
        udev_data: Path = Path('/run/udev/data')) -> bool:
    """Use udev's typing-keyboard classification, not the generic KEY flag.

    USB and connected Bluetooth HID keyboards expose input event devices.
    This reads device metadata only, never input events or typed characters.
    """
    for event in sys_input.glob('event*'):
        try:
            device = (event / 'dev').read_text().strip()
            properties = (udev_data / ('c' + device)).read_text().splitlines()
        except FileNotFoundError:
            continue  # Device may have been unplugged during this scan.
        if 'E:ID_INPUT_KEYBOARD=1' in properties:
            return True
    return False


@contextmanager
def keyboard_status(
        status_path: Path | None = None,
        public_path: Path | None = None):
    """Publish a tiny status file through the existing static-file route.

    The changing file lives in the kiosk's tmpfs runtime directory, avoiding
    writes to the SD card on each poll. The static directory has only a link.
    No controller imports, extra web listener, or controller restart needed.
    """
    if status_path is None:
        status_path = Path(os.environ['XDG_RUNTIME_DIR']) / 'keyboard-status.json'
    if public_path is None:
        public_path = Path(__file__).resolve().parents[1] / 'jsGui/kiosk-input.json'
    stop = Event()
    temporary = status_path.with_suffix('.tmp')
    link = public_path.with_suffix('.tmp')

    def publish():
        try:
            connected = physical_keyboard_connected()
        except OSError:
            connected = None
        temporary.write_text(json.dumps({
            'keyboardConnected': connected, 'updatedAt': int(time.time() * 1000)
        }))
        temporary.replace(status_path)

    def monitor():
        while not stop.wait(1):
            try:
                publish()
            except OSError as error:
                print('Keyboard status unavailable: ' + str(error), flush=True)
                return  # The browser rejects stale status and offers its keyboard.

    worker = None
    try:
        publish()
        link.unlink(missing_ok=True)
        link.symlink_to(status_path)
        link.replace(public_path)
        worker = Thread(target=monitor, name='keyboard-status', daemon=True)
        worker.start()
    except OSError as error:
        print('Keyboard detection unavailable: ' + str(error), flush=True)
    try:
        yield
    finally:
        stop.set()
        if worker is not None:
            worker.join(timeout=2)
        for path in (public_path, link, status_path, temporary):
            path.unlink(missing_ok=True)


def display_ready() -> bool:
    """Require accessible KMS and render nodes; numbering may change at boot."""
    accessible = lambda path: os.access(path, os.R_OK | os.W_OK)
    return (any(map(accessible, glob.glob('/dev/dri/card*')))
            and any(map(accessible, glob.glob('/dev/dri/renderD*'))))


def wait_for_server(stop: Event) -> bool:
    """Only GET the UI; never invoke controller commands or start its service."""
    opener = build_opener(ProxyHandler({}))
    print('Waiting for DRM devices and the local web interface', flush=True)
    while not stop.is_set():
        if display_ready():
            try:
                with opener.open(URL, timeout=2) as response:
                    if response.status == 200:
                        return True
            except (OSError, URLError):
                pass
        stop.wait(2)
    return False


@contextmanager
def console_mode():
    """Own the service's VT; keep keyboard input out of the text console."""
    # Linux VT ioctls from linux/kd.h. systemd supplies tty1 as our controlling TTY.
    kd_get, kd_set = 0x4B3B, 0x4B3A
    kb_get, kb_set = 0x4B44, 0x4B45
    kd_graphics, kb_off = 1, 4
    fd = sys.stdin.fileno()
    old_display = array.array('i', [0])
    old_keyboard = array.array('i', [0])
    fcntl.ioctl(fd, kd_get, old_display, True)
    fcntl.ioctl(fd, kb_get, old_keyboard, True)
    old_termios = termios.tcgetattr(fd)
    try:
        tty.setraw(fd, termios.TCSANOW)
        fcntl.ioctl(fd, kb_set, kb_off)
        fcntl.ioctl(fd, kd_set, kd_graphics)
        yield
    finally:
        fcntl.ioctl(fd, kd_set, old_display[0])
        fcntl.ioctl(fd, kb_set, old_keyboard[0])
        termios.tcsetattr(fd, termios.TCSANOW, old_termios)


def main() -> int:
    stop = Event()
    child: subprocess.Popen | None = None

    def request_stop(signum, frame):
        stop.set()
        if child is not None and child.poll() is None:
            try:
                child.terminate()
            except ProcessLookupError:
                pass

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    if not wait_for_server(stop):
        return 0
    env = os.environ.copy()
    env.pop('DISPLAY', None)
    env.pop('WAYLAND_DISPLAY', None)
    env['COG_PLATFORM_DRM_MODE_MAX'] = '800x480'
    with keyboard_status(), console_mode():
        if stop.is_set():
            return 0
        print('Starting Cog with direct DRM/GLES at ' + URL, flush=True)
        child = subprocess.Popen(COG_COMMAND, env=env)
        result = child.wait()
    return 0 if stop.is_set() else (result if result >= 0 else 1)


if __name__ == '__main__':
    raise SystemExit(main())
