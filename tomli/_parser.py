import datetime
import string
import sys
from types import MappingProxyType
from typing import Any, Callable, Dict, Iterable, Optional, Set, TextIO, Tuple, Union

from tomli import _re

if sys.version_info < (3, 7):
    from typing import re  # pragma: no cover
else:
    import re  # pragma: no cover

ASCII_CTRL = frozenset(chr(i) for i in range(32)) | frozenset(chr(127))

# Neither of these sets include quotation mark or backslash. They are
# currently handled as separate cases in the parser functions.
ILLEGAL_BASIC_STR_CHARS = ASCII_CTRL - frozenset("\t")
ILLEGAL_MULTILINE_BASIC_STR_CHARS = ASCII_CTRL - frozenset("\t\n\r")

ILLEGAL_LITERAL_STR_CHARS = ASCII_CTRL - frozenset("\t")
ILLEGAL_MULTILINE_LITERAL_STR_CHARS = ASCII_CTRL - frozenset("\t\n")

ILLEGAL_COMMENT_CHARS = ASCII_CTRL - frozenset("\t")

TOML_WS = frozenset(" \t")
TOML_WS_AND_NEWLINE = TOML_WS | {"\n"}
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

ParseFloat = Callable[[str], Any]
Namespace = Tuple[str, ...]


class TOMLDecodeError(ValueError):
    """An error raised if a document is not valid TOML."""


def load(fp: TextIO, *, parse_float: ParseFloat = float) -> Dict[str, Any]:
    """Parse TOML from a file object."""
    s = fp.read()
    return loads(s, parse_float=parse_float)


def loads(s: str, *, parse_float: ParseFloat = float) -> Dict[str, Any]:  # noqa: C901
    """Parse TOML from a string."""

    # The spec allows converting "\r\n" to "\n", even in string
    # literals. Let's do so to simplify parsing.
    s = s.replace("\r\n", "\n")

    state = ParseState(s, parse_float)

    # Parse one statement at a time
    # (typically means one line in TOML source)
    while True:
        # 1. Skip line leading whitespace
        skip_chars(state, TOML_WS)

        # 2. Parse rules. Expect one of the following:
        #    - end of file
        #    - end of line
        #    - comment
        #    - key->value
        #    - append dict to list (and move to its namespace)
        #    - create dict (and move to its namespace)
        char = state.try_char()
        if not char:
            break
        if char == "\n":
            state.pos += 1
            continue
        elif char == "#":
            comment_rule(state)
        elif char in BARE_KEY_CHARS or char in "\"'":
            key_value_rule(state)
        elif state.src[state.pos : state.pos + 2] == "[[":
            create_list_rule(state)
        elif char == "[":
            create_dict_rule(state)
        else:
            raise TOMLDecodeError("Invalid TOML")

        # 3. Skip trailing whitespace and line comment
        skip_chars(state, TOML_WS)
        skip_comment(state)

        # 4. Expect end of line or end of file
        char = state.try_char()
        if not char:
            break
        if char == "\n":
            state.pos += 1
        else:
            raise TOMLDecodeError(
                "End of line or end of document not found after a statement"
            )

    return state.out.dict


class ParseState:
    def __init__(self, src: str, parse_float: ParseFloat):
        # Read only
        self.src: str = src
        self.out: NestedDict = NestedDict({})
        self.parse_float = parse_float

        # Read and write
        self.pos: int = 0
        self.header_namespace: Namespace = ()

    def try_char(self) -> Optional[str]:
        try:
            return self.src[self.pos]
        except IndexError:
            return None


class NestedDict:
    def __init__(self, wrapped_dict: dict):
        self.dict: Dict[str, Any] = wrapped_dict
        # Keep track of keys that have been explicitly set
        self._explicitly_created: Set[Tuple[str, ...]] = set()
        # Keep track of keys that hold immutable values. Immutability
        # applies recursively to sub-structures.
        self._frozen: Set[Tuple[str, ...]] = set()

    def get_or_create_nest(self, key: Tuple[str, ...]) -> dict:
        container: Any = self.dict
        for k in key:
            if k not in container:
                container[k] = {}
            container = container[k]
            if isinstance(container, list):
                container = container[-1]
            if not isinstance(container, dict):
                raise KeyError("There is no nest behind this key")
        self._explicitly_created.add(key)
        return container

    def append_nest_to_list(self, key: Tuple[str, ...]) -> None:
        container = self.get_or_create_nest(key[:-1])
        nest: dict = {}
        last_key = key[-1]
        if last_key in container:
            list_ = container[last_key]
            if not isinstance(list_, list):
                raise KeyError("An object other than list found behind this key")
            list_.append(nest)
        else:
            container[last_key] = [nest]
        self._explicitly_created.add(key)

    def is_explicitly_created(self, key: Tuple[str, ...]) -> bool:
        return key in self._explicitly_created

    def is_frozen(self, key: Tuple[str, ...]) -> bool:
        for frozen_space in self._frozen:
            if key[: len(frozen_space)] == frozen_space:
                return True
        return False

    def mark_frozen(self, key: Tuple[str, ...]) -> None:
        self._frozen.add(key)


