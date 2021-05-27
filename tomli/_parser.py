import datetime
import string
import sys
from types import MappingProxyType
from typing import Any, Dict, Iterable, Optional, Set, Tuple, Union

from tomli import _re

if sys.version_info < (3, 7):
    from typing import re
else:
    import re

ASCII_CTRL = frozenset(chr(i) for i in range(32)) | frozenset(chr(127))

# Neither of these sets include quotation mark or backslash. They are
# currently handled as separate cases in the parser functions.
ILLEGAL_BASIC_STR_CHARS = ASCII_CTRL - frozenset("\t")
ILLEGAL_MULTILINE_BASIC_STR_CHARS = ASCII_CTRL - frozenset("\t\n\r")

ILLEGAL_LITERAL_STR_CHARS = ASCII_CTRL - frozenset("\t")
ILLEGAL_MULTILINE_LITERAL_STR_CHARS = ASCII_CTRL - frozenset("\t\n")

ILLEGAL_COMMENT_CHARS = ASCII_CTRL - frozenset("\t")

TOML_WS = frozenset(" \t")
BARE_KEY_CHARS = frozenset(string.ascii_letters + string.digits + "-_")

BASIC_STR_ESCAPE_REPLACEMENTS = MappingProxyType(
    {
        "\\b": "\u0008",  # backspace
        "\\t": "\u0009",  # tab
        "\\n": "\u000A",  # linefeed
        "\\f": "\u000C",  # form feed
        "\\r": "\u000D",  # carriage return
        '\\"': "\u0022",  # quote
        "\\\\": "\u005C",  # backslash
    }
)

Namespace = Tuple[str, ...]


class TOMLDecodeError(ValueError):
    """An error raised if a document is not valid TOML."""


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
        try:
            char = state.char()
        except IndexError:
            break
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
            raise TOMLDecodeError("Invalid TOML")

        # 3. Skip trailing whitespace and line comment
        _skip_chars(state, TOML_WS)
        _skip_comment(state)

        # 4. Expect end of line of end of file
        try:
            char = state.char()
        except IndexError:
            break
        if char == "\n":
            state.pos += 1
        else:
            raise TOMLDecodeError(
                "End of line or end of document not found after a statement"
            )

    return state.out.dict


class ParseState:
    def __init__(self, src: str):
        self.src: str = src
        self.src_len = len(self.src)
        self.pos: int = 0
        self.out: NestedDict = NestedDict({})
        self.header_namespace: Namespace = ()

    def done(self) -> bool:
        return self.pos >= self.src_len

    def char(self) -> str:
        return self.src[self.pos]


class NestedDict:
    def __init__(self, wrapped_dict: dict):
        self.dict: Dict[str, Any] = wrapped_dict
        # Keep track of keys that have been explicitly set
        self._explicitly_created: Set[Tuple[str, ...]] = set()
        # Keep track of keys that hold immutable values. Immutability
        # applies recursively to sub-structures.
        self._frozen: Set[Tuple[str, ...]] = set()

    def get_or_create_nest(self, keys: Tuple[str, ...]) -> dict:
        container: Any = self.dict
        for k in keys:
            if k not in container:
                container[k] = {}
            container = container[k]
            if isinstance(container, list):
                container = container[-1]
        if not isinstance(container, dict):
            raise KeyError("There is no nest behind this key")
        self.mark_explicitly_created(keys)
        return container

    def append_nest_to_list(self, keys: Tuple[str, ...]) -> dict:
        container = self.get_or_create_nest(keys[:-1])
        nest: dict = {}
        last_key = keys[-1]
        if last_key in container:
            list_ = container[last_key]
            if not isinstance(list_, list):
                raise KeyError("An object other than list found behind this key")
            list_.append(nest)
        else:
            container[last_key] = [nest]
        self.mark_explicitly_created(keys)
        return nest

    def is_explicitly_created(self, keys: Tuple[str, ...]) -> bool:
        return keys in self._explicitly_created

    def mark_explicitly_created(self, keys: Tuple[str, ...]) -> None:
        self._explicitly_created.add(keys)

    def is_frozen(self, keys: Tuple[str, ...]) -> bool:
        for frozen_space in self._frozen:
            if keys[: len(frozen_space)] == frozen_space:
                return True
        return False

    def mark_frozen(self, keys: Tuple[str, ...]) -> None:
        self._frozen.add(keys)


def _skip_chars(state: ParseState, chars: Iterable[str]) -> None:
    try:
        while state.char() in chars:
            state.pos += 1
    except IndexError:
        pass


