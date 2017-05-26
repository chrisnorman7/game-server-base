"""Test the Server class."""

from gsb import Server

s = Server()


def test_init():
    assert s.connections == []
    assert s.is_banned('test') is False
