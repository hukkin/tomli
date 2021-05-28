from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
import timeit

import pytomlpp
import qtoml
import rtoml
import toml
import tomlkit

import tomli


def benchmark(
    name: str, run_count: int, func: Callable, compare_to: float | None = None
) -> float:
    print(f"{name:>10}: Running...", end="", flush=True)
    time_taken = timeit.timeit(func, number=run_count)
    res = str(time_taken).split(".")
    print("\b" * 10, end="")
    print(f"{res[0]:>4}.{res[1][:3]} s", end="")
    if compare_to is not None:
        delta = time_taken / compare_to
        relation = "slower"
        if delta < 1.0:
            delta = 1.0 / delta
            relation = "faster"
        delta = int(delta * 10.0) / 10.0
        print(f" ({delta}x {relation})", end="")
    print()
    return time_taken


def run(run_count: int) -> None:
    data_path = Path(__file__).parent / "data.toml"
    test_data = data_path.read_text(encoding="utf-8")
    print(f"Parsing data.toml {run_count} times:")
    baseline = benchmark("pytomlpp", run_count, lambda: pytomlpp.loads(test_data))
    benchmark("rtoml", run_count, lambda: rtoml.loads(test_data), compare_to=baseline)
    benchmark("tomli", run_count, lambda: tomli.loads(test_data), compare_to=baseline)
    benchmark("toml", run_count, lambda: toml.loads(test_data), compare_to=baseline)
    benchmark("qtoml", run_count, lambda: qtoml.loads(test_data), compare_to=baseline)
    benchmark(
        "tomlkit", run_count, lambda: tomlkit.parse(test_data), compare_to=baseline
    )


if __name__ == "__main__":
    run(5000)