def _skip_until(
    state: ParseState, chars: Iterable[str], *, error_on: Iterable[str]
) -> None:
    try:
        while True:
            char = state.char()
            if char in chars:
                break
            if char in error_on:
                raise TOMLDecodeError(f'Invalid character "{char!r}" found')
            state.pos += 1
    except IndexError:
        pass


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
            raise TOMLDecodeError(f'Illegal character "{c!r}" found in a comment')
        state.pos += 1


def _create_dict_rule(state: ParseState) -> None:
    state.pos += 1
    _skip_chars(state, TOML_WS)
    key_parts = _parse_key(state)

    if state.out.is_explicitly_created(key_parts):
        raise TOMLDecodeError(f'Can not declare "{".".join(key_parts)}" twice')
    try:
        state.out.get_or_create_nest(key_parts)
    except KeyError:
        raise TOMLDecodeError("Can not overwrite a value")
    state.header_namespace = key_parts

    if not state.char() == "]":
        raise TOMLDecodeError(
            f'Found "{state.char()!r}" at the end of a table declaration. Expected "]"'
        )
    state.pos += 1


def _create_list_rule(state: ParseState) -> None:
    state.pos += 2
    _skip_chars(state, TOML_WS)
    key_parts = _parse_key(state)

    if state.out.is_frozen(key_parts):
        raise TOMLDecodeError(
            f'Can not mutate immutable namespace "{".".join(key_parts)}"'
        )
    try:
        state.out.append_nest_to_list(key_parts)
    except KeyError:
        raise TOMLDecodeError("Can not overwrite a value")
    state.header_namespace = key_parts

    end_marker = state.src[state.pos : state.pos + 2]
    if not end_marker == "]]":
        raise TOMLDecodeError(
            f'Found "{end_marker!r}" at the end of an array declaration. Expected "]]"'
        )
    state.pos += 2


def _key_value_rule(state: ParseState) -> None:
    key, value = _parse_key_value_pair(state)
    parent_key, key_stem = key[:-1], key[-1]
    abs_parent_key = state.header_namespace + parent_key
    abs_key = state.header_namespace + key

    if state.out.is_frozen(abs_parent_key):
        raise TOMLDecodeError(
            f'Can not mutate immutable namespace "{".".join(abs_parent_key)}"'
        )
    # Set the value in the right place in `state.out`
    try:
        nest = state.out.get_or_create_nest(abs_parent_key)
    except KeyError:
        raise TOMLDecodeError("Can not overwrite a value")
    if key_stem in nest:
        raise TOMLDecodeError(f'Can not define "{".".join(abs_key)}" twice')
    # Mark inline table and array namespaces as recursively immutable
    if isinstance(value, (dict, list)):
        state.out.mark_explicitly_created(abs_key)
        state.out.mark_frozen(abs_key)
    nest[key_stem] = value


def _parse_key_value_pair(state: ParseState) -> Tuple[Tuple[str, ...], Any]:
    key_parts = _parse_key(state)
    if state.char() != "=":
        raise TOMLDecodeError(f'Found "{state.char()!r}" after a key. Expected "="')
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
    if char == "'":
        return _parse_literal_str(state)
    if char == '"':
        return _parse_basic_str(state)
    raise TOMLDecodeError("Invalid key definition")


def _parse_basic_str(state: ParseState) -> str:
    state.pos += 1
    result = ""
    while not state.done():
        c = state.char()
        if c == '"':
            state.pos += 1
            return result
        if c in ILLEGAL_BASIC_STR_CHARS:
            raise TOMLDecodeError(f'Illegal character "{c!r}" found in a string')

        if c == "\\":
            result += _parse_basic_str_escape_sequence(state, multiline=False)
        else:
            result += c
            state.pos += 1

    raise TOMLDecodeError("Closing quote of a string not found")


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
            raise TOMLDecodeError(
                f'Found "{state.char()!r}" after an array item. Expected "," or "]"'
            )
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
            raise TOMLDecodeError(
                f'Found "{state.char()!r}" after an inline table key value pair. '
                + 'Expected "," or "}"'
            )
        state.pos += 1
        _skip_chars(state, TOML_WS)


