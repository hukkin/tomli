import datetime
import re
import string
from typing import Any, Dict, Iterable, Optional, Set, Tuple, Union

from lil_toml import _re
from lil_toml._tz import CustomTzinfo

Namespace = Tuple[str, ...]


class ParseState:
    def __init__(self, src: str):
        self.src: str = src
        self.pos: int = 0
        self.out: NestedDict = NestedDict({})
        self.header_namespace: Namespace = ()

    def done(self) -> bool:
        return self.pos >= len(self.src)

    def char(self) -> str:
        return self.src[self.pos]


class NestedDict:
    def __init__(self, wrapped_dict: dict):
        self.dict: Dict[str, Any] = wrapped_dict
        self.explicitly_created: Set[Tuple[str, ...]] = set()

    # def __contains__(self, keys: Tuple[str, ...]) -> bool:
    #     try:
    #         self._get_nest(keys)
    #     except KeyError:
    #         return False
    #     return True
    #
    # def _get_nest(self, keys: Tuple[str, ...]) -> dict:
    #     container: Any = self.dict
    #     for part in keys:
    #         container = container[part]
    #         if isinstance(container, list):
    #             container = container[-1]
    #     return container

    def get_or_create_nest(self, keys: Tuple[str, ...]) -> dict:
        container: Any = self.dict
        for k in keys:
            if k not in container:
                container[k] = {}
            container = container[k]
            if isinstance(container, list):
                container = container[-1]
        self.explicitly_created.add(keys)
        return container

    def append_nest_to_list(self, keys: Tuple[str, ...]) -> dict:
        container = self.get_or_create_nest(keys[:-1])
        nest: dict = {}
        last_key = keys[-1]
        if last_key in container:
            container[last_key].append(nest)
        else:
            container[last_key] = [nest]
        self.explicitly_created.add(keys)
        return nest


def loads(s: str) -> dict:  # noqa: C901
    # The spec allows converting "\r\n" to "\n", even in string
    # literals. Let's do so to simplify parsing.
    s = s.replace("\r\n", "\n")

    state = ParseState(s)

    # Parse one statement at a time
    # (typically means one line in TOML source)
    while True:
        # 1. Skip line leading whitespace
        _skip_chars(state, TOML_WS)

        # 2. Parse rules. Do one of:
        #    - end of file
        #    - end of line
        #    - comment
        #    - key->value
        #    - append dict to list (and move to its namespace)
        #    - create dict (and move to its namespace)
        if state.done():
            break
        char = state.char()
        if char == "\n":
            state.pos += 1
            continue
        elif char == "#":
            _comment_rule(state)
        elif char in BARE_KEY_CHARS or char in "\"'":
            _key_value_rule(state)
        elif state.src[state.pos : state.pos + 2] == "[[":
            _create_list_rule(state)
        elif char == "[":
            _create_dict_rule(state)
        else:
            raise Exception("TODO: msg and type --- not able to apply any rule")

        # 3. Skip trailing whitespace and line comment
        _skip_chars(state, TOML_WS)
        _skip_comment(state)

        # 4. Expect end of line of end of file
        if state.done():
            break
        elif state.char() == "\n":
            state.pos += 1
        else:
            raise Exception("TODO: msg and type --- statement didnt end in EOF or EOL")

    return state.out.dict


TOML_WS = frozenset(" \t")
BARE_KEY_CHARS = frozenset(string.ascii_letters + string.digits + "-_")


def _skip_chars(state: ParseState, chars: Iterable[str]) -> None:
    while not state.done() and state.char() in chars:
        state.pos += 1


def _skip_until(
    state: ParseState, chars: Iterable[str], *, error_on: Iterable[str]
) -> None:
    while not state.done() and state.char() not in chars:
        if state.char() in error_on:
            raise Exception("TODO: msg and type")
        state.pos += 1


def _skip_comment(state: ParseState) -> None:
    if not state.done() and state.char() == "#":
        _comment_rule(state)


