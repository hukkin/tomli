"""Utilities for tests that are in the "burntsushi" format."""

import datetime
import json
from typing import Any

import dateutil.parser
import pytest


def convert(obj):  # noqa: C901
    if isinstance(obj, str):
        # The test case JSONs seem to have inconsistent escape chars. E.g. tab is
        # escaped with '\\t' (two backspaces), but quotation mark with '\"' (only one
        # backspace. This line does its best to fix such issues.
        normalized_str = (
            json.dumps(obj)[1:-1]
            .replace('\\"', '"')
            .replace("\\\\", "\\")
            .replace("\\u00e9", "é")
        )
        return {
            "type": "string",
            "value": normalized_str,
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
            "value": [convert(i) for i in obj],
        }
    elif isinstance(obj, dict):
        return {k: convert(v) for k, v in obj.items()}
    raise Exception("unsupported type")


def normalize_floats(d: dict) -> dict:
    normalized: Any = {}
    for k, v in d.items():
        if isinstance(v, list):
            normalized[k] = [normalize_floats(item) for item in v]
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