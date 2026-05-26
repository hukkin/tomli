# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2021 Taneli Hukkinen
# Licensed to PSF under a Contributor Agreement.

from __future__ import annotations

from typing import Any
import unittest

from . import tomllib


class TestError(unittest.TestCase):
    def test_line_and_col(self):
        with self.assertRaises(tomllib.TOMLDecodeError) as exc_info:
            tomllib.loads("val=.")
        self.assertEqual(str(exc_info.exception), "Invalid value (at line 1, column 5)")

        with self.assertRaises(tomllib.TOMLDecodeError) as exc_info:
            tomllib.loads(".")
        self.assertEqual(
            str(exc_info.exception), "Invalid statement (at line 1, column 1)"
        )

        with self.assertRaises(tomllib.TOMLDecodeError) as exc_info:
            tomllib.loads("\n\nval=.")
        self.assertEqual(str(exc_info.exception), "Invalid value (at line 3, column 5)")

        with self.assertRaises(tomllib.TOMLDecodeError) as exc_info:
            tomllib.loads("\n\n.")
        self.assertEqual(
            str(exc_info.exception), "Invalid statement (at line 3, column 1)"
        )

    def test_missing_value(self):
        with self.assertRaises(tomllib.TOMLDecodeError) as exc_info:
            tomllib.loads("\n\nfwfw=")
        self.assertEqual(str(exc_info.exception), "Invalid value (at end of document)")

    def test_invalid_char_quotes(self):
        with self.assertRaises(tomllib.TOMLDecodeError) as exc_info:
            tomllib.loads("v = '\n'")
        self.assertTrue(" '\\n' " in str(exc_info.exception))

    def test_type_error(self):
        with self.assertRaises(TypeError) as exc_info:
            tomllib.loads(b"v = 1")  # type: ignore[arg-type]
        # Mypyc extension leads to different message than pure Python
        self.assertIn(
            str(exc_info.exception),
            ("Expected str object, not 'bytes'", "str object expected; got bytes"),
        )

        with self.assertRaises(TypeError) as exc_info:
            tomllib.loads(False)  # type: ignore[arg-type]
        # Mypyc extension leads to different message than pure Python
        self.assertIn(
            str(exc_info.exception),
            ("Expected str object, not 'bool'", "str object expected; got bool"),
        )

    def test_invalid_parse_float(self):
        def dict_returner(s: str) -> dict[Any, Any]:
            return {}

        def list_returner(s: str) -> list[Any]:
            return []

        for invalid_parse_float in (dict_returner, list_returner):
            with self.assertRaises(ValueError) as exc_info:
                tomllib.loads("f=0.1", parse_float=invalid_parse_float)
            self.assertEqual(
                str(exc_info.exception), "parse_float must not return dicts or lists"
            )

    def test_deprecated_tomldecodeerror(self):
        for args in [
            (),
            ("err msg",),
            (None,),
            (None, "doc"),
            ("err msg", None),
            (None, "doc", None),
            ("err msg", "doc", None),
            ("one", "two", "three", "four"),
            ("one", "two", 3, "four", "five"),
        ]:
            with self.assertWarns(DeprecationWarning):
                e = tomllib.TOMLDecodeError(*args)  # type: ignore[arg-type]
            self.assertEqual(e.args, args)

    def test_tomldecodeerror(self):
        msg = "error parsing"
        doc = "v=1\n[table]\nv='val'"
        pos = 13
        formatted_msg = "error parsing (at line 3, column 2)"
        e = tomllib.TOMLDecodeError(msg, doc, pos)
        self.assertEqual(e.args, (formatted_msg,))
        self.assertEqual(str(e), formatted_msg)
        self.assertEqual(e.msg, msg)
        self.assertEqual(e.doc, doc)
        self.assertEqual(e.pos, pos)
        self.assertEqual(e.lineno, 3)
        self.assertEqual(e.colno, 2)

    def test_edge_case_pos_and_message(self):
        # Unterminated multi-line basic string
        with self.assertRaises(tomllib.TOMLDecodeError) as exc_info:
            tomllib.loads('a = """hello')
        self.assertEqual(exc_info.exception.msg, "Unterminated string")
        self.assertEqual(exc_info.exception.pos, 12)
        self.assertEqual(str(exc_info.exception), "Unterminated string (at end of document)")
        self.assertEqual(exc_info.exception.lineno, 1)
        self.assertEqual(exc_info.exception.colno, 13)

        # Unterminated multi-line literal string
        with self.assertRaises(tomllib.TOMLDecodeError) as exc_info:
            tomllib.loads("a = '''hello")
        self.assertEqual(exc_info.exception.msg, "Expected \"'''\"")
        self.assertEqual(exc_info.exception.pos, 12)
        self.assertEqual(str(exc_info.exception), "Expected \"'''\" (at end of document)")
        self.assertEqual(exc_info.exception.lineno, 1)
        self.assertEqual(exc_info.exception.colno, 13)

        # Malformed inline table: missing '=' after key
        with self.assertRaises(tomllib.TOMLDecodeError) as exc_info:
            tomllib.loads("a = { b = 1, c }")
        self.assertEqual(
            exc_info.exception.msg, "Expected '=' after a key in a key/value pair"
        )
        self.assertEqual(exc_info.exception.pos, 15)
        self.assertEqual(
            str(exc_info.exception),
            "Expected '=' after a key in a key/value pair (at line 1, column 16)",
        )
        self.assertEqual(exc_info.exception.lineno, 1)
        self.assertEqual(exc_info.exception.colno, 16)

        # Unclosed inline table
        with self.assertRaises(tomllib.TOMLDecodeError) as exc_info:
            tomllib.loads("a = { b = 1")
        self.assertEqual(exc_info.exception.msg, "Unclosed inline table")
        self.assertEqual(exc_info.exception.pos, 11)
        self.assertEqual(
            str(exc_info.exception), "Unclosed inline table (at end of document)"
        )
        self.assertEqual(exc_info.exception.lineno, 1)
        self.assertEqual(exc_info.exception.colno, 12)

        # Invalid date (regex matches but datetime() rejects)
        with self.assertRaises(tomllib.TOMLDecodeError) as exc_info:
            tomllib.loads("a = 2021-02-30")
        self.assertEqual(exc_info.exception.msg, "Invalid date or datetime")
        self.assertEqual(exc_info.exception.pos, 4)
        self.assertEqual(
            str(exc_info.exception),
            "Invalid date or datetime (at line 1, column 5)",
        )
        self.assertEqual(exc_info.exception.lineno, 1)
        self.assertEqual(exc_info.exception.colno, 5)

        # Multi-line unterminated string on a later line
        with self.assertRaises(tomllib.TOMLDecodeError) as exc_info:
            tomllib.loads("a = 1\n\nb = \"\"\"hello\nworld")
        self.assertEqual(exc_info.exception.msg, "Unterminated string")
        self.assertEqual(exc_info.exception.pos, 25)
        self.assertEqual(str(exc_info.exception), "Unterminated string (at end of document)")
        self.assertEqual(exc_info.exception.lineno, 4)
        self.assertEqual(exc_info.exception.colno, 6)
