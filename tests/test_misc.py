# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2021 Taneli Hukkinen
# Licensed to PSF under a Contributor Agreement.

import copy
import datetime
from decimal import Decimal as D
import importlib
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest

from . import tomllib


class TestMiscellaneous(unittest.TestCase):
    def test_load(self):
        content = "one=1 \n two='two' \n arr=[]"
        expected = {"one": 1, "two": "two", "arr": []}
        with tempfile.TemporaryDirectory() as tmp_dir_path:
            file_path = Path(tmp_dir_path) / "test.toml"
            file_path.write_text(content)

            with open(file_path, "rb") as bin_f:
                actual = tomllib.load(bin_f)
        self.assertEqual(actual, expected)

    def test_incorrect_load(self):
        content = "one=1"
        with tempfile.TemporaryDirectory() as tmp_dir_path:
            file_path = Path(tmp_dir_path) / "test.toml"
            file_path.write_text(content)

            with open(file_path, "r") as txt_f:
                with self.assertRaises(TypeError) as exc_info:
                    tomllib.load(txt_f)  # type: ignore[arg-type]
            # Mypyc extension leads to different message than pure Python
            self.assertIn(
                str(exc_info.exception),
                (
                    "File must be opened in binary mode, e.g. use `open('foo.toml', 'rb')`",  # noqa: E501
                    "bytes object expected; got str",
                ),
            )

    def test_parse_float(self):
        doc = """
              val=0.1
              biggest1=inf
              biggest2=+inf
              smallest=-inf
              notnum1=nan
              notnum2=-nan
              notnum3=+nan
              """
        obj = tomllib.loads(doc, parse_float=D)
        expected = {
            "val": D("0.1"),
            "biggest1": D("inf"),
            "biggest2": D("inf"),
            "smallest": D("-inf"),
            "notnum1": D("nan"),
            "notnum2": D("-nan"),
            "notnum3": D("nan"),
        }
        for k, expected_val in expected.items():
            actual_val = obj[k]
            self.assertIsInstance(actual_val, D)
            if actual_val.is_nan():
                self.assertTrue(expected_val.is_nan())
            else:
                self.assertEqual(actual_val, expected_val)

    def test_deepcopy(self):
        doc = """
              [bliibaa.diibaa]
              offsettime=[1979-05-27T00:32:00.999999-07:00]
              """
        obj = tomllib.loads(doc)
        obj_copy = copy.deepcopy(obj)
        self.assertEqual(obj_copy, obj)
        expected_obj = {
            "bliibaa": {
                "diibaa": {
                    "offsettime": [
                        datetime.datetime(
                            1979,
                            5,
                            27,
                            0,
                            32,
                            0,
                            999999,
                            tzinfo=datetime.timezone(datetime.timedelta(hours=-7)),
                        )
                    ]
                }
            }
        }
        self.assertEqual(obj_copy, expected_obj)

    def test_inline_array_recursion_limit(self):
        nest_count = 401
        recursive_array_toml = "arr = " + nest_count * "[" + nest_count * "]"
        tomllib.loads(recursive_array_toml)

        nest_count = 402
        recursive_array_toml = "arr = " + nest_count * "[" + nest_count * "]"
        with self.assertRaisesRegex(
            RecursionError,
            r"maximum recursion depth exceeded"
            r"|"
            r"TOML inline arrays/tables are nested more than the allowed [0-9]+ levels",
        ):
            tomllib.loads(recursive_array_toml)

    def test_inline_table_recursion_limit(self):
        nest_count = 310
        recursive_table_toml = nest_count * "key = {" + nest_count * "}"
        tomllib.loads(recursive_table_toml)

        nest_count = 402
        recursive_table_toml = nest_count * "key = {" + nest_count * "}"
        with self.assertRaisesRegex(
            RecursionError,
            r"maximum recursion depth exceeded"
            r"|"
            r"TOML inline arrays/tables are nested more than the allowed [0-9]+ levels",
        ):
            tomllib.loads(recursive_table_toml)

    def test_key_recursion_limit(self):
        nest_count = 310
        nested_key_toml = "a." * nest_count + "a = 1"
        tomllib.loads(nested_key_toml)

        nest_count = sys.getrecursionlimit() - 2
        nested_key_toml = "a." * nest_count + "a = 1"
        tomllib.loads(nested_key_toml)

        nest_count = sys.getrecursionlimit() + 2
        nested_key_toml = "a." * nest_count + "a = 1"
        with self.assertRaisesRegex(
            RecursionError,
            r"TOML key has more than the allowed [0-9]+ parts",
        ):
            tomllib.loads(nested_key_toml)

    def test_many_keys_under_deep_table_header(self):
        # A table section with a deep header may contain any number of keys
        # (regression test for gh-152930).
        depth = tomllib._parser.MAX_KEY_PARTS - 2
        num_keys = 1000
        header = "[" + ".".join(f"h{i}" for i in range(depth)) + "]\n"
        body = "".join(f"k{i} = {i}\n" for i in range(num_keys))

        actual = tomllib.loads(header + body)

        for i in range(depth):
            actual = actual[f"h{i}"]
        self.assertEqual(len(actual), num_keys)
        for i in (0, num_keys // 2, num_keys - 1):
            with self.subTest(msg=i):
                self.assertEqual(actual[f"k{i}"], i)

    def test_deep_table_header_not_rewalked_per_key(self):
        # A key/value pair in a table section must be parsed in time
        # independent of the length of the section's header. The same
        # key/value body is parsed under a shallow and a deep header, and the
        # two documents are measured alternately, keeping the fastest of
        # several runs, so that the measured ratio does not depend on how
        # fast or how loaded the machine is (gh-152930).
        num_keys = 5000
        body = "".join(f"k{i} = 1\n" for i in range(num_keys))
        shallow_depth = 1
        deep_depth = tomllib._parser.MAX_KEY_PARTS - 2
        docs = {}
        for depth in (shallow_depth, deep_depth):
            docs[depth] = "[" + ".".join(f"h{i}" for i in range(depth)) + "]\n" + body

        def measure(depth: int) -> float:
            start = time.perf_counter()
            tomllib.loads(docs[depth])
            return time.perf_counter() - start

        for depth in docs:
            measure(depth)  # Warm up

        best: dict[int, float] = {}
        for _ in range(5):
            for depth in docs:
                elapsed = measure(depth)
                if elapsed < best.get(depth, float("inf")):
                    best[depth] = elapsed

        shallow, deep = best[shallow_depth], best[deep_depth]
        self.assertLess(
            deep / shallow,
            5,
            f"deep header {deep:.4f}s, shallow header {shallow:.4f}s",
        )

    def test_types_import(self):
        """Test that `_types` module runs.

        The module is for type annotations only, so it is otherwise
        never imported by tests.
        """
        importlib.import_module(f"{tomllib.__name__}._types")

    @unittest.skipUnless(
        sys.version_info >= (3, 15) and tomllib._parser.__file__.endswith(".py"),
        "need pure Python 3.15+",
    )
    def test_lazy_import(self):
        # Test the TOML file can be parsed without importing regular
        # expressions (tomli._re)
        code = textwrap.dedent("""
            import sys, tomli, textwrap
            document = textwrap.dedent('''
                [metadata]
                key = "text"
                array = ["array", "of", "text"]
                booleans = [true, false]
            ''')
            tomli.loads(document)
            print("lazy import?", 'tomli._re' not in sys.modules)
        """)
        cmd = [sys.executable, "-c", code]
        proc = subprocess.run(cmd, check=True, capture_output=True)
        self.assertIn(b"lazy import? True", proc.stdout.rstrip())