def _comment_rule(state: ParseState) -> None:
    state.pos += 1
    while not state.done():
        c = state.char()
        if c == "\n":
            break
        if c in ILLEGAL_COMMENT_CHARS:
            raise Exception("TODO: msg and type")
        state.pos += 1


def _create_dict_rule(state: ParseState) -> None:
    state.pos += 1
    _skip_chars(state, TOML_WS)
    key_parts = _parse_key(state)

    if key_parts in state.out.explicitly_created:
        raise Exception("TODO: msg and type")
    state.out.get_or_create_nest(key_parts)
    state.header_namespace = key_parts

    if not state.char() == "]":
        raise Exception("TODO: type and msg")
    state.pos += 1


def _create_list_rule(state: ParseState) -> None:
    state.pos += 2
    _skip_chars(state, TOML_WS)
    key_parts = _parse_key(state)

    state.out.append_nest_to_list(key_parts)
    state.header_namespace = key_parts

    if not state.src[state.pos : state.pos + 2] == "]]":
        raise Exception("TODO: type and msg")
    state.pos += 2


def _key_value_rule(state: ParseState) -> None:
    key_parts, value = _parse_key_value_pair(state)
    parent_key, key_stem = key_parts[:-1], key_parts[-1]

    # Set the value in the right place in `state.out`
    nest = state.out.get_or_create_nest(state.header_namespace + parent_key)
    if key_stem in nest:
        raise Exception("TODO: type and msg")
    nest[key_stem] = value


def _parse_key_value_pair(state: ParseState) -> Tuple[Tuple[str, ...], Any]:
    key_parts = _parse_key(state)
    if state.char() != "=":
        raise Exception("TODO: type and msg")
    state.pos += 1
    _skip_chars(state, TOML_WS)
    value = _parse_value(state)
    return key_parts, value


def _parse_key(state: ParseState) -> Tuple[str, ...]:
    """Return parsed key as list of strings.

    Move state.pos after the key, to the start of the value that
    follows. Throw if parsing fails.
    """
    key_parts = [_parse_key_part(state)]
    _skip_chars(state, TOML_WS)
    while state.char() == ".":
        state.pos += 1
        _skip_chars(state, TOML_WS)
        key_parts.append(_parse_key_part(state))
        _skip_chars(state, TOML_WS)
    return tuple(key_parts)


def _parse_key_part(state: ParseState) -> str:
    """Return parsed key part.

    Move state.pos after the key part. Throw if parsing fails.
    """
    char = state.char()
    if char in BARE_KEY_CHARS:
        start_pos = state.pos
        _skip_chars(state, BARE_KEY_CHARS)
        return state.src[start_pos : state.pos]
    elif char == "'":
        return _parse_literal_str(state)
    elif char == '"':
        return _parse_basic_str(state)
    else:
        raise Exception("TODO: add type and msg")


ASCII_CTRL = frozenset(chr(i) for i in range(32)) | frozenset(chr(127))

# Neither of these sets include quotation mark or backslash. They are
# currently handled as separate cases in the parser functions.
ILLEGAL_BASIC_STR_CHARS = ASCII_CTRL - frozenset("\t")
ILLEGAL_MULTILINE_BASIC_STR_CHARS = ASCII_CTRL - frozenset("\t\n\r")

ILLEGAL_LITERAL_STR_CHARS = ASCII_CTRL - frozenset("\t")

ILLEGAL_COMMENT_CHARS = ASCII_CTRL - frozenset("\t")


def _parse_basic_str(state: ParseState) -> str:
    state.pos += 1
    result = ""
    while not state.done():
        c = state.char()
        if c == '"':
            state.pos += 1
            return result
        if c in ILLEGAL_BASIC_STR_CHARS:
            raise Exception("TODO: msg and type")

        if c == "\\":
            result += _parse_basic_str_escape_sequence(state, multiline=False)
        else:
            result += c
            state.pos += 1

    raise Exception("TODO: msg and type")


