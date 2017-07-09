"""Simple chatroom with nickname capabilities."""

import logging
from gsb import Server, Parser


class MainParser(Parser):
    """The main parser with all the fun stuff."""

    def on_attach(self, connection):
        """Say hello to the connection."""
        connection.notify(
            'You are now known as %s.',
            connection.nickname
        )

    def huh(self, caller):
        """Send a chat message."""
        caller.connection.server.broadcast(
            '%s: %s',
            caller.connection.nickname,
            caller.text
        )


parser = MainParser()


class LoginParser(Parser):
    """Let the connection choose a name."""

    def huh(self, caller):
        """Set a nickname."""
        caller.connection.nickname = caller.text
        caller.connection.parser = parser


class MyServer(Server):
    """A modified Server with an altered on_connect event."""

    def on_connect(self, caller):
        """Set a default nickname."""
        caller.connection.notify(
            'Welcome to the chatroom. Type /commands for help.\n\n'
            'What do you want your name to be on this server?'
        )
        caller.connection.nickname = caller.connection.host
        self.broadcast('%s has connected.', caller.connection.nickname)

    def on_disconnect(self, caller):
        """Called when clients disconnect."""
        self.broadcast('%s has disconnected.', caller.connection.nickname)


logging.basicConfig(level='INFO')

s = MyServer(default_parser=LoginParser())


@parser.command(names=['@quit', 'quit'])
def do_quit(caller):
    """Disconnect from the server."""
    s.notify(caller.connection, 'Goodbye.')
    s.disconnect(caller.connection)


@parser.command(names=['/commands', '?'])
def do_commands(caller):
    """Show all commands with brief help messages."""
    s.notify(
        caller.connection,
        'Showing help for %d commands.',
        len(parser.commands)
    )
    for cmd in parser.all_commands():
        parser.explain(cmd, caller.connection)


commands = ['/nick', '/nickname', '/name', '/handle']


@parser.command(
    names=commands,
    help=' <nickname>\n'.join(commands),
    args_regexp='([^$]+)'
)
def nickname(caller):
    """Set a nickname."""
    name = caller.args[0]
    for con in s.connections:
        if con.nickname == name:
            caller.connection.notify('That nickname is already taken.')
            break
    else:
        s.broadcast('%s is now known as %s.', caller.connection.nickname, name)
        caller.connection.nickname = name


@parser.command(
    names='emote',
    help='emote <anything>',
    args_regexp='([^$]+)'
)
def emote(caller):
    """Emote something."""
    s.broadcast(
        '%s %s',
        caller.connection.nickname,
        *caller.args
    )


if __name__ == '__main__':
    s.run()
