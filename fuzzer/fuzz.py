# TODO: move all imports except `atheris` under this contextmanager in atheris>1.0.11
# with atheris.instrument_imports():
from math import isnan
import re
import sys
import warnings

import atheris
import tomli_w

import tomli

# Suppress all warnings.
warnings.simplefilter("ignore")


def test_one_input(input_bytes: bytes) -> None:
    # We need a Unicode string, not bytes
    fdp = atheris.FuzzedDataProvider(input_bytes)
    data = fdp.ConsumeUnicode(sys.maxsize)

    try:
        toml_obj = tomli.loads(data)
    except (tomli.TOMLDecodeError, RecursionError):
        return
    except BaseException:
        print_err(data)
        raise

    try:
        roundtripped_obj = tomli.loads(tomli_w.dumps(toml_obj))
        if normalize_toml_obj(roundtripped_obj) != normalize_toml_obj(toml_obj):
            sys.stderr.write(
                f"Original dict:\n{toml_obj}\nRoundtripped dict:\n{roundtripped_obj}\n"
            )
            sys.stderr.flush()
            raise Exception("Dicts not equal after roundtrip")
    except RecursionError:
        return
    except BaseException:
        print_err(data)
        raise


def print_err(data):
    codepoints = [hex(ord(x)) for x in data]
    sys.stderr.write(f"Input was {type(data)}:\n{data}\nCodepoints:\n{codepoints}\n")
    sys.stderr.flush()


def normalize_toml_obj(toml_obj):
    """Make NaNs equal when compared.

    Normalize line breaks.
    """
    if isinstance(toml_obj, dict):
        return {k: normalize_toml_obj(v) for k, v in toml_obj.items()}
    if isinstance(toml_obj, list):
        return [normalize_toml_obj(v) for v in toml_obj]
    if isinstance(toml_obj, float) and isnan(toml_obj):
        return "nan"
    if isinstance(toml_obj, str):
        return re.sub(r"\r+\n", r"\n", toml_obj)
    return toml_obj


def main():
    # For possible options, see https://llvm.org/docs/LibFuzzer.html#options
    fuzzer_options = sys.argv
    atheris.Setup(fuzzer_options, test_one_input)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
