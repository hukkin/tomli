import re

# E.g.
# - 00:32:00.999999
# - 00:32:00
_TIME_RE_STR = r"([01][0-9]|2[0-3]):([0-5][0-9]):([0-5][0-9])(\.[0-9]+)?"

RE_HEX = re.compile(r"[0-9A-Fa-f](?:_?[0-9A-Fa-f])*")
RE_BIN = re.compile(r"[01](?:_?[01])*")
RE_OCT = re.compile(r"[0-7](?:_?[0-7])*")
RE_DEC_OR_FLOAT = re.compile(
    r"[+-]?(?:0|[1-9](?:_?[0-9])*)"  # integer
    + r"(?:\.[0-9](?:_?[0-9])*)?"  # optional fractional part
    + r"(?:[eE][+-]?[0-9](?:_?[0-9])*)?"  # optional exponent part
)
RE_LOCAL_TIME = re.compile(_TIME_RE_STR)
RE_DATETIME = re.compile(
    r"([0-9]{4})-(0[1-9]|1[0-2])-(0[1-9]|1[0-9]|2[0-9]|3[01])"  # date, e.g. 1988-10-27
    + r"(?:"
    + r"[T ]"
    + _TIME_RE_STR
    + r"(?:Z|[+-]([01][0-9]|2[0-3]):([0-5][0-9]))?"  # time offset
    + r")?"
)
