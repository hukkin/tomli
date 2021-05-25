import datetime
import json
from pathlib import Path

import pytest

import lil_toml

DATA_DIR = Path(__file__).parent / "data" / "BurntSushi"

VALID_FILES = tuple((DATA_DIR / "valid").glob("*.toml"))
VALID_FILES_EXPECTED = tuple(
    json.loads(p.with_suffix(".json").read_text("utf-8")) for p in VALID_FILES
)
INVALID_FILES = tuple((DATA_DIR / "invalid").glob("*.toml"))


@pytest.mark.parametrize(
    "invalid",
    INVALID_FILES,
    ids=[p.stem for p in INVALID_FILES],
)
def test_invalid(invalid):
    toml_str = invalid.read_text(encoding="utf-8")
    with pytest.raises(Exception):
        lil_toml.loads(toml_str)


@pytest.mark.parametrize(
    "valid,expected",
    zip(VALID_FILES, VALID_FILES_EXPECTED),
    ids=[p.stem for p in VALID_FILES],
)
def test_valid(valid, expected):
    toml_str = valid.read_text(encoding="utf-8")
    actual = lil_toml.loads(toml_str)
    actual = convert_dict_to_burntsushi(actual)
    assert actual == normalize_burntsushi_floats(expected)


def convert_dict_to_burntsushi(d: dict) -> dict:
    converted = {}
    for k, v in d.items():
        if isinstance(v, dict):
            converted[k] = convert_dict_to_burntsushi(v)
        else:
            converted[k] = _convert_primitive_to_burntsushi(v)
    return converted


def _convert_primitive_to_burntsushi(obj):
    if isinstance(obj, str):
        return {"type": "string", "value": obj}
    elif isinstance(obj, bool):
        return {"type": "bool", "value": str(obj).lower()}
    elif isinstance(obj, int):
        return {"type": "integer", "value": str(obj)}
    elif isinstance(obj, float):
        return {"type": "float", "value": str(obj)}
    elif isinstance(obj, datetime.datetime):
        return {"type": "datetime", "value": str(obj)}
    elif isinstance(obj, list):
        return {
            "type": "array",
            "value": [_convert_primitive_to_burntsushi(item) for item in obj],
        }
    else:
        Exception("unsupported type")


def normalize_burntsushi_floats(d: dict) -> dict:
    normalized = {}
    for k, v in d.items():
        if not isinstance(v, dict):
            pytest.fail("Burntsushi fixtures should be dicts only")
        if v.get("type") == "float":
            normalized[k] = v.copy()
            normalized[k]["value"] = str(float(normalized[k]["value"]))
        else:
            normalized[k] = v
    return normalized