def skip_chars(state: ParseState, chars: Iterable[str]) -> None:
    # Use local variables for performance. This is the hottest loop in the
    # entire parser so the speedup seems to be well over 5% in CPython 3.8.
    src, pos = state.src, state.pos
    try:
        while src[pos] in chars:
            pos += 1
    except IndexError:
        pass
    state.pos = pos


def skip_until(state: ParseState, expect_char: str, *, error_on: Iterable[str]) -> None:
    """Skip until `expect_char` is found.

    Error if end of file or one of `error_on` is found.
    """
    while True:
        try:
            char = state.src[state.pos]
        except IndexError:
            raise TOMLDecodeError(f'Expected but did not find "{expect_char!r}"')
        if char == expect_char:
            break
        if char in error_on:
            raise TOMLDecodeError(f'Invalid character "{char!r}" found')
        state.pos += 1


def skip_comment(state: ParseState) -> None:
    if state.try_char() == "#":
        comment_rule(state)


def comment_rule(state: ParseState) -> None:
    state.pos += 1
    while True:
        c = state.try_char()
        if not c:
            break
        if c == "\n":
            break
        if c in ILLEGAL_COMMENT_CHARS:
            raise TOMLDecodeError(f'Illegal character "{c!r}" found in a comment')
        state.pos += 1


def create_dict_rule(state: ParseState) -> None:
    state.pos += 1
    skip_chars(state, TOML_WS)
    key = parse_key(state)

    if state.out.is_explicitly_created(key) or state.out.is_frozen(key):
        raise TOMLDecodeError(f'Can not declare "{".".join(key)}" twice')
    try:
        state.out.get_or_create_nest(key)
    except KeyError:
        raise TOMLDecodeError("Can not overwrite a value")
    state.header_namespace = key

    if state.try_char() != "]":
        raise TOMLDecodeError('Expected "]" at the end of a table declaration')
    state.pos += 1


def create_list_rule(state: ParseState) -> None:
    state.pos += 2
    skip_chars(state, TOML_WS)
    key = parse_key(state)

    if state.out.is_frozen(key):
        raise TOMLDecodeError(f'Can not mutate immutable namespace "{".".join(key)}"')
    try:
        state.out.append_nest_to_list(key)
    except KeyError:
        raise TOMLDecodeError("Can not overwrite a value")
    state.header_namespace = key

    end_marker = state.src[state.pos : state.pos + 2]
    if not end_marker == "]]":
        raise TOMLDecodeError(
            f'Found "{end_marker!r}" at the end of an array declaration. Expected "]]"'
        )
    state.pos += 2


def key_value_rule(state: ParseState) -> None:
    key, value = parse_key_value_pair(state)
    key_parent, key_stem = key[:-1], key[-1]
    abs_key_parent = state.header_namespace + key_parent
    abs_key = state.header_namespace + key

    if state.out.is_frozen(abs_key_parent):
        raise TOMLDecodeError(
            f'Can not mutate immutable namespace "{".".join(abs_key_parent)}"'
        )
    # Set the value in the right place in `state.out`
    try:
        nest = state.out.get_or_create_nest(abs_key_parent)
    except KeyError:
        raise TOMLDecodeError("Can not overwrite a value")
    if key_stem in nest:
        raise TOMLDecodeError(f'Can not define "{".".join(abs_key)}" twice')
    # Mark inline table and array namespaces recursively immutable
    if isinstance(value, (dict, list)):
        state.out.mark_frozen(abs_key)
    nest[key_stem] = value


def parse_key_value_pair(state: ParseState) -> Tuple[Tuple[str, ...], Any]:
    key = parse_key(state)
    if state.try_char() != "=":
        raise TOMLDecodeError('Expected "=" after a key in a key-to-value mapping')
    state.pos += 1
    skip_chars(state, TOML_WS)
    value = parse_value(state)
    return key, value


def parse_key(state: ParseState) -> Tuple[str, ...]:
    """Return parsed key as list of strings.

    Move state.pos after the key, to the start of the value that
    follows. Throw if parsing fails.
    """
    key = [parse_key_part(state)]
    skip_chars(state, TOML_WS)
    while state.try_char() == ".":
        state.pos += 1
        skip_chars(state, TOML_WS)
        key.append(parse_key_part(state))
        skip_chars(state, TOML_WS)
    return tuple(key)


