#!/usr/bin/env python3
"""Preliminary convergence scaffold for the sphere Mie full-NA PSF-bias route.

This script intentionally stays lightweight: it compares scalar review metrics
across grid/spectrum settings and does not write per-case NPZ field cubes.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import traceback
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import numpy as np


SCHEMA_VERSION = "sphere_mie_convergence_v1"
CONVERGENCE_METRICS = (
    "peakline_x_delta_um_vs_ideal",
    "self_peak_lateral_fwhm_delta_um_vs_ideal",
    "self_peak_lateral_centroid_delta_um_vs_ideal",
    "ideal_peak_plane_lateral_profile_relative_l2_vs_ideal",
    "normalized_image_relative_l2_vs_ideal",
)


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent if SCRIPT_DIR.name == "scripts" else SCRIPT_DIR
for path in (PROJECT_ROOT, SCRIPT_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import sphere_particle_sweep_runner as sphere_runner  # noqa: E402


@dataclass(frozen=True)
class GridSpec:
    config_id: str
    n_lambda: int
    n_z: int
    n_x: int
    n_bfp_dense: int

    @property
    def work_units(self) -> int:
        return int(self.n_lambda * self.n_z * self.n_x * max(1, self.n_bfp_dense))


def parse_grid_panel(text: str) -> list[GridSpec]:
    specs: list[GridSpec] = []
    for idx, chunk in enumerate(text.split(";")):
        chunk = chunk.strip()
        if not chunk:
            continue
        if ":" in chunk:
            config_id, values_text = chunk.split(":", 1)
            config_id = config_id.strip()
        else:
            config_id = f"config_{idx + 1}"
            values_text = chunk
        values = [int(v.strip()) for v in values_text.split(",") if v.strip()]
        if len(values) != 4:
            raise ValueError(
                "grid-panel entries must be config_id:n_lambda,n_z,n_x,n_bfp_dense "
                f"or n_lambda,n_z,n_x,n_bfp_dense; got {chunk!r}"
            )
        specs.append(GridSpec(config_id, *values))
    if len(specs) < 2:
        raise ValueError("grid-panel must contain at least two configurations")
    if len({spec.config_id for spec in specs}) != len(specs):
        raise ValueError("grid-panel config_id values must be unique")
    return specs


def finite_or_none(value):
    return sphere_runner.finite_or_none(value)


def convergence_args_for(args: argparse.Namespace, spec: GridSpec) -> SimpleNamespace:
    return SimpleNamespace(
        lambda0_nm=args.lambda0_nm,
        fwhm_nm=args.fwhm_nm,
        n_lambda=spec.n_lambda,
        z_span_um=args.z_span_um,
        n_z=spec.n_z,
        x_span_um=args.x_span_um,
        n_x=spec.n_x,
        n_bfp_dense=spec.n_bfp_dense,
        particle_material=args.particle_material,
        medium_material=args.medium_material,
        amp_component=args.amp_component,
        strict_material_range=args.strict_material_range,
    )


def solve_sphere_case(solver, args: argparse.Namespace, spec: GridSpec, na: float, diameter_nm: float) -> dict:
    run_args = convergence_args_for(args, spec)
    source = solver.SourceConfig(run_args.lambda0_nm, run_args.fwhm_nm, run_args.n_lambda)
    grid = solver.GridConfig(
        run_args.z_span_um,
        run_args.n_z,
        run_args.x_span_um,
        run_args.n_x,
        na,
        run_args.n_bfp_dense,
        max(5, min(11, run_args.n_bfp_dense)),
    )
    config = solver.SolverConfig(
        mode="full_na",
        particle_material=run_args.particle_material,
        medium_material=run_args.medium_material,
        diameter_nm=diameter_nm,
        eps=0.0,
        beta_deg=0.0,
        amp_component=run_args.amp_component,
        ideal=False,
        force_tmatrix=False,
        strict_material_range=run_args.strict_material_range,
    )
    ideal_reference = sphere_runner.ideal_reference_for(solver, run_args, na)
    result = solver.solve_oct_particle_response(source, grid, config)
    row = sphere_runner.extract_row(diameter_nm, na, result, ideal_reference)
    row.update(
        {
            "config_id": spec.config_id,
            "n_lambda": spec.n_lambda,
            "n_z": spec.n_z,
            "n_x": spec.n_x,
            "n_bfp_dense": spec.n_bfp_dense,
            "work_units": spec.work_units,
        }
    )
    return row


def failed_row(spec: GridSpec, diameter_nm: float, na: float, error: BaseException) -> dict:
    return {
        "config_id": spec.config_id,
        "diameter_nm": diameter_nm,
        "na": na,
        "status": "failed",
        "n_lambda": spec.n_lambda,
        "n_z": spec.n_z,
        "n_x": spec.n_x,
        "n_bfp_dense": spec.n_bfp_dense,
        "work_units": spec.work_units,
        "notes": f"{type(error).__name__}: {error}",
    }


def row_key(row: dict) -> tuple[float, float]:
    return (float(row["diameter_nm"]), float(row["na"]))


def attach_reference_drift(rows: list[dict], reference_config_id: str) -> dict:
    ok_rows = [row for row in rows if row.get("status") == "ok"]
    reference_by_case = {
        row_key(row): row for row in ok_rows if row.get("config_id") == reference_config_id
    }
    max_abs_by_metric = {metric: None for metric in CONVERGENCE_METRICS}
    comparable_count = 0
    missing_reference_count = 0
    for row in rows:
        if row.get("status") != "ok":
            continue
        row["reference_config_id"] = reference_config_id
        reference = reference_by_case.get(row_key(row))
        if reference is None:
            row["convergence_reference_available"] = False
            missing_reference_count += 1
            continue
        row["convergence_reference_available"] = True
        comparable_count += 1
        for metric in CONVERGENCE_METRICS:
            value = finite_or_none(row.get(metric))
            ref_value = finite_or_none(reference.get(metric))
            drift_key = f"{metric}_drift_vs_reference"
            abs_key = f"{metric}_abs_drift_vs_reference"
            if value is None or ref_value is None:
                row[drift_key] = None
                row[abs_key] = None
                continue
            drift = float(value - ref_value)
            row[drift_key] = drift
            row[abs_key] = abs(drift)
            current = max_abs_by_metric.get(metric)
            max_abs_by_metric[metric] = abs(drift) if current is None else max(current, abs(drift))
    return {
        "reference_config_id": reference_config_id,
        "comparable_count": comparable_count,
        "missing_reference_count": missing_reference_count,
        "max_abs_drift_by_metric": max_abs_by_metric,
    }


def decide_gate_status(package: dict, *, image_l2_tolerance: float, peakline_tolerance_um: float) -> str:
    if package.get("failed_count", 0) > 0:
        return "failed_cases_present"
    summary = package.get("convergence_reference_summary", {})
    max_abs = summary.get("max_abs_drift_by_metric", {}) or {}
    image_drift = finite_or_none(max_abs.get("normalized_image_relative_l2_vs_ideal"))
    peakline_drift = finite_or_none(max_abs.get("peakline_x_delta_um_vs_ideal"))
    if image_drift is None or peakline_drift is None:
        return "insufficient_comparable_metrics"
    if image_drift <= image_l2_tolerance and peakline_drift <= peakline_tolerance_um:
        return "preliminary_convergence_pass_not_paper_safe"
    return "preliminary_convergence_attention_not_paper_safe"


def metric_ranges(rows: list[dict]) -> dict:
    keys = list(CONVERGENCE_METRICS)
    keys += [f"{metric}_abs_drift_vs_reference" for metric in CONVERGENCE_METRICS]
    out = {}
    for key in keys:
        vals = []
        for row in rows:
            value = finite_or_none(row.get(key))
            if value is not None:
                vals.append(value)
        out[key] = [float(min(vals)), float(max(vals))] if vals else None
    return out


def write_csv(path: Path, rows: list[dict]) -> None:
    keys: list[str] = []
    for row in rows:
        for key in row:
            if key not in keys:
                keys.append(key)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(path: Path, package: dict) -> None:
    lines = [
        "# Sphere Mie Convergence Summary",
        "",
        f"- schema_version: `{package.get('schema_version')}`",
        f"- convergence_status: `{package.get('convergence_status')}`",
        f"- paper_safety_status: `{package.get('paper_safety_status')}`",
        f"- reference_config_id: `{package.get('reference_config_id')}`",
        f"- ok_count: `{package.get('ok_count')}`",
        f"- failed_count: `{package.get('failed_count')}`",
        "",
        "## Drift Ranges",
        "",
    ]
    for key, value in (package.get("metric_ranges", {}) or {}).items():
        if key.endswith("_abs_drift_vs_reference"):
            lines.append(f"- {key}: `{value}`")
    lines += [
        "",
        "## Rows",
        "",
        "| config_id | diameter_nm | na | image_l2_vs_ideal | image_l2_abs_drift | peakline_abs_drift_um |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in package.get("rows", []):
        lines.append(
            "| {config_id} | {diameter_nm} | {na} | {image_l2} | {image_drift} | {peakline_drift} |".format(
                config_id=row.get("config_id"),
                diameter_nm=row.get("diameter_nm"),
                na=row.get("na"),
                image_l2=row.get("normalized_image_relative_l2_vs_ideal"),
                image_drift=row.get("normalized_image_relative_l2_vs_ideal_abs_drift_vs_reference"),
                peakline_drift=row.get("peakline_x_delta_um_vs_ideal_abs_drift_vs_reference"),
            )
        )
    lines += [
        "",
        "## Interpretation",
        "",
        "This is a numerical-convergence scaffold for the sphere Mie full-NA PSF-bias trend.",
        "It is not a paper-safe device-level OCT conclusion.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a preliminary sphere Mie PSF-bias convergence panel.")
    parser.add_argument("--project-root", default=str(PROJECT_ROOT))
    parser.add_argument("--output-dir", default=str(PROJECT_ROOT / "reports" / "sphere_mie_convergence"))
    parser.add_argument("--diameters", default="200,500,1000")
    parser.add_argument("--na-values", default="0.05")
    parser.add_argument("--grid-panel", default="coarse:21,201,61,31;reference:41,401,81,41")
    parser.add_argument("--reference-config-id", default=None)
    parser.add_argument("--particle-material", default="TiO2-anatase")
    parser.add_argument("--medium-material", default="PDMS")
    parser.add_argument("--amp-component", default="S22")
    parser.add_argument("--lambda0-nm", type=float, default=855.0)
    parser.add_argument("--fwhm-nm", type=float, default=56.0)
    parser.add_argument("--z-span-um", type=float, default=40.0)
    parser.add_argument("--x-span-um", type=float, default=8.0)
    parser.add_argument("--image-l2-tolerance", type=float, default=0.05)
    parser.add_argument("--peakline-tolerance-um", type=float, default=0.25)
    parser.add_argument("--strict-material-range", action="store_true")
    parser.add_argument("--allow-failed-cases", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    project_root = Path(args.project_root).resolve()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    solver = sphere_runner.load_solver(project_root)
    diameters = sphere_runner.parse_float_list(args.diameters)
    na_values = sphere_runner.parse_float_list(args.na_values)
    grid_specs = parse_grid_panel(args.grid_panel)
    reference_config_id = args.reference_config_id or grid_specs[-1].config_id
    if reference_config_id not in {spec.config_id for spec in grid_specs}:
        raise ValueError(f"reference-config-id {reference_config_id!r} is not present in grid-panel")
    rows: list[dict] = []
    for spec in grid_specs:
        for na in na_values:
            for diameter_nm in diameters:
                try:
                    rows.append(solve_sphere_case(solver, args, spec, na, diameter_nm))
                except Exception as exc:
                    rows.append(failed_row(spec, diameter_nm, na, exc))
                    error_path = output_dir / f"{spec.config_id}_na{na:g}_d{int(round(diameter_nm)):04d}nm_ERROR.txt".replace(
                        ".", "p"
                    )
                    error_path.write_text(
                        "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
                        encoding="utf-8",
                    )
    reference_summary = attach_reference_drift(rows, reference_config_id)
    ok_count = sum(1 for row in rows if row.get("status") == "ok")
    failed_count = len(rows) - ok_count
    package = {
        "schema_version": SCHEMA_VERSION,
        "report_kind": "sphere_mie_convergence",
        "diameter_nm_values": diameters,
        "na_values": na_values,
        "grid_panel": [spec.__dict__ for spec in grid_specs],
        "reference_config_id": reference_config_id,
        "case_count": len(rows),
        "ok_count": ok_count,
        "failed_count": failed_count,
        "convergence_reference_summary": reference_summary,
        "metric_ranges": metric_ranges(rows),
        "interpretation_status": "preliminary_numerical_convergence_scaffold",
        "paper_safety_status": "not_paper_safe",
        "rows": rows,
    }
    package["convergence_status"] = decide_gate_status(
        package,
        image_l2_tolerance=args.image_l2_tolerance,
        peakline_tolerance_um=args.peakline_tolerance_um,
    )
    (output_dir / "sphere_mie_convergence_summary.json").write_text(
        json.dumps(package, indent=2) + "\n",
        encoding="utf-8",
    )
    write_csv(output_dir / "sphere_mie_convergence_summary.csv", rows)
    write_markdown(output_dir / "sphere_mie_convergence_summary.md", package)
    return 0 if args.allow_failed_cases or failed_count == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
