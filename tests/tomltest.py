#!/usr/bin/env python
#
# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2021 Taneli Hukkinen
# Licensed to PSF under a Contributor Agreement.

"""Utilities for https://github.com/toml-lang/toml-test."""

import datetime
from typing import Any


def convert(obj):  # noqa: C901
    if isinstance(obj, str):
        return {"type": "string", "value": obj}
    elif isinstance(obj, bool):
        return {"type": "bool", "value": str(obj).lower()}
    elif isinstance(obj, int):
        return {"type": "integer", "value": str(obj)}
    elif isinstance(obj, float):
        return {"type": "float", "value": str(obj)}
    elif isinstance(obj, datetime.datetime):
        val = obj.isoformat()
        if obj.tzinfo:
            return {"type": "datetime", "value": val}
        return {"type": "datetime-local", "value": val}
    elif isinstance(obj, datetime.time):
        return {"type": "time-local", "value": str(obj)}
    elif isinstance(obj, datetime.date):
        return {"type": "date-local", "value": str(obj)}
    elif isinstance(obj, list):
        return [convert(i) for i in obj]
    elif isinstance(obj, dict):
        return {k: convert(v) for k, v in obj.items()}
    raise Exception("unsupported type")


def normalize(obj: Any) -> Any:
    """Normalize test objects; all values are strings, so make sure they're
    compared consistently."""
    if isinstance(obj, list):
        return [normalize(item) for item in obj]
    elif isinstance(obj, dict) and "type" not in obj and "value" not in obj:
        return {k: normalize(v) for k, v in obj.items()}
    elif isinstance(obj, dict):
        if False:
            pass
        elif obj["type"] == "float":
            obj["value"] = _normalize_float_str(obj["value"])
        elif obj["type"] in ["datetime", "datetime-local"]:
            obj["value"] = _normalize_datetime_str(obj["value"])
        elif obj["type"] == "time-local":
            obj["value"] = _normalize_localtime_str(obj["value"])
        return obj
    raise AssertionError("fixtures should be dicts/lists only")


def _normalize_datetime_str(dt_str: str) -> str:
    if dt_str[-1].lower() == "z":
        dt_str = dt_str[:-1] + "+00:00"

    date = dt_str[:10]
    rest = dt_str[11:]

    if "+" in rest:
        sign = "+"
    elif "-" in rest:
        sign = "-"
    else:
        sign = ""

    if sign:
        time, _, offset = rest.partition(sign)
    else:
        time = rest
        offset = ""

    time = time.rstrip("0") if "." in time else time
    return date + "T" + time + sign + offset


def _normalize_localtime_str(lt_str: str) -> str:
    return lt_str.rstrip("0") if "." in lt_str else lt_str


def _normalize_float_str(float_str: str) -> str:
    as_float = float(float_str)

    # Normalize "-0.0" and "+0.0"
    if as_float == 0:
        return "0"

    return str(as_float)


if __name__ == "__main__":
    import json
    import sys

    import tomli

    t = tomli.loads(sys.stdin.read())
    print(json.dumps(convert(t)))