def parse_key_part(state: ParseState) -> str:
    """Return parsed key part.

    Move state.pos after the key part. Throw if parsing fails.
    """
    char = state.try_char()
    if char in BARE_KEY_CHARS:
        start_pos = state.pos
        skip_chars(state, BARE_KEY_CHARS)
        return state.src[start_pos : state.pos]
    if char == "'":
        return parse_literal_str(state)
    if char == '"':
        return parse_basic_str(state)
    raise TOMLDecodeError("Invalid key definition")


def parse_basic_str(state: ParseState) -> str:
    state.pos += 1
    result = ""
    while True:
        c = state.try_char()
        if not c:
            raise TOMLDecodeError("Closing quote of a string not found")
        if c == '"':
            state.pos += 1
            return result
        if c in ILLEGAL_BASIC_STR_CHARS:
            raise TOMLDecodeError(f'Illegal character "{c!r}" found in a string')

        if c == "\\":
            result += parse_basic_str_escape_sequence(state, multiline=False)
        else:
            result += c
            state.pos += 1


def parse_array(state: ParseState) -> list:
    state.pos += 1
    array: list = []

    skip_comments_and_array_ws(state)
    if state.try_char() == "]":
        state.pos += 1
        return array
    while True:
        array.append(parse_value(state))
        skip_comments_and_array_ws(state)

        c = state.try_char()
        if c == "]":
            state.pos += 1
            return array
        if c != ",":
            raise TOMLDecodeError("Unclosed array")
        state.pos += 1

        skip_comments_and_array_ws(state)

        c = state.try_char()
        if not c:
            raise TOMLDecodeError("Invalid array")
        if c == "]":
            state.pos += 1
            return array


def skip_comments_and_array_ws(state: ParseState) -> None:
    while True:
        pos_before_skip = state.pos
        skip_chars(state, TOML_WS_AND_NEWLINE)
        skip_comment(state)
        if state.pos == pos_before_skip:
            break


def parse_inline_table(state: ParseState) -> dict:
    state.pos += 1
    nested_dict = NestedDict({})

    skip_chars(state, TOML_WS)
    c = state.try_char()
    if not c:
        raise TOMLDecodeError("Unclosed inline table")
    if c == "}":
        state.pos += 1
        return nested_dict.dict
    while True:
        key, value = parse_key_value_pair(state)
        key_parent, key_stem = key[:-1], key[-1]
        nest = nested_dict.get_or_create_nest(key_parent)
        if key_stem in nest:
            raise TOMLDecodeError(f'Duplicate inline table key "{key_stem}"')
        nest[key_stem] = value
        skip_chars(state, TOML_WS)
        c = state.try_char()
        if c == "}":
            state.pos += 1
            return nested_dict.dict
        if c != ",":
            raise TOMLDecodeError("Unclosed inline table")
        state.pos += 1
        skip_chars(state, TOML_WS)


def parse_basic_str_escape_sequence(state: ParseState, *, multiline: bool) -> str:
    escape_id = state.src[state.pos : state.pos + 2]
    if not len(escape_id) == 2:
        raise TOMLDecodeError("String value not closed before end of document")
    state.pos += 2

    if multiline and escape_id in {"\\ ", "\\\t", "\\\n"}:
        # Skip whitespace until next non-whitespace character or end of
        # the doc. Error if non-whitespace is found before newline.
        if escape_id != "\\\n":
            skip_chars(state, TOML_WS)
            char = state.try_char()
            if not char:
                return ""
            if char != "\n":
                raise TOMLDecodeError('Unescaped "\\" character found in a string')
            state.pos += 1
        skip_chars(state, TOML_WS_AND_NEWLINE)
        return ""
    if escape_id in BASIC_STR_ESCAPE_REPLACEMENTS:
        return BASIC_STR_ESCAPE_REPLACEMENTS[escape_id]
    if escape_id == "\\u":
        return parse_hex_char(state, 4)
    if escape_id == "\\U":
        return parse_hex_char(state, 8)
    raise TOMLDecodeError('Unescaped "\\" character found in a string')


def parse_hex_char(state: ParseState, hex_len: int) -> str:
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


def parse_literal_str(state: ParseState) -> str:
    state.pos += 1  # Skip starting apostrophe
    start_pos = state.pos
    skip_until(state, "'", error_on=ILLEGAL_LITERAL_STR_CHARS)
    literal_str = state.src[start_pos : state.pos]
    state.pos += 1  # Skip ending apostrophe
    return literal_str


