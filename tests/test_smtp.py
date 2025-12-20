"""Tests for Dummy SMTP Server
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
import html
import logging
import unittest
import email.policy
from email.message import MIMEPart
from email.message import EmailMessage
from smtplib import SMTP
import igbpyutils.error
from dummy_servers.smtp import DummySMTPServer

# spell-checker: ignore preferencelist

VERBOSE = False

def send_test_mail(*, subj :str, body :str, smtp_server :str, smtp_port :int, as_bcc :bool = False):
    msg = EmailMessage(policy=email.policy.SMTP)
    msg['From'] = 'sender@example.com'
    if as_bcc:
        msg['To'] = 'fake@example.com'
        msg['BCC'] = 'real@example.com'
    else:
        msg['To'] = 'recipient@example.com'
    msg['Subject'] = subj
    msg.set_content(body)
    msg.add_alternative(f"<html><body>{html.escape(body)}</body></html>", subtype='html')
    with SMTP(host=smtp_server, port=smtp_port, timeout=3) as smtp:
        smtp.send_message(msg)

class TestSMTPServer(unittest.TestCase):

    def test_smtp(self):
        igbpyutils.error.logging_config(level=logging.DEBUG if VERBOSE else logging.INFO)
        with DummySMTPServer(verbose=VERBOSE) as smtp:
            send_test_mail(subj='Test1', body='Hello, World!', smtp_server=smtp.host, smtp_port=smtp.port)
            send_test_mail(subj='Test2', body='Foobar', as_bcc=True, smtp_server=smtp.host, smtp_port=smtp.port)

            msg = smtp.queue.get(timeout=5)
            self.assertEqual( msg["From"], 'sender@example.com' )
            self.assertEqual( msg["X-MailFrom"], 'sender@example.com' )
            self.assertEqual( msg["To"], 'recipient@example.com' )
            self.assertEqual( msg["X-RcptTo"], 'recipient@example.com' )
            self.assertEqual( msg["Subject"], "Test1" )
            body = msg.get_body()
            assert isinstance( body, MIMEPart )
            self.assertEqual( body.get_content(), '<html><body>Hello, World!</body></html>\r\n' )
            body = msg.get_body(preferencelist=('plain',))
            assert isinstance( body, MIMEPart )
            self.assertEqual( body.get_content(), "Hello, World!\r\n" )

            msg = smtp.queue.get(timeout=5)
            self.assertEqual( msg["From"], 'sender@example.com' )
            self.assertEqual( msg["X-MailFrom"], 'sender@example.com' )
            self.assertEqual( msg["To"], 'fake@example.com' )
            self.assertEqual( msg["X-RcptTo"], 'fake@example.com, real@example.com' )
            self.assertEqual( msg["Subject"], "Test2" )
            body = msg.get_body()
            assert isinstance( body, MIMEPart )
            self.assertEqual( body.get_content(), '<html><body>Foobar</body></html>\r\n' )
            body = msg.get_body(preferencelist=('plain',))
            assert isinstance( body, MIMEPart )
            self.assertEqual( body.get_content(), "Foobar\r\n" )
