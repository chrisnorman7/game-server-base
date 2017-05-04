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

    Attributes:
    connection
    The connection which initiated the action.
    text
    The full text of the command (or None if this is an event).
    match
    The match from the regularexpression which matched to call this command, or
    None if this is an event.
    """

    connection = attrib()
    text = attrib(default=Factory(lambda: None))
    match = attrib(default=Factory(lambda: None))

    def dont_stop(self):
        """If called from a command the command interpreter will not stop
        hunting for matching commands."""
        raise DontStopException()
