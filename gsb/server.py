"""Contains the Server base class."""

import logging
from re import search
from inspect import isclass
from contextlib import contextmanager
from datetime import datetime
from twisted.internet import reactor
from attr import attrs, attrib, Factory
from .caller import Caller, DontStopException
from .factory import Factory as ServerFactory
from .command import Command, CommandMatch
from .intercept import Intercept

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
    command_class
    The class for new commands.
    commands
    A list of the commands added to this server with the @Server.command
    decorator.
    connections
    A list of protocol objects that are connected.
    """

    port = attrib(default=Factory(lambda: 4000))
    interface = attrib(default=Factory(lambda: '0.0.0.0'))
    factory = attrib(default=Factory(lambda: None), repr=False)
    command_class = attrib(default=Factory(lambda: Command))
    abort_command = attrib(default=Factory(lambda: '@abort'))
    commands = attrib(default=Factory(list), repr=False, init=False)
    connections = attrib(default=Factory(list), init=False, repr=False)
    started = attrib(default=Factory(lambda: None))

    def __attrs_post_init__(self):
        if self.factory is None:
            self.factory = ServerFactory(self)

    def is_banned(self, host):
        """Determine if host is banned. Simply returns False by default."""
        return False

    def run(self):
        """Run the server."""
        if self.started is None:
            self.started = datetime.now()
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

    def on_command(self, caller):
        """A command was sent. This event should evaluate to True to allow
        further processing."""
        return True

    def on_error(self, caller):
        """An exception was raised by a command. In this instance caller has
        an extra exception attribute which holds the exception which was
        thrown."""
        caller.connection.notify('There was an error with your command.')

    def on_connect(self, caller):
        """A connection has been established. Send welcome message ETC."""
        pass

    def on_disconnect(self, caller):
        """A client has disconnected."""
        pass

    def match_commands(self, caller):
        """Search for commands which match."""
        line = caller.text
        for cmd in self.commands:
            match = search(cmd.regexp, line)
            if match and (
                cmd.allowed is None or cmd.allowed(caller)
            ):
                yield CommandMatch(cmd, match)

    def call_command(self, command, caller):
        """Call command with caller as it's argument."""
        return command.func(caller)

    def handle_line(self, connection, line):
        """Handle a line of text from a connection."""
        # Let's build an instance of Caller:
        caller = Caller(connection, text=line)
        if self.on_command(caller):
            if line == self.abort_command and connection.intercept is not None:
                if connection.intercept.no_abort:
                    connection.notify(connection.intercept.no_abort)
                    return connection.intercept.explain(connection)
                else:
                    connection.notify(connection.intercept.aborted)
                    connection.intercept = None
            elif connection.intercept:
                intercept = connection.intercept
                connection.intercept = None
                intercept.feed(caller)
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

    def huh(self, caller):
        """Notify the connection that we have no idea what it's on about."""
        caller.connection.notify("I don't understand that.")

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

    @contextmanager
    def default_kwargs(self, **kwargs):
        """Decorator to automatically send kwargs to self.add_command."""
        def f(*a, **kw):
            for key, value in kwargs.items():
                kw.setdefault(key, value)
            return self.command(*a, **kw)
        try:
            logger.debug('Adding commands with default kwargs: %r.', kwargs)
            yield f
        finally:
            logger.debug('Context manager closing.')

    def disconnect(self, connection):
        """Disconnect a connection."""
        connection.transport.loseConnection()
