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


def lateral_line_metrics_at_z(result: dict, z_idx: int | None) -> dict[str, float | None]:
    raw = np.asarray(result.get("raw_intensity_xz"), dtype=float)
    x_um = np.asarray(result.get("x_um"), dtype=float)
    if raw.ndim != 2 or x_um.ndim != 1 or raw.shape[0] != x_um.size or z_idx is None:
        return {
            "lateral_fwhm_um": None,
            "lateral_centroid_um": None,
            "lateral_peak_x_um": None,
        }
    peak_z_idx = int(z_idx)
    if peak_z_idx < 0 or peak_z_idx >= raw.shape[1]:
        return {
            "lateral_fwhm_um": None,
            "lateral_centroid_um": None,
            "lateral_peak_x_um": None,
        }
    line = raw[:, peak_z_idx]
    if np.max(line) <= 0:
        return {
            "lateral_fwhm_um": None,
            "lateral_centroid_um": None,
            "lateral_peak_x_um": None,
        }
    norm = line / np.max(line)
    idx = np.flatnonzero(norm >= 0.5)
    fwhm = None
    if idx.size:
        fwhm = float(x_um[idx[-1]] - x_um[idx[0]])
    centroid = float(np.sum(x_um * line) / (np.sum(line) + 1e-30))
    peak_x = float(x_um[int(np.argmax(line))])
    return {
        "lateral_fwhm_um": fwhm,
        "lateral_centroid_um": centroid,
        "lateral_peak_x_um": peak_x,
    }


def lateral_line_metrics(result: dict) -> dict[str, float | None]:
    peak_idx = result.get("global_peak_index", None)
    peak_z_idx = None
    if peak_idx is not None:
        peak_z_idx = [int(v) for v in peak_idx][1]
    return lateral_line_metrics_at_z(result, peak_z_idx)


def lateral_line_at_z(result: dict, z_idx: int | None) -> np.ndarray | None:
    raw = np.asarray(result.get("raw_intensity_xz"), dtype=float)
    if raw.ndim != 2 or z_idx is None:
        return None
    peak_z_idx = int(z_idx)
    if peak_z_idx < 0 or peak_z_idx >= raw.shape[1]:
        return None
    return np.asarray(raw[:, peak_z_idx], dtype=float)


def normalized_relative_l2(a, b) -> float | None:
    if a is None or b is None:
        return None
    lhs = np.asarray(a, dtype=float)
    rhs = np.asarray(b, dtype=float)
    if lhs.shape != rhs.shape or lhs.size == 0:
        return None
    if not np.all(np.isfinite(lhs)) or not np.all(np.isfinite(rhs)):
        return None
    lhs_peak = float(np.max(np.abs(lhs)))
    rhs_peak = float(np.max(np.abs(rhs)))
    if lhs_peak <= 0.0 or rhs_peak <= 0.0:
        return None
    lhs_norm = lhs / lhs_peak
    rhs_norm = rhs / rhs_peak
    denom = float(np.linalg.norm(rhs_norm.ravel()))
    if denom <= 0.0:
        return None
    return float(np.linalg.norm((lhs_norm - rhs_norm).ravel()) / denom)


def delta_or_none(value, reference) -> float | None:
    value = finite_or_none(value)
    reference = finite_or_none(reference)
    if value is None or reference is None:
        return None
    return float(value - reference)


def ideal_reference_for(solver, args, na: float) -> dict:
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
        diameter_nm=0.0,
        eps=0.0,
        beta_deg=0.0,
        amp_component=args.amp_component,
        ideal=True,
        force_tmatrix=False,
        strict_material_range=args.strict_material_range,
    )
    return solver.solve_oct_particle_response(source, grid, config)


