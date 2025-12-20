"""Tests for Dummy FTP Server
=============================

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
from tempfile import TemporaryDirectory
from contextlib import closing
from pathlib import Path
import unittest
import ftplib
import io
from dummy_servers.ftp import DummyCustomPureFtpd, DockerNetwork
from dummy_servers.valkey import DummyValkeyServer

# spell-checker: ignore Unicödé xread

VERBOSE = False

class TestPureFtpdServer(unittest.TestCase):

    def _ftp_test(self, ftp :tuple[str, int]):
        with closing(ftplib.FTP_TLS()) as ftps:
            if VERBOSE:  # pragma: no cover
                ftps.set_debuglevel(2)
            ftps.connect(host=ftp[0], port=ftp[1])
            ftps.login(user='test_user', passwd='PASS_WORD')
            ftps.storbinary("STOR Hello.txt", io.BytesIO(b'Hello, World!'))
            ftps.storbinary("STOR Unicödé.txt", io.BytesIO('€uro'.encode('UTF-8')))
            ftps.storbinary("STOR World.txt", io.BytesIO(b'foobar'))
            self.assertEqual( sorted(ftps.nlst()), sorted([".","..","Hello.txt","Unicödé.txt","World.txt"]) )
            ftps.quit()

    def test_ftpd(self):
        with TemporaryDirectory() as td:
            tempdir = Path(td)
            with DummyCustomPureFtpd(verbose=VERBOSE, data_dir=td, docker_name='test-ftp-server') as ftp:
                # Note the context manager already does a health check on the server.
                self.assertTrue( (tempdir/'test_user').is_dir() )
                self.assertFalse( (tempdir/'test_user'/'Hello.txt').exists() )
                self.assertFalse( (tempdir/'test_user'/'Unicödé.txt').exists() )
                self.assertFalse( (tempdir/'test_user'/'World.txt').exists() )
                self._ftp_test(ftp)
                self.assertEqual( (tempdir/'test_user'/'Hello.txt').read_text('ASCII'), 'Hello, World!' )
                self.assertEqual( (tempdir/'test_user'/'Unicödé.txt').read_text('UTF-8'), '€uro' )
                self.assertEqual( (tempdir/'test_user'/'World.txt').read_text('ASCII'), 'foobar' )
            self.assertRegex( (tempdir/'upload.log').read_text(encoding='UTF-8'),
                r'^[-0-9T:,+]+\ttest_user\t13\t/srv/ftp/test_user/Hello\.txt\n'
                r'[-0-9T:,+]+\ttest_user\t6\t/srv/ftp/test_user/Unicödé\.txt\n'
                r'[-0-9T:,+]+\ttest_user\t6\t/srv/ftp/test_user/World\.txt$' )

    def test_ftpd_valkey(self):
        with DockerNetwork(verbose=VERBOSE) as network_name:
            with ( DummyValkeyServer(verbose=VERBOSE, docker_name='test-valkey', docker_network=network_name) as vk,
                   DummyCustomPureFtpd(verbose=VERBOSE, docker_network=network_name, valkey_host='test-valkey') as ftp ):
                self._ftp_test(ftp)

                # look at the upload log
                uploads :list[dict] = []
                last_id = b'0'
                for _ in range(3):
                    rv = vk.xread(count=1, block=1000, streams={ 'pure-ftpd.uploads': last_id })
                    # [ [ b'pure-ftpd.uploads', [
                    #   (b'1760026109534-0', {b'time': b'2025-10-09T16:08:29,526222249+00:00', ...}),
                    #   (b'1760026109543-0', {b'time': b'2025-10-09T16:08:29,537292982+00:00', ...}),
                    # ] ] ]
                    assert isinstance(rv, list) and len(rv)==1, rv
                    assert isinstance(rv[0], list) and len(rv[0])==2 and rv[0][0]==b'pure-ftpd.uploads', rv[0]
                    assert isinstance(rv[0][1], list) and len(rv[0][1])==1, rv[0][1]
                    assert isinstance(rv[0][1][0], tuple) and len(rv[0][1][0])==2 and isinstance(rv[0][1][0][0], bytes), rv[0][1][0]
                    last_id = rv[0][1][0][0]
                    assert isinstance(rv[0][1][0][1], dict), rv[0][1][0][1]
                    uploads.append(rv[0][1][0][1])
                self.assertEqual(len(uploads), 3)
                self.assertEqual(uploads[0][b'user'], b'test_user')
                self.assertEqual(uploads[0][b'size'], b'13')
                self.assertEqual(uploads[0][b'name'], b'/srv/ftp/test_user/Hello.txt')
                self.assertEqual(uploads[1][b'user'], b'test_user')
                self.assertEqual(uploads[1][b'size'], b'6')
                self.assertEqual(uploads[1][b'name'], '/srv/ftp/test_user/Unicödé.txt'.encode('UTF-8'))
                self.assertEqual(uploads[2][b'user'], b'test_user')
                self.assertEqual(uploads[2][b'size'], b'6')
                self.assertEqual(uploads[2][b'name'], b'/srv/ftp/test_user/World.txt')

                # make sure there are a few entries in the log
                rv = vk.xread( streams={'pure-ftpd.log': '0'} )
                assert isinstance(rv, list) and len(rv)==1, rv
                assert isinstance(rv[0], list) and len(rv[0])==2 and rv[0][0]==b'pure-ftpd.log', rv[0]
                assert isinstance(rv[0][1], list) and all(
                    isinstance(x, tuple) and len(x)==2 and isinstance(x[0], bytes) and isinstance(x[1], dict)
                    and list(x[1])==[b'msg'] and isinstance(x[1][b'msg'], bytes) for x in rv[0][1] ), rv[0][1]
                logs :list[bytes] = [ x[1][b'msg'] for x in rv[0][1] ]
                if VERBOSE:  # pragma: no cover
                    print("===== Valkey pure-ftpd.log =====")
                    for line in logs:
                        print(line)
                    print("=====")
                self.assertGreater( len(logs), 5 )