def parse_multiline_literal_str(state: ParseState) -> str:
    state.pos += 3
    c = state.try_char()
    if not c:
        raise TOMLDecodeError(
            "Multiline literal string not closed before end of document"
        )
    if c == "\n":
        state.pos += 1
    consecutive_apostrophes = 0
    start_pos = state.pos
    while True:
        c = state.try_char()
        if not c:
            raise TOMLDecodeError(
                "Multiline literal string not closed before end of document"
            )
        state.pos += 1
        if c == "'":
            consecutive_apostrophes += 1
            if consecutive_apostrophes == 3:
                # Add at maximum two extra apostrophes if the end sequence is 4 or 5
                # apostrophes long instead of just 3.
                if state.try_char() == "'":
                    state.pos += 1
                    if state.try_char() == "'":
                        state.pos += 1
                return state.src[start_pos : state.pos - 3]
            continue  # pragma: no cover
        consecutive_apostrophes = 0
        if c in ILLEGAL_MULTILINE_LITERAL_STR_CHARS:
            raise TOMLDecodeError(
                f'Illegal character "{c!r}" found in a multiline literal string'
            )


def parse_multiline_basic_str(state: ParseState) -> str:  # noqa: C901
    state.pos += 3
    c = state.try_char()
    if not c:
        raise TOMLDecodeError("Multiline string not closed before end of the document")
    if c == "\n":
        state.pos += 1
    result = ""
    while True:
        c = state.try_char()
        if not c:
            raise TOMLDecodeError(
                "Multiline string not closed before end of the document"
            )
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
            result += parse_basic_str_escape_sequence(state, multiline=True)
        else:
            result += c
            state.pos += 1


def parse_regex(state: ParseState, regex: re.Pattern) -> str:
    match = regex.match(state.src[state.pos :])
    if not match:
        raise TOMLDecodeError("Invalid document")
    match_str = match.group()
    state.pos += len(match_str)
    return match_str


def parse_datetime(
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
        tz = datetime.timezone.utc
    else:  # local date-time
        tz = None
    return datetime.datetime(year, month, day, hour, minute, sec, micros, tzinfo=tz)


def parse_localtime(state: ParseState, match: re.Match) -> datetime.time:
    state.pos += len(match.group())
    groups = match.groups()
    hour, minute, sec = (int(x) for x in groups[:3])
    micros = int(groups[3][1:].ljust(6, "0")[:6]) if groups[3] else 0
    return datetime.time(hour, minute, sec, micros)


def parse_dec_or_float(state: ParseState, match: re.Match) -> Any:
    match_str = match.group()
    state.pos += len(match_str)
    if "." in match_str or "e" in match_str or "E" in match_str:
        return state.parse_float(match_str)
    return int(match_str)


def parse_value(state: ParseState) -> Any:  # noqa: C901
    src = state.src[state.pos :]
    char = state.try_char()

    # Basic strings
    if char == '"':
        if src.startswith('"""'):
            return parse_multiline_basic_str(state)
        return parse_basic_str(state)

    # Literal strings
    if char == "'":
        if src.startswith("'''"):
            return parse_multiline_literal_str(state)
        return parse_literal_str(state)

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
        return parse_datetime(state, date_match)
    localtime_match = _re.LOCAL_TIME.match(src)
    if localtime_match:
        return parse_localtime(state, localtime_match)

    # Non-decimal integers
    if src.startswith("0x"):
        state.pos += 2
        hex_str = parse_regex(state, _re.HEX)
        return int(hex_str, 16)
    if src.startswith("0o"):
        state.pos += 2
        oct_str = parse_regex(state, _re.OCT)
        return int(oct_str, 8)
    if src.startswith("0b"):
        state.pos += 2
        bin_str = parse_regex(state, _re.BIN)
        return int(bin_str, 2)

    # Decimal integers and "normal" floats.
    # The regex will greedily match any type starting with a decimal
    # char, so needs to be located after handling of non-decimal ints,
    # and dates and times.
    dec_match = _re.DEC_OR_FLOAT.match(src)
    if dec_match:
        return parse_dec_or_float(state, dec_match)

    # Arrays
    if char == "[":
        return parse_array(state)

    # Inline tables
    if char == "{":
        return parse_inline_table(state)

    # Special floats
    if src[:3] in {"inf", "nan"}:
        state.pos += 3
        return state.parse_float(src[:3])
    if src[:4] in {"-inf", "+inf", "-nan", "+nan"}:
        state.pos += 4
        return state.parse_float(src[:4])

    raise TOMLDecodeError("Invalid value")
