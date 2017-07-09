"""Provides the Parser class."""

import logging
from contextlib import contextmanager
from attr import attrs, attrib, Factory
from .caller import Caller, DontStopException
from .command import Command

logger = logging.getLogger(__name__)


@attrs
class Parser:
    """
    Used for parsing commands.
    """

    command_separator = attrib(default=Factory(lambda: ' '))
    commands = attrib(default=Factory(dict), repr=False)
    command_substitutions = attrib(default=Factory(dict))

    def all_commands(self):
        """Get all the command objects present on this parser."""
        l = list()
        for objects in self.commands.values():
            for cmd in objects:
                if cmd not in l:
                    l.append(cmd)
        return l

    def huh(self, caller):
        """Notify the connection that we have no idea what it's on about."""
        caller.connection.notify("I don't understand that.")

    def on_attach(self, connection):
        """This instance has been attached to connection."""
        pass

    def on_detach(self, connection):
        """This instance has been disconnected from connection."""
        pass

    def on_error(self, caller):
        """An exception was raised by a command. In this instance caller has
        its exception attribute set to the exception which was thrown."""
        caller.connection.notify('There was an error with your command.')

    def make_command_names(self, func):
        """Get the name of a command from the name of a function."""
        return [func.__name__]

    def make_command_description(self, func):
        """Make a suitable description for a command."""
        return func.__doc__ or 'No description available.'

    def make_command_help(self, func):
        """Make a suitable help message for a command."""
        return 'No help available.'

    @contextmanager
    def default_kwargs(self, **kwargs):
        """Decorator to automatically send kwargs to self.add_command."""
        def f(*a, **kw):
            for key, value in kwargs.items():
                if key in kw:
                    logger.warning(
                        'Keyword argument %s specified twice: %r, %r.',
                        key,
                        kwargs,
                        kw
                    )
                kw[key] = value
            return self.command(*a, **kw)
        try:
            logger.debug('Adding commands with default kwargs: %r.', kwargs)
            yield f
        finally:
            logger.debug('Context manager closing.')

    def command(self, func=None, **kwargs):
        """A decorator to add a command to this parser."""
        def inner(func):
            names = kwargs.pop(
                'names',
                self.make_command_names(func)
            )
            description = kwargs.pop(
                'description',
                self.make_command_description(func)
            )
            help = kwargs.pop(
                'help',
                self.make_command_help(func)
            )
            args_regexp = kwargs.pop('args_regexp', None)
            allowed = kwargs.pop(
                'allowed',
                lambda caller: True
            )
            c = Command(
                func,
                names,
                description,
                help,
                args_regexp,
                allowed,
                **kwargs
            )
            for name in c.names:
                l = self.commands.get(name, [])
                l.append(c)
                self.commands[name] = l
            return c
        if func is None:
            return inner
        return inner(func)

    def pre_command(self, caller):
        """Called before any command is sent. Should return True if the command
        is to be processed."""
        return True

    def split(self, line):
        """Splits the command and returns (command, args). Both args and string
        should be strings."""
        split = line.split(self.command_separator, 1)
        if len(split) == 1:
            split.append(split[0].__class__())
        return split

    def post_command(self, caller):
        """Called after 0 or more commands were matched."""
        pass

    def get_commands(self, name):
        """Get the commands named name."""
        return self.commands.get(name, [])

    def explain_substitution(self, connection, short, long):
        """Explain command substitutions."""
        connection.notify(
            'Instead of typing "%s%s", you can type %s.',
            long,
            self.command_separator,
            short
        )

    def explain(self, command, connection):
        """Explain command to connection."""
        connection.notify('%s:', ' or '.join(command.names))
        for key, value in self.command_substitutions.items():
            if value in command.names:
                self.explain_substitution(connection, key, value)
        connection.notify(command.description)
        connection.notify(command.help)

    def handle_line(self, connection, line, allow_huh=True):
        """Handle a line of textt from a connection. If no commands are found
        and allow_huh evaluates to True then self.huh is called with caller."""
        if line and line[0] in self.command_substitutions:
            line = self.command_substitutions[
                line[0]
            ] + self.command_separator + line[1:]
        caller = Caller(connection, text=line)
        if not self.pre_command(caller):
            return
        command, args = self.split(line)
        commands = 0  # The number of matched commands.
        for cmd in self.get_commands(command):
            if cmd.allowed(caller):
                if cmd.args_regexp is None:
                    caller.args = ()
                    caller.kwargs = {}
                else:
                    m = cmd.args_regexp.match(args)
                    if m is None:
                        self.explain(cmd, caller.connection)
                        break
                    caller.args = m.groups()
                    caller.kwargs = m.groupdict()
                commands += 1
                try:
                    cmd.func(caller)
                    break
                except DontStopException:
                    continue
                except Exception as e:
                    logger.warning(
                        'Error caught by %r from command %r:',
                        self,
                        cmd
                    )
                    logger.exception(e)
                    caller.exception = e
                    self.on_error(caller)
        else:
            if not commands and allow_huh:
                self.huh(caller)
        if commands:
            return commands
