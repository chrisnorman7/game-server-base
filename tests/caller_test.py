"""Test Caller instances."""

import pytest
from gsb.caller import Caller, DontStopException


def test_init():
    c = Caller(None)
    assert c.connection is None
    assert c.text is None
    assert c.match is None
    assert c.args == ()
    assert c.kwargs == {}
    assert c.exception is None


def test_dont_stop():
    c = Caller(None)
    with pytest.raises(DontStopException):
        c.dont_stop()
