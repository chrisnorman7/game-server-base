"""Test a running server."""

import logging
from gsb import Server


class MyServer(Server):
    """A modified Server with an altered on_connect event."""

    def on_connect(self, caller):
        """Set a default nickname."""
        caller.connection.nickname = caller.connection.host


logging.basicConfig(level='INFO')

s = MyServer()


@s.command('^quit$')
def do_quit(caller):
    """Disconnect from the server."""
    s.broadcast('%s disconnected.', caller.connection.nickname)
    s.disconnect(caller.connection)


@s.command('^(nick|nickname|name|handle) (?P<nickname>[^$]+)$')
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


@s.command('^[\:,`](?P<string>[^$]+)$')
def emote(caller):
    """Emote something."""
    s.broadcast(
        '%s %s',
        caller.connection.nickname,
        caller.match.groupdict()['string']
    )


@s.command('^[^$]+$')
def speak(caller):
    """Say something."""
    s.broadcast('%s: %s', caller.connection.nickname, caller.text)


if __name__ == '__main__':
    s.run()
