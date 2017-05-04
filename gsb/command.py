"""Provides the Command class."""

from re import compile
from attr import attrs, attrib


@attrs
class Command:
    """
    Command

    Instances of this class represent an entry in the Server.commands list.

    Attributes:
    regexp
    The regular expression which will match this command.
    func
    The command function. This function will be called with an instance of
    Caller as it's only argument assuming allow returns True.
    allowed
    A function which will be called with the same instance of Caller which
    will be used to call func. Should return True (the default) if it is okay
    to run this command, False otherwise.
    """

    regexp = attrib()
    func = attrib()
    allowed = attrib()

    def __attrs_post_init__(self):
        self.regexp = compile(self.regexp)
