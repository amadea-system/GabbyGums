"""
Subclasses of discord.ext.commands.Command and discord.ext.commands.Group that add in example fields for the help system

Part of the Gabby Gums Discord Logger.
"""

from discord.ext import commands as dpy_cmds


class ECommand(dpy_cmds.Command):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.examples = kwargs.get('examples', [])


class EGroup(dpy_cmds.Group):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.examples = kwargs.get('examples', [])


    def command(self, *args, **kwargs):
        """A shortcut decorator that invokes :func:`.command` and adds it to
        the internal command list via :meth:`~.GroupMixin.add_command`.
        """
        def decorator(func):
            kwargs.setdefault('parent', self)
            result = command(*args, **kwargs)(func)
            self.add_command(result)
            return result

        return decorator

    def group(self, *args, **kwargs):
        """A shortcut decorator that invokes :func:`.group` and adds it to
        the internal command list via :meth:`~.GroupMixin.add_command`.
        """
        def decorator(func):
            kwargs.setdefault('parent', self)
            result = group(*args, **kwargs)(func)
            self.add_command(result)
            return result

        return decorator


# Decorators
def command(name=None, cls=None, **attrs):
    """A decorator that transforms a function into a :class:`.Command`
    or if called with :func:`.group`, :class:`.Group`.

    By default the ``help`` attribute is received automatically from the
    docstring of the function and is cleaned up with the use of
    ``inspect.cleandoc``. If the docstring is ``bytes``, then it is decoded
    into :class:`str` using utf-8 encoding.

    All checks added using the :func:`.check` & co. decorators are added into
    the function. There is no way to supply your own checks through this
    decorator.

    Parameters
    -----------
    name: :class:`str`
        The name to create the command with. By default this uses the
        function name unchanged.
    cls
        The class to construct with. By default this is :class:`.Command`.
        You usually do not change this.
    attrs
        Keyword arguments to pass into the construction of the class denoted
        by ``cls``.

    Raises
    -------
    TypeError
        If the function is not a coroutine or is already a command.
    """
    if cls is None:
        cls = ECommand

    def decorator(func):
        if isinstance(func, dpy_cmds.Command):
            raise TypeError('Callback is already a command.')
        return cls(func, name=name, **attrs)
        
    return decorator


def group(name=None, **attrs):
    """A decorator that transforms a function into a :class:`.Group`.

    This is similar to the :func:`.command` decorator but the ``cls``
    parameter is set to :class:`Group` by default.

    .. versionchanged:: 1.1
        The ``cls`` parameter can now be passed.
    """

    attrs.setdefault('cls', EGroup)
    return command(name=name, **attrs)



