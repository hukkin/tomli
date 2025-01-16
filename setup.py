import os

from setuptools import setup  # type: ignore[import-untyped]

if os.environ.get("TOMLI_USE_MYPYC") == "1":
    import glob

    from mypyc.build import mypycify  # type: ignore[import-untyped]

    files = glob.glob("src/**/*.py", recursive=True)
    ext_modules = mypycify(files)
else:
    ext_modules = []

setup(ext_modules=ext_modules)
