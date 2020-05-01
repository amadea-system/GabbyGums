"""
Provides convenience functions for the various custom colors used by GG.
Colors include:
    GG Dark Green
    GG Light Green
    GG Purple

Part of the Gabby Gums Discord Logger.
"""

from discord.colour import Colour


def gabby_gums_dark_green() -> Colour:
    """A convenience function that returns a :class:`Colour` with a value of 0x508787 (R80, G135, B135)."""
    # discord.Color.from_rgb(80, 135, 135))
    return Colour(0x508787)


def gabby_gums_light_green() -> Colour:
    """A convenience function that returns a :class:`Colour` with a value of 0xA5B8A5 (R165, G184, B165)."""
    # discord.Color.from_rgb(80, 135, 135))
    return Colour(0xA5B8A5)


def gabby_gums_purple() -> Colour:
    """A convenience function that returns a :class:`Colour` with a value of 0x9932CC."""
    return Colour(0x9932CC)




