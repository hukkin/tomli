__all__ = ("loads", "load", "TOMLDecodeError")
__version__ = "1.0.0"  # DO NOT EDIT THIS LINE MANUALLY. LET bump2version UTILITY DO IT

from tomli._parser import TOMLDecodeError, load, loads
