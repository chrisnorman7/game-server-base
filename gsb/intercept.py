"""
Provides the intercept class, a couple of useful subclasses, and some useful
functions.

To Use them, simply send an instance of Intercept with any of the notify
functions.

You can also lazily create Intercept (or subclass) instances with notify:

con.notify(Intercept, ...)

The notify code will create the instance for you and do its thing.

Functions:
after
A contextmanager to use to call a function after a function.

For example:
with after(print, 'Done.'):
    # Do something.

Calls callback with *args and **kwargs after the body has been executed.
"""

from contextlib import contextmanager
from attr import attrs, attrib, Factory
from .caller import Caller
from .parser import Parser


@attrs
class Intercept(Parser):
    """
    Use instances of this class to intercept normal command processing.

    Attributes:
    abort_command
    The command the user can use to abort this instance.
    no_abort
    Don't let the user use the abort command. Can either be a string or a
    callable with the standard signature.
    aborted
    Line of text sent when a connection successfully uses @abort. If this value
    is callable then it shal be treated like a hook and called with a valid
    Caller instance.
    prepared to take a caller as the only argument.
    restore_parser
    Set connection.parser to this value with a successful abort.

    When sending things which can either be a callable or a string (like
    self.no_abort for example), consider using self.send.
    """

    abort_command = attrib(default=Factory(lambda: '@abort'))
    aborted = attrib(default=Factory(lambda: 'Aborted.'))
    no_abort = attrib(default=Factory(lambda: None))
    restore_parser = attrib(default=Factory(lambda: None))

    def send(self, value, caller):
        """If value is a callable call it with caller. Otherwise use
        caller.connection.notify to send it to a connection."""
        if callable(value):
            value(caller)
        else:
            caller.connection.notify(value)

    def do_abort(self, caller):
        """Try to abort this caller."""
        if self.no_abort:
            self.send(self.no_abort, caller)
            return False
        else:
            self.send(self.aborted, caller)
            caller.connection.parser = self.restore_parser
            return True

    def explain(self, connection):
        """Tell the connection what we do. Called by self.on_attach."""
        pass

    def on_attach(self, connection, old_parser):
        """Explain this instance to connnection."""
        self.explain(connection)

    def huh(self, caller):
        """Check for self.abort_command."""
        line = caller.text
        if line == self.abort_command:
            return self.do_abort(caller)
        else:
            return False


@attrs
class MenuItem:
    """A menu item.

    Attributes:
    text
    The Text which is printed to the client.
    func
    The function which is called when this item is matched. Should be prepared
    to take an instance of Caller as it's only argument.
    index
    The index of this item. Set automatically by Menu.__attrs_post_init__.
    """

    text = attrib()
    func = attrib()
    index = attrib(default=Factory(lambda: None), init=False)

    def __str__(self):
        """Return text suitable for printing to a connection."""
        return self.as_string()

    def as_string(self):
        """Get a string representation of this item."""
        return '[{0.index}] {0.text}'.format(self)


@attrs
class MenuLabel:
    """
    A menu heading.

    text
    The text to print to the user.
    after
    The MenuItem instance this label comes after or None if it's at the
    beginning.
    """
    text = attrib()
    after = attrib()

    def __str__(self):
        return self.text


@attrs
class _MenuBase:
    """Provides the title and items attributes."""
    title = attrib(default=Factory(lambda: 'Select an item:'))
    items = attrib(default=Factory(list))
    labels = attrib(default=Factory(list))
    prompt = attrib(
        default=Factory(lambda: 'Type a number or @abort to abort.')
    )
    no_matches = attrib(default=Factory(lambda: None))
    multiple_matches = attrib(default=Factory(lambda: None))


