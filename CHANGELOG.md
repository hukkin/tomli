# Changelog

## **unreleased**

- no changes yet

## 1.2.2

- Fixed
  - Illegal characters in error messages were surrounded by two pairs of quotation marks
- Improved
  - `TOMLDecodeError.__module__` is now the public import path (`tomli`) instead of private import path (`tomli._parser`)
  - Eliminated an import cycle when `typing.TYPE_CHECKING` is `True`.
    This allows `sphinx-autodoc-typehints` to resolve type annotations.

## 1.2.1

- Fixed
  - Raise an error if a carriage return (without a following line feed) is found in a multi-line basic string
- Type annotations
  - Type annotate `load` input as `typing.BinaryIO` only to discourage use of deprecated text file objects.
- Packaging
  - Remove legacy `setup.py` from PyPI source distribution.
    If you're a packager and absolutely need this file, please create an issue.

## 1.2.0

- Deprecated
  - Text file objects as input to `load`.
    Binary file objects should be used instead to avoid opening a TOML file with universal newlines or with an encoding other than UTF-8.

## 1.1.0

- Added
  - `load` can now take a binary file object

## 1.0.4

- Performance
  - Minor boost (~4%)

## 1.0.3

- Fixed
  - Raise `TOMLDecodeError` instead of `ValueError` when parsing dates and datetimes that pass the regex check but don't correspond to a valid date or datetime.
- Performance
  - Improved multiline literal string parsing performance

## 1.0.2

- Performance
  - Minor boost (~4%)

## 1.0.1

- Performance
  - A significant boost

## 1.0.0

- Fixed
  - Raise `TOMLDecodeError` instead of `KeyError` when overwriting implicitly in an inline table

## 0.2.10

- Fixed
  - Raise `TOMLDecodeError` if overwriting nested inline tables from the parent inline
  - Raise `TOMLDecodeError` if escaped Unicode character is not a Unicode scalar value
- Performance
  - Increased parsing speed of single line basic strings, and multi-line literal and basic strings

## 0.2.9

- Fixed
  - `TOMLDecodeError` now raised when opening a table implicitly created by a key/value pair
  - Don't error when two array-of-tables items open a subtable with the same name
  - Don't error when opening parent table of an already defined array-of-tables item

## 0.2.8

- Performance
  - Significant boost to comment parsing speed

## 0.2.7

- Added
  - Improved `TOMLDecodeError` error messages.
    Line and column are included when applicable.

## 0.2.6

- Performance
  - Over 5% boost

## 0.2.5

- Fixed
  - Made exception type `TOMLDecodeError` when  overwriting a value with a deeply nested table

## 0.2.4

- Fixed
  - `TOMLDecodeError` is now raised when attempting to overwrite a value in an inline table's or array's namespace with a table definition

## 0.2.3

- Fixed
  - Error type was not TOMLDecodeError in some obscure cases

## 0.2.2

- Added
  - `tomli.load` for parsing IO streams returned by `open()`
  - `parse_float` keyword argument to `tomli.loads`.
    Allows parsing TOML floats to a non-float type in Python.

## 0.2.1

- Fixed
  - `TOMLDecodeError` is now raised for duplicate keys in inline tables,
    as opposed to silently overriding the previous value

## 0.2.0

- Changed
  - Project name to Tomli
- Performance
  - A performance boost

## 0.1.0

- Added
  - `tomli.loads` for parsing TOML strings
  - `tomli.TOMLDecodeError` that is raised for parse errors
