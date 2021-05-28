[![Build Status](https://github.com/hukkinj1/tomli/workflows/Tests/badge.svg?branch=master)](https://github.com/hukkinj1/tomli/actions?query=workflow%3ATests+branch%3Amaster+event%3Apush)
[![codecov.io](https://codecov.io/gh/hukkinj1/tomli/branch/master/graph/badge.svg)](https://codecov.io/gh/hukkinj1/tomli)
[![PyPI version](https://img.shields.io/pypi/v/tomli)](https://pypi.org/project/tomli)

# Tomli

> A lil' TOML parser

Tomli is a Python library for parsing [TOML](https://toml.io).
Tomli is fully compatible with [TOML v1.0.0](https://toml.io/en/v1.0.0).

## Installation

```bash
pip install tomli
```

## Usage

### Parse a TOML string

```python
import tomli

toml_str = """
gretzky = 99

[kurri]
jari = 17
"""

toml_dict = tomli.loads(toml_str)
assert toml_dict == {"gretzky": 99, "kurri": {"jari": 17}}
```

### Parse a TOML file

```python
import tomli

with open("path_to_file/conf.toml", encoding="utf-8") as f:
    toml_dict = tomli.load(f)
```

### Handle invalid TOML

```python
import tomli

try:
    toml_dict = tomli.loads("]] this is invalid TOML [[")
except tomli.TOMLDecodeError:
    print("Yep, definitely not valid.")
```

### Construct `decimal.Decimal`s from TOML floats

```python
from decimal import Decimal
import tomli

toml_dict = tomli.loads("precision-matters = 0.982492", parse_float=Decimal)
assert isinstance(toml_dict["precision-matters"], Decimal)
```

## FAQ

### Why this parser?

- it's lil'
- pure Python with zero dependencies
- fairly fast (but pure Python so can't do any miracles there)
- 100% spec compliance: passes all tests in
  [a test set](https://github.com/toml-lang/compliance/pull/8)
  soon to be merged to the official
  [compliance tests for TOML](https://github.com/toml-lang/compliance)
  repository
- 100% test coverage

### Is comment preserving round-trip parsing supported?

No. The `tomli.loads` function returns a plain `dict` that is populated with builtin types and types from the standard library only
(`list`, `int`, `str`, `datetime.datetime` etc.).
Preserving comments requires a custom type to be returned so will not be supported,
at least not by the `tomli.loads` function.

### Is there a `dumps`, `write` or `encode` function?

Not yet, and it's possible there never will be.

## Performance

The `benchmark/` folder in this repository contains a performance benchmark for comparing the various Python TOML parsers.
The benchmark can be run with `tox -e benchmark-pypi`.
On May 28 2021 running the benchmark output the following on my notebook computer.

```console
foo@bar:~/dev/tomli$ tox -e benchmark-pypi
benchmark-pypi installed: attrs==19.3.0,click==7.1.2,pytomlpp==1.0.2,qtoml==0.3.0,rtoml==0.6.1,toml==0.10.2,tomli==0.2.0,tomlkit==0.7.2
benchmark-pypi run-test-pre: PYTHONHASHSEED='305387179'
benchmark-pypi run-test: commands[0] | python benchmark/run.py
Parsing data.toml 5000 times:
------------------------------------------------------
    parser |  exec time | performance (more is better)
-----------+------------+-----------------------------
  pytomlpp |     1.16 s | baseline
     rtoml |     1.17 s | 1x baseline
     tomli |     8.94 s | 0.13x baseline
      toml |     9.33 s | 0.12x baseline
     qtoml |     15.7 s | 0.074x baseline
   tomlkit |       70 s | 0.017x baseline
```

The parsers are ordered from fastest to slowest, using the fastest parser (pytomlpp) as baseline.
Tomli performed the best out of all pure Python TOML parsers,
losing only to pytomlpp (wraps C++) and rtoml (wraps Rust).
