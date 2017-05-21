"""
Provides the intercept class as well as a couple of useful subclasses.

To Use them, simply send an instance of Intercept with any of the notify
functions.

You can also lazily create Intercept (or subclass) instances with notify:

con.notify(Intercept, ...)

The notify code will create the instance for you and do its thing.
"""

import six
from attr import attrs, attrib, Factory, validators
from .caller import Caller


@attrs
class Intercept:
    """
    Use instances of this class to intercept normal command processing.

    Attributes:
    persistant
    Set the connection's intercept attribute after every feed.
    no_abort
    Don't let the user use the @abort command.
    aborted
    Line of text sent when a connection successfully uses @abort.
    """

    persistant = attrib(default=Factory(bool))
    no_abort = attrib(default=Factory(lambda: None))
    aborted = attrib(default=Factory(lambda: 'Aborted.'))

    def explain(self, connection):
        """Tell the connection what we do. Called when the connection tries to
        @abort if we're persistant and when using notify with an instance of
        this class."""
        pass

    def feed(self, caller):
        """Feed this object with a line of text."""
        if self.persistant:
            caller.connection.intercept = self


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

    text = attrib(validator=validators.instance_of(six.string_types))
    func = attrib()
    index = attrib(default=Factory(lambda: None), init=False)

    def __str__(self):
        """Return text suitable for printing to a connection."""
        return '[{0.index}] {0.text}'.format(self)


@attrs
class _MenuBase:
    """Provides the title and items attributes."""
    title = attrib(validator=validators.instance_of(six.string_types))
    items = attrib(validator=validators.instance_of(list))


@attrs
class Menu(Intercept, _MenuBase):
    """A menu object.

    Attributes:
    title
    The line which is sent before the options.
    items
    A list of MenuItem instances.
    prompt
    The line which is sent after all the options.
    no_matches
    The connection entered something, but it was invalid. This should be a
    callable and expect to be sent an instance of Caller as its only argument.
    Defaults to Menu._no_matches.
    multiple_matches
    The connection entered something which matched multiple results. This
    should be a caller and breaks convention by expecting 2 arguments: An
    instance of Caller and a list of the MenuItem instances which matched.
    Defaults to Menu._multiple_matches.
    """

    prompt = attrib(
        default=Factory(lambda: 'Type a number or @abort to abort.'),
        validator=validators.instance_of(six.string_types)
    )
    no_matches = attrib(default=Factory(lambda: None))
    multiple_matches = attrib(default=Factory(lambda: None))

    def __attrs_post_init__(self):
        for item in self.items:
            item.index = self.items.index(item) + 1

    def explain(self, connection):
        """Explain this menu to connection."""
        connection.notify(self.title)
        self.send_items(connection)
        connection.notify(self.prompt)

    def send_items(self, connection, items=None):
        """Send the provided items to connection. If items is None use
        self.items."""
        if items is None:
            items = self.items
        for i in items:
            connection.notify(str(i))

    def _no_matches(self, caller):
        """The connection sent something but it doesn't match any of this menu's
        items."""
        caller.connection.notify('Invalid selection.')
        self.explain(caller.connection)

    def _multiple_matches(self, caller, matches):
        """The connection entered something but it matches multiple items."""
        connection = caller.connection
        connection.notify('That matched multiple items:')
        self.send_items(connection, items=matches)
        connection.notify(self.prompt)

    def feed(self, caller):
        """Do the user's bidding."""
        m = self.match(caller)
        if m is None:
            return super(Menu, self).feed(caller)
        else:
            m.func(caller)

    def match(self, caller):
        """Sent by the server when a menu is found.Returns either an item or
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
    persistant
    Inhereted from Intercept, we use this flag to indicate whether or not this
    is a multiline reader or not. If True, keep collecting lines until a single
    full stop (.) is received.
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
    prompt = attrib(
        default=Factory(lambda: None),
    )
    before_line = attrib(default=Factory(lambda: None))
    after_line = attrib(default=Factory(lambda: None))
    buffer = attrib(
        default=Factory(str),
        validator=validators.instance_of(six.string_types)
    )

    def send(self, thing, caller):
        """If self.name is a callable call it with caller. Otherwise use
        caller.connection.notify to send it to a connection."""
        if callable(thing):
            thing(caller)
        else:
            caller.connection.notify(thing)

    def get_buffer(self):
        """Get the contents of self.buffer without the leading backslash."""
        return self.buffer.strip('\n')

    def explain(self, connection):
        """Explain this reader."""
        if self.prompt is None:
            if self.persistant:
                connection.notify(
                    'Enter lines of text. Type a full stop (.) on a blank '
                    'line to finish%s.',
                    ' or @abort to exit' if self.no_abort is None else ''
                )
            else:
                connection.notify(
                    'Enter a line of text%s.',
                    ' or @abort to exit' if self.no_abort is None else ''
                )
        else:
            self.send(self.prompt, Caller(connection, text=self.get_buffer()))
        if self.before_line is not None:
            self.send(
                self.before_line,
                Caller(connection, text=self.get_buffer())
            )

    def feed(self, caller):
        """Add the line of text to the buffer."""
        self.buffer = '%s\n%s' % (self.buffer, caller.text)
        caller.text = self.get_buffer()
        if self.after_line is not None:
            self.send(self.after_line, caller)
        if not self.persistant or caller.text == '.':
            self.done(caller)
        else:
            if self.before_line is not None:
                self.send(self.before_line, caller)
            return super(Reader, self).feed(caller)


__all__ = [
    x.__name__ for x in [
        Intercept,
        MenuItem,
        Menu,
        Reader
    ]
]