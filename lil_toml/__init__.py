import datetime
import re
import string
from typing import Any, Iterable, List, Optional, Sequence, Tuple

__all__ = ("loads", "dumps")
__version__ = "0.0.0"  # DO NOT EDIT THIS LINE MANUALLY. LET bump2version UTILITY DO IT

# E.g.
# - 00:32:00.999999
# - 00:32:00
_TIME_RE_STR = r"([01][0-9]|2[0-3]):([0-5][0-9]):([0-5][0-9])(\.[0-9]+)?"

_HEX_RE = re.compile(r"0x[0-9A-Fa-f](?:_?[0-9A-Fa-f]+)*")
_BIN_RE = re.compile(r"0b[01](?:_?[01]+)*")
_OCT_RE = re.compile(r"0o[0-7](?:_?[0-7]+)*")
_DEC_OR_FLOAT_RE = re.compile(
    r"^"
    + r"[+-]?(?:0|[1-9](?:_?[0-9])*)"  # integer
    + r"(?:\.[0-9](?:_?[0-9])*)?"  # optional fractional part
    + r"(?:[eE][+-]?[0-9](?:_?[0-9])*)?"  # optional exponent part
    + r"$"
)
_LOCAL_TIME_RE = re.compile(_TIME_RE_STR)
_DATETIME_RE = re.compile(
    r"([0-9]{4})-(0[1-9]|1[0-2])-(0[1-9]|1[0-9]|2[0-9]|3[01])"  # date, e.g. 1988-10-27
    + r"(?:[T ]"
    + _TIME_RE_STR
    + r"(?:Z|[+-]([01][0-9]|2[0-3]):([0-5][0-9]))?"  # time offset
    + r")?"
)


_Namespace = Tuple[str, ...]


class _CustomTzinfo(datetime.tzinfo):
    def __init__(self, offset: datetime.timedelta) -> None:
        self._offset = offset

    def __deepcopy__(self, memo: Any) -> Any:
        return type(self)(self._offset)

    def utcoffset(self, dt: Optional[datetime.datetime]) -> datetime.timedelta:
        return self._offset

    def dst(self, dt: Optional[datetime.datetime]) -> None:
        return None

    def tzname(self, dt: Optional[datetime.datetime]) -> None:
        return None


class _ParseState:
    def __init__(self, src: str):
        self.src: str = src
        self.pos: int = 0
        self.out: dict = {}
        self.header_namespace: _Namespace = ()

    def done(self) -> bool:
        return self.pos >= len(self.src)

    def char(self) -> str:
        return self.src[self.pos]


def loads(s: str) -> dict:  # noqa: C901
    # The spec allows converting "\r\n" to "\n", even in string
    # literals. Let's do so to simplify parsing.
    s = s.replace("\r\n", "\n")

    state = _ParseState(s)

    # Parse one statement at a time (typically means one line)
    while True:
        # 0. skip whitespace
        _skip_chars(state, _TOML_WS)

        # 1. rules
        #      - end of file
        #      - end of line
        #      - comment
        #      - key->value
        #      - get/create list and append dict (change ns)
        #      - create dict (change ns)
        if state.done():
            break
        char = state.char()
        if char == "\n":
            state.pos += 1
            continue
        elif char == "#":
            _comment_rule(state)
        elif char in _BARE_KEY_CHARS or char in "\"'":
            _key_value_rule(state)
        elif state.src[state.pos : state.pos + 2] == "[[":
            _create_list_rule(state)
        elif char == "[":
            _create_dict_rule(state)
        else:
            raise Exception("TODO: msg and type --- not able to apply any rule")

        # 2. skip whitespace and line comment
        _skip_chars(state, _TOML_WS)
        if not state.done() and state.char() == "#":
            _comment_rule(state)

        # 3. either:
        #      - EOF
        #      - newline
        #      - error
        if state.done():
            break
        elif state.char() == "\n":
            state.pos += 1
        else:
            raise Exception("TODO: msg and type --- statement didnt end in EOF or EOL")

    return state.out


def dumps(*args: Any, **kwargs: Any) -> str:
    raise NotImplementedError


_TOML_WS = frozenset(" \t")
_BARE_KEY_CHARS = frozenset(string.ascii_letters + string.digits + "-_")


def _skip_chars(state: _ParseState, chars: Iterable[str]) -> None:
    while not state.done() and state.char() in chars:
        state.pos += 1


def _skip_until(state: _ParseState, chars: Iterable[str]) -> None:
    while not state.done() and state.char() not in chars:
        state.pos += 1


def _comment_rule(state: _ParseState) -> None:
    try:
        state.pos = state.src.index("\n", state.pos + 1)
    except ValueError:
        state.pos = len(state.src)


