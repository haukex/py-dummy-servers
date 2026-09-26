"""Tests for Dummy LDAP Server
==============================

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
import io
import unittest
from pathlib import Path
from contextlib import redirect_stderr
from tempfile import TemporaryDirectory
from igbpyutils.file import NamedTempFileDeleteLater
from dummy_servers.ldap import DummyLDAPServer
from dummy_servers.ftp import DockerNetwork

# spell: ignore ldif ldifs attributetype objectclass filterstr

VERBOSE = False

# https://github.com/haukex/openldap-for-test/blob/main/ldif/10-example-people.ldif
LDIF = b'''
dn: ou=people,dc=example,dc=de
objectClass: organizationalUnit
ou: people

dn: uid=alice,ou=people,dc=example,dc=de
objectClass: inetOrgPerson
uid: alice
cn: Alice Example
sn: Example
userPassword: alice-test-password
objectClass: withExampleMail
exampleMailAddress: alice@example.com
'''

class TestDummyLDAPServer(unittest.TestCase):

    def test_ldap(self) -> None:
        with NamedTempFileDeleteLater(suffix='.schema') as tf1, NamedTempFileDeleteLater(suffix='.ldif') as tf2:
            # https://github.com/haukex/openldap-for-test/blob/main/schemas/10-example.schema
            tf1.write(b"attributetype ( 1.1.1 NAME 'exampleMailAddress' EQUALITY caseIgnoreMatch SYNTAX 1.3.6.1.4.1.1466.115.121.1.15 )\n"
                      b"objectclass ( 1.1.2 NAME 'withExampleMail' SUP top AUXILIARY MAY ( exampleMailAddress ) )")
            tf1.close()
            tf2.write(LDIF)
            tf2.close()
            ldap_root = 'dc=example,dc=de'
            with DummyLDAPServer(ldap_root=ldap_root, schemas=[tf1.name], ldifs=[tf2.name], verbose=VERBOSE) as ldap:
                with ldap.connect(ldap.admin_user, ldap.admin_pass) as conn:
                    for ldn, attrs in ldap.search(conn):
                        if VERBOSE:  # pragma: no cover
                            print(f"{ldn=} {attrs=}")
                # Note I believe there is a bug in coverage in Python 3.14 that is requiring the following "no branch":
                with ldap.connect('uid=alice,ou=people,dc=example,dc=de', 'alice-test-password') as conn:  # pragma: no branch
                    rv = ldap.search(conn, '(uid=alice)')
                    self.assertEqual(len(rv), 1)
                    self.assertEqual(rv[0][0], 'uid=alice,ou=people,dc=example,dc=de')
                    self.assertEqual(rv[0][1]['cn'][0], b'Alice Example')
                    self.assertEqual(rv[0][1]['exampleMailAddress'][0], b'alice@example.com')

    def test_coverage(self) -> None:
        with DockerNetwork(verbose=VERBOSE) as network_name, redirect_stderr(io.StringIO()) as err, TemporaryDirectory() as td:
            with DummyLDAPServer(ldifs=[td], docker_name='test_ldap', docker_network=network_name, verbose=VERBOSE):
                pass
        self.assertEqual(err.getvalue().strip(), f"Warning: not copying non-regular file {Path(td)}")
