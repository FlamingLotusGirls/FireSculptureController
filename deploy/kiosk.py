#!/usr/bin/env python3
"""Run the local touchscreen browser without importing the controller."""
from __future__ import annotations

import array
from contextlib import contextmanager
import fcntl
import glob
import os
import signal
import subprocess
import sys
import termios
from threading import Event
import tty
from urllib.error import URLError
from urllib.request import ProxyHandler, build_opener

URL = 'http://127.0.0.1/?display=touch'
COG_COMMAND = [
    '/usr/bin/dbus-run-session', '--', '/usr/bin/cog',
    '--platform=drm', '--platform-params=renderer=gles',
    '--webprocess-failure=exit', URL,
]


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
    with console_mode():
        if stop.is_set():
            return 0
        print('Starting Cog with direct DRM/GLES at ' + URL, flush=True)
        child = subprocess.Popen(COG_COMMAND, env=env)
        result = child.wait()
    return 0 if stop.is_set() else (result if result >= 0 else 1)


if __name__ == '__main__':
    raise SystemExit(main())
