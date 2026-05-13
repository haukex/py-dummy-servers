"""Tests for Dummy Valkey Server
================================

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
import unittest
from unittest.mock import patch
from tempfile import TemporaryDirectory
import valkey
from dummy_servers.valkey import DummyValkeyServer

VERBOSE = False

class TestValkeyServer(unittest.TestCase):

    def test_valkey(self):
        with DummyValkeyServer(verbose=VERBOSE):
            pass  # The context manager already does its own PING self test.

    def test_valkey_persist(self):
        with TemporaryDirectory() as td:
            with DummyValkeyServer(verbose=VERBOSE, data_dir=td, no_clean=True) as vk:
                vk.set('Foo', 'Bar')
            with DummyValkeyServer(verbose=VERBOSE, data_dir=td) as vk:
                self.assertEqual( vk.get('Foo'), b'Bar' )

    def test_valkey_err(self):
        with patch('valkey.Valkey.ping', side_effect=valkey.ValkeyError):
            with self.assertRaisesRegex(TimeoutError, r'\bfailed to get response from Valkey server within\b'):
                with DummyValkeyServer(verbose=VERBOSE, timeout_s=2):
                    pass  # pragma: no cover
