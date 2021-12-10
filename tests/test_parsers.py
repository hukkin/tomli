from datetime import datetime, time

import numpy as np

import tomli


def custom_parse_time(time_str: str) -> time:
    """Strips the fractional part from seconds."""
    time_str = time_str.split(".")[0]
    return time.fromisoformat(time_str)


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


def test_numpy_w_nanoseconds():
    """Nanosecond precision in datetime64 objects."""
    doc = """
          [bliibaa]
          datetime=1979-05-27T00:32:00.999999999
          """
    obj = tomli.loads(doc, parse_datetime=np.datetime64)
    expected_obj = {
        "bliibaa": {"datetime": np.datetime64("1979-05-27T00:32:00.999999999")}
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