def _create_dict_rule(state: _ParseState) -> None:
    state.pos += 1
    _skip_chars(state, _TOML_WS)
    key_parts = _parse_key(state)

    _get_or_create_nested_dict(state.out, key_parts)
    state.header_namespace = tuple(key_parts)

    if not state.char() == "]":
        raise Exception("TODO: type and msg")
    state.pos += 1


def _create_list_rule(state: _ParseState) -> None:
    state.pos += 2
    _skip_chars(state, _TOML_WS)
    key_parts = _parse_key(state)

    _append_dict_to_nested_list(state.out, key_parts)
    state.header_namespace = tuple(key_parts)

    if not state.src[state.pos : state.pos + 2] == "]]":
        raise Exception("TODO: type and msg")
    state.pos += 2


def _key_value_rule(state: _ParseState) -> None:
    key_parts = _parse_key(state)
    last_key_part = key_parts.pop()
    if state.char() != "=":
        raise Exception("TODO: type and msg")
    state.pos += 1
    _skip_chars(state, _TOML_WS)

    container: Any = state.out
    for part in state.header_namespace:
        container = container[part]
        if isinstance(container, list):
            container = container[-1]

    container = _get_or_create_nested_dict(container, key_parts)

    if last_key_part in container:
        raise Exception("TODO: type and msg")

    value = _parse_value(state)
    container[last_key_part] = value


def _parse_key(state: _ParseState) -> List[str]:
    """Return parsed key as list of strings.

    Move state.pos after the key, to the start of the value that
    follows. Throw if parsing fails.
    """
    key_parts = [_parse_key_part(state)]
    _skip_chars(state, _TOML_WS)
    while state.char() == ".":
        state.pos += 1
        _skip_chars(state, _TOML_WS)
        key_parts.append(_parse_key_part(state))
        _skip_chars(state, _TOML_WS)
    return key_parts


def _parse_key_part(state: _ParseState) -> str:
    """Return parsed key part.

    Move state.pos after the key part. Throw if parsing fails.
    """
    char = state.char()
    if char in _BARE_KEY_CHARS:
        start_pos = state.pos
        _skip_chars(state, _BARE_KEY_CHARS)
        return state.src[start_pos : state.pos]
    elif char == "'":
        return _parse_literal_str(state)
    elif char == '"':
        return _parse_basic_str(state)
    else:
        raise Exception("TODO: add type and msg")


_ASCII_CTRL = frozenset(chr(i) for i in range(32)) | frozenset(chr(127))
_DISALLOWED_BASIC_STR_CHARS = _ASCII_CTRL - frozenset("\t")


def _parse_basic_str(state: _ParseState) -> str:
    state.pos += 1
    result = ""
    while not state.done():
        c = state.char()
        if c == '"':
            state.pos += 1
            return result
        if c in _DISALLOWED_BASIC_STR_CHARS:
            raise Exception("TODO: msg and type")

        if c == "\\":
            result += _parse_basic_str_escape_sequence(state)
        else:
            result += c
            state.pos += 1

    raise Exception("TODO: msg and type")


_BASIC_STR_ESCAPE_REPLACEMENTS = {
    "\\b": "\u0008",  # backspace
    "\\t": "\u0009",  # tab
    "\\n": "\u000A",  # linefeed
    "\\f": "\u000C",  # form feed
    "\\r": "\u000D",  # carriage return
    "\\": "\u0022",  # quote
    "\\\\": "\u005C",  # backslash
}


def _parse_basic_str_escape_sequence(state: _ParseState) -> str:
    escape_id = state.src[state.pos : state.pos + 2]
    if not len(escape_id) == 2:
        raise Exception("TODO: type and msg")
    state.pos += 2

    if escape_id in _BASIC_STR_ESCAPE_REPLACEMENTS:
        return _BASIC_STR_ESCAPE_REPLACEMENTS[escape_id]
    elif escape_id == "\\u":
        return _parse_hex_char(state, 4)
    elif escape_id == "\\U":
        return _parse_hex_char(state, 8)
    raise Exception("TODO: type and msg")


def _parse_hex_char(state: _ParseState, hex_len: int) -> str:
    hex_str = state.src[state.pos : state.pos + hex_len]
    if not len(hex_str) == hex_len or any(c not in string.hexdigits for c in hex_str):
        raise Exception("TODO: type and msg")
    state.pos += hex_len
    return chr(int(hex_str, 16))


def _parse_literal_str(state: _ParseState) -> str:
    state.pos += 1
    start_pos = state.pos
    _skip_until(state, "'\n")
    end_pos = state.pos
    if state.done() or state.char() == "\n":
        raise Exception("TODO: msg and type")
    state.pos += 1
    return state.src[start_pos:end_pos]


