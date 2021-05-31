__all__ = ("loads", "load", "TOMLDecodeError")
__version__ = "0.2.6"  # DO NOT EDIT THIS LINE MANUALLY. LET bump2version UTILITY DO IT

from tomli._parser import TOMLDecodeError, load, loads
