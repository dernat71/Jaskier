"""Utilities module"""
from pyfiglet import Figlet


def print_figlet():
    figleter = Figlet(font="big")
    print(figleter.renderText("Jaskier"))


class Context(object):
    """An information object to pass data between CLI functions."""

    def __init__(self):  # Note: This object must have an empty constructor.
        """Create a new instance."""
        self.verbose: int = 0
