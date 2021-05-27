# Benchmark

## Acknowledgments

This benchmark was shamelessly copied from
[pytomlpp](https://github.com/bobfang1992/pytomlpp/tree/e6b03726f8347c6a6757f520ad1b5fab68ed8534/benchmark)
repository and edited.
Credit goes to the authors of that project.

## Running

### Against the local Tomli state

```bash
tox -e benchmark
```

### Against the latest Tomli PyPI release

```bash
tox -e benchmark-pypi
```
