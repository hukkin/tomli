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

ILLEGAL_LITERAL_STR_CHARS = ILLEGAL_BASIC_STR_CHARS
ILLEGAL_MULTILINE_LITERAL_STR_CHARS = ASCII_CTRL - frozenset("\t\n")

ILLEGAL_COMMENT_CHARS = ILLEGAL_BASIC_STR_CHARS

TOML_WS = frozenset(" \t")
TOML_WS_AND_NEWLINE = TOML_WS | frozenset("\n")
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
            raise TOMLDecodeError(suffix_coord(state, "Invalid statement"))

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
                suffix_coord(
                    state, "Expected newline or end of document after a statement"
                )
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

    def get_or_create_nest(
        self, key: Tuple[str, ...], *, explicit_access: bool = True
    ) -> dict:
        container: Any = self.dict
        for k in key:
            if k not in container:
                container[k] = {}
            container = container[k]
            if isinstance(container, list):
                container = container[-1]
            if not isinstance(container, dict):
                raise KeyError("There is no nest behind this key")
        if explicit_access:
            self._explicitly_created.add(key)
        return container

    def append_nest_to_list(self, key: Tuple[str, ...]) -> None:
        container = self.get_or_create_nest(key[:-1], explicit_access=False)
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

    def mark_relative_path_explicitly_created(
        self, head_key: Tuple[str, ...], rel_key: Tuple[str, ...]
    ) -> None:
        for i in range(len(rel_key)):
            self._explicitly_created.add(head_key + rel_key[: i + 1])

    def reset(self, key: Tuple[str, ...]) -> None:
        """Recursively unmark explicitly created and frozen statuses in the
        namespace."""
        len_key = len(key)
        self._frozen = {f for f in self._frozen if f[:len_key] != key}
        self._explicitly_created = {
            e for e in self._explicitly_created if e[:len_key] != key
        }


def skip_chars(state: ParseState, chars: Iterable[str]) -> None:
    # Use local variables for performance. This is the hottest loop in the
    # entire parser so the speedup seems to be well over 5% (CPython 3.8).
    src, pos = state.src, state.pos
    try:
        while src[pos] in chars:
            pos += 1
    except IndexError:
        pass
    state.pos = pos


def skip_until(
    state: ParseState, expect_char: str, *, error_on: Iterable[str], error_on_eof: bool
) -> None:
    # Use local variables for performance. This is a hot loop so the entire
    # parser seems to be a few percent faster as result (CPython 3.8).
    src, pos = state.src, state.pos
    while True:
        try:
            char = src[pos]
        except IndexError:
            if error_on_eof:
                state.pos = pos
                raise TOMLDecodeError(
                    suffix_coord(state, f'Expected "{expect_char!r}"')
                )
            break
        if char == expect_char:
            break
        if char in error_on:
            state.pos = pos
            raise TOMLDecodeError(
                suffix_coord(state, f'Found invalid character "{char!r}"')
            )
        pos += 1
    state.pos = pos


def skip_comment(state: ParseState) -> None:
    if state.try_char() == "#":
        comment_rule(state)


def skip_comments_and_array_ws(state: ParseState) -> None:
    while True:
        pos_before_skip = state.pos
        skip_chars(state, TOML_WS_AND_NEWLINE)
        skip_comment(state)
        if state.pos == pos_before_skip:
            break


def comment_rule(state: ParseState) -> None:
    state.pos += 1
    skip_until(state, "\n", error_on=ILLEGAL_COMMENT_CHARS, error_on_eof=False)


def create_dict_rule(state: ParseState) -> None:
    state.pos += 1
    skip_chars(state, TOML_WS)
    key = parse_key(state)

    if state.out.is_explicitly_created(key) or state.out.is_frozen(key):
        raise TOMLDecodeError(suffix_coord(state, f"Can not declare {key} twice"))
    try:
        state.out.get_or_create_nest(key)
    except KeyError:
        raise TOMLDecodeError(suffix_coord(state, "Can not overwrite a value"))
    state.header_namespace = key

    if state.try_char() != "]":
        raise TOMLDecodeError(
            suffix_coord(state, 'Expected "]" at the end of a table declaration')
        )
    state.pos += 1


