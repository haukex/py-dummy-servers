"""Dummy Postgres Server
========================

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
import os
import time
from typing import Any, Generator, Optional
from contextlib import closing, contextmanager
import requests
import psycopg
import docker.errors
import docker

# spell: ignore urandom

@contextmanager
def DummyPostgresServer(*,  # pylint: disable=invalid-name
        docker_network :Optional[str] = None, docker_name :Optional[str] = None,
        postgres_tag :str = '18',
        host_address :str = '127.0.0.1', host_port :int = 15432, verbose :bool = False) -> Generator[psycopg.Connection[tuple[Any, ...]], None, None]:
    xtra_args :dict[str,Any] = {}  # pylint: disable=duplicate-code
    if docker_name:
        xtra_args['name'] = docker_name
    if docker_network:
        xtra_args['network'] = docker_network
    with closing(docker.from_env()) as client:
        admin_pw = os.urandom(16).hex()
        dsn = f"postgresql://postgres:{admin_pw}@{host_address}:{host_port}/postgres"
        container = client.containers.run(
            image='postgres:'+postgres_tag, detach=True, auto_remove=True, ports={ '5432/tcp':(host_address,host_port) },
            environment={ 'POSTGRES_PASSWORD': admin_pw }, **xtra_args )
        try:
            deadline = time.monotonic() + 10
            while True:
                try:
                    conn = psycopg.connect(dsn, connect_timeout=2)
                except psycopg.OperationalError as ex:
                    if time.monotonic() >= deadline:
                        raise  # pragma: no cover
                    if verbose:  # pragma: no cover
                        print(f"Postgres connect failed ({ex}), will retry in 1s...")
                    time.sleep(1)
                else:
                    break
            with conn:
                yield conn
        finally:  # pylint: disable=duplicate-code
            if verbose:  # pragma: no cover
                print("\n##### ##### ##### ##### ##### Postgres Docker Logs ##### ##### ##### ##### #####")
                print(container.logs().decode('UTF-8'))
                print("##### ##### ##### ##### #####")
            container.kill()
            try:
                container.wait(timeout=10)
            except (requests.RequestException, docker.errors.DockerException) as ex:  # pragma: no cover
                print(f"Warning: container.wait failed with {type(ex).__qualname__} {ex}")
