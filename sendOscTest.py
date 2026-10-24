
"""Send one pulse to the controller's default local OSC listener."""
from typing import cast
from pythonosc.udp_client import SimpleUDPClient


if __name__ == '__main__':
	with SimpleUDPClient('127.0.0.1', 8000) as client:
		# python-osc annotates __enter__ as its base client, but returns this same instance.
		cast(SimpleUDPClient, client).send_message('/1/button1', '1')
