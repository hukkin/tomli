import pytest

import tomli


def test_line_and_col():
    with pytest.raises(tomli.TOMLDecodeError) as exc_info:
        tomli.loads("val=.")
    assert str(exc_info.value) == "Invalid value (at line 1, column 5)"

    with pytest.raises(tomli.TOMLDecodeError) as exc_info:
        tomli.loads(".")
    assert str(exc_info.value) == "Invalid statement (at line 1, column 1)"

    with pytest.raises(tomli.TOMLDecodeError) as exc_info:
        tomli.loads("\n\nval=.")
    assert str(exc_info.value) == "Invalid value (at line 3, column 5)"

    with pytest.raises(tomli.TOMLDecodeError) as exc_info:
        tomli.loads("\n\n.")
    assert str(exc_info.value) == "Invalid statement (at line 3, column 1)"


def test_missing_value():
    with pytest.raises(tomli.TOMLDecodeError) as exc_info:
        tomli.loads("\n\nfwfw=")
    assert str(exc_info.value) == "Invalid value (at end of document)"


def test_invalid_char_quotes():
    with pytest.raises(tomli.TOMLDecodeError) as exc_info:
        tomli.loads("v = '\n'")
    assert " '\\n' " in str(exc_info.value)


def test_module_name():
    assert tomli.TOMLDecodeError().__module__ == "tomli"
