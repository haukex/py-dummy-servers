"""Dummy HTTP Server
====================

Author, Copyright, and License
------------------------------

Copyright (c) 2025-2026 Hauke Daempfling (haukex@zero-g.net)
at the Leibniz Institute of Freshwater Ecology and Inland Fisheries (IGB),
Berlin, Germany, https://www.igb-berlin.de/

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Lesser General Public License as
published by the Free Software Foundation, either version 3 of
the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU Lesser General Public License for more details.

You should have received a copy of the GNU Lesser General Public License
along with this program. If not, see https://www.gnu.org/licenses/
"""
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Semaphore, Thread
from contextlib import contextmanager
from typing import NamedTuple
from queue import SimpleQueue

class LoggedRequest(NamedTuple):
    method :str
    path :str
    headers :dict[str, str]
    body :bytes

class _MyHTTPServer(HTTPServer):
    request_log :SimpleQueue[LoggedRequest]
    verbose :bool = False
    def __init__(self, *args, **kwargs):
        self.start_sem = Semaphore(0)
        self.request_log = SimpleQueue()
        if 'verbose' in kwargs:  # pragma: no cover
            self.verbose = kwargs['verbose']
            del kwargs['verbose']
        super().__init__(*args, **kwargs)
    def server_activate(self):
        super().server_activate()
        self.start_sem.release()

class _MyHTTPRequestHandler(BaseHTTPRequestHandler):
    def log_message(self, *args, **kwargs):
        assert isinstance(self.server, _MyHTTPServer)
        if self.server.verbose:  # pragma: no cover
            super().log_message(*args, **kwargs)
    def do_POST(self):  # pylint: disable=invalid-name
        assert isinstance(self.server, _MyHTTPServer)
        body = b''
        try:
            _cl = self.headers.get('Content-Length')
            if _cl is None:
                raise TypeError()
            content_len = int(_cl)
        except (TypeError, ValueError):
            pass
        else:
            body = self.rfile.read( int(content_len) )
        self.server.request_log.put( LoggedRequest(
            method=self.command, path=self.path, headers=dict(self.headers.items()),
            body=body ) )
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Length", "0")
        self.end_headers()
    do_GET = do_POST  # pylint: disable=invalid-name
    do_HEAD = do_POST  # pylint: disable=invalid-name

class DummyHTTP(NamedTuple):
    port :int
    queue :SimpleQueue[LoggedRequest]

@contextmanager
def DummyHTTPServer(*, bind_address :str = '127.0.0.1', bind_port :int = 8083, verbose :bool = False):  # pylint: disable=invalid-name
    """A context manager that provides a dummy HTTP server that can handle GET, POST, and HEAD requests.

    :return: A named tuple that includes a :class:`~queue.SimpleQueue` from which received requests can be retrieved.
    """
    httpd = _MyHTTPServer((bind_address, bind_port), _MyHTTPRequestHandler, verbose=verbose)
    thread = Thread(target=httpd.serve_forever)
    thread.start()
    try:
        httpd.start_sem.acquire(timeout=5)
        yield DummyHTTP(port=httpd.server_port, queue=httpd.request_log)
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(5)
