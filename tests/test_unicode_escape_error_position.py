# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2021 Taneli Hukkinen
# Licensed to PSF under a Contributor Agreement.

# Test for error position in Unicode escapes
# Regression test for: error position was reported at END of escape instead of START
# This file is NEW and exercises the real bug independently of the fix.

from __future__ import annotations

import pytest

from . import tomllib


def test_unicode_escape_surrogate_error_position():
    """Error position for surrogate escapes should point to start of hex digits."""
    # Surrogate codepoints are not valid Unicode scalar values
    # Error should point to start of the hex digits, not the end of the escape
    doc = 'val = "\\uD800"'
    with pytest.raises(tomllib.TOMLDecodeError) as exc_info:
        tomllib.loads(doc)

    err = exc_info.value
    # The error should be at or near the start of "D800"
    # Column 10 is position 9 (0-indexed), which is the 'D' in D800
    # Before the fix, this would report column 14 (the closing quote)
    assert (
        err.colno <= 11
    ), f"Error column {err.colno} is too late, should be near start of hex digits"


def test_unicode_escape_large_codepoint_error_position():
    """Error position for codepoints > U+10FFFF should point to start of hex digits."""
    # Codepoints > U+10FFFF are not valid Unicode scalar values
    doc = 'val = "\\U00110000"'
    with pytest.raises(tomllib.TOMLDecodeError) as exc_info:
        tomllib.loads(doc)

    err = exc_info.value
    # Error should be at start of hex digits, not at end
    assert err.colno <= 11, f"Error column {err.colno} is too late"


def test_unicode_escape_in_middle_of_string():
    """Error position for invalid escape in middle of string."""
    doc = 'key = "before \\uDFFF after"'
    with pytest.raises(tomllib.TOMLDecodeError) as exc_info:
        tomllib.loads(doc)

    err = exc_info.value
    # Error should be around where the hex digits are, not at end of string
    # The escape starts around position 14-15
    assert err.colno < 25, f"Error column {err.colno} is too late"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
