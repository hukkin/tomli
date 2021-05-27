[![Build Status](https://github.com/hukkinj1/ltoml/workflows/Tests/badge.svg?branch=master)](https://github.com/hukkinj1/ltoml/actions?query=workflow%3ATests+branch%3Amaster+event%3Apush)
[![codecov.io](https://codecov.io/gh/hukkinj1/ltoml/branch/master/graph/badge.svg)](https://codecov.io/gh/hukkinj1/ltoml)
[![PyPI version](https://img.shields.io/pypi/v/ltoml)](https://pypi.org/project/ltoml)

# LTOML

> A lil' TOML parser

LTOML is a Python library for parsing [TOML](https://toml.io).
LTOML is fully compatible with [TOML v1.0.0](https://toml.io/en/v1.0.0).

## Installation

```bash
pip install ltoml
```

## Usage

### Parse a TOML string

```python
import ltoml

toml_str = """
gretzky = 99

[kurri]
jari = 17
"""

toml_dict = ltoml.loads(toml_str)
assert toml_dict == {"gretzky": 99, "kurri": {"jari": 17}}
```

### Handle invalid TOML

```python
import ltoml

try:
    toml_dict = ltoml.loads("]] this is invalid TOML [[")
except ltoml.TOMLDecodeError:
    print("Yep, definitely not valid.")
```

## FAQ

### Why this parser?

Because it's lil'.

### Is comment preserving round-trip parsing supported?

No. The `ltoml.loads` function returns a plain `dict` that is populated with builtin types and types from the standard library only
(`list`, `int`, `str`, `datetime.datetime` etc.).
Preserving comments requires a custom type to be returned so will not be supported,
at least not by the `ltoml.loads` function.

### Is there a `dumps`, `write` or `encode` function?

Not yet, and it's possible there never will be.
