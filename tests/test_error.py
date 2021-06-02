import pytest

import tomli


def test_line_and_col():
    with pytest.raises(tomli.TOMLDecodeError) as exc_info:
        tomli.loads("val=.")
    assert str(exc_info.value) == "Invalid value (at line 1, column 5)"

    with pytest.raises(tomli.TOMLDecodeError) as exc_info:
        tomli.loads("\n\nval=.")
    assert str(exc_info.value) == "Invalid value (at line 3, column 5)"


def test_missing_value():
    with pytest.raises(tomli.TOMLDecodeError) as exc_info:
        tomli.loads("\n\nfwfw=")
    assert str(exc_info.value) == "Invalid value (at end of document)"
