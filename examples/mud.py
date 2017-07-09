"""Creates a very minimal MUD."""

import logging
from hashlib import sha256  # For encrypting password.
from attrs_sqlalchemy import attrs_sqlalchemy
from sqlalchemy import create_engine, Column, String, Integer, ForeignKey, \
     and_, or_, func
from sqlalchemy.ext.declarative import declarative_base, declared_attr
from sqlalchemy.orm import sessionmaker, relationship
from gsb import Server, Parser
from gsb.intercept import Reader, Menu


welcome_msg = """Welcome to this minimal MUD server.

By what name do they call you?"""


class UsernameParser(Parser):
    """Get a username from the player."""

    def on_attach(self, connection):
        connection.notify(welcome_msg)

    def huh(self, caller):
        """Get the username."""
        obj = Player.objects().filter(
            func.lower(Player.name) == caller.text
        ).first()
        if obj is None:
            obj = Player(name=caller.text.title(), location=first_room)
            caller.connection.notify('Created a new player: %s.', obj.name)
        else:
            caller.connection.notify('Connecting you as %s.', obj.name)
        caller.connection.player = obj
        caller.connection.parser = PasswordParser()


class PasswordParser(Parser):
    """Get the password from the player."""

    def on_attach(self, connection):
        connection.notify('Password:')

    def huh(self, caller):
        """Perform a login."""
        con = caller.connection
        player = con.player
        password = caller.text
        if not password:
            con.notify('Passwords cannot be blank.')
        elif player.password is None:
            player.set_password(password)
            player.save()
        if player.check_password(password):
            if getattr(player, 'connection', None) is not None:
                old = player.connection
                old.player = None
                old.notify('** Reconnecting somewhere else.')
                server.disconnect(old)
            con.notify('Welcome back, %s.', player.name)
            player.connection = con
            player.do_look()
            con.parser = parser
            server.broadcast('%s has connected.', player.name)
            return
        else:
            con.notify('Incorrect password.')
        con.parser = UsernameParser()


class MainParser(Parser):
    """Adds a huh which checks for directions."""

    def huh(self, caller):
        """Check for exits."""
        print(caller.text)
        player = caller.connection.player
        x = player.match_exit(caller.text).first()
        if x is not None:
            for thing in player.location.contents:
                if thing is player:
                    thing.notify('You travel through %s.', x.name)
                else:
                    thing.notify('%s travels through %s.', player.name, x.name)
            for thing in x.destination.contents:
                thing.notify('%s arrives from %s.', player.name, x.name)
            player.location = x.destination
            player.do_look()
            player.save()
        else:
            return super(MainParser, self).huh(caller)


parser = MainParser(
    command_substitutions={
        "'": 'say',
        '"': 'say',
        '!': 'shout'
    }
)


class MudServer(Server):
    """Set things up for the game."""

    def on_connect(self, caller):
        """Give it a player object for authentication."""
        con = caller.connection
        con.player = None
        con.parser = UsernameParser()

    def on_disconnect(self, caller):
        """Clear caller.connection.player.connection if it's not None."""
        if caller.connection.player is not None:
            caller.connection.player.connection = None
            server.broadcast(
                '%s has disconnected.',
                caller.connection.player.name
            )


server = MudServer(default_parser=None)


class _Base:
    """No point in putting keys on everything."""
    id = Column(Integer, primary_key=True)

    def notify(self, *args, **kwargs):
        """If this object is connected send it a notification."""
        if hasattr(self, 'connection'):
            self.connection.notify(*args, **kwargs)
            return True
        return False

    def _try_commit_session(self):
        """Try to commit the session."""
        try:
            session.commit()
        except Exception as e:
            # Rollback the session before reraising.session.rollback()
            session.rollback()
            raise e

    def save(self):
        """Save this object."""
        session.add(self)
        self._try_commit_session()

    def delete(self):
        """Delete this object."""
        session.delete(self)
        self._try_commit_session()

    @classmethod
    def objects(cls):
        """Return a query object for this class."""
        return session.query(cls)


engine = create_engine('sqlite:///db.sqlite3')

Base = declarative_base(bind=engine, cls=_Base)


class NameDescriptionMixin:
    """Add a name and description."""

    name = Column(String(50), nullable=False)
    description = Column(String(200), nullable=True)

    def get_description(self):
        """Get a palyer-friendly description."""
        return self.description or 'You see nothing special.'


class LocationMixin:
    """Adds location information to objects."""
    @declared_attr
    def location_id(cls):
        return Column(
            Integer,
            ForeignKey('rooms.id'),
            nullable=False
        )

    @declared_attr
    def location(cls):
        return relationship(
            'Room',
            backref=cls.__tablename__,
            foreign_keys=[cls.location_id],
            remote_side='Room.id'
        )


@attrs_sqlalchemy
class Room(Base, NameDescriptionMixin):
    """A room."""
    __tablename__ = 'rooms'

    @property
    def contents(self):
        """Return the contents of this room."""
        l = []
        for thing in [Player, Exit]:
            l += thing.objects().filter_by(location=self).all()
        return l

    def build_exit(self, name, destination):
        """Returns (exit, entrance)."""
        x = Exit(name=name, location=self, destination=destination)
        d = Exit(name=name, location=destination, destination=self)
        x.save()
        d.save()
        return (x, d)


