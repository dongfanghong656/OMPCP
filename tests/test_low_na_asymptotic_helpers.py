"""Unittest-discovery wrapper for the round6p1 helper suite.

The canonical helper suite lives at the repository root so it can also be
renamed into a flat numbered handoff bundle. This wrapper lets
`python -m unittest discover` find the same tests in both layouts.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HELPER_CANDIDATES = (
    ROOT / "test_low_na_asymptotic_helpers.py",
    ROOT / "12_test_low_na_asymptotic_helpers.py",
)


def _load_helper_module():
    for candidate in HELPER_CANDIDATES:
        if candidate.exists():
            spec = importlib.util.spec_from_file_location("round6p1_helper_suite_for_discovery", candidate)
            if spec is None or spec.loader is None:
                raise RuntimeError(f"Cannot load helper tests from {candidate}")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
    raise FileNotFoundError(
        "Cannot find root helper test suite. Checked: "
        + ", ".join(str(candidate) for candidate in HELPER_CANDIDATES)
    )


_helper_module = _load_helper_module()

for _name in dir(_helper_module):
    _value = getattr(_helper_module, _name)
    if _name.startswith("Test") or _name.endswith("Tests"):
        globals()[_name] = _value

