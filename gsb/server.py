"""Contains the Server base class."""

import logging
from re import search
from datetime import datetime
from twisted.internet import reactor
from attr import attrs, attrib, Factory
from .caller import Caller, DontStopException
from .factory import Factory as ServerFactory
from .command import Command

logger = logging.getLogger(__name__)


@attrs
class Server:
    """
    A game server instance.

    This class represents an instance of a game server. It has several
    important properties and methods.
    Any method which starts with on_ is an event. Events are called the same
    as commands, except that caller.text and caller.match are both None.


    port
    The port the server should run on.
    interface
    The interface the server should listen on.
    factory
    The Twisted factory to use for dishing out connections.
    connections
    A list of protocol objects that are connected.
    banned_hosts
    A list of banned IP addresses.
    on_connect
    Event which fires when a client connects.
    on_disconnect
    An event which fires when a client disconnects.
    run
    A method which runs the server.
    """

    interface = attrib(default=Factory(lambda: '0.0.0.0'))
    port = attrib(default=Factory(lambda: 4000))
    factory = attrib(default=Factory(lambda: None), repr=False)
    commands = attrib(default=Factory(list), repr=False, init=False)
    connections = attrib(default=Factory(list), init=False, repr=False)
    banned_hosts = attrib(default=Factory(list), repr=False)

    def __attrs_post_init__(self):
        if self.factory is None:
            self.factory = ServerFactory(self)

    def run(self):
        """Run the server."""
        started = datetime.now()
        reactor.listenTCP(
            self.port,
            self.factory,
            interface=self.interface
        )
        logger.info(
            'Now listening for connections on %s:%d.',
            self.interface,
            self.port
        )
        reactor.run()
        logger.info('Finished after %s.', datetime.now() - started)

    def on_connect(self, caller):
        """A connection has been established. Send welcome message ETC."""
        pass

    def on_disconnect(self, caller):
        """A client has disconnected."""
        pass

    def handle_line(self, connection, line):
        """Handle a line of text from a connection."""
        # Let's build an instance of Caller:
        caller = Caller(connection, text=line)
        for cmd in self.commands:
            caller.match = search(cmd.regexp, line)
            if caller.match is not None:
                try:
                    cmd.func(caller)
                except DontStopException:
                    continue
                except Exception as e:
                    logger.exception(
                        'Command %r threw an error:',
                        cmd
                    )
                    logger.exception(e)
                break
        else:
            caller.match = None
            self.huh(caller)

    def huh(self, caller):
        """Notify the connection that we have no idea what it's on about."""
        self.notify(caller.connection, "I don't understand that.")

    def format_text(self, text, *args, **kwargs):
        """Format text for use with notify and broadcast."""
        if args:
            text = text % args
        if kwargs:
            text = text % kwargs
        return text

    def notify(self, connection, text, *args, **kwargs):
        """Notify connection of text formatted with args and kwargs."""
        connection.sendLine(
            self.format_text(
                text,
                *args,
                **kwargs
            ).encode()
        )

    def broadcast(self, text, *args, **kwargs):
        """Notify all connections."""
        text = self.format_text(text, *args, **kwargs)
        for con in self.connections:
            self.notify(con, text)

    def command(self, regexp, allowed=lambda: True):
        """
        Add a command to the commands list.

        Arguments:
        regexp
        The regular expression used to invoke the command.
        allowed
        An optional function which should return True if the provided caller
        is allowed to call this command.
        """
        def inner(func):
            """Add func to self.commands."""
            cmd = Command(regexp, func, allowed)
            logger.info(
                'Adding command %r.',
                cmd
            )
            self.commands.append(cmd)
        return inner

    def disconnect(self, connection):
        """Disconnect a connection."""
        connection.transport.loseConnection()
