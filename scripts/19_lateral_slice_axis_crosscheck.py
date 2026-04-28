from __future__ import annotations

import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from diagnostics.slice_axis_crosscheck import *  # noqa: F401,F403
from diagnostics.slice_axis_crosscheck import main


if __name__ == "__main__":
    raise SystemExit(main())
