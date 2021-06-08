from datetime import date, datetime, time, timedelta, timezone, tzinfo
import string
from types import MappingProxyType
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    Iterable,
    Optional,
    TextIO,
    Tuple,
    Union,
)

from tomli._re import (
    RE_BIN,
    RE_DATETIME,
    RE_DEC_OR_FLOAT,
    RE_HEX,
    RE_LOCAL_TIME,
    RE_OCT,
)

if TYPE_CHECKING:
    from re import Match, Pattern


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
Key = Tuple[str, ...]


class TOMLDecodeError(ValueError):
    """An error raised if a document is not valid TOML."""


def load(fp: TextIO, *, parse_float: ParseFloat = float) -> Dict[str, Any]:
    """Parse TOML from a file object."""
    s = fp.read()
    return loads(s, parse_float=parse_float)


def loads(s: str, *, parse_float: ParseFloat = float) -> Dict[str, Any]:
    """Parse TOML from a string."""

    # The spec allows converting "\r\n" to "\n", even in string
    # literals. Let's do so to simplify parsing.
    s = s.replace("\r\n", "\n")

    state = State(s, parse_float)

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
        if char == "#":
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


class State:
    def __init__(self, src: str, parse_float: ParseFloat):
        # Immutable read-only
        self.src = src
        self.parse_float = parse_float

        # Mutable read-only
        self.out = NestedDict()
        self.flags = Flags()

        # Read and write
        self.pos = 0
        self.header_namespace: Key = ()

    def try_char(self) -> Optional[str]:
        try:
            return self.src[self.pos]
        except IndexError:
            return None


class Flags:
    """Flags that map to parsed keys/namespaces."""

    # Marks an immutable namespace (inline array or inline table).
    FROZEN = 0
    # Marks a nest that has been explicitly created and can no longer
    # be opened using the "[table]" syntax.
    EXPLICIT_NEST = 1

    def __init__(self) -> None:
        self._flags: Dict[str, dict] = {}

    def unset_all(self, key: Key) -> None:
        cont = self._flags
        for k in key[:-1]:
            if k not in cont:
                return
            cont = cont[k]["nested"]
        cont.pop(key[-1], None)

    def set_for_relative_key(self, head_key: Key, rel_key: Key, flag: int) -> None:
        cont = self._flags
        for k in head_key:
            if k not in cont:
                cont[k] = {"flags": set(), "recursive_flags": set(), "nested": {}}
            cont = cont[k]["nested"]
        for k in rel_key:
            if k in cont:
                cont[k]["flags"].add(flag)
            else:
                cont[k] = {"flags": {flag}, "recursive_flags": set(), "nested": {}}
            cont = cont[k]["nested"]

    def set(self, key: Key, flag: int, *, recursive: bool) -> None:  # noqa: A003
        cont = self._flags
        key_parent, key_stem = key[:-1], key[-1]
        for k in key_parent:
            if k not in cont:
                cont[k] = {"flags": set(), "recursive_flags": set(), "nested": {}}
            cont = cont[k]["nested"]
        if key_stem not in cont:
            cont[key_stem] = {"flags": set(), "recursive_flags": set(), "nested": {}}
        cont[key_stem]["recursive_flags" if recursive else "flags"].add(flag)

    def is_(self, key: Key, flag: int) -> bool:
        if not key:
            return False  # document root has no flags
        cont = self._flags
        for k in key[:-1]:
            if k not in cont:
                return False
            inner_cont = cont[k]
            if flag in inner_cont["recursive_flags"]:
                return True
            cont = inner_cont["nested"]
        key_stem = key[-1]
        if key_stem in cont:
            cont = cont[key_stem]
            return flag in cont["flags"] or flag in cont["recursive_flags"]
        return False


class NestedDict:
    def __init__(self) -> None:
        # The parsed content of the TOML document
        self.dict: Dict[str, Any] = {}

    def get_or_create_nest(
        self,
        key: Key,
        *,
        access_lists: bool = True,
    ) -> dict:
        cont: Any = self.dict
        for k in key:
            if k not in cont:
                cont[k] = {}
            cont = cont[k]
            if access_lists and isinstance(cont, list):
                cont = cont[-1]
            if not isinstance(cont, dict):
                raise KeyError("There is no nest behind this key")
        return cont

    def append_nest_to_list(self, key: Key) -> None:
        cont = self.get_or_create_nest(key[:-1])
        last_key = key[-1]
        if last_key in cont:
            list_ = cont[last_key]
            if not isinstance(list_, list):
                raise KeyError("An object other than list found behind this key")
            list_.append({})
        else:
            cont[last_key] = [{}]


