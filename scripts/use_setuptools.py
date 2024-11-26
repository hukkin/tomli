from pathlib import Path
import tomllib

import tomli_w  # type: ignore[import-not-found]

pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
data = tomllib.loads(pyproject_path.read_bytes().decode())
data["build-system"] = {
    "requires": ["setuptools>=69", "mypy[mypyc]>=1.13"],
    "build-backend": "setuptools.build_meta",
}
pyproject_path.write_bytes(tomli_w.dumps(data).encode())