def psf_bias_metrics_vs_ideal(result: dict, ideal_reference: dict | None) -> dict:
    if ideal_reference is None:
        return {
            "ideal_reference_available": False,
            "psf_bias_against_ideal_reference_status": "ideal_reference_unavailable",
        }
    particle_self = lateral_line_metrics(result)
    ideal_self = lateral_line_metrics(ideal_reference)
    ideal_peak_idx = ideal_reference.get("global_peak_index", None)
    ideal_peak_z_idx = [int(v) for v in ideal_peak_idx][1] if ideal_peak_idx is not None else None
    particle_at_ideal = lateral_line_metrics_at_z(result, ideal_peak_z_idx)
    ideal_at_ideal = lateral_line_metrics_at_z(ideal_reference, ideal_peak_z_idx)
    return {
        "ideal_reference_available": True,
        "ideal_reference_scattering_branch": ideal_reference.get("scattering_branch"),
        "ideal_reference_sample_arm_spectral_cube_contract_status": ideal_reference.get(
            "sample_arm_spectral_cube_contract_status"
        ),
        "psf_bias_against_ideal_reference_status": "computed_against_ideal_full_na_reference",
        "ideal_reference_peakline_x_um": finite_or_none(ideal_reference.get("peakline_x_um")),
        "peakline_x_delta_um_vs_ideal": delta_or_none(result.get("peakline_x_um"), ideal_reference.get("peakline_x_um")),
        "ideal_reference_self_peak_lateral_fwhm_um": finite_or_none(ideal_self.get("lateral_fwhm_um")),
        "ideal_reference_self_peak_lateral_centroid_um": finite_or_none(ideal_self.get("lateral_centroid_um")),
        "self_peak_lateral_fwhm_delta_um_vs_ideal": delta_or_none(
            particle_self.get("lateral_fwhm_um"), ideal_self.get("lateral_fwhm_um")
        ),
        "self_peak_lateral_centroid_delta_um_vs_ideal": delta_or_none(
            particle_self.get("lateral_centroid_um"), ideal_self.get("lateral_centroid_um")
        ),
        "self_peak_lateral_profile_relative_l2_vs_ideal": normalized_relative_l2(
            lateral_line_at_z(result, (result.get("global_peak_index") or [None, None])[1]),
            lateral_line_at_z(ideal_reference, (ideal_reference.get("global_peak_index") or [None, None])[1]),
        ),
        "ideal_peak_plane_z_index": ideal_peak_z_idx,
        "ideal_peak_plane_particle_lateral_peak_x_um": finite_or_none(particle_at_ideal.get("lateral_peak_x_um")),
        "ideal_peak_plane_lateral_fwhm_um": finite_or_none(particle_at_ideal.get("lateral_fwhm_um")),
        "ideal_peak_plane_lateral_centroid_um": finite_or_none(particle_at_ideal.get("lateral_centroid_um")),
        "ideal_peak_plane_peak_x_delta_um_vs_ideal": delta_or_none(
            particle_at_ideal.get("lateral_peak_x_um"), ideal_at_ideal.get("lateral_peak_x_um")
        ),
        "ideal_peak_plane_lateral_fwhm_delta_um_vs_ideal": delta_or_none(
            particle_at_ideal.get("lateral_fwhm_um"), ideal_at_ideal.get("lateral_fwhm_um")
        ),
        "ideal_peak_plane_lateral_centroid_delta_um_vs_ideal": delta_or_none(
            particle_at_ideal.get("lateral_centroid_um"), ideal_at_ideal.get("lateral_centroid_um")
        ),
        "ideal_peak_plane_lateral_profile_relative_l2_vs_ideal": normalized_relative_l2(
            lateral_line_at_z(result, ideal_peak_z_idx),
            lateral_line_at_z(ideal_reference, ideal_peak_z_idx),
        ),
        "normalized_image_relative_l2_vs_ideal": normalized_relative_l2(
            result.get("raw_intensity_xz"), ideal_reference.get("raw_intensity_xz")
        ),
    }


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