def skip_chars(state: State, chars: Iterable[str]) -> None:
    src, pos = state.src, state.pos
    try:
        while src[pos] in chars:
            pos += 1
    except IndexError:
        pass
    state.pos = pos


def skip_until(
    state: State, expect_char: str, *, error_on: Iterable[str], error_on_eof: bool
) -> None:
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


def skip_comment(state: State) -> None:
    if state.try_char() == "#":
        comment_rule(state)


def skip_comments_and_array_ws(state: State) -> None:
    while True:
        pos_before_skip = state.pos
        skip_chars(state, TOML_WS_AND_NEWLINE)
        skip_comment(state)
        if state.pos == pos_before_skip:
            break


def comment_rule(state: State) -> None:
    state.pos += 1
    skip_until(state, "\n", error_on=ILLEGAL_COMMENT_CHARS, error_on_eof=False)


def create_dict_rule(state: State) -> None:
    state.pos += 1
    skip_chars(state, TOML_WS)
    key = parse_key(state)

    if state.flags.is_(key, Flags.EXPLICIT_NEST) or state.flags.is_(key, Flags.FROZEN):
        raise TOMLDecodeError(suffix_coord(state, f"Can not declare {key} twice"))
    state.flags.set(key, Flags.EXPLICIT_NEST, recursive=False)
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


def create_list_rule(state: State) -> None:
    state.pos += 2
    skip_chars(state, TOML_WS)
    key = parse_key(state)

    if state.flags.is_(key, Flags.FROZEN):
        raise TOMLDecodeError(
            suffix_coord(state, f"Can not mutate immutable namespace {key}")
        )
    # Free the namespace now that it points to another empty list item...
    state.flags.unset_all(key)
    # ...but this key precisely is still prohibited from table declaration
    state.flags.set(key, Flags.EXPLICIT_NEST, recursive=False)
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


def key_value_rule(state: State) -> None:
    key, value = parse_key_value_pair(state)
    key_parent, key_stem = key[:-1], key[-1]
    abs_key_parent = state.header_namespace + key_parent
    abs_key = state.header_namespace + key

    if state.flags.is_(abs_key_parent, Flags.FROZEN):
        raise TOMLDecodeError(
            suffix_coord(
                state,
                f"Can not mutate immutable namespace {abs_key_parent}",
            )
        )
    # Containers in the relative path can't be opened with the table syntax after this
    state.flags.set_for_relative_key(state.header_namespace, key, Flags.EXPLICIT_NEST)
    try:
        nest = state.out.get_or_create_nest(abs_key_parent)
    except KeyError:
        raise TOMLDecodeError(suffix_coord(state, "Can not overwrite a value"))
    if key_stem in nest:
        raise TOMLDecodeError(suffix_coord(state, f"Can not define {abs_key} twice"))
    # Mark inline table and array namespaces recursively immutable
    if isinstance(value, (dict, list)):
        state.flags.set(abs_key, Flags.FROZEN, recursive=True)
    nest[key_stem] = value


def parse_key_value_pair(state: State) -> Tuple[Key, Any]:
    key = parse_key(state)
    if state.try_char() != "=":
        raise TOMLDecodeError(
            suffix_coord(state, 'Expected "=" after a key in a key/value pair')
        )
    state.pos += 1
    skip_chars(state, TOML_WS)
    value = parse_value(state)
    return key, value


def parse_key(state: State) -> Key:
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


def parse_key_part(state: State) -> str:
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


def parse_basic_str(state: State) -> str:
    state.pos += 1
    return parse_string(
        state,
        delim='"',
        delim_len=1,
        error_on=ILLEGAL_BASIC_STR_CHARS,
        parse_escapes=parse_basic_str_escape,
    )


def parse_array(state: State) -> list:
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


