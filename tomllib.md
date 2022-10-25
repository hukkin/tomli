# `tomllib` – Tomli in the standard library

Tomli was added to the Python standard library in Python 3.11.

Relevant links:

- Python Issue Tracker: https://bugs.python.org/issue40059
- Tomli issue tracker: https://github.com/hukkin/tomli/issues/141
- Discussion on PyPA "blessing" a TOML parser and/or including one in the standard library: https://discuss.python.org/t/adopting-recommending-a-toml-parser/4068
- Python Enhancement Proposal: https://peps.python.org/pep-0680
- CPython pull request: https://github.com/python/cpython/pull/31498

## Converting Tomli to tomllib

### Sync status

`tomllib` in CPython commit https://github.com/python/cpython/commit/deaf509e8fc6e0363bd6f26d52ad42f976ec42f2
matches Tomli commit https://github.com/hukkin/tomli/commit/7e563eed5286b5d46b8290a9f56a86d955b23a9a

### Steps to convert

- Move everything in `tomli:src/tomli` to `cpython:Lib/tomllib`. Exclude `py.typed`.

- Remove `__version__ = ...` line from `cpython:Lib/tomllib/__init__.py`

- Move everything in `tomli:tests` to `cpython:Lib/test/test_tomllib`. Exclude the following test data dirs recursively:

  - `tomli:tests/data/invalid/_external/`
  - `tomli:tests/data/valid/_external/`

- Create `cpython:Lib/test/test_tomllib/__main__.py`:

  ```python
  import unittest

  from . import load_tests


  unittest.main()
  ```

- Add the following to `cpython:Lib/test/test_tomllib/__init__.py`:

  ```python
  import os
  from test.support import load_package_tests


  def load_tests(*args):
      return load_package_tests(os.path.dirname(__file__), *args)
  ```

  Also change `import tomli as tomllib` to `import tomllib`.

- In `cpython:Lib/tomllib/_parser.py` replace `__fp` with `fp` and `__s` with `s`. Add the `/` to `load` and `loads` function signatures.
