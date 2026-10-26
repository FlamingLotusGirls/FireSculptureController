"""Launcher checks that do not open hardware or start the controller."""
import unittest
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


if __name__ == '__main__':
    unittest.main()
