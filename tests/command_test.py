"""Test commands."""

from gsb import Command, Parser, Caller

p = Parser()


def command(caller):
    """A test command."""
    assert isinstance(caller, Caller)


def test_add_command():
    p.commands.clear()
    cmd = p.command(func=command)
    assert isinstance(
        cmd,
        Command
    )
    assert cmd.func is command
    assert p.commands == {'command': [cmd]}


def test_default_kwargs():
    p.commands.clear()
    with p.default_kwargs(allowed=7) as add_command:
        cmd = add_command(func=command)
        assert isinstance(cmd, Command)
        assert cmd.func is command
        assert cmd.allowed == 7
    p.command(func=print)
    assert len(p.commands) == 2


def test_match_commands():
    p.commands.clear()
    p.command(names=['test'])(command)
    p.command(names=['not test'])(print)
    r = p.get_commands('test')
    assert len(r) == 1
    assert r[0].func is command


def test_split():
    assert p.split('hello world') == ('hello', 'world')
    assert p.split('hello') == ('hello', '')
    assert p.split('') == ('', '')


def test_names():
    cmd = p.command(names='test')(print)
    assert cmd.names == ['test']


def test_description():
    cmd = p.command(func=print)
    assert cmd.description == print.__doc__
