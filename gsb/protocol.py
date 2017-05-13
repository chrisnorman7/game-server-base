"""Provides the Protocol class which is a subclass of
twisted.protocols.basic.LineReceiver until I figure out how the Telnet protocol
works."""

import logging
from twisted.protocols.basic import LineReceiver
from attr import attrs, attrib
from .caller import Caller


@attrs
class Protocol(LineReceiver):
    """
    Server protocol

    Instances oof this class represent a connection to the server.

    server
    An instance of gsb.Server.
    host
    The IP address of the host which this connection represents.
    port
    The port number this connection is connected on.
    """

    server = attrib()
    host = attrib()
    port = attrib()

    def lineReceived(self, line):
        """Handle a line from a client."""
        line = line.decode()
        self.server.handle_line(self, line)

    def connectionMade(self):
        """Call self.server.on_connect."""
        self.logger = logging.getLogger(
            '%s:%d' % (
                self.host,
                self.port
            )
        )
        self.server.connections.append(self)
        self.server.on_connect(Caller(self))

    def connectionLost(self, reason):
        """Call self.server.on_disconnect."""
        if self in self.server.connections:
            self.server.connections.remove(self)
        self.logger.info(
            'Disconnected: %s',
            reason.getErrorMessage()
        )
        self.server.on_disconnect(Caller(self))

    def notify(self, *args, **kwargs):
        """Notify this connection of something."""
        self.server.notify(self, *args, **kwargs)
