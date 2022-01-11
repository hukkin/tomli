import json
from pathlib import Path
import unittest

from . import burntsushi, tomllib

DATA_DIR = Path(__file__).parent / "data" / "extras"

VALID_FILES = tuple((DATA_DIR / "valid").glob("**/*.toml"))
VALID_FILES_EXPECTED = tuple(
    json.loads(p.with_suffix(".json").read_bytes().decode()) for p in VALID_FILES
)

INVALID_FILES = tuple((DATA_DIR / "invalid").glob("**/*.toml"))


class TestExtraCases(unittest.TestCase):
    def test_invalid(self):
        for invalid in INVALID_FILES:
            with self.subTest(msg=invalid.stem):
                toml_bytes = invalid.read_bytes()
                try:
                    toml_str = toml_bytes.decode()
                except UnicodeDecodeError:
                    # Some BurntSushi tests are not valid UTF-8. Skip those.
                    continue
                with self.assertRaises(tomllib.TOMLDecodeError):
                    tomllib.loads(toml_str)

    def test_valid(self):
        for valid, expected in zip(VALID_FILES, VALID_FILES_EXPECTED):
            with self.subTest(msg=valid.stem):
                toml_str = valid.read_bytes().decode()
                actual = tomllib.loads(toml_str)
                actual = burntsushi.convert(actual)
                expected = burntsushi.normalize(expected)
                self.assertEqual(actual, expected)
