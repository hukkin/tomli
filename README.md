[![Build Status](https://github.com/hukkinj1/tomli/workflows/Tests/badge.svg?branch=master)](https://github.com/hukkinj1/tomli/actions?query=workflow%3ATests+branch%3Amaster+event%3Apush)
[![codecov.io](https://codecov.io/gh/hukkinj1/tomli/branch/master/graph/badge.svg)](https://codecov.io/gh/hukkinj1/tomli)
[![PyPI version](https://img.shields.io/pypi/v/tomli)](https://pypi.org/project/tomli)

# Tomli

> A lil' TOML parser

**Table of Contents**  *generated with [mdformat-toc](https://github.com/hukkinj1/mdformat-toc)*

<!-- mdformat-toc start --slug=github --maxlevel=6 --minlevel=2 -->

- [Intro](#intro)
- [Installation](#installation)
- [Usage](#usage)
  - [Parse a TOML string](#parse-a-toml-string)
  - [Parse a TOML file](#parse-a-toml-file)
  - [Handle invalid TOML](#handle-invalid-toml)
  - [Construct `decimal.Decimal`s from TOML floats](#construct-decimaldecimals-from-toml-floats)
- [FAQ](#faq)
  - [Why this parser?](#why-this-parser)
  - [Is comment preserving round-trip parsing supported?](#is-comment-preserving-round-trip-parsing-supported)
  - [Is there a `dumps`, `write` or `encode` function?](#is-there-a-dumps-write-or-encode-function)
  - [How do TOML types map into Python types?](#how-do-toml-types-map-into-python-types)
- [Performance](#performance)

<!-- mdformat-toc end -->

## Intro<a name="intro"></a>

Tomli is a Python library for parsing [TOML](https://toml.io).
Tomli is fully compatible with [TOML v1.0.0](https://toml.io/en/v1.0.0).

## Installation<a name="installation"></a>

```bash
pip install tomli
```

## Usage<a name="usage"></a>

### Parse a TOML string<a name="parse-a-toml-string"></a>

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

### Parse a TOML file<a name="parse-a-toml-file"></a>

```python
import tomli

with open("path_to_file/conf.toml", encoding="utf-8") as f:
    toml_dict = tomli.load(f)
```

### Handle invalid TOML<a name="handle-invalid-toml"></a>

```python
import tomli

try:
    toml_dict = tomli.loads("]] this is invalid TOML [[")
except tomli.TOMLDecodeError:
    print("Yep, definitely not valid.")
```

### Construct `decimal.Decimal`s from TOML floats<a name="construct-decimaldecimals-from-toml-floats"></a>

```python
from decimal import Decimal
import tomli

toml_dict = tomli.loads("precision-matters = 0.982492", parse_float=Decimal)
assert isinstance(toml_dict["precision-matters"], Decimal)
```

Note that you may replace `decimal.Decimal` with any callable that converts a TOML float from string to any Python type (except `list` or `dict`).
The `decimal.Decimal` type is, however, the most typical replacement when float inaccuracies can not be tolerated.

## FAQ<a name="faq"></a>

### Why this parser?<a name="why-this-parser"></a>

- it's lil'
- pure Python with zero dependencies
- the fastest pure Python parser [\*](#performance):
  10x as fast as [tomlkit](https://pypi.org/project/tomlkit/),
  1.4x as fast as [toml](https://pypi.org/project/toml/)
- outputs [basic data types](#how-do-toml-types-map-into-python-types) only
- 100% spec compliant: passes all tests in
  [a test set](https://github.com/toml-lang/compliance/pull/8)
  soon to be merged to the official
  [compliance tests for TOML](https://github.com/toml-lang/compliance)
  repository
- thoroughly tested: 100% branch coverage

### Is comment preserving round-trip parsing supported?<a name="is-comment-preserving-round-trip-parsing-supported"></a>

No.

The `tomli.loads` function returns a plain `dict` that is populated with builtin types and types from the standard library only.
Preserving comments requires a custom type to be returned so will not be supported,
at least not by the `tomli.loads` function.

### Is there a `dumps`, `write` or `encode` function?<a name="is-there-a-dumps-write-or-encode-function"></a>

Not yet, and it's possible there never will be.

This library is deliberately minimal, and most TOML use cases are read-only.
Also, most use cases where writes are relevant could also benefit from comment and whitespace preserving reads,
which this library does not currently support.

### How do TOML types map into Python types?<a name="how-do-toml-types-map-into-python-types"></a>

| TOML type        | Python type         |
| ---------------- | ------------------- |
| Document Root    | `dict`              |
| String           | `str`               |
| Integer          | `int`               |
| Float            | `float`             |
| Boolean          | `bool`              |
| Offset Date-Time | `datetime.datetime` |
| Local Date-Time  | `datetime.datetime` |
| Local Date       | `datetime.date`     |
| Local Time       | `datetime.time`     |
| Array            | `list`              |
| Inline Table     | `dict`              |

## Performance<a name="performance"></a>

The `benchmark/` folder in this repository contains a performance benchmark for comparing the various Python TOML parsers.
The benchmark can be run with `tox -e benchmark-pypi`.
On June 1 2021 running the benchmark output the following on my notebook computer.

```console
foo@bar:~/dev/tomli$ tox -e benchmark-pypi
benchmark-pypi installed: attrs==19.3.0,click==7.1.2,pytomlpp==1.0.2,qtoml==0.3.0,rtoml==0.6.1,toml==0.10.2,tomli==0.2.6,tomlkit==0.7.2
benchmark-pypi run-test-pre: PYTHONHASHSEED='3747534643'
benchmark-pypi run-test: commands[0] | python --version
Python 3.8.0
benchmark-pypi run-test: commands[1] | python benchmark/run.py
Parsing data.toml 5000 times:
------------------------------------------------------
    parser |  exec time | performance (more is better)
-----------+------------+-----------------------------
  pytomlpp |     1.14 s | baseline (100%)
     rtoml |     1.16 s | 98.05%
     tomli |     6.72 s | 16.93%
      toml |     9.32 s | 12.19%
     qtoml |     15.3 s | 7.41%
   tomlkit |     67.2 s | 1.69%
```

The parsers are ordered from fastest to slowest, using the fastest parser (pytomlpp) as baseline.
Tomli performed the best out of all pure Python TOML parsers,
losing only to pytomlpp (wraps C++) and rtoml (wraps Rust).