def _parse_array(state: ParseState) -> list:
    state.pos += 1
    array: list = []

    _skip_comments_and_array_ws(state)
    if state.char() == "]":
        state.pos += 1
        return array
    while True:
        array.append(_parse_value(state))
        _skip_comments_and_array_ws(state)

        if state.char() == "]":
            state.pos += 1
            return array
        elif state.char() != ",":
            raise Exception("TODO: msg and type")
        state.pos += 1

        _skip_comments_and_array_ws(state)

        if state.char() == "]":
            state.pos += 1
            return array


def _skip_comments_and_array_ws(state: ParseState) -> None:
    array_ws = TOML_WS | {"\n"}
    while True:
        pos_before_skip = state.pos
        _skip_chars(state, array_ws)
        _skip_comment(state)
        if state.pos == pos_before_skip:
            break


def _parse_inline_table(state: ParseState) -> dict:
    state.pos += 1
    nested_dict = NestedDict({})

    _skip_chars(state, TOML_WS)
    if state.char() == "}":
        state.pos += 1
        return nested_dict.dict
    while True:
        keys, value = _parse_key_value_pair(state)
        nest = nested_dict.get_or_create_nest(keys[:-1])
        nest[keys[-1]] = value  # TODO: check that "keys[-1]" isnt already there
        _skip_chars(state, TOML_WS)
        if state.char() == "}":
            state.pos += 1
            return nested_dict.dict
        if state.char() != ",":
            raise Exception("TODO: type and msg")
        state.pos += 1
        _skip_chars(state, TOML_WS)


BASIC_STR_ESCAPE_REPLACEMENTS = {
    "\\b": "\u0008",  # backspace
    "\\t": "\u0009",  # tab
    "\\n": "\u000A",  # linefeed
    "\\f": "\u000C",  # form feed
    "\\r": "\u000D",  # carriage return
    '\\"': "\u0022",  # quote
    "\\\\": "\u005C",  # backslash
}


def _parse_basic_str_escape_sequence(state: ParseState, *, multiline: bool) -> str:
    escape_id = state.src[state.pos : state.pos + 2]
    if not len(escape_id) == 2:
        raise Exception("TODO: type and msg")
    state.pos += 2

    if multiline and escape_id in {"\\ ", "\\\t", "\\\n"}:
        _skip_chars(state, TOML_WS | frozenset("\n"))
        return ""
    if escape_id in BASIC_STR_ESCAPE_REPLACEMENTS:
        return BASIC_STR_ESCAPE_REPLACEMENTS[escape_id]
    if escape_id == "\\u":
        return _parse_hex_char(state, 4)
    if escape_id == "\\U":
        return _parse_hex_char(state, 8)
    raise Exception("TODO: type and msg")


def _parse_hex_char(state: ParseState, hex_len: int) -> str:
    hex_str = state.src[state.pos : state.pos + hex_len]
    if not len(hex_str) == hex_len or any(c not in string.hexdigits for c in hex_str):
        raise Exception("TODO: type and msg")
    state.pos += hex_len
    return chr(int(hex_str, 16))


def _parse_literal_str(state: ParseState) -> str:
    state.pos += 1
    start_pos = state.pos
    _skip_until(state, "'\n", error_on=ILLEGAL_LITERAL_STR_CHARS)
    end_pos = state.pos
    if state.done() or state.char() == "\n":
        raise Exception("TODO: msg and type")
    state.pos += 1
    return state.src[start_pos:end_pos]


def _parse_multiline_literal_str(state: ParseState) -> str:
    state.pos += 3
    if state.char() == "\n":
        state.pos += 1
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

    return state.src[start_pos:end_pos]


def _parse_multiline_basic_str(state: ParseState) -> str:
    state.pos += 3
    if state.char() == "\n":
        state.pos += 1
    result = ""
    while not state.done():
        c = state.char()
        if c == '"':
            next_five = state.src[state.pos : state.pos + 5]
            if next_five == '"""""':
                result += '""'
                state.pos += 5
                return result
            if next_five.startswith('""""'):
                result += '"'
                state.pos += 4
                return result
            if next_five.startswith('"""'):
                state.pos += 3
                return result
            if next_five.startswith('""'):
                result += '""'
                state.pos += 2
            else:
                result += '"'
                state.pos += 1
            continue
        if c in ILLEGAL_MULTILINE_BASIC_STR_CHARS:
            raise Exception("TODO: msg and type")

        if c == "\\":
            result += _parse_basic_str_escape_sequence(state, multiline=True)
        else:
            result += c
            state.pos += 1

    raise Exception("TODO: msg and type")


