"""Tests for Dummy Postgres Server
==================================

Author, Copyright, and License
------------------------------

Copyright (c) 2026 Hauke Daempfling (haukex@zero-g.net)
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
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from dummy_servers.ftp import DockerNetwork
from dummy_servers.postgres import DummyPostgresServer

# spell: ignore poolclass

VERBOSE = False

class TestDummyPostgresServer(unittest.TestCase):

    def test_postgres(self) -> None:
        with DummyPostgresServer(verbose=VERBOSE) as conn:
            with conn.cursor() as cur:
                cur.execute("CREATE TABLE test ( id serial PRIMARY KEY, num integer, data text) ")
                cur.execute("INSERT INTO test (num, data) VALUES (%s, %s)", (100, "abc'def") )
                cur.execute("SELECT * FROM test")
                self.assertEqual( cur.fetchone(), (1, 100, "abc'def") )
        with DockerNetwork(verbose=VERBOSE) as network_name:
            with DummyPostgresServer(docker_name='test_postgres', docker_network=network_name, verbose=VERBOSE) as conn:
                engine = create_engine( "postgresql+psycopg://", creator=lambda: conn, poolclass=StaticPool )
                # I'm not sure why this "no branch" is necessary on Python 3.14:
                with engine.connect() as sa_conn:  # pragma: no branch
                    self.assertEqual( sa_conn.exec_driver_sql('SELECT 1').scalar_one(), 1 )