def extract_row(diameter_nm: float, na: float, result: dict, ideal_reference: dict | None = None) -> dict:
    axial = result.get("axial_intensity_metrics", {}) or {}
    lateral = lateral_line_metrics(result)
    row = {
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
        "sample_arm_spectral_cube_shape": result.get("sample_arm_spectral_cube_shape"),
        "sample_arm_spectral_cube_contract_status": result.get("sample_arm_spectral_cube_contract_status"),
        "fd_oct_measurement_scaffold_route_available": bool(result.get("fd_oct_measurement_scaffold_route_available")),
        "peakline_x_um": finite_or_none(result.get("peakline_x_um")),
        "lateral_fwhm_um": finite_or_none(lateral.get("lateral_fwhm_um")),
        "lateral_centroid_um": finite_or_none(lateral.get("lateral_centroid_um")),
        "axial_fwhm_opd_um": finite_or_none(axial.get("fwhm_opd_um")),
        "axial_peak_opd_um": finite_or_none(axial.get("peak_opd_um")),
        "main_to_sidelobe_rejection_db": finite_or_none(axial.get("main_to_sidelobe_rejection_db")),
        "raw_peak_intensity": finite_or_none(result.get("raw_peak_intensity")),
        "paper_safe": bool(result.get("paper_safe", False)),
    }
    row.update(psf_bias_metrics_vs_ideal(result, ideal_reference))
    return row


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