def create_list_rule(state: ParseState) -> None:
    state.pos += 2
    skip_chars(state, TOML_WS)
    key = parse_key(state)

    if state.out.is_frozen(key):
        raise TOMLDecodeError(
            suffix_coord(state, f"Can not mutate immutable namespace {key}")
        )
    # Free the namespace again now that it points to another empty list item
    state.out.reset(key)
    try:
        state.out.append_nest_to_list(key)
    except KeyError:
        raise TOMLDecodeError(suffix_coord(state, "Can not overwrite a value"))
    state.header_namespace = key

    end_marker = state.src[state.pos : state.pos + 2]
    if end_marker != "]]":
        raise TOMLDecodeError(
            suffix_coord(
                state,
                f'Found "{end_marker!r}" at the end of an array declaration.'
                + ' Expected "]]"',
            )
        )
    state.pos += 2


def key_value_rule(state: ParseState) -> None:
    key, value = parse_key_value_pair(state)
    key_parent, key_stem = key[:-1], key[-1]
    abs_key_parent = state.header_namespace + key_parent
    abs_key = state.header_namespace + key

    if state.out.is_frozen(abs_key_parent):
        raise TOMLDecodeError(
            suffix_coord(
                state,
                f"Can not mutate immutable namespace {abs_key_parent}",
            )
        )
    # Containers in the relative path can't be opened with the table syntax after this
    state.out.mark_relative_path_explicitly_created(state.header_namespace, key_parent)
    # Set the value in the right place in `state.out`
    try:
        nest = state.out.get_or_create_nest(abs_key_parent)
    except KeyError:
        raise TOMLDecodeError(suffix_coord(state, "Can not overwrite a value"))
    if key_stem in nest:
        raise TOMLDecodeError(suffix_coord(state, f"Can not define {abs_key} twice"))
    # Mark inline table and array namespaces recursively immutable
    if isinstance(value, (dict, list)):
        state.out.mark_frozen(abs_key)
    nest[key_stem] = value


def parse_key_value_pair(state: ParseState) -> Tuple[Tuple[str, ...], Any]:
    key = parse_key(state)
    if state.try_char() != "=":
        raise TOMLDecodeError(
            suffix_coord(state, 'Expected "=" after a key in a key-to-value mapping')
        )
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
    raise TOMLDecodeError(
        suffix_coord(state, "Invalid initial character for a key part")
    )


def parse_basic_str(state: ParseState) -> str:
    state.pos += 1
    result = ""
    while True:
        c = state.try_char()
        if c == '"':
            state.pos += 1
            return result
        if c == "\\":
            result += parse_basic_str_escape_sequence(state, multiline=False)
            continue
        if c in ILLEGAL_BASIC_STR_CHARS:
            raise TOMLDecodeError(
                suffix_coord(state, f'Illegal character "{c!r}" found in a string')
            )
        if not c:
            raise TOMLDecodeError(suffix_coord(state, "Unterminated string"))
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
            raise TOMLDecodeError(suffix_coord(state, "Unclosed array"))
        state.pos += 1

        skip_comments_and_array_ws(state)
        if state.try_char() == "]":
            state.pos += 1
            return array


def parse_inline_table(state: ParseState) -> dict:
    state.pos += 1
    # A normal dict could be used here, but the get_or_create_nest method
    # is convenient. Possible performance increase with normal dict?
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
            raise TOMLDecodeError(
                suffix_coord(state, f'Duplicate inline table key "{key_stem}"')
            )
        nest[key_stem] = value
        skip_chars(state, TOML_WS)
        c = state.try_char()
        if c == "}":
            state.pos += 1
            return nested_dict.dict
        if c != ",":
            raise TOMLDecodeError(suffix_coord(state, "Unclosed inline table"))
        state.pos += 1
        skip_chars(state, TOML_WS)


