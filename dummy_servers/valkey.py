"""Dummy Valkey Server
======================

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
import os
import sys
import time
from typing import Any, Generator, Optional
from contextlib import closing, contextmanager
from igbpyutils.file import Filename
import docker.errors
import docker
import valkey
import requests

# spell-checker: ignore appendonly getuid getgid

# Separate CM to help with: https://pylint.readthedocs.io/en/latest/user_guide/messages/warning/contextmanager-generator-missing-cleanup.html
@contextmanager
def _valkey_container(*, docker_network :Optional[str], docker_name :Optional[str], host_address :str, host_port :int,
        verbose :bool, data_dir :Optional[Filename], no_clean :bool) -> Generator[None, None, None]:
    xtra_args :dict[str,Any] = {}  # pylint: disable=duplicate-code
    if docker_name:
        xtra_args['name'] = docker_name
    if docker_network:
        xtra_args['network'] = docker_network
    if data_dir is not None:
        xtra_args['volumes'] = { str(data_dir): {'bind': '/data', 'mode': 'rw'} }
        xtra_args['environment'] = { 'VALKEY_EXTRA_FLAGS': '--appendonly yes' }
    with closing(docker.from_env()) as client:
        container = client.containers.run(
            image='valkey/valkey:8', detach=True, auto_remove=True, ports={ '6379/tcp':(host_address,host_port) }, **xtra_args )
        try:
            yield
        finally:  # pylint: disable=duplicate-code
            if verbose:  # pragma: no cover
                print("\n##### ##### ##### ##### ##### Valkey Docker Logs ##### ##### ##### ##### #####")
                print(container.logs().decode('UTF-8'))
                print("##### ##### ##### ##### #####")
            if not no_clean and data_dir is not None and sys.platform in ('linux','darwin','freebsd'):  # cover-not-win32
                container.exec_run(['valkey-cli','config','set','appendonly','no'], user='root')
                container.exec_run(['chown','-R',f"{os.getuid()}:{os.getgid()}",'/data'], user='root')  # type: ignore[attr-defined,unused-ignore]  # pylint: disable=no-member,line-too-long,useless-suppression  # noqa: E501
            container.kill()  # pylint: disable=duplicate-code
            try:
                container.wait(timeout=10)
            except (requests.RequestException, docker.errors.DockerException) as ex:  # pragma: no cover
                print(f"Warning: container.wait failed with {type(ex).__qualname__} {ex}")

@contextmanager
def DummyValkeyServer(*,  # pylint: disable=invalid-name
        docker_network :Optional[str] = None, docker_name :Optional[str] = None,
        host_address :str = '127.0.0.1', host_port :int = 6379, verbose :bool = False,
        timeout_s :float = 5, data_dir :Optional[Filename] = None, no_clean :bool = False) -> Generator[valkey.Valkey, None, None]:
    """A context manager that provides a Valkey server.

    Ensures that the Valkey server is up before returning.

    :return: A :class:`~valkey.Valkey` instance connected to the server.
    """
    with _valkey_container(docker_network=docker_network, docker_name=docker_name, host_address=host_address,
            host_port=host_port, verbose=verbose, data_dir=data_dir, no_clean=no_clean):
        retry_interval_s :float = 0.5
        start_time = time.monotonic()
        while True:
            try:
                vk = valkey.Valkey()
                # The valkey package leaves the keyword arguments in this method's inherited signature untyped.
                vk.ping()  # pyright: ignore[reportUnknownMemberType]
            except Exception as ex:
                if time.monotonic() > start_time + timeout_s:
                    raise TimeoutError(f'failed to get response from Valkey server within {timeout_s:.3f}s') from ex
                if verbose:  # pragma: no cover
                    print(f"Valkey: Ping failed, will retry in {retry_interval_s:.3f}s...")
                time.sleep(retry_interval_s)
            else:
                if verbose:  # pragma: no cover
                    print(f"Valkey: Ping successful after {time.monotonic()-start_time:.3f}s")
                # https://pylint.readthedocs.io/en/latest/user_guide/messages/warning/contextmanager-generator-missing-cleanup.html
                try:
                    yield vk
                except GeneratorExit:  # pragma: no cover
                    pass
                break
