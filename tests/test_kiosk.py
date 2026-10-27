"""Launcher checks that do not open hardware or start the controller."""
import unittest
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import time
from threading import Event
from unittest.mock import MagicMock, patch
from urllib.error import URLError

from deploy import kiosk


class KioskLauncherTests(unittest.TestCase):
    def test_readiness_retries_devices_and_http_without_commands(self):
        stop = MagicMock()
        stop.is_set.return_value = False
        opener = MagicMock()
        response = MagicMock()
        response.__enter__.return_value.status = 200
        opener.open.side_effect = [URLError('not listening yet'), response]
        with patch.object(kiosk, 'build_opener', return_value=opener), \
                patch.object(kiosk, 'display_ready', side_effect=[False, True, True]):
            self.assertTrue(kiosk.wait_for_server(stop))
        self.assertEqual(opener.open.call_count, 2)
        for call in opener.open.call_args_list:
            self.assertEqual(call.args, ('http://127.0.0.1/?display=touch',))
            self.assertEqual(call.kwargs, {'timeout': 2})
        self.assertEqual(stop.wait.call_count, 2)

    def test_stopping_before_readiness_makes_no_http_request(self):
        stop = Event()
        stop.set()
        with patch.object(kiosk, 'build_opener') as build:
            self.assertFalse(kiosk.wait_for_server(stop))
            build.return_value.open.assert_not_called()

    def test_console_modes_are_restored_when_browser_fails(self):
        changes = []

        def ioctl(fd, operation, value, *args):
            if operation == 0x4B3B:
                value[0] = 0  # KD_TEXT
            elif operation == 0x4B44:
                value[0] = 3  # K_UNICODE
            else:
                changes.append((operation, value))

        previous_termios = [1, 2, 3]
        with patch.object(kiosk.sys, 'stdin') as stdin, \
                patch.object(kiosk.fcntl, 'ioctl', side_effect=ioctl), \
                patch.object(kiosk.termios, 'tcgetattr', return_value=previous_termios), \
                patch.object(kiosk.termios, 'tcsetattr') as restore, \
                patch.object(kiosk.tty, 'setraw'):
            stdin.fileno.return_value = 0
            with self.assertRaisesRegex(RuntimeError, 'browser failed'):
                with kiosk.console_mode():
                    raise RuntimeError('browser failed')
            restore.assert_called_once_with(0, kiosk.termios.TCSANOW, previous_termios)
        self.assertEqual(changes, [
            (0x4B45, 4), (0x4B3A, 1),  # Disable console keys; graphics mode.
            (0x4B3A, 0), (0x4B45, 3),  # Restore text and original keyboard mode.
        ])


class KeyboardDetectionTests(unittest.TestCase):
    def test_typing_keyboard_hotplug_ignores_cec_and_touch(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            sys_input, udev = root / 'input', root / 'udev'
            udev.mkdir()

            def device(number, properties):
                event = sys_input / ('event' + str(number))
                event.mkdir(parents=True)
                (event / 'dev').write_text('13:' + str(64 + number))
                data = udev / ('c13:' + str(64 + number))
                data.write_text(properties)
                return data

            device(0, 'E:ID_INPUT_KEY=1\n')  # HDMI CEC has keys, not a keyboard.
            device(4, 'E:ID_INPUT_TOUCHSCREEN=1\n')
            self.assertFalse(kiosk.physical_keyboard_connected(sys_input, udev))
            keyboard = device(5, 'E:ID_BUS=bluetooth\nE:ID_INPUT_KEYBOARD=1\n')
            self.assertTrue(kiosk.physical_keyboard_connected(sys_input, udev))
            keyboard.unlink()  # Unplug during a scan is harmless.
            self.assertFalse(kiosk.physical_keyboard_connected(sys_input, udev))
            device(6, 'E:ID_BUS=usb\nE:ID_INPUT_KEYBOARD=1\n')
            self.assertTrue(kiosk.physical_keyboard_connected(sys_input, udev))

    def test_status_tracks_connection_and_cleans_up(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            status, public = root / 'runtime.json', root / 'public.json'
            with patch.object(kiosk, 'physical_keyboard_connected', return_value=False) as detect:
                with kiosk.keyboard_status(status, public):
                    self.assertTrue(public.is_symlink())
                    self.assertFalse(json.loads(public.read_text())['keyboardConnected'])
                    detect.return_value = True
                    deadline = time.monotonic() + 3
                    while time.monotonic() < deadline:
                        data = json.loads(public.read_text())
                        if data['keyboardConnected']:
                            break
                        time.sleep(0.05)
                    self.assertTrue(data['keyboardConnected'])
                    self.assertLess(abs(data['updatedAt'] - time.time() * 1000), 2000)
                self.assertFalse(public.is_symlink())
                self.assertFalse(status.exists())

    def test_unavailable_detection_reports_unknown(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(kiosk, 'physical_keyboard_connected', side_effect=PermissionError):
                with kiosk.keyboard_status(root / 'runtime.json', root / 'public.json'):
                    data = json.loads((root / 'public.json').read_text())
                    self.assertIsNone(data['keyboardConnected'])


if __name__ == '__main__':
    unittest.main()
