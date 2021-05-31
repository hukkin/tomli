# Changelog

## 0.2.6

- Added
  - Over 5% performance boost

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
- Added
  - A performance boost

## 0.1.0

- Added
  - `tomli.loads` for parsing TOML strings
  - `tomli.TOMLDecodeError` that is raised for parse errors