def _parse_regex(state: ParseState, regex: re.Pattern) -> str:
    match = regex.match(state.src[state.pos :])
    if not match:
        raise Exception("TODO: type and msg")
    match_str = match.group()
    state.pos += len(match_str)
    return match_str


def _parse_datetime(
    state: ParseState, match: re.Match
) -> Union[datetime.datetime, datetime.date]:
    match_str = match.group()
    state.pos += len(match_str)
    groups: Any = match.groups()
    year, month, day = (int(x) for x in groups[:3])
    if groups[3] is None:
        # Returning local date
        return datetime.date(year, month, day)
    hour, minute, sec = (int(x) for x in groups[3:6])
    micros = int(groups[6][1:].ljust(6, "0")[:6]) if groups[6] else 0
    if groups[7] is not None:
        offset_dir = 1 if "+" in match_str else -1
        tz: Optional[datetime.tzinfo] = CustomTzinfo(
            datetime.timedelta(
                hours=offset_dir * int(groups[7]),
                minutes=offset_dir * int(groups[8]),
            )
        )
    elif "Z" in match_str:
        tz = CustomTzinfo(datetime.timedelta())
    else:  # local date-time
        tz = None
    return datetime.datetime(year, month, day, hour, minute, sec, micros, tzinfo=tz)


def _parse_localtime(state: ParseState, match: re.Match) -> datetime.time:
    state.pos += len(match.group())
    groups = match.groups()
    hour, minute, sec = (int(x) for x in groups[:3])
    micros = int(groups[3][1:].ljust(6, "0")[:6]) if groups[3] else 0
    return datetime.time(hour, minute, sec, micros)


def _parse_value(state: ParseState) -> Any:  # noqa: C901
    src = state.src[state.pos :]
    char = state.char()

    # Multiline strings
    if src.startswith('"""'):
        return _parse_multiline_basic_str(state)
    if src.startswith("'''"):
        return _parse_multiline_literal_str(state)

    # Single line strings
    if char == '"':
        return _parse_basic_str(state)
    if char == "'":
        return _parse_literal_str(state)

    # Inline tables
    if char == "{":
        return _parse_inline_table(state)

    # Arrays
    if char == "[":
        return _parse_array(state)

    # Dates and times
    date_match = _re.DATETIME.match(src)
    if date_match:
        return _parse_datetime(state, date_match)
    localtime_match = _re.LOCAL_TIME.match(src)
    if localtime_match:
        return _parse_localtime(state, localtime_match)

    # Booleans
    if src.startswith("true"):
        state.pos += 4
        return True
    if src.startswith("false"):
        state.pos += 5
        return False

    # Non-decimal integers
    if src.startswith("0x"):
        hex_str = _parse_regex(state, _re.HEX)
        return int(hex_str, 16)
    if src.startswith("0o"):
        oct_str = _parse_regex(state, _re.OCT)
        return int(oct_str, 8)
    if src.startswith("0b"):
        bin_str = _parse_regex(state, _re.BIN)
        return int(bin_str, 2)

    # Special floats
    if src[:3] in {"inf", "nan"}:
        state.pos += 3
        return float(src[:3])
    if src[:4] in {"-inf", "+inf", "-nan", "+nan"}:
        state.pos += 4
        return float(src[:4])

    # Decimal integers and "normal" floats
    dec_match = _re.DEC_OR_FLOAT.match(src)
    if dec_match:
        match_str = dec_match.group()
        state.pos += len(match_str)
        if "." in match_str or "e" in match_str or "E" in match_str:
            return float(match_str)
        return int(match_str)

    raise Exception("TODO: msg and type")
