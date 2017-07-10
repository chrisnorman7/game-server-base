"""Various utility functions."""


def command_parsers(parsers, **kwargs):
    """A decorator to add the same function to multiple parsers in the provided
    list."""
    def inner(func):
        for parser in parsers:
            parser.command(**kwargs)(func)
    return inner
