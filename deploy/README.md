# Headless Python 3 controller

From the repository root, using Python 3.11+ with `requirements.txt` installed:

```text
python flaskServer.py --sculpture aota --host 0.0.0.0 --port 8080 --log-level INFO
```

Available sculptures are `aota` (Angel), `serpent`, and `tympani`. Omit `--sculpture` to
choose in the GUI. Configuration paths do not depend on the working directory. The
existing serial ports and mappings remain in `sculptureDefinitions/*.json`.

## Raspberry Pi service template

`firesculpture.service` is configured for the current Pi:

| Setting | Template value |
| --- | --- |
| Source directory | `/home/pi/FireSculptureController` |
| Interpreter | `/usr/bin/python3` |
| Runtime dependencies | `/home/pi/.local/lib/firesculpture`, supplied through `PYTHONPATH` |
| Service account/group | `pi` |
| Serial access | Supplementary group `dialout` |
| Startup sculpture | `serpent`, starting in safe mode |
| Web listener | `0.0.0.0:80` |
| Logs | systemd journal |

The unit gives the service process `dialout` membership for serial access and
`CAP_NET_BIND_SERVICE` to bind port 80 while running as `pi`. The capability is granted
by systemd to this service; see [systemd capabilities](https://www.freedesktop.org/software/systemd/man/latest/systemd.exec.html#Capabilities).
It uses the existing source checkout and does not require a virtual environment. Runtime
packages are separate from the ignored test artifacts. If installing on another Pi, adjust the
account, paths, and `--sculpture` setting to match that installation.

For a fresh installation, install the pinned runtime packages as the `pi` user:

```sh
cd /home/pi/FireSculptureController
sudo apt install python3-pip
python3 -m pip install --target /home/pi/.local/lib/firesculpture -r requirements.txt
```

The runtime packages have already been installed in that directory on this Pi.
To check imports without starting the controller:

```sh
PYTHONPATH=/home/pi/.local/lib/firesculpture /usr/bin/python3 -c 'import flask, serial, pythonosc; print("Runtime imports OK")'
```

Install the prepared unit, start it now, and enable it at boot:

```sh
cd /home/pi/FireSculptureController
sudo install -m 644 deploy/firesculpture.service /etc/systemd/system/firesculpture.service
sudo systemctl daemon-reload
sudo systemctl enable --now firesculpture
sudo systemctl status firesculpture --no-pager
```

Open `http://<pi-address>/` in a browser. Use `hostname -I` on the Pi to list its
addresses. View recent logs or follow them live:

```sh
sudo journalctl -u firesculpture -n 50 --no-pager
sudo journalctl -u firesculpture -f
```

Ctrl+C exits the log viewer; the service keeps running. Common controls:

```sh
sudo systemctl stop firesculpture
sudo systemctl start firesculpture
sudo systemctl restart firesculpture
sudo systemctl disable --now firesculpture
```

Stop with `sudo systemctl stop firesculpture`. SIGTERM enters safe mode, cancels governed
output without sending ON or OFF, and stops the workers. Tympani's exempt controls retain
their exception. The unit restarts on failure and allows 15 seconds for process shutdown.
A restart begins in safe mode. A successful write is not a relay acknowledgement.

To apply a unit change, including the switch from port 8080 to port 80:

```sh
cd /home/pi/FireSculptureController
sudo install -m 644 deploy/firesculpture.service /etc/systemd/system/firesculpture.service
sudo systemctl daemon-reload
sudo systemctl restart firesculpture
sudo systemctl status firesculpture --no-pager
```

Changes to the application or sculpture JSON need only a restart.
Serpent's unused `ledBus` entry may log a missing `/dev/ttyUSB2`; its configured modules
use `flameBus` at `/dev/ttyUSB0`.

On 2026-10-24, the unit passed `systemd-analyze verify` on the Pi's systemd 257. The pinned
runtime packages installed successfully in `/home/pi/.local/lib/firesculpture`; dependency
checks and controller imports passed using that directory. The port 80 unit was installed
and the running service restarted successfully. It remains enabled at boot, runs as `pi`
with only `CAP_NET_BIND_SERVICE` in its capability sets, and listens on `0.0.0.0:80`.
The GUI returned HTTP 200; `/getData` reported Serpent in safe mode with `flameBus`
connected. Nothing was listening on port 8080 after the restart. Reboot and physical
disconnect/reconnect checks remain pending.

The unchanged Python 2 fallback has its own [setup and launcher](py2/README.md).

## Local touchscreen kiosk

In order to run sculptures onsite without a dedicated laptop computer, we have built
a kiosk mode implementation for embedded devices. This is running on an "RPI 4" with the "classic"
touchscreen ( 800x480 ) not the "version 2" with higher resolution.

WPE, WebKit Embedded, is a way to run a simple kiosk front end for the existing web
app. The web app was not modified, and still exists on port 80 (embedded)

The separate `firesculpture-kiosk.service` runs Cog 0.18.4 with WPE WebKit 2.48.3
directly on DRM/KMS using `renderer=gles`. It displays
`http://127.0.0.1/?display=touch` as an additional client. Flask continues to serve
other devices on port 80. The query parameter identifies the touchscreen for future
UI adaptations; the current page does not yet change its layout for this parameter.

The browser runs as `pi` with `video`, `render`, and `input` access. Its launcher
waits for graphics devices and a successful GET of the local UI, then opens Cog in
a private D-Bus session. It neither imports nor manages the controller. The service
owns tty1 and disables console keyboard processing while active, so keyboard input
goes to the browser through libinput. There is no desktop, external compositor, or
interactive login. WebKit's normal sandbox remains enabled.

Packages used on this Pi were installed with:

```sh
sudo apt-get install --no-install-recommends cog mesa-utils libdrm-tests libinput-tools
```

To install and start the prepared kiosk service:

```sh
sudo sh /home/pi/FireSculptureController/deploy/install-kiosk.sh
```

The installer reserves tty1 by masking its getty and enables the kiosk at boot.
It does not change or restart `firesculpture.service`. Browser failures restart only
the display client. No reboot is required to start it. Inspect or stop it over SSH:

```sh
systemctl status firesculpture-kiosk --no-pager
journalctl -u firesculpture-kiosk -n 50 --no-pager
sudo systemctl stop firesculpture-kiosk
```

To remove automatic kiosk startup and restore the tty1 login prompt:

```sh
sudo systemctl disable --now firesculpture-kiosk
sudo systemctl unmask getty@tty1.service
sudo systemctl enable --now getty@tty1.service
```

### Display assessment, 2026-10-26

Live inspection confirmed a Pi 4 Model B Rev 1.5, Debian 13.7/aarch64, kernel
6.18.50+rpt-rpi-v8, full `vc4-kms-v3d`, and the original official 7-inch DSI panel
at 800 × 480 and 60.03 Hz. The FT5x06 touchscreen is handled by libinput. Mesa
26.2.2 initialized EGL 1.5/OpenGL ES 3.1 on V3D; browser GPU handles showed actual
V3D rendering activity.

Cog's default `modeset` renderer failed to create a framebuffer (`Invalid argument`).
The `gles` renderer presented the page successfully without Cage or Weston. A
two-minute test confirmed physical corner taps, canvas-knob changes, and app-tab
navigation. A subsequent five-minute run completed without a renderer crash or
framebuffer error. The animation test ran near 60 fps; file-descriptor counts stayed
bounded. This is a smoke test, not an unattended endurance or reboot qualification.

