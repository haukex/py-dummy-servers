"""Dummy FTP Server
===================

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
from uuid import uuid4
from typing import Any, Optional, NamedTuple
from contextlib import closing, contextmanager
from igbpyutils.file import NamedTempFileDeleteLater, Filename
import docker.errors
import docker
import requests

@contextmanager
def DockerNetwork(*, verbose :bool):  # pylint: disable=invalid-name
    """A context manager that provides a Docker network.

    :return: The network name (a random string).
    """
    name = f"test-net-{uuid4()}"
    with closing(docker.from_env()) as client:
        net = client.networks.create(name=name)
        if verbose:  # pragma: no cover
            print(f"Created Docker network {net}")
        try:
            yield name
        finally:
            net.remove()
            if verbose:  # pragma: no cover
                print(f"Removed Docker network {net}")

# spell-checker: ignore lftp getuid getgid

class DummyFTP(NamedTuple):
    host :str
    port :int

@contextmanager
def DummyCustomPureFtpd(*,  # pylint: disable=invalid-name, too-many-locals
        docker_network :Optional[str] = None, docker_name :Optional[str] = None,
        image :str = 'ghcr.io/haukex/pure-ftpd:v0.9.6-7a5df7bf',
        host_address :str = '127.0.0.1', host_port :int = 2121, verbose :bool = False,
        ftp_passwd :bytes = b'test_user:PASS_WORD\n', valkey_host :Optional[str] = None,
        data_dir :Optional[Filename] = None):
    """A context manager that provides a `Pure-FTPd <https://github.com/jedisct1/pure-ftpd/>`_
    FTPS server via the custom Docker image <https://ghcr.io/haukex/pure-ftpd>.

    Ensures that the FTP server is up before returning.

    .. note:: While the server's control connection port can be changed via the corresponding
        argument, there is currently no argument for remapping the data ports 30000-30009.
    """
    with closing(docker.from_env()) as client, NamedTempFileDeleteLater() as tfh:
        tfh.write(ftp_passwd)
        tfh.close()
        xtra_args :dict[str,Any] = {}  # pylint: disable=duplicate-code
        if docker_name:
            xtra_args['name'] = docker_name
        if docker_network:
            xtra_args['network'] = docker_network
        if valkey_host:
            xtra_args['environment'] = {'VALKEY_HOST':valkey_host}
        volumes = { tfh.name: {'bind': '/run/secrets/ftp-passwd', 'mode': 'ro'} }
        if data_dir is not None:
            volumes[str(data_dir)] = {'bind': '/srv/ftp', 'mode': 'rw'}
        container = client.containers.run( image=image, init=True, detach=True, auto_remove=True,
            ports={ '21/tcp':(host_address,host_port) }|{ f"{i}/tcp":(host_address,i) for i in range(30000,30010) },
            #extra_hosts={ 'host.docker.internal': 'host-gateway' },  # --add-host=host.docker.internal:host-gateway
            volumes=volumes,
            **xtra_args )
        try:
            if verbose:  # pragma: no cover
                print("Starting Pure-FTPd server...")
            # Note lftp has a built-in auto-reconnect feature, so we just use that here to wait for the server to be up:
            (exitcode, output) = container.exec_run([
                'lftp', '-e', 'set ssl:verify-certificate no; set net:reconnect-interval-base 1; set net:reconnect-interval-multiplier 2;'
                'set net:max-retries 5; ls -a; exit', '-u', 'test_user,PASS_WORD', 'localhost' ])
            if verbose:  # pragma: no cover
                print(f"Pure-FTPd health check output: {output!r}")
            if exitcode:  # pragma: no cover
                raise RuntimeError("Failed to get a positive health check on the Pure-FTPd server")
            yield DummyFTP(host=host_address, port=host_port)
        finally:  # pylint: disable=duplicate-code
            if verbose:  # pragma: no cover
                print("\n##### ##### ##### ##### ##### Pure-FTPd Docker Logs ##### ##### ##### ##### #####")
                print(container.logs().decode('UTF-8'))
                print("##### ##### ##### ##### #####")
            if data_dir is not None and sys.platform in ('linux','darwin','freebsd'):  # cover-not-win32
                container.exec_run(['chown','-R',f"{os.getuid()}:{os.getgid()}",'/srv/ftp'], user='root')  # type: ignore[attr-defined,unused-ignore]  # pylint: disable=no-member,line-too-long,useless-suppression  # noqa: E501
            container.kill()  # pylint: disable=duplicate-code
            try:
                container.wait(timeout=10)
            except (requests.RequestException, docker.errors.DockerException) as ex:  # pragma: no cover
                print(f"Warning: container.wait failed with {type(ex).__qualname__} {ex}")
