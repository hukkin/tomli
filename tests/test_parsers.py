from datetime import datetime, time

import tomli


def custom_parse_time(time_str: str) -> time:
    """Strips the fractional part from seconds."""
    time_str = time_str.split(".")[0]
    return time.fromisoformat(time_str)


def custom_parse_datetime(time_str: str) -> datetime:
    """Strips the fractional part from seconds."""
    time_str = time_str.split(".")[0]
    return datetime.fromisoformat(time_str)


def test_datetime_w_nanoseconds():
    """Microsecond precision in datetime objects."""
    doc = """
          [bliibaa]
          datetime=1979-05-27T00:32:00.999999999
          """
    obj = tomli.loads(doc)
    expected_obj = {
        "bliibaa": {
            "datetime": datetime(
                1979,
                5,
                27,
                0,
                32,
                0,
                999999,
            )
        }
    }
    assert obj == expected_obj


def test_custom_parse_time():
    """Test parser that strips the fractional part."""
    doc = """
          [bliibaa]
          time=00:32:00.999999999
          """
    obj = tomli.loads(doc, parse_time=custom_parse_time)
    expected_obj = {"bliibaa": {"time": time.fromisoformat("00:32:00")}}
    assert obj == expected_obj


def test_custom_parse_datetime():
    """Test parser that strips the fractional part."""
    doc = """
          [bliibaa]
          datetime=1979-05-27T00:32:00.999999999
          """
    obj = tomli.loads(doc, parse_datetime=custom_parse_datetime)
    expected_obj = {
        "bliibaa": {"datetime": datetime.fromisoformat("1979-05-27T00:32:00")}
    }
    assert obj == expected_obj
