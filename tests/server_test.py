"""Test the Server class."""

from pytest import raises
from gsb import Server

s = Server()


class RunException(Exception):
    pass


def test_init():
    assert s.connections == []
    assert s.is_banned('test') is False


def test_event_name():
    server = Server()
    with raises(AttributeError):
        @server.event
        def no_event(self):
            """There is no attribute named no_event."""


def test_event_type():
    server = Server()
    with raises(TypeError):
        @server.event
        def port(self):
            """Port is not a method."""


def test_works():
    server = Server()

    @server.event
    def run(self):
        return self

    assert server.run() is server

    del run  # Shut up, flake8!

    @server.event
    def run(self):
        raise RunException()

    with raises(RunException):
        server.run()
