# Changelog

## **unreleased**

- Added
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
