"""Simple chatroom with nickname capabilities."""

import logging
from attr import attrs, attrib, Factory
from gsb import Server, Command


@attrs
class MyCommand(Command):
    """Give commands a help message."""
    help = attrib(default=Factory(lambda: None))

    def __attrs_post_init__(self):
        super(MyCommand, self).__attrs_post_init__()
        if self.help is None:
            self.help = self.regexp.pattern
            while self.help[0] in '^(':
                self.help = self.help[1:]
            while self.help[-1] in '$)':
                self.help = self.help[:-1]
            self.help = self.help.replace('|', ' or ')


class MyServer(Server):
    """A modified Server with an altered on_connect event."""

    def on_connect(self, caller):
        """Set a default nickname."""
        self.notify(
            caller.connection,
            'Welcome to the chatroom. Type help for help.'
        )
        caller.connection.nickname = caller.connection.host
        self.broadcast('%s has connected.', caller.connection.nickname)

    def on_disconnect(self, caller):
        """Called when clients disconnect."""
        self.broadcast('%s has disconnected.', caller.connection.nickname)


logging.basicConfig(level='INFO')

s = MyServer(command_class=MyCommand)


@s.command('^/quit$')
def do_quit(caller):
    """Disconnect from the server."""
    s.notify(caller.connection, 'Goodbye.')
    s.disconnect(caller.connection)


@s.command(
    '^(/commands|\\?)$',
    help='/commands or ?'
)
def do_commands(caller):
    """Show all commands with brief help messages."""
    s.notify(
        caller.connection,
        'Showing help for %d commands.',
        len(s.commands)
    )
    for cmd in s.commands:
        s.notify(
            caller.connection,
            '%s\n%s\n',
            cmd.help,
            cmd.func.__doc__ or 'No help available.'
        )


commands = ['nick', 'nickname', 'name', 'handle']


@s.command(
    '^\/(%s) (?P<nickname>[^$]+)$' % '|'.join(commands),
    help='/%s <nickname>' % ' or '.join(commands)
)
def nickname(caller):
    """Set a nickname."""
    name = caller.match.groupdict()['nickname']
    for con in s.connections:
        if con.nickname == name:
            s.notify(caller.connection, 'That nickname is already taken.')
            break
    else:
        s.broadcast('%s is now known as %s.', caller.connection.nickname, name)
        caller.connection.nickname = name


@s.command(
    '^[\:,`](?P<string>[^$]+)$',
    help='emote <anything> or :<anything>'
)
def emote(caller):
    """Emote something."""
    s.broadcast(
        '%s %s',
        caller.connection.nickname,
        caller.match.groupdict()['string']
    )


@s.command(
    '^[^$]+$',
    help='Type anything else'
)
def speak(caller):
    """Say something."""
    s.broadcast('%s: %s', caller.connection.nickname, caller.text)


if __name__ == '__main__':
    s.run()
