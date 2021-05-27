"""Test for profiling.

This test can be useful for profiling, as most of the execution time
will be spent parsing and rendering instead of managing pytest execution
environment. To get profiler results:
  - `pip install pytest-profiling`
  - `pytest -k test_for_profiler --profile-svg`
  - `firefox prof/combined.svg`
"""
from pathlib import Path

import ltoml


def test_for_profiler():
    path = Path(__file__).parent / "data" / "benchmark.toml"
    benchmark_toml = path.read_text("utf-8")
    # increase the count here to reduce the impact of
    # setting up pytest execution environment. Let's keep
    # the count low here because this is part of the
    # standard test suite.
    for _ in range(10):
        ltoml.loads(benchmark_toml)
