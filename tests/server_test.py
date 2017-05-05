"""Test the Server class."""

from gsb import Server, Command, Caller

s = Server()


def command(caller):
    """A test command."""
    assert isinstance(caller, Caller)


def test_init():
    assert s.connections == []
    assert s.banned_hosts == []


def test_command():
    s.commands.clear()
    cmd = s.command('^$')(command)
    assert isinstance(
        cmd,
        Command
    )
    assert cmd.func is command
    assert s.commands == [cmd]
