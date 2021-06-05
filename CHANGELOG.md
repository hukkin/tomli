# Changelog

## **unreleased**

- Fixed
  - Raise `TOMLDecodeError` if overwriting nested inline tables from the parent inline

## 0.2.9

- Fixed
  - `TOMLDecodeError` now raised when opening a table implicitly created by a key/value pair
  - Don't error when two array-of-tables items open a subtable with the same name
  - Don't error when opening parent table of an already defined array-of-tables item

## 0.2.8

- Added
  - Significant boost to comment parsing speed

## 0.2.7

- Added
  - Improved `TOMLDecodeError` error messages.
    Line and column are included when applicable.

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
