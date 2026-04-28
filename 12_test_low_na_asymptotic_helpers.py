from __future__ import annotations

import runpy
from pathlib import Path


if __name__ == "__main__":
    runpy.run_path(
        str(Path(__file__).resolve().with_name("test_low_na_asymptotic_helpers.py")),
        run_name="__main__",
    )
