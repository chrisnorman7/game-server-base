"""Provides the Command class."""

from re import compile
from attr import attrs, attrib, Factory


@attrs
class Command:
    """
    Command

    Instances of this class represent an entry in the Server.commands list.

    func
    The command function. This function will be called with an instance of
    regexp
    The regular expression which will match this command.
    Caller as it's only argument assuming allow returns True.
    allowed
    A function which will be called with the same instance of Caller which
    will be used to call func. Should return True (the default) if it is okay
    to run this command, False otherwise.
    """

    func = attrib()
    regexp = attrib()
    allowed = attrib(default=Factory(lambda: None))

    def __attrs_post_init__(self):
        self.regexp = compile(self.regexp)
