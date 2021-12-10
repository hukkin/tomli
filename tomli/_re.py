from __future__ import annotations

from datetime import datetime, time
import re
from typing import Any

from tomli._types import Parsers

# E.g.
# - 00:32:00.999999
# - 00:32:00
_TIME_RE_STR = r"""(?P<hms>(?:[01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9])
(?:(?P<micros>\.[0-9]{1,6})[0-9]*)?"""

RE_NUMBER = re.compile(
    r"""
0
(?:
    x[0-9A-Fa-f](?:_?[0-9A-Fa-f])*   # hex
    |
    b[01](?:_?[01])*                 # bin
    |
    o[0-7](?:_?[0-7])*               # oct
)
|
[+-]?(?:0|[1-9](?:_?[0-9])*)         # dec, integer part
(?P<floatpart>
    (?:\.[0-9](?:_?[0-9])*)?         # optional fractional part
    (?:[eE][+-]?[0-9](?:_?[0-9])*)?  # optional exponent part
)
""",
    flags=re.VERBOSE,
)
RE_LOCALTIME = re.compile(_TIME_RE_STR, flags=re.VERBOSE)
RE_DATETIME = re.compile(
    fr"""
    # date, e.g. 1988-10-27
(?P<ymd>[0-9]{{4}}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12][0-9]|3[01]))
(?:
    [Tt ]
    {_TIME_RE_STR}
    # optional time offset
    (?:(?P<zulu>[Zz])|(?P<offset>[+-](?:[01][0-9]|2[0-3]):[0-5][0-9]))?
)?
""",
    flags=re.VERBOSE,
)


def match_to_datetime(match: re.Match, parsers: Parsers) -> Any:
    """Convert a `RE_DATETIME` match to `datetime.datetime` or `datetime.date`.

    Raises ValueError if the match does not correspond to a valid date
    or datetime.
    """

    if not match.group("hms"):
        return parsers.parse_date(match.group("ymd"))
    if parsers.parse_datetime != datetime.fromisoformat:
        return parsers.parse_datetime(match.group())
    # Standard library can't handle "Z"
    # or arbitrary precision in fractional seconds
    micros_str = get_micros(match)
    offset = ""
    if match.group("offset"):
        offset = match.group("offset")
    elif match.group("zulu"):
        offset = "+00:00"
    dt_str = f'{match.group("ymd")}T{match.group("hms")}{micros_str}{offset}'
    return parsers.parse_datetime(dt_str)


def match_to_localtime(match: re.Match, parsers: Parsers) -> Any:
    if parsers.parse_time != time.fromisoformat:
        return parsers.parse_time(match.group())
    # Standard library can't handle arbitrary precision in fractional seconds
    micros_str = get_micros(match)
    return parsers.parse_time(match.group("hms") + micros_str)


def match_to_number(match: re.Match, parsers: Parsers) -> Any:
    if match.group("floatpart"):
        return parsers.parse_float(match.group())
    return parsers.parse_int(match.group(), 0)


def get_micros(match: re.Match) -> str:
    if not match.group("micros"):
        return ""
    return match.group("micros").ljust(7, "0")
