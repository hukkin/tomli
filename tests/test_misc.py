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
        nest_count = 470
        recursive_array_toml = "arr = " + nest_count * "[" + nest_count * "]"
        tomllib.loads(recursive_array_toml)

        nest_count = sys.getrecursionlimit() + 2
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

        nest_count = sys.getrecursionlimit() + 2
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

    def test_types_import(self):
        """Test that `_types` module runs.

        The module is for type annotations only, so it is otherwise
        never imported by tests.
        """
        importlib.import_module(f"{tomllib.__name__}._types")

    def test_try_simple_decimal(self):
        try_simple_decimal = tomllib._parser.try_simple_decimal
        self.assertEqual(try_simple_decimal("123", 0), (3, 123))
        self.assertEqual(try_simple_decimal("123\n", 0), (3, 123))
        self.assertEqual(try_simple_decimal("123 456", 0), (3, 123))
        self.assertEqual(try_simple_decimal("+123\n", 0), (4, 123))
        self.assertEqual(try_simple_decimal("-123\n", 0), (4, -123))
        self.assertEqual(try_simple_decimal("0\n", 0), (1, 0))
        self.assertEqual(try_simple_decimal("+0\n", 0), (2, 0))
        self.assertEqual(try_simple_decimal("-0\n", 0), (2, 0))
        self.assertEqual(try_simple_decimal("[23]\n", 1), (3, 23))
        self.assertEqual(try_simple_decimal("[23, 24]\n", 1), (3, 23))
        self.assertEqual(try_simple_decimal("{x = 42}\n", 5), (7, 42))

        self.assertIsNone(try_simple_decimal("+", 0), None)
        self.assertIsNone(try_simple_decimal("-", 0), None)
        self.assertIsNone(try_simple_decimal("+\n", 0), None)
        self.assertIsNone(try_simple_decimal("-\n", 0), None)
        self.assertIsNone(try_simple_decimal("+inf\n", 0), None)
        self.assertIsNone(try_simple_decimal("-nan\n", 0), None)
        self.assertIsNone(try_simple_decimal("0123\n", 0))
        self.assertIsNone(try_simple_decimal("1979-05-27\n", 0))
        self.assertIsNone(try_simple_decimal("12:32:00\n", 0))
        self.assertIsNone(try_simple_decimal("1.0\n", 0))
        self.assertIsNone(try_simple_decimal("1_000\n", 0))
        self.assertIsNone(try_simple_decimal("0x123\n", 0))
        self.assertIsNone(try_simple_decimal("0o123\n", 0))
        self.assertIsNone(try_simple_decimal("0b100\n", 0))

    def test_use_simple_decimal(self):
        # USE_SIMPLE_DECIMAL remains True if parsing only simple numbers
        toml = textwrap.dedent("""
            [metadata]
            only_ints = [123, 456]
        """)
        tomllib._parser.USE_SIMPLE_DECIMAL = True
        tomllib.loads(toml)
        self.assertTrue(tomllib._parser.USE_SIMPLE_DECIMAL)

        # Turn off USE_SIMPLE_DECIMAL when meeting the first non-simple number
        # (a datetime in this case)
        toml = textwrap.dedent("""
            [metadata]
            datatime = 2007-02-01T17:09:54-08:45
        """)
        tomllib.loads(toml)
        self.assertFalse(tomllib._parser.USE_SIMPLE_DECIMAL)

    @unittest.skipUnless(sys.version_info >= (3, 15), "need Python 3.15+")
    def test_lazy_import(self):
        # Test that try_simple_decimal() can parse the TOML file without
        # importing regular expressions (tomli._re)
        with tempfile.TemporaryDirectory() as tmp_dir_path:
            file_path = Path(tmp_dir_path) / "test.toml"
            toml = textwrap.dedent("""
                [metadata]
                int = 123
                list = [+1, -2, 3]
                table = {x=1, y=2}
            """)
            with open(file_path, "w") as fp:
                fp.write(toml)

            code = textwrap.dedent(f"""
                import sys, tomli
                with open({str(file_path)!a}, "rb") as fp:
                    tomli.load(fp)
                print("lazy import?", 'tomli._re' not in sys.modules)
            """)
            cmd = [sys.executable, "-c", code]
            proc = subprocess.run(cmd, check=True, capture_output=True)
            self.assertIn(b"lazy import? True", proc.stdout.rstrip())
