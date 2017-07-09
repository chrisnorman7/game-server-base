"""Provides the Command class."""

from re import compile, _pattern_type
from attr import attrs, attrib


@attrs
class Command:
    """
    Command

    Instances of this class represent an entry in the Server.commands list.

    func
    The command function. This function will be called with an instance of
    Caller as its only argument assuming allow returns True.
    names
    1 or more names which describe this command.
    description
    A brief description of this command.
    help
    A help message for this command.
    args_regexp
    The regular expression which will match the arguments of this command, or
    None if no arguments are necessary.
    allowed
    A function which will be called with the same instance of Caller which
    will be used to call func. Should return True (the default) if it is okay
    to run this command, False otherwise.
    """

    func = attrib()
    names = attrib()
    description = attrib()
    help = attrib()
    args_regexp = attrib()
    allowed = attrib()

    def __attrs_post_init__(self):
        if self.args_regexp is not None:
            if not isinstance(self.args_regexp, _pattern_type):
                self.args_regexp = compile(self.args_regexp)
        if not isinstance(self.names, list):
            self.names = [self.names]

    def ok_for(self, caller):
        """Check if caller is allowed to access this command."""
        return self.allowed is None or self.allowed(caller)
