import copy
import datetime
from decimal import Decimal as D
from pathlib import Path

import tomli


def test_load(tmp_path):
    content = "one=1 \n two='two' \n arr=[]"
    file_path = tmp_path / "test.toml"
    file_path.write_text(content)
    with open(file_path, encoding="utf-8") as f:
        actual = tomli.load(f)
    assert actual == {"one": 1, "two": "two", "arr": []}


def test_parse_float():
    doc = """
          val=0.1
          biggest1=inf
          biggest2=+inf
          smallest=-inf
          notnum1=nan
          notnum2=-nan
          notnum3=+nan
          """
    obj = tomli.loads(doc, parse_float=D)
    expected = {
        "val": D("0.1"),
        "biggest1": D("inf"),
        "biggest2": D("inf"),
        "smallest": D("-inf"),
        "notnum1": D("nan"),
        "notnum2": D("-nan"),
        "notnum3": D("nan"),
    }
    for k, expected_val in expected.items():
        actual_val = obj[k]
        assert isinstance(actual_val, D)
        if actual_val.is_nan():
            assert expected_val.is_nan()
        else:
            assert actual_val == expected_val


def test_deepcopy():
    doc = """
          [bliibaa.diibaa]
          offsettime=[1979-05-27T00:32:00.999999-07:00]
          """
    obj = tomli.loads(doc)
    obj_copy = copy.deepcopy(obj)
    assert obj_copy == obj
    expected_obj = {
        "bliibaa": {
            "diibaa": {
                "offsettime": [
                    datetime.datetime(
                        1979,
                        5,
                        27,
                        0,
                        32,
                        0,
                        999999,
                        tzinfo=datetime.timezone(datetime.timedelta(hours=-7)),
                    )
                ]
            }
        }
    }
    assert obj_copy == expected_obj


def test_own_pyproject():
    pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
    with open(pyproject_path, encoding="utf-8") as f:
        pyproject = tomli.load(f)
    assert pyproject["project"]["version"] == tomli.__version__
