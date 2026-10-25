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