def _parse_basic_str_escape_sequence(state: ParseState, *, multiline: bool) -> str:
    escape_id = state.src[state.pos : state.pos + 2]
    if not len(escape_id) == 2:
        raise TOMLDecodeError("String value not closed before end of document")
    state.pos += 2

    if multiline and escape_id in {"\\ ", "\\\t", "\\\n"}:
        # Skip whitespace until next non-whitespace character or end of
        # the doc. Error if non-whitespace is found before newline.
        if escape_id != "\\\n":
            _skip_chars(state, TOML_WS)
            if state.done():
                return ""
            if state.char() != "\n":
                raise TOMLDecodeError('Unescaped "\\" character found in a string')
            state.pos += 1
        _skip_chars(state, TOML_WS | frozenset("\n"))
        return ""
    if escape_id in BASIC_STR_ESCAPE_REPLACEMENTS:
        return BASIC_STR_ESCAPE_REPLACEMENTS[escape_id]
    if escape_id == "\\u":
        return _parse_hex_char(state, 4)
    if escape_id == "\\U":
        return _parse_hex_char(state, 8)
    raise TOMLDecodeError('Unescaped "\\" character found in a string')


def _parse_hex_char(state: ParseState, hex_len: int) -> str:
    hex_str = state.src[state.pos : state.pos + hex_len]
    if not len(hex_str) == hex_len or any(c not in string.hexdigits for c in hex_str):
        raise TOMLDecodeError("Invalid hex value")
    state.pos += hex_len
    hex_int = int(hex_str, 16)
    try:
        char = chr(hex_int)
    except (ValueError, OverflowError):
        raise TOMLDecodeError("Hex value too large to convert into a character")
    return char


def _parse_literal_str(state: ParseState) -> str:
    state.pos += 1
    start_pos = state.pos
    _skip_until(state, "'\n", error_on=ILLEGAL_LITERAL_STR_CHARS)
    end_pos = state.pos
    if state.done() or state.char() == "\n":
        raise TOMLDecodeError("Literal string closing apostrophe not found")
    state.pos += 1
    return state.src[start_pos:end_pos]


def _parse_multiline_literal_str(state: ParseState) -> str:
    state.pos += 3
    if state.char() == "\n":
        state.pos += 1
    consecutive_apostrophes = 0
    start_pos = state.pos
    while not state.done():
        c = state.char()
        state.pos += 1
        if c == "'":
            consecutive_apostrophes += 1
            if consecutive_apostrophes == 3:
                # Add at maximum two extra apostrophes if the end sequence is 4 or 5
                # apostrophes long instead of just 3.
                if not state.done() and state.char() == "'":
                    state.pos += 1
                    if not state.done() and state.char() == "'":
                        state.pos += 1
                return state.src[start_pos : state.pos - 3]
            continue
        consecutive_apostrophes = 0
        if c in ILLEGAL_MULTILINE_LITERAL_STR_CHARS:
            raise TOMLDecodeError(
                f'Illegal character "{c!r}" found in a multiline literal string'
            )

    raise TOMLDecodeError(
        "Multiline literal string not closed before end of the document"
    )


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
            raise TOMLDecodeError(
                f'Illegal character "{c!r}" found in a multiline string'
            )

        if c == "\\":
            result += _parse_basic_str_escape_sequence(state, multiline=True)
        else:
            result += c
            state.pos += 1

    raise TOMLDecodeError("Multiline string not closed before end of the document")


def _parse_regex(state: ParseState, regex: re.Pattern) -> str:
    match = regex.match(state.src[state.pos :])
    if not match:
        raise TOMLDecodeError("Invalid document")
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
        tz: Optional[datetime.tzinfo] = datetime.timezone(
            datetime.timedelta(
                hours=offset_dir * int(groups[7]),
                minutes=offset_dir * int(groups[8]),
            )
        )
    elif "Z" in match_str:
        tz = datetime.timezone(datetime.timedelta())
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

    # Basic strings
    if char == '"':
        if src.startswith('"""'):
            return _parse_multiline_basic_str(state)
        return _parse_basic_str(state)

    # Literal strings
    if char == "'":
        if src.startswith("'''"):
            return _parse_multiline_literal_str(state)
        return _parse_literal_str(state)

    # Inline tables
    if char == "{":
        return _parse_inline_table(state)

    # Arrays
    if char == "[":
        return _parse_array(state)

    # Booleans
    if src.startswith("true"):
        state.pos += 4
        return True
    if src.startswith("false"):
        state.pos += 5
        return False

    # Dates and times
    date_match = _re.DATETIME.match(src)
    if date_match:
        return _parse_datetime(state, date_match)
    localtime_match = _re.LOCAL_TIME.match(src)
    if localtime_match:
        return _parse_localtime(state, localtime_match)

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

    raise TOMLDecodeError("Invalid value")
