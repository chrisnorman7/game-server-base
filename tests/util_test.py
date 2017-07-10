"""Test utility functions."""

from gsb.util import command_parsers
from gsb import Parser


def test_command_parsers():
    p1 = Parser()
    p2 = Parser()
    assert not p1.commands
    assert not p2.commands

    @command_parsers((p1, p2), names='test')
    def do_test(caller):
        pass

    assert 'test' in p1.commands
    assert 'test' in p2.commands