@attrs
class Menu(Intercept, _MenuBase):
    """
    A menu object.

    Attributes:
    title
    The line which is sent before the options.
    items
    A list of MenuItem instances.
    labels
    A list of MenuLabel instances.
    prompt
    The line which is sent after all the options. Can also be a callable which
    accepts a Caller instance.
    no_matches
    The connection entered something, but it was invalid. This should be a
    callable and expect to be sent an instance of Caller as its only argument.
    Defaults to Menu._no_matches.
    multiple_matches
    The connection entered something which matched multiple results. This
    should be a caller and breaks convention by expecting 2 arguments: An
    instance of Caller and a list of the MenuItem instances which matched.
    Defaults to Menu._multiple_matches.
    persistent
    Don't use self.restore_parser if no match is found.
    """

    persistent = attrib(default=Factory(bool))

    def __attrs_post_init__(self):
        for item in self.items:
            item.index = self.items.index(item) + 1

    def add_label(self, text, after):
        """Add a label."""
        l = MenuLabel(text, after)
        self.labels.append(l)
        return l

    def item(self, name):
        """A decorator to add an item with the specified name."""
        def inner(func):
            """Add the item."""
            i = MenuItem(name, func)
            self.items.append(i)
            self.__attrs_post_init__()
            return i
        return inner

    def explain(self, connection):
        """Explain this menu to connection."""
        connection.notify(self.title)
        self.send_items(connection)
        self.send(self.prompt, Caller(connection))

    def send_items(self, connection, items=None):
        """Send the provided items to connection. If items is None use
        self.items."""
        if items is None:
            items = self.items
        for label in self.labels:
            if label.after is None:
                connection.notify(label.text)
        for i in items:
            connection.notify(i.as_string())
            for label in self.labels:
                if label.after is i:
                    connection.notify(label.text)

    def _no_matches(self, caller):
        """The connection sent something but it doesn't match any of this menu's
        items."""
        caller.connection.notify('Invalid selection.')
        if not self.persistent:
            caller.connection.parser = self.restore_parser

    def _multiple_matches(self, caller, matches):
        """The connection entered something but it matches multiple items."""
        connection = caller.connection
        connection.notify('That matched multiple items:')
        self.send_items(connection, items=matches)
        connection.notify(self.prompt)

    def huh(self, caller):
        """Do the user's bidding."""
        if super(Menu, self).huh(caller):
            return True
        m = self.match(caller)
        if m is not None:
            caller.connection.parser = self.restore_parser
            m.func(caller)
        else:
            if self.persistent:
                self.explain(caller.connection)
        return True

    def match(self, caller):
        """Sent by the server when a menu is found. Returns either an item or
        None if no or multiple matches were found (a case which is handled by
        this function)."""
        text = caller.text.lower()
        if text == '$':  # Return the last item.
            return self.items[-1]
        try:
            num = int(text)
            if num > 0:
                num -= 1
            return self.items[num]
        except (ValueError, IndexError):
            items = []
            if text:
                for item in self.items:
                    if item.text.lower().startswith(text):
                        items.append(item)
            if not items:  # No matches
                if self.no_matches is None:
                    self._no_matches(caller)
                else:
                    self.no_matches(caller)
            elif len(items) == 1:  # Result!
                return items[0]
            else:  # Multiple matches.
                if self.multiple_matches is None:
                    self._multiple_matches(caller, items)
                else:
                    self.multiple_matches(caller, items)


@attrs
class _ReaderBase:
    """Provides the positional attributes of Reader."""

    done = attrib()


