import atheris

with atheris.instrument_imports():
    from math import isnan
    import sys
    import warnings

    import tomli_w

    import tomli

# Disable any caching used so that the same lines of code run
# on a given input consistently.
tomli._re.cached_tz = tomli._re.cached_tz.__wrapped__

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
        recovered_data = tomli_w.dumps(toml_obj)
    except RecursionError:
        return
    except BaseException:
        print_err(data)
        raise

    roundtripped_obj = tomli.loads(recovered_data)
    normalize_toml_obj(roundtripped_obj)
    normalize_toml_obj(toml_obj)
    if roundtripped_obj != toml_obj:
        sys.stderr.write(
            f"Original dict:\n{toml_obj}\nRoundtripped dict:\n{roundtripped_obj}\n"
        )
        sys.stderr.flush()
        print_err(data)
        raise Exception("Dicts not equal after roundtrip")


def print_err(data):
    codepoints = [hex(ord(x)) for x in data]
    sys.stderr.write(f"Input was {type(data)}:\n{data}\nCodepoints:\n{codepoints}\n")
    sys.stderr.flush()


def normalize_toml_obj(toml_obj: dict) -> None:
    """Make NaNs equal when compared (without using recursion)."""
    to_process = [toml_obj]
    while to_process:
        cont = to_process.pop()
        for k, v in cont.items() if isinstance(cont, dict) else enumerate(cont):
            if isinstance(v, float) and isnan(v):
                cont[k] = "nan"
            elif isinstance(v, (dict, list)):
                to_process.append(v)


def main():
    # For possible options, see https://llvm.org/docs/LibFuzzer.html#options
    fuzzer_options = sys.argv
    atheris.Setup(fuzzer_options, test_one_input)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
