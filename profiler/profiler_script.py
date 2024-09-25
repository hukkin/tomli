"""A script for profiling.

To generate and read results:
  - `tox -e profile`
  - `firefox .tox/prof/output.svg`
"""

from pathlib import Path

import tomli

benchmark_toml = (
    (Path(__file__).parent.parent / "benchmark" / "data.toml").read_bytes().decode()
)

# Run this a few times to emphasize over imports and other overhead above.
for _ in range(1000):
    tomli.loads(benchmark_toml)
