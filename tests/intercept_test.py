"""Test intercepts."""

from pytest import raises
from attr import attrs
from gsb import Server, Protocol, Caller, intercept, Parser


class YesException(Exception):
    pass


class NoException(Exception):
    pass


class AfterException(Exception):
    pass


class MenuItem1(Exception):
    pass


class MenuItem2(Exception):
    pass


class MenuItem3(Exception):
    pass


class NotifyException(Exception):
    """So we know what gets notified."""
    pass


@attrs
class _TestProtocol(Protocol):
    """Override sendLine."""
    def __attrs_post_init__(self):
        self.line = None
        self.command = None

    def sendLine(self, line):
        line = line.decode()
        self.line = line
        raise NotifyException(line)


def good_command(caller):
    assert caller.text == 'good'
    assert caller.connection is p
    p.command = 'good'


def bad_command(caller):
    assert caller.text == 'bad'
    assert caller.connection is p
    p.command = 'bad'


def menu_command_1(caller):
    raise MenuItem1


def menu_command_2(caller):
    raise MenuItem2


def menu_command_3(caller):
    raise MenuItem3


s = Server()
d = s.default_parser
p = _TestProtocol(s, '127.0.0.1', 1987, d)  # Pretend protocol.
p.connectionMade()
assert p.line is None


def test_notify():
    """This should go in server_test.py, but what the hell!"""
    text = 'Testing, testing, 1, 2, 3.'
    with raises(NotifyException):
        p.notify(text)
    assert p.line == text


def test_handle_line():
    d.command(names='good', func=good_command)
    d.command(names='bad', func=bad_command)
    p.lineReceived('good'.encode())
    assert p.command == 'good'
    with raises(NotifyException):
        p.lineReceived('nothing'.encode())
    p.lineReceived('bad'.encode())
    assert p.command == 'bad'


def test_menuitem():
    i = intercept.MenuItem('testing', print)
    assert i.text == 'testing'
    assert i.func == print


def test_menulabel():
    l = intercept.MenuLabel('test', None)
    l.text == 'test'
    assert l.after is None
    i = intercept.MenuItem('Item', print)
    l = intercept.MenuLabel('whatever', after=i)
    assert l.after is i


def test_menu():
    i1 = intercept.MenuItem('First Thing', menu_command_1)
    i2 = intercept.MenuItem('second Thing', menu_command_2)
    i3 = intercept.MenuItem('Third Thing', menu_command_3)
    m = intercept.Menu('Test Menu', items=[i1, i2, i3])
    assert m.title == 'Test Menu'
    c = Caller(p)
    c.text = '$'
    assert m.match(c) is i3
    c.text = 'first'
    assert m.match(c) == i1
    c.text = 'thing'  # Multiple results.
    with raises(NotifyException):
        m.match(c)
    c.text = 'nothing'
    with raises(NotifyException):
        assert m.match(c) is None


def test_reader():
    def done(caller):
        caller.connection.text = caller.text

    def multiline_done(caller):
        done(caller)

    r = intercept.Reader(done)
    assert r.done is done
    r.handle_line(p, 'testing')
    assert p.text == 'testing'
    r.buffer = ''
    p.text = None
    r.multiline = True
    r.done = multiline_done
    r.handle_line(p, '1')
    assert r.buffer == '1'
    assert p.text is None
    r.handle_line(p, '2')
    assert r.buffer == '1\n2'
    assert p.text is None
    r.handle_line(p, r.done_command)
    assert r.buffer == '1\n2'
    assert p.text == '1\n2'


def test_abort():
    abortable = intercept.Intercept()
    not_abortable = intercept.Intercept(
        no_abort='You cannot abort this test thingy'
    )
    p.parser = s.default_parser
    p.parser = abortable
    assert p._parser is abortable
    try:
        p.lineReceived(abortable.abort_command.encode())
    except NotifyException as e:
        assert str(e) == abortable.aborted
    p.parser = not_abortable
    try:
        p.lineReceived('@abort'.encode())
    except NotifyException as e:
        assert str(e) == not_abortable.no_abort
    assert p.parser is not_abortable


def test_subclass_menu():
    m = intercept.Menu('Test Menu')
    assert m.items == []
    item_name = 'First Item'
    i = m.item(item_name)(print)
    assert isinstance(i, intercept.MenuItem)
    assert i.func is print
    assert i.text == item_name
    assert i.index == 1
    second_item_name = 'Second Test Item'
    i2 = m.item(second_item_name)(id)
    assert isinstance(i2, intercept.MenuItem)
    assert i2.text == second_item_name
    assert i2.index == 2
    assert i2.func == id


def test_yes_or_no():

    def yes(caller):
        raise YesException

    def no(caller):
        raise NoException

    question = 'This is a test?'
    yon = intercept.YesOrNo(question, yes, no=no)
    assert yon.question == question
    assert yon.yes is yes
    assert yon.no is no
    for response in ['yes', 'y', 'ye']:
        with raises(YesException):
            yon.handle_line(p, response)
    for response in ['no', 'n', 'anything should be fine here']:
        with raises(NoException):
            yon.handle_line(p, response)


def test_after():
    args = (1, 2, 3)
    kwargs = {'hello': 'world'}

    def f(*args, **kwargs):
        assert args == args
        assert kwargs == kwargs
        raise AfterException
    with raises(AfterException), intercept.after(f, *args, **kwargs):
        assert 1 is 1
    with raises(RuntimeError):
        with intercept.after(print, 'Never should happen!'):
            raise RuntimeError()


def test_switch_parsers():
    parser = Parser()
    i = intercept.Intercept()
    p = Protocol(s, 'localhost', 0, parser)
    assert p.parser is parser
    assert p._parser is parser
    p.parser = i
    assert p._parser is i
