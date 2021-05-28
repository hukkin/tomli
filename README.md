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
benchmark-pypi installed: attrs==19.3.0,click==7.1.2,pytomlpp==1.0.2,qtoml==0.3.0,rtoml==0.6.1,toml==0.10.2,tomli==0.2.0,tomlkit==0.7.2
benchmark-pypi run-test-pre: PYTHONHASHSEED='3494638500'
benchmark-pypi run-test: commands[0] | python benchmark/run.py
Parsing data.toml 5000 times:
  pytomlpp:    1.126 s
     rtoml:    1.178 s (1.0x slower)
     tomli:    8.913 s (7.9x slower)
      toml:    9.456 s (8.3x slower)
     qtoml:   15.925 s (14.1x slower)
   tomlkit:   71.509 s (63.5x slower)
```

Tomli performed the best out of all pure Python TOML parsers,
losing only to pytomlpp (wraps C++) and rtoml (wraps Rust).

## FAQ

### Why this parser?

- it's lil'
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