@attrs_sqlalchemy
class Exit(Base, NameDescriptionMixin, LocationMixin):
    """An exit between two rooms."""
    __tablename__ = 'exits'
    destination_id = Column(
        Integer,
        ForeignKey('rooms.id'),
        nullable=False
    )
    destination = relationship(
        'Room',
        backref='entrances',
        foreign_keys=[destination_id]
    )


@attrs_sqlalchemy
class Player(Base, NameDescriptionMixin, LocationMixin):
    """A player object."""
    __tablename__ = 'players'
    password = Column(String(64), nullable=True)

    def match_exit(self, name):
        """Match an exit."""
        return Exit.objects().filter(
            and_(
                Exit.location_id == self.location_id,
                or_(
                    func.lower(Exit.name) == name.lower(),
                    func.lower(Exit.description) == name.lower()
                )
            )
        )

    def do_look(self, target=None):
        """Look at something."""
        if target is None:
            target = self.location
        self.notify('%s\n%s', target.name, target.get_description())
        if isinstance(target, Room):
            self.notify('Exits:')
            if target.exits:
                for x in target.exits:
                    self.notify('%s to %s', x.name, x.destination.name)
            else:
                self.notify('None')
        elif isinstance(target, Exit):
            self.notify('Through it you see:')
            self.do_look(target=target.destination)

    def to_password(self, value):
        """Return a hashed password."""
        return sha256(value.encode()).hexdigest()

    def set_password(self, value):
        """Set the password for this player."""
        self.password = self.to_password(value)
        self.save()

    def check_password(self, value):
        """Check to see if the provided password is the right one for this
        player."""
        return self.password == self.to_password(value)


Base.metadata.create_all()

Session = sessionmaker(bind=engine)
session = Session()

# Let's create an initial room.

first_room = Room.objects().first()
if first_room is None:
    first_room = Room(name='The First Room')


# Commands:


@parser.command(names=['quit', '@quit'])
def do_quit(caller):
    """Quit the game."""
    caller.connection.notify('Goodbye.')
    server.disconnect(caller.connection)


@parser.command(
    help='dig <name> to <place>\n'
    'If place starts with a hash (#) character, it is assumed to be the '
    'id of an existing room.\n'
    'If there is a comma in the exit name, anything after the comma will '
    'be used as the exit\'s description.',
    args_regexp='(.+) to ([^$]+)$'
)
def dig(caller):
    """Dig an exit to a new room."""
    player = caller.connection.player
    exit_name, destination_name = caller.args
    if destination_name.startswith('#'):
        destination = Room.objects().get(destination_name[1:])
    else:
        destination = Room(name=destination_name)
        destination.save()
        player.notify(
            'Created room %s (#%d).',
            destination.name,
            destination.id
        )
    if destination is None:
        player.notify('Invalid destination: %s.', destination_name)
    else:
        if ',' in exit_name:
            name = exit_name[:exit_name.index(',')].strip()
            description = exit_name[exit_name.index(',') + 1:]
        else:
            name = exit_name
            description = None
        for thing in player.location.build_exit(name, destination):
            thing.description = description
            thing.save()
        player.notify('Rooms linked.')


@parser.command(names=['l', 'look'], args_regexp='^(?: ([^$]+))?$')
def do_look(caller):
    """Look at stuff."""
    player = caller.connection.player
    name = caller.args[0]
    if name is None:
        player.do_look()
    else:
        for thing in player.location.contents:
            if name in thing.name.lower():
                player.do_look(target=thing)
                break
        else:
            player.notify("I don't see that here.")


@parser.command
def describe(caller):
    """Describe this room."""
    player = caller.connection.player
    location = player.location

    def set_value(value):
        """Actually set the value."""
        location.description = value
        location.save()
        player.notify(
            'Description %s.',
            'cleared' if value is None else 'set'
        )

    def set(caller):
        """Set the description."""
        def f(caller):
            """Actually do the setting."""
            set_value(caller.text)

        player.notify('Enter a new description for %s.', location.name)
        player.notify(Reader, f, persistent=True)

    def clear(caller):
        """Clear the room description."""
        set_value(None)

    m = Menu('Describe Menu')
    m.item('Set Room Description')(set)
    m.item('Clear Room Description')(clear)
    player.notify(m)


@parser.command(
    args_regexp='([^$]+)$',
    help='say <text>'
)
def say(caller):
    """Say something."""
    player = caller.connection.player
    for obj in player.location.contents:
        obj.notify('%s says: "%s"', player.name, *caller.args)


@parser.command(
    names=['shout', '@shout'],
    args_regexp='^([^$]+)$',
    help='shout <anything>'
)
def do_shout(caller):
    """Shout something to everyone."""
    server.broadcast(
        '%s shouts: "%s"',
        caller.connection.player.name,
        *caller.args
    )


@parser.command
def who(caller):
    """Show who is logged in."""
    player = caller.connection.player
    player.notify('Connected players:')
    for con in server.connections:
        if con.player is None:
            name = 'Unauthenticated player'
        else:
            name = con.player.name
        player.notify('%s from %s:%d', name, con.host, con.port)


if __name__ == '__main__':
    logging.basicConfig(level='INFO')
    server.run()
