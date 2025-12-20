"""Tests for Dummy HTTP Server
==============================

Author, Copyright, and License
------------------------------

Copyright (c) 2025 Hauke Daempfling (haukex@zero-g.net)
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
import unittest
import requests
from dummy_servers.http import DummyHTTPServer

VERBOSE = False

class TestHTTPServer(unittest.TestCase):

    def test_httpd(self):
        with DummyHTTPServer(verbose=VERBOSE) as httpd:
            requests.get( f'http://localhost:{httpd.port}/', timeout=5 ).raise_for_status()
            requests.head( f'http://localhost:{httpd.port}/hello', timeout=5 ).raise_for_status()
            requests.post( f'http://localhost:{httpd.port}/testing/', json={'foo':'bar'}, timeout=5,
                headers={ 'Authorization': 'Token testing' } ).raise_for_status()

            req = httpd.request_log.get(timeout=5)
            self.assertEqual( req.method, 'GET' )
            self.assertEqual( req.path, '/' )
            self.assertEqual( req.body, b'' )

            req = httpd.request_log.get(timeout=5)
            self.assertEqual( req.method, 'HEAD' )
            self.assertEqual( req.path, '/hello' )
            self.assertEqual( req.body, b'' )

            req = httpd.request_log.get(timeout=5)
            self.assertEqual( req.method, 'POST' )
            self.assertEqual( req.path, '/testing/' )
            self.assertEqual( req.headers['Content-Length'], str(len(req.body)) )
            self.assertEqual( req.headers['Authorization'], 'Token testing' )
            self.assertEqual( req.body.strip(), b'{"foo": "bar"}' )

            with self.assertRaises(Exception):
                httpd.request_log.get(timeout=1)
