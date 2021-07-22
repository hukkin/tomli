"""Test for profiling.

This test can be useful for profiling, as most of the execution time
will be spent parsing and rendering instead of managing pytest execution
environment. To get and read profiler results:
  - `tox -e profile`
  - `firefox .tox/prof/combined.svg`
"""
import os
from pathlib import Path

import tomli


def test_for_profiler():
    path = Path(__file__).parent.parent / "benchmark" / "data.toml"
    benchmark_toml = path.read_bytes().decode()
    # increase the count here to reduce the impact of
    # setting up pytest execution environment. Let's keep
    # the count low by default because this is part of the
    # standard test suite.
    iterations = int(os.environ.get("PROFILER_ITERATIONS", 1))
    for _ in range(iterations):
        tomli.loads(benchmark_toml)
