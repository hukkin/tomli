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

```python
import ltoml

toml_str = """
top-level-key = 99

[namespace]
namespace-key = 17
"""
toml_dict = ltoml.loads(toml_str)
assert toml_dict == {"top-level-key": 99, "namespace": {"namespace-key": 17}}
```