def _parse_multiline_literal_str(state: _ParseState) -> str:
    state.pos += 3
    start_pos = state.pos
    try:
        end_pos = state.src.index("'''", state.pos)
    except ValueError:
        raise Exception("TODO: msg and type here")
    state.pos = end_pos + 3

    # Add at maximum two extra apostrophes if the end sequence is 4 or 5
    # apostrophes long instead of just 3.
    if not state.done() and state.char() == "'":
        state.pos += 1
        end_pos += 1
        if not state.done() and state.char() == "'":
            state.pos += 1
            end_pos += 1

    content = state.src[start_pos:end_pos]

    if content.startswith("\n"):
        content = content[1:]
    return content


def _parse_regex(state: _ParseState, regex: re.Pattern) -> str:
    match = regex.match(state.src[state.pos :])
    if not match:
        raise Exception("TODO: type and msg")
    match_str = match.group()
    state.pos += len(match_str)
    return match_str


def _parse_value(state: _ParseState) -> Any:  # noqa: C901
    src = state.src[state.pos :]
    char = state.char()

    # Multiline strings
    if src.startswith('"""'):
        raise NotImplementedError
    if src.startswith("'''"):
        return _parse_multiline_literal_str(state)

    # Single line strings
    if char == '"':
        return _parse_basic_str(state)
    if char == "'":
        return _parse_literal_str(state)

    # Inline tables
    if char == "{":
        raise NotImplementedError

    # Arrays
    if char == "[":
        raise NotImplementedError

    # Dates and times
    date_match = _DATETIME_RE.match(src)
    if date_match:
        match_str = date_match.group()
        state.pos += len(match_str)
        groups: Any = date_match.groups()
        year, month, day = (int(x) for x in groups[:3])
        if groups[3] is None:
            # Returning local date
            return datetime.date(year, month, day)
        hour, minute, sec = (int(x) for x in groups[3:6])
        micros_str = groups[6] or "0"
        micros = int(micros_str.ljust(6, "0")[:6])
        if groups[7] is not None:
            offset_dir = 1 if "+" in match_str else -1
            tz: Optional[datetime.tzinfo] = _CustomTzinfo(
                datetime.timedelta(
                    hours=offset_dir * int(groups[7]),
                    minutes=offset_dir * int(groups[8]),
                )
            )
        elif "Z" in match_str:
            tz = _CustomTzinfo(datetime.timedelta())
        else:  # local date-time
            tz = None
        return datetime.datetime(year, month, day, hour, minute, sec, micros, tzinfo=tz)
    localtime_match = _LOCAL_TIME_RE.match(src)
    if localtime_match:
        state.pos += len(localtime_match.group())
        groups = localtime_match.groups()
        hour, minute, sec = (int(x) for x in groups[:3])
        micros_str = groups[3] or "0"
        micros = int(micros_str.ljust(6, "0")[:6])
        return datetime.time(hour, minute, sec, micros)

    # Booleans
    if src.startswith("true"):
        state.pos += 4
        return True
    if src.startswith("false"):
        state.pos += 5
        return False

    # Non-decimal integers
    if src.startswith("0x"):
        hex_str = _parse_regex(state, _HEX_RE)
        return int(hex_str, 16)
    if src.startswith("0o"):
        oct_str = _parse_regex(state, _OCT_RE)
        return int(oct_str, 8)
    if src.startswith("0b"):
        bin_str = _parse_regex(state, _BIN_RE)
        return int(bin_str, 2)

    # First "word". A substring before whitespace or line comment
    first_word = src.split(maxsplit=1)[0].split("#", maxsplit=1)[0]

    # Decimal integers and "normal" floats
    if _DEC_OR_FLOAT_RE.match(first_word):
        state.pos += len(first_word)
        if "." in first_word or "e" in first_word or "E" in first_word:
            return float(first_word)
        return int(first_word)

    # Special floats
    if first_word in {"-inf", "inf", "+inf", "-nan", "nan", "+nan"}:
        state.pos += len(first_word)
        return float(first_word)

    raise Exception("TODO: msg and type")


def _get_or_create_nested_dict(base_dict: dict, keys: Iterable[str]) -> dict:
    container = base_dict
    for k in keys:
        if k not in container:
            container[k] = {}
        container = container[k]
    return container


def _append_dict_to_nested_list(base_dict: dict, keys: Sequence[str]) -> dict:
    container: Any = base_dict
    for k in keys[:-1]:
        if k not in container:
            container[k] = {}
        container = container[k]
        if isinstance(container, list):
            container = container[-1]
    new_dict: dict = {}
    last_key = keys[-1]
    if last_key in container:
        container[last_key].append(new_dict)
    else:
        container[last_key] = [new_dict]
    return new_dict
