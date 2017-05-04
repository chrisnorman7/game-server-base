"""Provides the Factory class which is a subclass of
twisted.internet.protocol.ServerFactory."""

import logging
from twisted.internet.protocol import ServerFactory
from attr import attrs, attrib, Factory
from .protocol import Protocol

logger = logging.getLogger(__name__)


@attrs
class Factory(ServerFactory):
    """
    The server facotyr.

    Attributes:
    server
    The instance of Server which this factory is connected to.
    protocol
    The protocol class to use with buildConnection.
    """

    server = attrib()
    protocol = attrib(default=Factory(lambda: Protocol))

    def buildProtocol(self, addr):
        if addr.host in self.server.banned_hosts:
            logger.warning(
                'Blocked incoming connection from banned host %s.',
                addr.host
            )
        else:
            logger.info(
                'Incoming connection from %s:%d.',
                addr.host,
                addr.port
            )
            return self.protocol(
                self.server,
                addr.host,
                addr.port)
