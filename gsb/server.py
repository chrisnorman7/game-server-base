"""Contains the Server base class."""

import logging
from inspect import isclass
from datetime import datetime
from twisted.internet import reactor
from attr import attrs, attrib, Factory
from .caller import Caller, DontStopException
from .parser import Parser
from .factory import Factory as ServerFactory
from .intercept import Intercept, Reader, SpellCheckerMenu

logger = logging.getLogger(__name__)


@attrs
class Server:
    """
    A game server instance.
    This class represents an instance of a game server.

    port
    The port the server should run on.
    interface
    The interface the server should listen on.
    factory
    The Twisted factory to use for dishing out connections.
    default_parser
    The default instance of Parser for new connections.
    connections
    A list of protocol objects that are connected.
    Started
    The time the server was started with Server.run.
    """

    port = attrib(default=Factory(lambda: 4000))
    interface = attrib(default=Factory(lambda: '0.0.0.0'))
    factory = attrib(default=Factory(lambda: None), repr=False)
    default_parser = attrib(default=Factory(Parser), repr=False)
    connections = attrib(default=Factory(list), init=False, repr=False)
    started = attrib(default=Factory(lambda: None), init=False)

    def __attrs_post_init__(self):
        if self.factory is None:
            self.factory = ServerFactory(self)

    def is_banned(self, host):
        """Determine if host is banned. Simply returns False by default."""
        return False

    def run(self):
        """Run the server."""
        if self.started is None:
            self.started = datetime.utcnow()
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
        self.on_start(Caller(None))
        reactor.addSystemEventTrigger(
            'before',
            'shutdown',
            self.on_stop,
            Caller(None)
        )
        reactor.run()

    def on_start(self, caller):
        """The server has started. The passed instance of Caller does nothing,
        but ensures compatibility with the other events. Is called from
        Server.run."""
        pass

    def on_stop(self, caller):
        """The server is about to stop. The passed instance of Caller does
        nothing but maintains compatibility with the other events. Is scheduled
        when Server.run is used."""
        pass

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
        if self.on_command(caller):  # Processing can continue.
            if line == self.abort_command and connection.intercept is not None:
                if connection.intercept.no_abort:
                    connection.notify(connection.intercept.no_abort)
                    return connection.intercept.explain(connection)
                else:
                    intercept = connection.intercept
                    connection.intercept = None
                    connection.notify(intercept.aborted)
            elif connection.intercept:
                intercept = connection.intercept
                connection.intercept = None
                if isinstance(
                    intercept,
                    Reader
                ) and line == self.spell_check_command:
                    connection.notify(
                        SpellCheckerMenu,
                        intercept.get_buffer(),
                        self.reinstate_intercept(intercept)
                    )
                else:
                    try:
                        intercept.feed(caller)
                    except Exception as e:
                        caller.exception = e
                        logger.warning(
                            'Intercept %r threw an error:',
                            intercept
                        )
                        logger.exception(e)
                        self.on_error(caller)
            else:
                for match in self.match_commands(caller):
                    caller.args = match.match.groups()
                    caller.kwargs = match.match.groupdict()
                    try:
                        self.call_command(match.command, caller)
                    except DontStopException:
                        continue
                    except Exception as e:
                        caller.exception = e
                        logger.exception(
                            'Command %r threw an error:',
                            match.command
                        )
                        logger.exception(e)
                        self.on_error(caller)
                    break
                else:
                    caller.args = None
                    caller.kwargs = None
                    caller.match = None
                    self.huh(caller)

    def format_text(self, text, *args, **kwargs):
        """Format text for use with notify and broadcast."""
        if args:
            text = text % args
        if kwargs:
            text = text % kwargs
        return text

    def notify(self, connection, text, *args, **kwargs):
        """Notify connection of text formatted with args and kwargs. Supports
        instances of, and the instanciation of Intercept."""
        if connection is not None:
            if isclass(text) and issubclass(text, Intercept):
                text = text(*args, **kwargs)
            if isinstance(text, Intercept):
                connection.intercept = text
                text.explain(connection)
            else:
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

    def add_command(self, func, *args, **kwargs):
        """Add func to self.commands."""
        cmd = self.command_class(func, *args, **kwargs)
        self.commands.append(cmd)
        return cmd

    def command(self, *args, **kwargs):
        """Add a command to the commands list. Passes all arguments to
        command_class."""
        def inner(func):
            """Calls self.add_command with *args and **kwargs."""
            return self.add_command(func, *args, **kwargs)
        return inner

    def disconnect(self, connection):
        """Disconnect a connection."""
        connection.transport.loseConnection()
