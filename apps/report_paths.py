from __future__ import annotations

from pathlib import Path


def resolve_runtime_root(anchor_path=None) -> Path:
    anchor = Path(anchor_path or __file__).resolve()
    base_dir = anchor if anchor.is_dir() else anchor.parent
    if base_dir.name == "scripts":
        return base_dir.parent
    if (base_dir / "00_README.txt").exists() and any(
        (base_dir / candidate_name).exists()
        for candidate_name in ("01_oct_nonspherical_psf_solver.py", "oct_nonspherical_psf_solver.py")
    ):
        return base_dir
    if (base_dir / "scripts").exists():
        return base_dir
    if (base_dir.parent / "scripts").exists():
        return base_dir.parent
    return base_dir


def resolve_reports_dir(anchor_path=None) -> Path:
    runtime_root = resolve_runtime_root(anchor_path)
    if (runtime_root / "scripts").exists():
        return runtime_root / "reports"
    return runtime_root


def build_report_path(prefix: str, stem: str, suffix: str, *, anchor_path=None) -> Path:
    return resolve_reports_dir(anchor_path) / f"{prefix}_{stem}.{suffix}"