def parse_inline_table(state: State) -> dict:  # noqa: C901
    state.pos += 1
    # We use a subset of the functionality NestedDict provides. We use it for
    # the convenient getter, and recursive freeze for inner arrays and tables.
    # Cutting a new lighter NestedDict base class could work here?
    nested_dict = NestedDict()
    flags = Flags()

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
        if flags.is_(key, Flags.FROZEN):
            raise TOMLDecodeError(
                suffix_coord(state, f"Can not mutate immutable namespace {key}")
            )
        try:
            nest = nested_dict.get_or_create_nest(key_parent, access_lists=False)
        except KeyError:
            raise TOMLDecodeError(suffix_coord(state, "Can not overwrite a value"))
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
        if isinstance(value, (dict, list)):
            flags.set(key, Flags.FROZEN, recursive=True)
        state.pos += 1
        skip_chars(state, TOML_WS)


def parse_basic_str_escape(state: State, *, multiline: bool = False) -> str:
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


def parse_basic_str_escape_multiline(state: State) -> str:
    return parse_basic_str_escape(state, multiline=True)


def parse_hex_char(state: State, hex_len: int) -> str:
    hex_str = state.src[state.pos : state.pos + hex_len]
    if len(hex_str) != hex_len or any(c not in string.hexdigits for c in hex_str):
        raise TOMLDecodeError(suffix_coord(state, "Invalid hex value"))
    state.pos += hex_len
    hex_int = int(hex_str, 16)
    if not is_unicode_scalar_value(hex_int):
        raise TOMLDecodeError(
            suffix_coord(state, "Escaped character is not a Unicode scalar value")
        )
    return chr(hex_int)


def parse_literal_str(state: State) -> str:
    state.pos += 1  # Skip starting apostrophe
    start_pos = state.pos
    skip_until(state, "'", error_on=ILLEGAL_LITERAL_STR_CHARS, error_on_eof=True)
    literal_str = state.src[start_pos : state.pos]
    state.pos += 1  # Skip ending apostrophe
    return literal_str


def parse_multiline_str(state: State, *, literal: bool) -> str:
    state.pos += 3
    if state.try_char() == "\n":
        state.pos += 1

    if literal:
        delim = "'"
        illegal_chars = ILLEGAL_MULTILINE_LITERAL_STR_CHARS
        escape_parser = None
    else:
        delim = '"'
        illegal_chars = ILLEGAL_MULTILINE_BASIC_STR_CHARS
        escape_parser = parse_basic_str_escape_multiline
    result = parse_string(
        state,
        delim=delim,
        delim_len=3,
        error_on=illegal_chars,
        parse_escapes=escape_parser,
    )

    # Add at maximum two extra apostrophes/quotes if the end sequence
    # is 4 or 5 chars long instead of just 3.
    if state.try_char() != delim:
        return result
    state.pos += 1
    if state.try_char() != delim:
        return result + delim
    state.pos += 1
    return result + (delim * 2)


def parse_string(
    state: State,
    *,
    delim: str,
    delim_len: int,
    error_on: Iterable[str],
    parse_escapes: Optional[Callable[[State], str]] = None,
) -> str:
    src, pos = state.src, state.pos
    expect_after = delim * (delim_len - 1)
    result = ""
    start_pos = pos
    while True:
        try:
            char = src[pos]
        except IndexError:
            state.pos = pos
            raise TOMLDecodeError(suffix_coord(state, "Unterminated string"))
        if char == delim:
            if src[pos + 1 : pos + delim_len] == expect_after:
                end_pos = pos
                state.pos = pos + delim_len
                return result + src[start_pos:end_pos]
            pos += 1
            continue
        if parse_escapes and char == "\\":
            result += src[start_pos:pos]
            state.pos = pos
            result += parse_escapes(state)
            pos = start_pos = state.pos
            continue
        if char in error_on:
            state.pos = pos
            raise TOMLDecodeError(suffix_coord(state, f'Illegal character "{char!r}"'))
        pos += 1


def parse_regex(state: State, regex: "Pattern") -> str:
    match = regex.match(state.src, state.pos)
    if not match:
        raise TOMLDecodeError(suffix_coord(state, "Unexpected sequence"))
    match_str = match.group()
    state.pos = match.end()
    return match_str


