"""Creates a very minimal MUD."""

import logging
from hashlib import sha256  # For encrypting password.
from attrs_sqlalchemy import attrs_sqlalchemy
from sqlalchemy import create_engine, Column, String, Integer, ForeignKey, \
     and_, or_, func
from sqlalchemy.ext.declarative import declarative_base, declared_attr
from sqlalchemy.orm import sessionmaker, relationship
from gsb import Server
from gsb.intercept import Reader, Menu


welcome_msg = """Welcome to this minimal MUD server.

By what name do they call you?"""


class MudServer(Server):
    """Set things up for the game."""

    def on_connect(self, caller):
        """Give it a player object for authentication."""
        caller.connection.player = None
        caller.connection.notify(welcome_msg)

    def on_disconnect(self, caller):
        """Clear caller.connection.player.connection if it's not None."""
        if caller.connection.player is not None:
            caller.connection.player.connection = None
            server.broadcast(
                '%s has disconnected.',
                caller.connection.player.name
            )

    def huh(self, caller):
        """Check for exits."""
        player = caller.connection.player
        if player is not None:
            x = player.match_exit(caller.text).first()
            if x is not None:
                player.notify('You travel through %s.', x.name)
                for thing in x.destination.contents:
                    thing.notify('%s arrives from %s.', player.name, x.name)
                player.location = x.destination
                player.do_look()
                player.save()
                return
        return super(MudServer, self).huh(caller)


server = MudServer()


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


@server.command('^@?quit$')
def do_quit(caller):
    """Quit the game."""
    caller.connection.notify('Goodbye.')
    server.disconnect(caller.connection)


@server.command(
    '^([^$]+)$',
    allowed=lambda caller: caller.connection.player is None
)
def do_connect(caller):
    """Connect with a character name. If the character doesn't exist then
    create a new one."""
    con = caller.connection
    name = caller.args[0]
    obj = Player.objects().filter(
        func.lower(Player.name) == name
    ).first()
    if obj is None:
        obj = Player(name=name.title(), location=first_room)
        con.notify('Created a new player: %s.', obj.name)
    else:
        con.notify('Connecting you as %s.', obj.name)
    con.notify('Enter password:')

    def login(caller):
        """Perform a login."""
        password = caller.text
        if not password:
            con.notify('Passwords cannot be blank.')
        elif obj.password is None:
            obj.set_password(password)
            obj.save()
        if obj.check_password(password):
            if hasattr(obj, 'connection') and obj.connection is not None:
                old = obj.connection
                old.player = None
                obj.connection = None
                old.notify('** Reconnecting somewhere else.')
                server.disconnect(old)
            obj.connection = con
            con.player = obj
            obj.notify('Welcome back, %s.', obj.name)
            obj.do_look()
            server.broadcast('%s has connected.', obj.name)
        else:
            con.notify('Incorrect password.')

    con.notify(Reader, login)


with server.default_kwargs(
    allowed=lambda caller: caller.connection.player is not None
) as command:
    @command('^dig(?: (.+) to ([^$]+))?$')
    def do_dig(caller):
        """Dig an exit to a new room."""
        player = caller.connection.player
        exit_name, destination_name = caller.args
        if exit_name is None:
            player.notify(
                'Syntax: dig name to place\n'
                'If place starts with a hash (#) character, it is assumed to '
                'be the id of an existing room.\n'
                'If there is a comma in the exit name, anything after the '
                'comma will be used as the exit\'s description.'
            )
        else:
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

    @command('^l(?: ([^$]+))?$')
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

    @command('^describe$')
    def do_describe(caller):
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

    @command('^(?:say |\'|")([^$]+)$')
    def do_say(caller):
        """Say something."""
        player = caller.connection.player
        for obj in player.location.contents:
            obj.notify('%s says: "%s"', player.name, *caller.args)

    @command('^(?:shout |@shout |!)([^$]+)$')
    def do_shout(caller):
        """Shout something to everyone."""
        server.broadcast(
            '%s shouts: "%s"',
            caller.connection.player.name,
            *caller.args
        )

    @command('^(?:who|@who)$')
    def do_who(caller):
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
