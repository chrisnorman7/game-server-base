"""Test commands."""

from gsb import Command, Server, Caller

s = Server()


def command(caller):
    """A test command."""
    assert isinstance(caller, Caller)


def test_add_command():
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
        assert cmd in s.commands
        assert cmd.func is command
        assert cmd.allowed == 7
    s.command('^$')(print)
    assert len(s.commands) == 2


def test_match_commands():
    s.commands.clear()
    s.command('^test$')(command)
    s.command('^not test$')(print)
    c = Caller(None, text='test')
    r = list(s.match_commands(c))
    assert len(r) == 1
    assert r[0].command.func is command