def write_markdown_summary(path: Path, package: dict) -> None:
    lines = [
        "# Sphere Mie Full-NA Sweep Summary",
        "",
        f"- schema_version: `{package.get('schema_version')}`",
        f"- sweep_status: `{package.get('sweep_status')}`",
        f"- psf_bias_against_ideal_reference_status: `{package.get('psf_bias_against_ideal_reference_status')}`",
        f"- paper_safety_status: `{package.get('paper_safety_status')}`",
        f"- ok_count: `{package.get('ok_count')}`",
        f"- failed_count: `{package.get('failed_count')}`",
        "",
        "## Ideal Reference Comparison",
        "",
    ]
    ideal = package.get("ideal_reference_comparison", {}) or {}
    for key in ("status", "reference_kind", "all_ok_rows_have_ideal_reference"):
        lines.append(f"- {key}: `{ideal.get(key)}`")
    modes = ideal.get("comparison_modes", [])
    lines.append(f"- comparison_modes: `{', '.join(modes) if modes else ''}`")
    lines += ["", "## Metric Ranges", ""]
    metric_ranges = package.get("metric_ranges", {}) or {}
    for key in (
        "peakline_x_delta_um_vs_ideal",
        "self_peak_lateral_fwhm_delta_um_vs_ideal",
        "self_peak_lateral_centroid_delta_um_vs_ideal",
        "ideal_peak_plane_lateral_profile_relative_l2_vs_ideal",
        "normalized_image_relative_l2_vs_ideal",
    ):
        lines.append(f"- {key}: `{metric_ranges.get(key)}`")
    lines += [
        "",
        "## Rows",
        "",
        "| diameter_nm | na | status | peakline_delta_um | fwhm_delta_um | image_l2_vs_ideal |",
        "|---:|---:|---|---:|---:|---:|",
    ]
    for row in package.get("rows", []):
        lines.append(
            "| {diameter_nm} | {na} | {status} | {peakline} | {fwhm} | {image_l2} |".format(
                diameter_nm=row.get("diameter_nm"),
                na=row.get("na"),
                status=row.get("status"),
                peakline=row.get("peakline_x_delta_um_vs_ideal"),
                fwhm=row.get("self_peak_lateral_fwhm_delta_um_vs_ideal"),
                image_l2=row.get("normalized_image_relative_l2_vs_ideal"),
            )
        )
    lines += [
        "",
        "## Interpretation",
        "",
        "This report is a PSF-bias trend scaffold, not a paper-safe device-level OCT truth claim.",
        "It compares the sphere Mie full-NA solver output against an ideal uniform-pupil full-NA reference.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def metric_ranges(rows: list[dict]) -> dict[str, list[float] | None]:
    out = {}
    for key in (
        "peakline_x_um",
        "lateral_fwhm_um",
        "lateral_centroid_um",
        "axial_fwhm_opd_um",
        "raw_peak_intensity",
        "peakline_x_delta_um_vs_ideal",
        "self_peak_lateral_fwhm_delta_um_vs_ideal",
        "self_peak_lateral_centroid_delta_um_vs_ideal",
        "self_peak_lateral_profile_relative_l2_vs_ideal",
        "ideal_peak_plane_peak_x_delta_um_vs_ideal",
        "ideal_peak_plane_lateral_fwhm_delta_um_vs_ideal",
        "ideal_peak_plane_lateral_centroid_delta_um_vs_ideal",
        "ideal_peak_plane_lateral_profile_relative_l2_vs_ideal",
        "normalized_image_relative_l2_vs_ideal",
    ):
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
    ideal_references: dict[float, dict | None] = {}
    for na in na_values:
        try:
            ideal_references[float(na)] = ideal_reference_for(solver, args, na)
        except Exception as exc:
            ideal_references[float(na)] = None
            (output_dir / f"sphere_mie_full_na_ideal_reference_na{na:g}_ERROR.txt".replace(".", "p")).write_text(
                "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
                encoding="utf-8",
            )
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
                rows.append(extract_row(diameter_nm, na, result, ideal_references.get(float(na))))
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
        "interpretation_status": "contract_smoke_only_not_final_particle_size_psf_conclusion",
        "paper_safety_status": (
            "not_paper_safe"
            if any(not bool(r.get("paper_safe")) for r in rows if r.get("status") == "ok")
            else "paper_safe_rows_reported"
        ),
        "diameter_nm_values": diameters,
        "na_values": na_values,
        "case_count": len(rows),
        "ok_count": sum(1 for r in rows if r.get("status") == "ok"),
        "failed_count": sum(1 for r in rows if r.get("status") != "ok"),
        "sphere_branch_contract": "full_na_eps0_force_tmatrix_false_must_use_sphere_mie_no_tmatrix",
        "sphere_branch_contract_checks": {
            "all_ok_rows_use_sphere_mie": all(bool(r.get("sphere_mie_used")) for r in rows if r.get("status") == "ok"),
            "all_ok_rows_avoid_tmatrix": all(not bool(r.get("tmatrix_used")) for r in rows if r.get("status") == "ok"),
            "all_ok_rows_particle_lateral_scattering_enters_profile": all(
                bool(r.get("particle_lateral_scattering_enters_profile")) for r in rows if r.get("status") == "ok"
            ),
            "all_ok_rows_fd_oct_scaffold_route_available": all(
                bool(r.get("fd_oct_measurement_scaffold_route_available")) for r in rows if r.get("status") == "ok"
            ),
        },
        "ideal_reference_comparison": {
            "status": (
                "computed_for_all_na_values"
                if all(ideal_references.get(float(na)) is not None for na in na_values)
                else "missing_for_one_or_more_na_values"
            ),
            "reference_kind": "ideal_uniform_pupil_full_na",
            "comparison_modes": [
                "self_peak_plane",
                "ideal_peak_plane",
                "normalized_full_xz_image",
            ],
            "all_ok_rows_have_ideal_reference": all(
                bool(r.get("ideal_reference_available")) for r in rows if r.get("status") == "ok"
            ),
        },
        "psf_bias_against_ideal_reference_status": (
            "computed_not_paper_safe"
            if all(bool(r.get("ideal_reference_available")) for r in rows if r.get("status") == "ok")
            else "incomplete_ideal_reference_comparison"
        ),
        "metric_ranges": metric_ranges(rows),
        "rows": rows,
    }
    (output_dir / "sphere_mie_full_na_sweep_summary.json").write_text(json.dumps(package, indent=2) + "\n", encoding="utf-8")
    write_markdown_summary(output_dir / "sphere_mie_full_na_sweep_summary.md", package)
    return 0 if args.allow_failed_cases or package["failed_count"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
