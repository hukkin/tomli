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

### Handle invalid TOML

```python
import tomli

try:
    toml_dict = tomli.loads("]] this is invalid TOML [[")
except tomli.TOMLDecodeError:
    print("Yep, definitely not valid.")
```

## Performance

The `benchmark/` folder in this repository contains a performance benchmark for comparing the various Python TOML parsers.
The benchmark can be run with `tox -e benchmark-pypi`.
On May 28 2021 running the benchmark output the following on my notebook computer.

```console
foo@bar:~/dev/tomli$ tox -e benchmark-pypi
Parsing data.toml 5000 times:
  pytomlpp:    0.961 s
     tomli:    7.073 s (7.3x slower)
      toml:    7.253 s (7.5x slower)
     qtoml:   12.292 s (12.7x slower)
   tomlkit:   56.114 s (58.3x slower)
```

Tomli performed the best out of all pure Python TOML parsers,
losing only to pytomlpp, which is a wrapper for a C++ parser.

## FAQ

### Why this parser?

- it's lil'
- fairly fast (but pure Python so can't do any miracles there)
- 100% spec compliance: passes all tests in [a test set](https://github.com/toml-lang/compliance/pull/8) soon to be merged to the official [compliance tests for TOML](https://github.com/toml-lang/compliance) repository

### Is comment preserving round-trip parsing supported?

No. The `tomli.loads` function returns a plain `dict` that is populated with builtin types and types from the standard library only
(`list`, `int`, `str`, `datetime.datetime` etc.).
Preserving comments requires a custom type to be returned so will not be supported,
at least not by the `tomli.loads` function.

### Is there a `dumps`, `write` or `encode` function?

Not yet, and it's possible there never will be.