def parse_datetime(state: State, match: "Match") -> Union[datetime, date]:
    match_str = match.group()
    state.pos = match.end()
    groups: Any = match.groups()
    year, month, day = int(groups[0]), int(groups[1]), int(groups[2])
    hour_str = groups[3]
    if hour_str is None:
        # Returning local date
        return date(year, month, day)
    hour, minute, sec = int(hour_str), int(groups[4]), int(groups[5])
    micros_str, offset_hour_str = groups[6], groups[7]
    micros = int(micros_str[1:].ljust(6, "0")[:6]) if micros_str else 0
    if offset_hour_str is not None:
        offset_dir = 1 if "+" in match_str else -1
        tz: Optional[tzinfo] = timezone(
            timedelta(
                hours=offset_dir * int(offset_hour_str),
                minutes=offset_dir * int(groups[8]),
            )
        )
    elif "Z" in match_str:
        tz = timezone.utc
    else:  # local date-time
        tz = None
    return datetime(year, month, day, hour, minute, sec, micros, tzinfo=tz)


def parse_localtime(state: State, match: "Match") -> time:
    state.pos = match.end()
    groups = match.groups()
    hour, minute, sec = int(groups[0]), int(groups[1]), int(groups[2])
    micros_str = groups[3]
    micros = int(micros_str[1:].ljust(6, "0")[:6]) if micros_str else 0
    return time(hour, minute, sec, micros)


def parse_dec_or_float(state: State, match: "Match") -> Any:
    match_str = match.group()
    state.pos = match.end()
    if "." in match_str or "e" in match_str or "E" in match_str:
        return state.parse_float(match_str)
    return int(match_str)


def parse_value(state: State) -> Any:  # noqa: C901
    src, pos = state.src, state.pos
    char = src[pos : pos + 1]

    # Basic strings
    if char == '"':
        if src[pos + 1 : pos + 3] == '""':
            return parse_multiline_str(state, literal=False)
        return parse_basic_str(state)

    # Literal strings
    if char == "'":
        if src[pos + 1 : pos + 3] == "''":
            return parse_multiline_str(state, literal=True)
        return parse_literal_str(state)

    # Booleans
    if char == "t":
        if src[pos + 1 : pos + 4] == "rue":
            state.pos = pos + 4
            return True
    if char == "f":
        if src[pos + 1 : pos + 5] == "alse":
            state.pos = pos + 5
            return False

    # Dates and times
    date_match = RE_DATETIME.match(src, pos)
    if date_match:
        return parse_datetime(state, date_match)
    localtime_match = RE_LOCAL_TIME.match(src, pos)
    if localtime_match:
        return parse_localtime(state, localtime_match)

    # Non-decimal integers
    if char == "0":
        second_char = src[pos + 1 : pos + 2]
        if second_char == "x":
            state.pos = pos + 2
            hex_str = parse_regex(state, RE_HEX)
            return int(hex_str, 16)
        if second_char == "o":
            state.pos = pos + 2
            oct_str = parse_regex(state, RE_OCT)
            return int(oct_str, 8)
        if second_char == "b":
            state.pos = pos + 2
            bin_str = parse_regex(state, RE_BIN)
            return int(bin_str, 2)

    # Decimal integers and "normal" floats.
    # The regex will greedily match any type starting with a decimal
    # char, so needs to be located after handling of non-decimal ints,
    # and dates and times.
    dec_match = RE_DEC_OR_FLOAT.match(src, pos)
    if dec_match:
        return parse_dec_or_float(state, dec_match)

    # Arrays
    if char == "[":
        return parse_array(state)

    # Inline tables
    if char == "{":
        return parse_inline_table(state)

    # Special floats
    first_three = src[pos : pos + 3]
    if first_three in {"inf", "nan"}:
        state.pos = pos + 3
        return state.parse_float(first_three)
    first_four = src[pos : pos + 4]
    if first_four in {"-inf", "+inf", "-nan", "+nan"}:
        state.pos = pos + 4
        return state.parse_float(first_four)

    raise TOMLDecodeError(suffix_coord(state, "Invalid value"))


def suffix_coord(state: State, msg: str) -> str:
    """Suffix an error message with coordinates in source."""

    def coord_repr(state: State) -> str:
        if not state.try_char():
            return "end of document"
        line = state.src.count("\n", 0, state.pos) + 1
        if line == 1:
            column = state.pos + 1
        else:
            column = state.pos - state.src.rindex("\n", 0, state.pos)
        return f"line {line}, column {column}"

    return f"{msg} (at {coord_repr(state)})"


def is_unicode_scalar_value(codepoint: int) -> bool:
    return (0 <= codepoint <= 55295) or (57344 <= codepoint <= 1114111)
