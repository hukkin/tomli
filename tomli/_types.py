from dataclasses import dataclass
from typing import Any, Callable, Tuple

# Type annotations
ParseDate = Callable[[str], Any]
ParseDateTime = Callable[[str], Any]
ParseFloat = Callable[[str], Any]
ParseInt = Callable[[str, int], Any]
ParseTime = Callable[[str], Any]
Key = Tuple[str, ...]
Pos = int


@dataclass
class Parsers:
    parse_date: ParseDate
    parse_datetime: ParseDateTime
    parse_float: ParseFloat
    parse_int: ParseInt
    parse_time: ParseTime
