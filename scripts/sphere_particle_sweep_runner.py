#!/usr/bin/env python3
"""Sphere-only Mie full-NA / FD-OCT sweep runner.

This runner stays separate from particle_size_sweep_runner.py so sphere
validation cannot be confused with the low_na_separable_baseline axial-smoke
sweep.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import sys
import traceback
from pathlib import Path

import numpy as np


SCHEMA_VERSION = "sphere_mie_sweep_v1"


def default_project_root_for(script_dir: Path) -> Path:
    script_dir = Path(script_dir).resolve()
    return script_dir.parent if script_dir.name == "scripts" else script_dir


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = default_project_root_for(SCRIPT_DIR)
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def parse_float_list(text: str) -> list[float]:
    values = []
    if ":" in text and "," not in text:
        start, step, stop = [float(x) for x in text.split(":")]
        v = start
        while v <= stop + 1e-12:
            values.append(float(v))
            v += step
    else:
        for chunk in text.replace(";", ",").split(","):
            chunk = chunk.strip()
            if chunk:
                values.append(float(chunk))
    if not values:
        raise ValueError("empty numeric list")
    return values


def resolve_solver_path(project_root: Path) -> Path:
    candidates = (
        project_root / "scripts" / "oct_nonspherical_psf_solver.py",
        project_root / "scripts" / "01_oct_nonspherical_psf_solver.py",
        project_root / "oct_nonspherical_psf_solver.py",
        project_root / "01_oct_nonspherical_psf_solver.py",
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError("Cannot find oct_nonspherical_psf_solver.py in repo or flat bundle layout.")


def load_solver(project_root: Path):
    solver_path = resolve_solver_path(project_root)
    for path in (project_root, solver_path.parent):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))
    spec = importlib.util.spec_from_file_location("oct_nonspherical_psf_solver_runtime", solver_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load solver from {solver_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    sys.modules.setdefault("oct_nonspherical_psf_solver", module)
    spec.loader.exec_module(module)
    return module


def finite_or_none(value):
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return numeric if np.isfinite(numeric) else None


def lateral_line_metrics(result: dict) -> dict[str, float | None]:
    raw = np.asarray(result.get("raw_intensity_xz"), dtype=float)
    x_um = np.asarray(result.get("x_um"), dtype=float)
    peak_idx = result.get("global_peak_index", None)
    if raw.ndim != 2 or x_um.ndim != 1 or raw.shape[0] != x_um.size or peak_idx is None:
        return {"lateral_fwhm_um": None, "lateral_centroid_um": None}
    _, peak_z_idx = [int(v) for v in peak_idx]
    line = raw[:, peak_z_idx]
    if np.max(line) <= 0:
        return {"lateral_fwhm_um": None, "lateral_centroid_um": None}
    norm = line / np.max(line)
    idx = np.flatnonzero(norm >= 0.5)
    fwhm = None
    if idx.size:
        fwhm = float(x_um[idx[-1]] - x_um[idx[0]])
    centroid = float(np.sum(x_um * line) / (np.sum(line) + 1e-30))
    return {"lateral_fwhm_um": fwhm, "lateral_centroid_um": centroid}


def compact_result_for_json(result: dict) -> dict:
    excluded = {
        "x_um",
        "opd_um",
        "lambda_nm",
        "sample_arm_spectral_cube",
        "field_xz",
        "raw_envelope_xz",
        "raw_intensity_xz",
        "envelope_xz",
        "intensity_xz",
        "centerline_raw_axial_envelope",
        "centerline_raw_axial_intensity",
        "peakline_raw_axial_envelope",
        "peakline_raw_axial_intensity",
        "centerline_axial_envelope",
        "centerline_axial_intensity",
        "peakline_axial_envelope",
        "peakline_axial_intensity",
    }
    return {k: v for k, v in result.items() if k not in excluded}


def json_default(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, complex):
        return {"real": float(np.real(value)), "imag": float(np.imag(value))}
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def save_npz(path: Path, result: dict) -> None:
    keys = [
        "x_um",
        "opd_um",
        "lambda_nm",
        "sample_arm_spectral_cube",
        "field_xz",
        "raw_envelope_xz",
        "raw_intensity_xz",
        "envelope_xz",
        "intensity_xz",
    ]
    payload = {k: np.asarray(result[k]) for k in keys if k in result}
    np.savez_compressed(path, **payload)


def extract_row(diameter_nm: float, na: float, result: dict) -> dict:
    axial = result.get("axial_intensity_metrics", {}) or {}
    lateral = lateral_line_metrics(result)
    return {
        "diameter_nm": diameter_nm,
        "na": na,
        "status": "ok",
        "mode_returned": result.get("mode"),
        "sphere_mie_used": bool(result.get("sphere_mie_used")),
        "tmatrix_used": bool(result.get("tmatrix_used")),
        "tmatrix_backend_required": bool(result.get("tmatrix_backend_required", False)),
        "scattering_branch": result.get("scattering_branch"),
        "lateral_response_model": result.get("lateral_response_model"),
        "particle_lateral_scattering_enters_profile": bool(result.get("particle_lateral_scattering_enters_profile")),
        "peakline_x_um": finite_or_none(result.get("peakline_x_um")),
        "lateral_fwhm_um": finite_or_none(lateral.get("lateral_fwhm_um")),
        "lateral_centroid_um": finite_or_none(lateral.get("lateral_centroid_um")),
        "axial_fwhm_opd_um": finite_or_none(axial.get("fwhm_opd_um")),
        "axial_peak_opd_um": finite_or_none(axial.get("peak_opd_um")),
        "main_to_sidelobe_rejection_db": finite_or_none(axial.get("main_to_sidelobe_rejection_db")),
        "raw_peak_intensity": finite_or_none(result.get("raw_peak_intensity")),
        "paper_safe": bool(result.get("paper_safe", False)),
    }


def failed_row(diameter_nm: float, na: float, error: BaseException) -> dict:
    return {
        "diameter_nm": diameter_nm,
        "na": na,
        "status": "failed",
        "sphere_mie_used": False,
        "tmatrix_used": False,
        "tmatrix_backend_required": False,
        "notes": f"{type(error).__name__}: {error}",
    }


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    keys: list[str] = []
    for row in rows:
        for key in row:
            if key not in keys:
                keys.append(key)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


def metric_ranges(rows: list[dict]) -> dict[str, list[float] | None]:
    out = {}
    for key in ("peakline_x_um", "lateral_fwhm_um", "lateral_centroid_um", "axial_fwhm_opd_um", "raw_peak_intensity"):
        vals = []
        for row in rows:
            value = row.get(key)
            if value is not None:
                try:
                    f = float(value)
                except (TypeError, ValueError):
                    continue
                if np.isfinite(f):
                    vals.append(f)
        out[key] = [float(min(vals)), float(max(vals))] if vals else None
    return out


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Run sphere-only Mie full-NA OCT sweep.")
    p.add_argument("--project-root", default=str(PROJECT_ROOT))
    p.add_argument("--output-dir", default=str(PROJECT_ROOT / "reports" / "sphere_mie_full_na_sweep"))
    p.add_argument("--diameters", default="200,300,400,500,600,700,800,900,1000")
    p.add_argument("--na-values", default="0.05")
    p.add_argument("--particle-material", default="TiO2-anatase")
    p.add_argument("--medium-material", default="PDMS")
    p.add_argument("--amp-component", default="S22")
    p.add_argument("--lambda0-nm", type=float, default=855.0)
    p.add_argument("--fwhm-nm", type=float, default=56.0)
    p.add_argument("--n-lambda", type=int, default=201)
    p.add_argument("--z-span-um", type=float, default=40.0)
    p.add_argument("--n-z", type=int, default=2001)
    p.add_argument("--x-span-um", type=float, default=8.0)
    p.add_argument("--n-x", type=int, default=129)
    p.add_argument("--n-bfp-dense", type=int, default=129)
    p.add_argument("--strict-material-range", action="store_true")
    p.add_argument("--allow-failed-cases", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    project_root = Path(args.project_root).resolve()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    solver = load_solver(project_root)
    diameters = parse_float_list(args.diameters)
    na_values = parse_float_list(args.na_values)
    rows: list[dict] = []
    for na in na_values:
        for diameter_nm in diameters:
            stem = f"sphere_mie_full_na_na{na:g}_d{int(round(diameter_nm)):04d}nm".replace(".", "p")
            try:
                source = solver.SourceConfig(args.lambda0_nm, args.fwhm_nm, args.n_lambda)
                grid = solver.GridConfig(
                    args.z_span_um,
                    args.n_z,
                    args.x_span_um,
                    args.n_x,
                    na,
                    args.n_bfp_dense,
                    max(5, min(11, args.n_bfp_dense)),
                )
                config = solver.SolverConfig(
                    mode="full_na",
                    particle_material=args.particle_material,
                    medium_material=args.medium_material,
                    diameter_nm=diameter_nm,
                    eps=0.0,
                    beta_deg=0.0,
                    amp_component=args.amp_component,
                    ideal=False,
                    force_tmatrix=False,
                    strict_material_range=args.strict_material_range,
                )
                result = solver.solve_oct_particle_response(source, grid, config)
                if result.get("tmatrix_used"):
                    raise RuntimeError("sphere branch contract violation: full_na sphere used T-matrix backend")
                if not result.get("particle_lateral_scattering_enters_profile"):
                    raise RuntimeError("sphere branch contract violation: lateral profile is not particle-aware")
                save_npz(output_dir / f"{stem}.npz", result)
                (output_dir / f"{stem}.json").write_text(
                    json.dumps(compact_result_for_json(result), indent=2, default=json_default) + "\n",
                    encoding="utf-8",
                )
                rows.append(extract_row(diameter_nm, na, result))
            except Exception as exc:
                rows.append(failed_row(diameter_nm, na, exc))
                (output_dir / f"{stem}_ERROR.txt").write_text(
                    "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
                    encoding="utf-8",
                )
    write_csv(output_dir / "sphere_mie_full_na_sweep.csv", rows)
    package = {
        "schema_version": SCHEMA_VERSION,
        "sweep_status": "complete" if all(r.get("status") == "ok" for r in rows) else "has_failed_cases",
        "diameter_nm_values": diameters,
        "na_values": na_values,
        "case_count": len(rows),
        "ok_count": sum(1 for r in rows if r.get("status") == "ok"),
        "failed_count": sum(1 for r in rows if r.get("status") != "ok"),
        "sphere_branch_contract": "full_na_eps0_force_tmatrix_false_must_use_sphere_mie_no_tmatrix",
        "metric_ranges": metric_ranges(rows),
        "rows": rows,
    }
    (output_dir / "sphere_mie_full_na_sweep_summary.json").write_text(json.dumps(package, indent=2) + "\n", encoding="utf-8")
    return 0 if args.allow_failed_cases or package["failed_count"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
