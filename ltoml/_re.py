import re

# E.g.
# - 00:32:00.999999
# - 00:32:00
_TIME_RE_STR = r"([01][0-9]|2[0-3]):([0-5][0-9]):([0-5][0-9])(\.[0-9]+)?"

HEX = re.compile(r"0x[0-9A-Fa-f](?:_?[0-9A-Fa-f]+)*")
BIN = re.compile(r"0b[01](?:_?[01]+)*")
OCT = re.compile(r"0o[0-7](?:_?[0-7]+)*")
DEC_OR_FLOAT = re.compile(
    r"[+-]?(?:0|[1-9](?:_?[0-9])*)"  # integer
    + r"(?:\.[0-9](?:_?[0-9])*)?"  # optional fractional part
    + r"(?:[eE][+-]?[0-9](?:_?[0-9])*)?"  # optional exponent part
)
LOCAL_TIME = re.compile(_TIME_RE_STR)
DATETIME = re.compile(
    r"([0-9]{4})-(0[1-9]|1[0-2])-(0[1-9]|1[0-9]|2[0-9]|3[01])"  # date, e.g. 1988-10-27
    + r"(?:[T ]"
    + _TIME_RE_STR
    + r"(?:Z|[+-]([01][0-9]|2[0-3]):([0-5][0-9]))?"  # time offset
    + r")?"
)
