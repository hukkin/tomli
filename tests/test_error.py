import unittest

import tomli


class TestError(unittest.TestCase):
    def test_line_and_col(self):
        with self.assertRaises(tomli.TOMLDecodeError) as exc_info:
            tomli.loads("val=.")
        self.assertEqual(str(exc_info.exception), "Invalid value (at line 1, column 5)")

        with self.assertRaises(tomli.TOMLDecodeError) as exc_info:
            tomli.loads(".")
        self.assertEqual(
            str(exc_info.exception), "Invalid statement (at line 1, column 1)"
        )

        with self.assertRaises(tomli.TOMLDecodeError) as exc_info:
            tomli.loads("\n\nval=.")
        self.assertEqual(str(exc_info.exception), "Invalid value (at line 3, column 5)")

        with self.assertRaises(tomli.TOMLDecodeError) as exc_info:
            tomli.loads("\n\n.")
        self.assertEqual(
            str(exc_info.exception), "Invalid statement (at line 3, column 1)"
        )

    def test_missing_value(self):
        with self.assertRaises(tomli.TOMLDecodeError) as exc_info:
            tomli.loads("\n\nfwfw=")
        self.assertEqual(str(exc_info.exception), "Invalid value (at end of document)")

    def test_invalid_char_quotes(self):
        with self.assertRaises(tomli.TOMLDecodeError) as exc_info:
            tomli.loads("v = '\n'")
        self.assertTrue(" '\\n' " in str(exc_info.exception))

    def test_module_name(self):
        self.assertEqual(tomli.TOMLDecodeError().__module__, "tomli")
