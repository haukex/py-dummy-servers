"""Dummy SMTP Server
====================

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
import logging
from queue import SimpleQueue
from typing import Generator, NamedTuple
from contextlib import contextmanager
from email.parser import Parser, BytesParser
from email.message import EmailMessage
import email.policy
from aiosmtpd import smtp  # https://aiosmtpd.aio-libs.org/
from aiosmtpd.controller import Controller

# spell-checker: ignore aiosmtpd

class _MyMailHandler:
    def __init__(self, *, queue :SimpleQueue[EmailMessage], verbose :bool):
        self.queue = queue
        self.verbose = verbose
    async def handle_DATA(self, _server: smtp.SMTP, session: smtp.Session, envelope: smtp.Envelope) -> str:  # pylint: disable=invalid-name
        # this code is based on aiosmtpd.handlers.Message, which doesn't use email.policy.default
        if isinstance(envelope.content, (bytes, bytearray)):
            msg = BytesParser(policy=email.policy.default).parsebytes(envelope.content)
        elif isinstance(envelope.content, str):  # pragma: no cover  # not sure how I can get this covered
            msg = Parser(policy=email.policy.default).parsestr(envelope.content)
        else:  # pragma: no cover
            raise TypeError(f"Expected str or bytes, got {type(envelope.content)}")
        assert isinstance(msg, EmailMessage)
        message = msg
        message["X-Peer"] = str(session.peer)
        message["X-MailFrom"] = 'unknown' if envelope.mail_from is None else envelope.mail_from
        message["X-RcptTo"] = ', '.join(envelope.rcpt_tos)
        if self.verbose:  # pragma: no cover
            print(f"=== Received an Email ===\n{message.as_string()}")
        self.queue.put(message)
        return "250 OK"

class DummySMTP(NamedTuple):
    host :str
    port :int
    queue :SimpleQueue[EmailMessage]

@contextmanager
def DummySMTPServer(*,  # pylint: disable=invalid-name
        hostname :str = '127.0.0.1', port :int = 8025, verbose :bool = False) -> Generator[DummySMTP, None, None]:
    """A context manager that provides a dummy SMTP server.

    :return: A named tuple that includes a :class:`~queue.SimpleQueue` from which received messages can be retrieved.
    """
    if not verbose:  # pragma: no branch
        for log in ('mail.log', 'asyncio'):
            logging.getLogger(log).setLevel(logging.WARNING)
    queue :SimpleQueue[EmailMessage] = SimpleQueue()
    smtpd = Controller(handler=_MyMailHandler(queue=queue, verbose=verbose), hostname=hostname, port=port)
    smtpd.start()
    if verbose:  # pragma: no cover
        print(f"SMTP Server up at {smtpd.hostname}:{smtpd.port}")
    try:
        yield DummySMTP(host=smtpd.hostname, port=smtpd.port, queue=queue)
    finally:
        smtpd.stop()
        if verbose:  # pragma: no cover
            print("SMTP Server down")
        assert queue.empty()