def parse_basic_str_escape_sequence(state: ParseState, *, multiline: bool) -> str:
    escape_id = state.src[state.pos : state.pos + 2]
    if len(escape_id) != 2:
        raise TOMLDecodeError(suffix_coord(state, "Unterminated string"))
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
                raise TOMLDecodeError(suffix_coord(state, 'Unescaped "\\" in a string'))
            state.pos += 1
        skip_chars(state, TOML_WS_AND_NEWLINE)
        return ""
    if escape_id in BASIC_STR_ESCAPE_REPLACEMENTS:
        return BASIC_STR_ESCAPE_REPLACEMENTS[escape_id]
    if escape_id == "\\u":
        return parse_hex_char(state, 4)
    if escape_id == "\\U":
        return parse_hex_char(state, 8)
    raise TOMLDecodeError(suffix_coord(state, 'Unescaped "\\" in a string'))


def parse_hex_char(state: ParseState, hex_len: int) -> str:
    hex_str = state.src[state.pos : state.pos + hex_len]
    if len(hex_str) != hex_len or any(c not in string.hexdigits for c in hex_str):
        raise TOMLDecodeError(suffix_coord(state, "Invalid hex value"))
    state.pos += hex_len
    hex_int = int(hex_str, 16)
    try:
        char = chr(hex_int)
    except (ValueError, OverflowError):
        raise TOMLDecodeError(
            suffix_coord(state, "Hex value too large to convert into a character")
        )
    return char


def parse_literal_str(state: ParseState) -> str:
    state.pos += 1  # Skip starting apostrophe
    start_pos = state.pos
    skip_until(state, "'", error_on=ILLEGAL_LITERAL_STR_CHARS, error_on_eof=True)
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
                suffix_coord(
                    state,
                    f'Illegal character "{c!r}" found in a multiline literal string',
                )
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
            state.pos += 1
            if state.try_char() != '"':
                result += '"'
                continue
            state.pos += 1
            if state.try_char() != '"':
                result += '""'
                continue
            state.pos += 1
            if state.try_char() != '"':
                return result
            state.pos += 1
            if state.try_char() != '"':
                return result + '"'
            state.pos += 1
            return result + '""'
        if c in ILLEGAL_MULTILINE_BASIC_STR_CHARS:
            raise TOMLDecodeError(
                suffix_coord(
                    state, f'Illegal character "{c!r}" found in a multiline string'
                )
            )

        if c == "\\":
            result += parse_basic_str_escape_sequence(state, multiline=True)
        else:
            result += c
            state.pos += 1


def parse_regex(state: ParseState, regex: re.Pattern) -> str:
    match = regex.match(state.src, state.pos)
    if not match:
        raise TOMLDecodeError(suffix_coord(state, "Unexpected sequence"))
    match_str = match.group()
    state.pos = match.end()
    return match_str


def parse_datetime(
    state: ParseState, match: re.Match
) -> Union[datetime.datetime, datetime.date]:
    match_str = match.group()
    state.pos = match.end()
    groups: Any = match.groups()
    year, month, day = int(groups[0]), int(groups[1]), int(groups[2])
    hour_str = groups[3]
    if hour_str is None:
        # Returning local date
        return datetime.date(year, month, day)
    hour, minute, sec = int(hour_str), int(groups[4]), int(groups[5])
    micros_str, offset_hour_str = groups[6], groups[7]
    micros = int(micros_str[1:].ljust(6, "0")[:6]) if micros_str else 0
    if offset_hour_str is not None:
        offset_dir = 1 if "+" in match_str else -1
        tz: Optional[datetime.tzinfo] = datetime.timezone(
            datetime.timedelta(
                hours=offset_dir * int(offset_hour_str),
                minutes=offset_dir * int(groups[8]),
            )
        )
    elif "Z" in match_str:
        tz = datetime.timezone.utc
    else:  # local date-time
        tz = None
    return datetime.datetime(year, month, day, hour, minute, sec, micros, tzinfo=tz)