@attrs
class Reader(Intercept, _ReaderBase):
    """Read 1 or more lines from the user.

    Attributes:
    done
    The function to call when we're done. Should be prepared to receive an
    instance of Caller with it's text attribute set to the contents of the
    buffer. This function will be called after 1 line of text if self.multiline
    evaluates to False or when a full stop (.) is received on its own.
    prompt
    Sent by self.explain. Can be either a string or a callable which will be
    sent an instance of Caller as its only argument. The caller's text
    attribute will be set to the text of this reader.
    line_separator
    The text to join lines of self.buffer with.
    done_command
    The command which is used to finish multiline entry.
    spell_check_command
    The command which is used to enter the spell checker if it is available.
    multiline
    Whether or not this Reader instance expects multiple lines. If True, keep
    collecting lines until self.done_command is received.
    before_line
    Sent before every new line. Can be either a string or a callable which will
    be sent an instance of Caller as its only argument. The caller's text
    attribute will be set to the text of this reader.
    after_line
    Sent after a line is received. Can be either a string or a callable which
    will be sent an instance of Caller as its only argument. The caller's text
    attribute will be set to the text of this reader.
    buffer
    The text received so far.
    """

    prompt = attrib(default=Factory(lambda: None))
    line_separator = attrib(default=Factory(lambda: '\n'))
    done_command = attrib(default=Factory(lambda: '.'))
    spell_check_command = attrib(default=Factory(lambda: '.spell'))
    multiline = attrib(Factory(bool))
    before_line = attrib(default=Factory(lambda: None))
    after_line = attrib(default=Factory(lambda: None))
    buffer = attrib(default=Factory(str))

    def explain(self, connection):
        """Explain this reader."""
        caller = Caller(connection, text=self.buffer)
        if self.prompt is None:
            if self.multiline:
                connection.notify(
                    'Enter lines of text. Type %s on a blank '
                    'line to finish%s.',
                    self.done_command,
                    (
                        ' or %s to exit' % self.abort_command
                    ) if self.no_abort is None else ''
                )
            else:
                connection.notify(
                    'Enter a line of text%s.',
                    (
                        ' or %s to exit' % self.abort_command
                    ) if self.no_abort is None else ''
                )
        else:
            self.send(self.prompt, caller)
        if self.before_line is not None:
            self.send(
                self.before_line,
                caller
            )

    def huh(self, caller):
        """Add the line of text to the buffer."""
        line = caller.text
        if self.after_line is not None:
            self.send(self.after_line, caller)
        if super(Reader, self).huh(caller):
            return True
        elif line == self.spell_check_command:
            m = caller.connection.server.get_spell_checker(caller)
            if m is not None:
                caller.connection.notify(
                    m,
                    self.buffer,
                    self.restore,
                    restore_parser=None
                )
            else:
                caller.connection.notify(
                    'Spell checking is not available on this system.'
                )
            return True
        elif not self.multiline or line != self.done_command:
            if self.buffer:
                self.buffer = self.line_separator.join(
                    [
                        self.buffer,
                        line
                    ]
                )
            else:
                self.buffer = caller.text
        caller.text = self.buffer
        if not self.multiline or line == self.done_command:
            caller.connection.parser = self.restore_parser
            self.done(caller)
            return True
        else:
            if self.before_line is not None:
                self.send(self.before_line, caller)
            return False

    def restore(self, caller):
        """Restore from a spell checker menu."""
        caller.connection.notify('Spell checking complete.')
        self.buffer = caller.text
        caller.connection.parser = self


@attrs
class _YesOrNoBase:
    """The base which makes up the YesOrNo class."""

    question = attrib()
    yes = attrib()


@attrs
class YesOrNo(Intercept, _YesOrNoBase):
    """Send this to a connection to ask a simple yes or no question.

    attributes:
    question
    The question you want to ask.
    yes
    The function which is called when the user answers in the afirmative.
    no
    The function which is called when the user answers no.
    prompt
    The prompt which is sent after the question to tell the user what to do.
    """

    no = attrib(default=Factory(lambda: None))
    prompt = attrib(default=Factory(lambda: None))

    def __attrs_post_init__(self):
        if self.prompt is None:
            self.prompt = 'Enter "yes" or "no" or %s to abort the command.' % \
                self.abort_command

    def explain(self, connection):
        """Send the connection our question."""
        connection.notify(self.question)
        connection.notify(self.prompt)

    def huh(self, caller):
        """Check for yes or no."""
        if not super(YesOrNo, self).huh(caller):
            caller.connection.parser = self.restore_parser
            if caller.text.lower().startswith('y'):
                self.yes(caller)
            else:
                if self.no is not None:
                    self.no(caller)
                else:
                    self.do_abort(caller)


@contextmanager
def after(_f, *args, **kwargs):
    """Call _f(*args, **kwargs) after everything else has been done."""
    yield
    _f(*args, **kwargs)


__all__ = [
    x.__name__ for x in [
        Intercept,
        MenuItem,
        Menu,
        Reader,
        YesOrNo,
        after
    ]
]
