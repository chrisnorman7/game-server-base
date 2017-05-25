"""Test the Server class."""

from gsb import Server, Command, Caller

s = Server()


def command(caller):
    """A test command."""
    assert isinstance(caller, Caller)


def test_init():
    assert s.connections == []
    assert s.is_banned('test') is False


def test_command():
    s.commands.clear()
    cmd = s.command('^$')(command)
    assert isinstance(
        cmd,
        Command
    )
    assert cmd.func is command
    assert s.commands == [cmd]


def test_default_kwargs():
    s.commands.clear()
    with s.default_kwargs(allowed=7) as add_command:
        cmd = add_command('^$')(command)
        assert isinstance(cmd, Command)
        assert cmd.func is command
        assert cmd.allowed == 7
