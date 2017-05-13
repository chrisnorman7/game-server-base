# game-server-base
Base for text-based games using Twisted and a Flask-like API.

## Usage

### Overview

```
from gsb import Server

s = Server()


@s.command('regexp')
def func(caller):
    """Do something..."""
    pass


s.run()
```

This is a fully working text-based server.

In fact the command is superfluous, but if it wasn't included anything you typed would result in `s.huh(caller)` being called.

### Commands

Commands are simply functions. They can be added with the `Server.command` decorator. All arguments passed to this decorator are passed to the constructor of the configured `command_class`.

By default this is `gsb.Command`, but can be changed at any time, either by passing the command_class argument when instantiating `gsb.Server`, or by setting the `command_class` attribute on your `gsb.Server` instance.

By default when a command has been found (by `gsb.Server.handle_line`), execution stops. This can be prevented - if you wish to continue searching for new commands - by calling `caller.dont_stop()` as the last thing in your code.

Imagine this code - which assumes that connection.is_in_car is either True or False:

```
@s.command('^drive$', allowed=lambda caller: caller.connection.is_in_car)
def continue_driving(caller):
    s.notify(caller.connection, 'You continue driving.')
    caller.dont_stop()


@s.command('^drive$')
def start_driving(caller):
    """Put the vehicle into gear."""
    caller.connection.is_in_car = True
    s.notify(caller.connection, 'You drive your car.')
```

With this setup you could have an overriding drive command, but with an extra one to provide pretty-printing. In actuality you'd probably want to simply use if, but hey, options are good, right?

### Callers
We have used this magical caller object in our commands, so let's talk a bit more about it.

An instance of `gsb.Caller` is sent as the only argument to any command or event. This means as versions progress, you don't need to change the signature for every event or command you write, just take advantage of the attributes on the `Caller` instance.

#### Attributes

* connection - The connection object which is responsible for this command or event.
* text - The full text which was sent by the connection (or None if this is an event).
* match - The re match object if this is a command, or None if this is an event.
* dont_stop - A method which prevents the command processor from giving up looking for commands now that one has been found.

### `gsb.Server` Objects

Instances of `gsb.Server` represent an app-like object. Since gsb draws it's inspiration from the likes of Flask and Klein, it is only proper that an app object exist.

This object has several useful attributes and methods which are documented here:

#### Attributes

* port - The port used by the run method and passed to reactor.run.
* interface - Also used by the run method and Passed to reactor.run.
* factory - The twisted factory used by the run method. By changing this you could easily encrypt your servers with SSH or whatever else tickled your fancy.
* command_class - The class used by the command decorator. See examples/chatroom.py for an example of a modified command_class.
* commands - The commands which have been added with the command decorator.
* connections - A list of all the connected clients.
* started - Used by the run method to store a datetime object representing when the server was started.

#### Methods

* is_banned - Return whether a provided host is banned and should not be allowed to connect.
* run - Run the server and start waiting for connections.
* handle_line - A method which is passed a connection object and a line of text and attempts to parse it as a command. Could be overridden for example to provide functionality similar to MOO's `read()` builtin.
* huh - Called when no commands are found.
* format_text - Formats text according to *args and **kwargs. Allows you to pass text such as `("There are %d %s", 50, 'planets')` or `('There are %(number)d %(objects)s', number=50, objects='planets')`. Used with the notify and broadcast methods.
* notify - Notify a single connection of some text.
* broadcast - Notify all connected connections of some text.
* command - A decorator to add new commands.
* disconnect - Boot a connection.

#### Events

* on_connect - Called when a new client connects.
* on_disconnect - Called after a client has disconnected.
* on_command - Called whenever a connection sends a line of text, but before any commands have been matched. If this event evaluates to False no further processing will be performed.
* on_error - Called when an error is raised by a command. When this event is called, the passed instance of Caller has an extra `exception` attribute which is the exceptionwhich which was raised.
* on_start - Called by `Server.run` before `twisted.internet.reactor.run` is called. The passed instance of Caller is only there to maintain compatibility with the other events.
* on_stop - Scheduled by `Server.run` to fire before the reactor shuts down.
