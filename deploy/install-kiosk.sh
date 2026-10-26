#!/bin/sh
# Install only the display client. Never start, stop, or restart the controller.
set -eu

if [ "$(id -u)" -ne 0 ]; then
    echo 'Run this installer with sudo from a Pi terminal or SSH session.' >&2
    exit 1
fi
project_dir=/home/pi/FireSculptureController
test -f "$project_dir/deploy/kiosk.py"
test -x /usr/bin/cog
test -x /usr/bin/dbus-run-session
test -x /usr/bin/chvt
/usr/bin/python3 -c 'import ast, pathlib; ast.parse(pathlib.Path("/home/pi/FireSculptureController/deploy/kiosk.py").read_text())'
systemd-analyze verify "$project_dir/deploy/firesculpture-kiosk.service"
install -m 644 "$project_dir/deploy/firesculpture-kiosk.service" /etc/systemd/system/firesculpture-kiosk.service
systemctl daemon-reload
# Reserve tty1 for the kiosk; SSH and other virtual consoles remain available.
systemctl mask --now getty@tty1.service
systemctl enable --now firesculpture-kiosk.service
systemctl status firesculpture-kiosk.service --no-pager
