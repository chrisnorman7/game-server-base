"""Test the Server class."""

from gsb import Server

s = Server()


def test_init():
    assert s.connections == []
    assert s.banned_hosts == []
