import datetime
import json
from pathlib import Path

import dateutil.parser
import pytest

import lil_toml


class MissingFile:
    def __init__(self, path: Path):
        self.path = path


DATA_DIR = Path(__file__).parent / "data" / "toml-lang-compliance"

VALID_FILES = tuple((DATA_DIR / "valid").glob("**/*.toml"))
# VALID_FILES_EXPECTED = tuple(
#     json.loads(p.with_suffix(".json").read_text("utf-8")) for p in VALID_FILES
# )
_expected_files = []
for p in VALID_FILES:
    json_path = p.with_suffix(".json")
    try:
        text = json.loads(json_path.read_text("utf-8"))
    except FileNotFoundError:
        text = MissingFile(json_path)
    _expected_files.append(text)

VALID_FILES_EXPECTED = tuple(_expected_files)
INVALID_FILES = tuple((DATA_DIR / "invalid").glob("**/*.toml"))


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
    if isinstance(expected, MissingFile):
        pytest.xfail(f"Missing a .json file corresponding the .toml: {expected.path}")
    toml_str = valid.read_text(encoding="utf-8")
    actual = lil_toml.loads(toml_str)
    actual = convert_to_burntsushi(actual)
    expected = normalize_burntsushi_floats(expected)
    assert actual == expected


def convert_to_burntsushi(obj):  # noqa: C901
    if isinstance(obj, str):
        return {
            "type": "string",
            "value": json.dumps(obj)[1:-1].replace('\\"', '"').replace("\\\\", "\\"),
        }
        # return {"type": "string", "value": obj}
    elif isinstance(obj, bool):
        return {"type": "boolean", "value": str(obj).lower()}
    elif isinstance(obj, int):
        return {"type": "integer", "value": str(obj)}
    elif isinstance(obj, float):
        return {"type": "float", "value": str(obj)}
    elif isinstance(obj, datetime.datetime):
        val = normalize_datetime_str(obj.isoformat())
        if obj.tzinfo:
            return {"type": "offset datetime", "value": val}
        return {"type": "local datetime", "value": val}
    elif isinstance(obj, datetime.time):
        return {
            "type": "local time",
            "value": str(obj),
        }
    elif isinstance(obj, datetime.date):
        return {
            "type": "local date",
            "value": str(obj),
        }
    elif isinstance(obj, list):
        return {
            "type": "array",
            "value": [convert_to_burntsushi(i) for i in obj],
        }
    elif isinstance(obj, dict):
        return {k: convert_to_burntsushi(v) for k, v in obj.items()}
    raise Exception("unsupported type")


def normalize_burntsushi_floats(d: dict) -> dict:
    normalized = {}
    for k, v in d.items():
        if isinstance(v, list):
            normalized[k] = [normalize_burntsushi_floats(item) for item in v]
        elif isinstance(v, dict):
            if "type" in v and "value" in v:
                if v["type"] == "float":
                    normalized[k] = v.copy()
                    normalized[k]["value"] = str(float(normalized[k]["value"]))
                elif v["type"] in {"offset datetime", "local datetime"}:
                    normalized[k] = v.copy()
                    normalized[k]["value"] = normalize_datetime_str(
                        normalized[k]["value"]
                    )
                else:
                    normalized[k] = v
            else:
                normalized[k] = v
        else:
            pytest.fail("Burntsushi fixtures should be dicts/lists only")
    return normalized


def normalize_datetime_str(dt_str: str) -> str:
    return dateutil.parser.isoparse(dt_str).isoformat()
