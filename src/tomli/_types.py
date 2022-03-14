# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2021 Taneli Hukkinen
# Licensed to PSF under a Contributor Agreement.

from numbers import Number
from typing import Callable, Tuple

# Type annotations
ParseFloat = Callable[[str], Number]
Key = Tuple[str, ...]
Pos = int
