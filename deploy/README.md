# Headless Python 3 controller

From the repository root, using Python 3.11+ with `requirements.txt` installed:

```text
python flaskServer.py --sculpture aota --host 0.0.0.0 --port 8080 --log-level INFO
```

Available sculptures are `aota` (Angel), `serpent`, and `tympani`. Omit `--sculpture` to
choose in the GUI. Configuration paths do not depend on the working directory. The
existing serial ports and mappings remain in `sculptureDefinitions/*.json`.

## Raspberry Pi service template

`firesculpture.service` assumes this final layout:

| Setting | Template value |
| --- | --- |
| Source directory | `/opt/FireSculptureController` |
| Interpreter | `/usr/bin/python3` with the application dependencies installed |
| Service account/group | `firesculpture` |
| Serial access | Supplementary group `dialout` |
| Startup sculpture | `aota` |
| Web listener | `0.0.0.0:8080` |
| Logs | systemd journal |

Prepare the source directory, dependencies, and service account before enabling it.
Adjust User, Group, WorkingDirectory, and ExecStart to the actual Pi installation; no
virtual environment is assumed. The account must be able to read the source and access
the configured serial devices. The unit gives the service process `dialout` membership.

Once those settings have been reviewed on the Pi, from the repository root:

```sh
sudo cp deploy/firesculpture.service /etc/systemd/system/firesculpture.service
sudo systemctl daemon-reload
sudo systemctl enable --now firesculpture
sudo systemctl status firesculpture
sudo journalctl -u firesculpture -f
```

Stop with `sudo systemctl stop firesculpture`. SIGTERM requests safe mode and bounded
serial OFF delivery; the unit restarts on failure and allows 15 seconds for process
shutdown. A restart begins in safe mode. A successful write is not a relay acknowledgement.

This template has not been installed or verified on the Pi. Reboot, physical serial,
disconnect/reconnect, and actual Linux service-stop checks remain pending.

The unchanged Python 2 fallback has its own [setup and launcher](py2/README.md).
