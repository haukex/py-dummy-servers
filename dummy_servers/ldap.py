"""Dummy LDAP Server
====================

Additionally requires ``openssl`` to be on your ``PATH``.

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
import sys
import time
import shutil
import subprocess
from pathlib import Path
from collections.abc import Iterable
from tempfile import TemporaryDirectory
from contextlib import closing, contextmanager
from typing import Any, Generator, Optional, NamedTuple
import ldap  # pyright: ignore [reportMissingTypeStubs]
from ldap import LDAPError  # pyright: ignore [reportMissingTypeStubs,reportAttributeAccessIssue,reportUnknownVariableType]
import ldap.ldapobject  # pyright: ignore [reportMissingTypeStubs]
from igbpyutils.file import Filename
import requests
import docker.errors
import docker

# spell: ignore urandom ldif ldifs tmpfs CACERTFILE NEWCTX ldapobject newkey noenc addext keyout filterstr

def _copy(src :Optional[Iterable[Filename]], dst :Path, verbose :bool) -> None:
    dst.mkdir()
    if src is not None:
        for fn in src:
            f = Path(fn)
            if f.is_file():
                if verbose:  # pragma: no cover
                    print(f"Copying {f} -> {dst}")
                shutil.copy(f, dst)
                (dst/f.name).chmod(0o644)
            else:
                print(f"Warning: not copying non-regular file {f}", file=sys.stderr)

class LDAPHelper(NamedTuple):
    host :str
    port :int
    root :str
    cert :Path
    admin_user :str
    admin_pass :str

    @property
    def uri(self) -> str:
        return f"ldap://{self.host}:{self.port}"

    @contextmanager
    def connect(self, user :str, passwd :str) -> Generator[ldap.ldapobject.SimpleLDAPObject, None, None]:
        # unfortunately, python-ldap doesn't have sufficient type information
        conn = ldap.initialize(self.uri)  # pyright: ignore [reportUnknownMemberType]
        conn.set_option(ldap.OPT_X_TLS_CACERTFILE, str(self.cert))  # pyright: ignore [reportUnknownMemberType,reportUnknownArgumentType,reportAttributeAccessIssue]  # noqa: E501  # pylint: disable=line-too-long,useless-suppression
        conn.set_option(ldap.OPT_X_TLS_REQUIRE_CERT, ldap.OPT_X_TLS_DEMAND)  # pyright: ignore [reportUnknownMemberType,reportUnknownArgumentType,reportAttributeAccessIssue]  # noqa: E501  # pylint: disable=line-too-long,useless-suppression
        # NEWCTX must be the last option after setting TLS opts
        conn.set_option(ldap.OPT_X_TLS_NEWCTX, 0)  # pyright: ignore [reportUnknownMemberType,reportUnknownArgumentType,reportAttributeAccessIssue]  # noqa: E501  # pylint: disable=line-too-long,useless-suppression
        conn.set_option(ldap.OPT_REFERRALS, 0)  # pyright: ignore [reportUnknownMemberType,reportUnknownArgumentType,reportAttributeAccessIssue]  # noqa: E501  # pylint: disable=line-too-long,useless-suppression
        conn.set_option(ldap.OPT_TIMEOUT, 5)  # pyright: ignore [reportUnknownMemberType,reportUnknownArgumentType,reportAttributeAccessIssue]  # noqa: E501  # pylint: disable=line-too-long,useless-suppression
        conn.start_tls_s()  # this actually opens the connection
        conn.simple_bind_s(user, passwd)  # pyright: ignore [reportUnknownMemberType]
        try:
            yield conn
        finally:
            conn.unbind_s()

    def search(self, conn :ldap.ldapobject.SimpleLDAPObject, filter_str :Optional[str] = None) -> list[tuple[str, dict[str, list[bytes]]]]:
        """A simple `search_s` helper to hide some of the type checker override ugliness.

        ``filterstr=None`` is equivalent to ``filterstr='(objectClass=*)'`` (as of python-ldap 3.0).

        See also https://www.python-ldap.org/en/python-ldap-3.4.6/reference/ldap.html#ldap.LDAPObject.search_s
        (That says "The keys of attrs are strings, and the associated values are lists of strings.", but testing shows they lists are of ``bytes``.)
        """
        return conn.search_s(base=self.root, scope=ldap.SCOPE_SUBTREE, filterstr=filter_str)  # type: ignore[no-any-return]

@contextmanager
def DummyLDAPServer(*,  # pylint: disable=invalid-name, too-many-locals
        docker_network :Optional[str] = None, docker_name :Optional[str] = None,
        image :str = 'ghcr.io/haukex/openldap-for-test:v0.1.0',
        ldap_root :str = 'dc=example,dc=org',
        schemas :Optional[Iterable[Filename]] = None, ldifs :Optional[Iterable[Filename]] = None,
        host_address :str = '127.0.0.1', host_port :int = 17389, verbose :bool = False) -> Generator[LDAPHelper, None, None]:
    xtra_args :dict[str,Any] = {}  # pylint: disable=duplicate-code
    if docker_name:
        xtra_args['name'] = docker_name
    if docker_network:
        xtra_args['network'] = docker_network
    with closing(docker.from_env()) as client, TemporaryDirectory() as temp_dir:
        td = Path(temp_dir)
        _copy(schemas, td/'schemas', verbose)
        _copy(ldifs, td/'ldifs', verbose)
        (td/'certs').mkdir()
        rv = subprocess.run(['openssl','req','-quiet','-batch','-x509','-newkey','rsa:2048','-sha256','-noenc','-days','30',
            '-keyout',td/'certs'/'server.key','-out',td/'certs'/'server.crt','-subj','/CN=localhost',
            '-addext','subjectAltName=DNS:localhost,DNS:ldap,IP:127.0.0.1',
            '-addext','basicConstraints=critical,CA:FALSE',
            '-addext','keyUsage=critical,digitalSignature,keyEncipherment',
            '-addext','extendedKeyUsage=serverAuth'], check=True, capture_output=True, encoding='UTF-8')
        if verbose:  # pragma: no cover
            print(f"openssl STDOUT={rv.stdout!r} STDERR={rv.stderr!r}")
        (td/'certs'/'server.key').chmod(0o600)
        (td/'certs'/'server.crt').chmod(0o644)
        admin_pw = os.urandom(16).hex()
        container = client.containers.run( image=image, detach=True, auto_remove=True,
            ports={ '7389/tcp':(host_address,host_port) },
            volumes={
                str(td/'certs'): {'bind': '/certs', 'mode': 'ro'},
                str(td/'schemas'): {'bind': '/schemas', 'mode': 'ro'},
                str(td/'ldifs'): {'bind': '/ldif', 'mode': 'ro'},
            }, tmpfs={ '/run': '' },
            environment={ 'LDAP_ROOT': ldap_root, 'LDAP_ADMIN_PASSWORD': admin_pw }, **xtra_args )
        h = LDAPHelper(host=host_address, port=host_port, root=ldap_root, cert=td/'certs'/'server.crt',
                       admin_user='cn=admin,'+ldap_root, admin_pass=admin_pw)
        try:
            deadline = time.monotonic() + 10
            while True:
                try:
                    with h.connect(h.admin_user, admin_pw):
                        pass
                except LDAPError as ex:  # pyright: ignore [reportUnknownVariableType]
                    if time.monotonic() >= deadline:
                        raise  # pragma: no cover
                    if verbose:  # pragma: no cover
                        print(f"LDAP connect failed ({ex}), will retry in 1s...")
                    time.sleep(1)
                else:
                    break
            yield h
        finally:  # pylint: disable=duplicate-code
            if verbose:  # pragma: no cover
                print("\n##### ##### ##### ##### ##### LDAP Docker Logs ##### ##### ##### ##### #####")
                print(container.logs().decode('UTF-8'))
                print("##### ##### ##### ##### #####")
            container.kill()
            try:
                container.wait(timeout=10)
            except (requests.RequestException, docker.errors.DockerException) as ex:  # pragma: no cover
                print(f"Warning: container.wait failed with {type(ex).__qualname__} {ex}")
