#!/usr/bin/env python3
"""LAN web UI and headless controller entry point."""
from __future__ import annotations
from collections.abc import Iterator, Sequence
from types import FrameType
from typing import cast
from werkzeug.serving import BaseWSGIServer

import argparse
import json
import logging
from queue import Empty, Queue
import signal
from threading import Event, Lock, Thread

from flask import Flask, Response, abort, jsonify, request
from werkzeug.serving import make_server

import ProgramModules.sharedObjects as app
from ProgramModules.Runtime import failureEvent, synchronized
from SculptureController import ControllerStopped, SculptureController

logger = logging.getLogger(__name__)
flaskApp = Flask(__name__, static_folder='jsGui', static_url_path='/jsGui')
flaskApp.debug = False
sculpture = SculptureController()
serverSentEventStreams: list[Queue[str | None]] = []
streamLock = Lock()
stopping = Event()


class ServerSentEvent:
	def __init__(self, data: str) -> None:
		self.data = data

	def encode(self) -> str:
		return f'data: {self.data}\n\n'


def sendNewOutputState(whatChanged: str) -> None:
	data = json.dumps({whatChanged: app.messenger.getMessages(whatChanged)})
	with streamLock:
		for stream in serverSentEventStreams:
			stream.put(data)


def bindOutputStreams() -> None:
	for channel in ('outputChanged', 'log'):
		app.messenger.addBinding(channel, sendNewOutputState, (channel,))


@synchronized
def executeCommand(command):
	if stopping.is_set():
		raise ControllerStopped('Controller is shutting down')
	result = sculpture.doCommand(command)
	if command[0] == 'loadSculpture':
		bindOutputStreams()
	return result


@flaskApp.before_request
def rejectRequestsDuringShutdown() -> None:
	if stopping.is_set():
		abort(503)


@flaskApp.route('/')
def jsGui() -> Response:
	return flaskApp.send_static_file('index.htm')


@flaskApp.route('/getData', methods=['GET', 'POST'])
def getData() -> Response:
	return jsonify(sculpture.getCurrentStateData())


@flaskApp.route('/doCommand', methods=['POST'])
def doCommand() -> Response:
	command = request.get_json(force=True)
	if not isinstance(command, list) or not command or not isinstance(command[0], str):
		abort(400, description='Expected a non-empty command list')
	try:
		result = executeCommand(command)
	except ControllerStopped:
		abort(503)
	return jsonify({'command': command[0], 'result': result})


@flaskApp.errorhandler(500)
def unexpectedRequestFailure(error: Exception) -> tuple[Response, int]:
	# The main loop will stop producers and attempt relay OFF before exiting.
	failureEvent.set()
	return jsonify({'error': 'Controller command failed; shutting down'}), 500


@flaskApp.route('/dataStream')
def subscribe() -> Response:
	def gen() -> Iterator[str]:
		stream: Queue[str | None] = Queue()
		with streamLock:
			if stopping.is_set():
				return
			serverSentEventStreams.append(stream)
		try:
			yield ': connected\n\n'
			while not stopping.is_set():
				try:
					data = stream.get(timeout=15)
				except Empty:
					yield ': keepalive\n\n'
					continue
				if data is None:
					break
				yield ServerSentEvent(data).encode()
		finally:
			with streamLock:
				if stream in serverSentEventStreams:
					serverSentEventStreams.remove(stream)
	return Response(gen(), mimetype='text/event-stream', headers={'Cache-Control': 'no-cache'})


def closeStreams() -> None:
	with streamLock:
		for stream in serverSentEventStreams:
			stream.put(None)
		serverSentEventStreams.clear()


def main(argv: Sequence[str] | None = None) -> int:
	parser = argparse.ArgumentParser(description='FireSculptureController')
	parser.add_argument('--host', default='0.0.0.0', help='web listener address')
	parser.add_argument('--port', type=int, default=8080, help='web listener port')
	parser.add_argument('--sculpture', choices=sorted(sculpture.sculptureDefinitions),
		help='load this sculpture at startup, in safe mode')
	parser.add_argument('--log-level', type=str.upper, default='INFO',
		choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'])
	args = parser.parse_args(argv)
	logging.basicConfig(level=getattr(logging, args.log_level))
	shutdownRequested = Event()
	previousHandlers = {}
	server: BaseWSGIServer | None = None
	serverThread: Thread | None = None
	result = 0

	def requestShutdown(signum: int, frame: FrameType | None) -> None:
		# Signal handlers only set an event; cleanup runs in normal control flow.
		shutdownRequested.set()

	def serve() -> None:
		try:
			cast(BaseWSGIServer, server).serve_forever(poll_interval=0.05)
		except Exception:
			logger.exception('Web server failed')
			failureEvent.set()
		finally:
			shutdownRequested.set()

	try:
		for signum in (signal.SIGINT, signal.SIGTERM):
			previousHandlers[signum] = signal.signal(signum, requestShutdown)
		if args.sculpture:
			executeCommand(['loadSculpture', args.sculpture])
		server = make_server(args.host, args.port, flaskApp, threaded=True)
		serverThread = Thread(target=serve, name='http-server')
		serverThread.start()
		logger.info('Web server listening on %s:%s', args.host, server.server_port)
		while not shutdownRequested.wait(0.1):
			if failureEvent.is_set():
				break
		if failureEvent.is_set():
			result = 1
	except KeyboardInterrupt:
		pass
	except Exception:
		logger.exception('Controller failed')
		result = 1
	finally:
		stopping.set()
		closeStreams()
		try:
			if not sculpture.stop():
				logger.error('Shutdown could not confirm completion of serial writes')
				result = 1
		except Exception:
			logger.exception('Controller shutdown failed')
			result = 1
		finally:
			if server is not None:
				if serverThread is not None and serverThread.is_alive():
					server.shutdown()
					serverThread.join()
				server.server_close()
			for signum, handler in previousHandlers.items():
				signal.signal(signum, handler)
	return result


if __name__ == '__main__':
	raise SystemExit(main())
