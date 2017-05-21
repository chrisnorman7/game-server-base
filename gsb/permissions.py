"""Various allow functions for use with commands."""

from attr import attrs, attrib, validators


def anyone(caller):
    """Always allow."""
    return True


@attrs
class FuncPermission:
    """return self.func(x(caller) for x in self.validators"""

    validators = attrib(validator=validators.instance_of(tuple))
    func = attrib()

    def __call__(self, caller):
        return self.func(x(caller) for x in self.validators)


def and_(*validators):
    """Ensure all validators pass."""
    return FuncPermission(validators, all)


def or_(*validators):
    """Ensure any of the validators pass."""
    return FuncPermission(validators, any)
