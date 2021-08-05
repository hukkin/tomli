"""A lil' TOML parser."""

__all__ = ("loads", "load", "TOMLDecodeError")
__version__ = "1.2.1"  # DO NOT EDIT THIS LINE MANUALLY. LET bump2version UTILITY DO IT

from tomli._parser import TOMLDecodeError, load, loads
