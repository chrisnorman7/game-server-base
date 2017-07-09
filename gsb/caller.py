"""Provides the Caller class."""

from attr import attrs, attrib, Factory


class DontStopException(Exception):
    """The exception raised by Caller.dont_stop."""
    pass


@attrs
class Caller:
    """A
    Caller

    Instances of this class represent a connection calling either a command
    provided with the Server.command decorator or an event such as
    Server.on_connect.

    connection
    The connection which initiated the action.
    text
    The full text of the command (or None if this is an event).
    command
    The command extracted from text.
    args_str
    The full string arguments from the command.
    match
    The match from the regularexpression which matched to call this command (or
    None if this is an event).
    args
    The result of match.groups()
    kwargs
    The result of match.groupdict()
    exception
    An exception which is set by on_error.
    """

    connection = attrib()
    text = attrib(default=Factory(lambda: None))
    command = attrib(default=Factory(str))
    args_str = attrib(default=Factory(str))
    match = attrib(default=Factory(lambda: None))
    args = attrib(default=Factory(tuple))
    kwargs = attrib(default=Factory(dict))
    exception = attrib(default=Factory(lambda: None))

    def dont_stop(self):
        """If called from a command the command interpreter will not stop
        hunting for matching commands."""
        raise DontStopException()