def parse_localtime(state: ParseState, match: re.Match) -> datetime.time:
    state.pos = match.end()
    groups = match.groups()
    hour, minute, sec = int(groups[0]), int(groups[1]), int(groups[2])
    micros_str = groups[3]
    micros = int(micros_str[1:].ljust(6, "0")[:6]) if micros_str else 0
    return datetime.time(hour, minute, sec, micros)


def parse_dec_or_float(state: ParseState, match: re.Match) -> Any:
    match_str = match.group()
    state.pos = match.end()
    if "." in match_str or "e" in match_str or "E" in match_str:
        return state.parse_float(match_str)
    return int(match_str)


def parse_value(state: ParseState) -> Any:  # noqa: C901
    char = state.try_char()

    # Basic strings
    if char == '"':
        if state.src[state.pos + 1 : state.pos + 3] == '""':
            return parse_multiline_basic_str(state)
        return parse_basic_str(state)

    # Literal strings
    if char == "'":
        if state.src[state.pos + 1 : state.pos + 3] == "''":
            return parse_multiline_literal_str(state)
        return parse_literal_str(state)

    # Booleans
    if char == "t":
        if state.src[state.pos + 1 : state.pos + 4] == "rue":
            state.pos += 4
            return True
    if char == "f":
        if state.src[state.pos + 1 : state.pos + 5] == "alse":
            state.pos += 5
            return False

    # Dates and times
    date_match = _re.DATETIME.match(state.src, state.pos)
    if date_match:
        return parse_datetime(state, date_match)
    localtime_match = _re.LOCAL_TIME.match(state.src, state.pos)
    if localtime_match:
        return parse_localtime(state, localtime_match)

    # Non-decimal integers
    if char == "0":
        second_char = state.src[state.pos + 1 : state.pos + 2]
        if second_char == "x":
            state.pos += 2
            hex_str = parse_regex(state, _re.HEX)
            return int(hex_str, 16)
        if second_char == "o":
            state.pos += 2
            oct_str = parse_regex(state, _re.OCT)
            return int(oct_str, 8)
        if second_char == "b":
            state.pos += 2
            bin_str = parse_regex(state, _re.BIN)
            return int(bin_str, 2)

    # Decimal integers and "normal" floats.
    # The regex will greedily match any type starting with a decimal
    # char, so needs to be located after handling of non-decimal ints,
    # and dates and times.
    dec_match = _re.DEC_OR_FLOAT.match(state.src, state.pos)
    if dec_match:
        return parse_dec_or_float(state, dec_match)

    # Arrays
    if char == "[":
        return parse_array(state)

    # Inline tables
    if char == "{":
        return parse_inline_table(state)

    # Special floats
    first_three = state.src[state.pos : state.pos + 3]
    if first_three in {"inf", "nan"}:
        state.pos += 3
        return state.parse_float(first_three)
    first_four = state.src[state.pos : state.pos + 4]
    if first_four in {"-inf", "+inf", "-nan", "+nan"}:
        state.pos += 4
        return state.parse_float(first_four)

    raise TOMLDecodeError(suffix_coord(state, "Invalid value"))


def suffix_coord(state: ParseState, msg: str) -> str:
    """Suffix an error message with coordinates in source."""

    def coord_repr(state: ParseState) -> str:
        if not state.try_char():
            return "end of document"
        line = state.src.count("\n", 0, state.pos) + 1
        if line == 1:
            column = state.pos + 1
        else:
            column = state.pos - state.src.rindex("\n", 0, state.pos)
        return f"line {line}, column {column}"

    return f"{msg} (at {coord_repr(state)})"
