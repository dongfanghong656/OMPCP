#!/usr/bin/env python3
"""Run a 200-1000 nm particle-size sweep against the current OCT solver stack.

This runner is intentionally a sweep/smoke harness, not a proof that the
low-NA separable baseline captures particle-aware lateral PSF distortion.
For `mode=low_na`, lateral response remains the Gaussian system surrogate.
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


def default_project_root_for(script_dir: Path) -> Path:
    """Return the project root for repo scripts/ and flat numbered bundles."""
    script_dir = Path(script_dir).resolve()
    return script_dir.parent if script_dir.name == "scripts" else script_dir


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = default_project_root_for(SCRIPT_DIR)
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from physics.tmatrix_backend_contract import TMATRIX_BACKEND_IDS
from physics.tmatrix_backend_registry import (
    build_backend_provenance,
    require_backend_available,
    write_backend_provenance,
)

SWEEP_SCHEMA_VERSION = "particle_size_sweep_v1"
LOW_NA_LATERAL_SCOPE_NOTE = (
    "For mode=low_na, this sweep is an axial spectral/Mie smoke harness: "
    "the lateral profile is still the Gaussian system surrogate, so it must "
    "not be used as evidence that particle scattering leaves lateral PSF "
    "shape unchanged."
)


def parse_diameters(text: str) -> list[float]:
    """Parse a comma list or start:step:stop notation."""
    text = text.strip()
    if ":" in text and "," not in text:
        parts = [float(part) for part in text.split(":")]
        if len(parts) != 3:
            raise ValueError("Range notation must be start:step:stop, e.g. 200:50:1000")
        start, step, stop = parts
        if step <= 0.0:
            raise ValueError("step must be positive")
        values = []
        value = start
        while value <= stop + 1e-9:
            values.append(float(value))
            value += step
        return values

    values = []
    for chunk in text.replace(";", ",").split(","):
        chunk = chunk.strip()
        if chunk:
            values.append(float(chunk))
    if not values:
        raise ValueError("No diameters were provided.")
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
    raise FileNotFoundError(
        "Cannot find an OCT solver module. Checked: "
        + ", ".join(str(candidate) for candidate in candidates)
    )


def load_solver(project_root: Path):
    solver_path = resolve_solver_path(project_root)
    for path in (project_root, solver_path.parent):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))
    spec = importlib.util.spec_from_file_location("oct_nonspherical_psf_solver_runtime", solver_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import solver from {solver_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    # Some round6 bundle loaders expect the public module alias to exist.
    sys.modules.setdefault("oct_nonspherical_psf_solver", module)
    spec.loader.exec_module(module)
    return module


def json_default(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, complex):
        return {"real": float(np.real(value)), "imag": float(np.imag(value))}
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def compact_json_result(result: dict) -> dict:
    array_keys = {
        "x_um",
        "opd_um",
        "geometric_roundtrip_um",
        "single_pass_geometric_depth_um",
        "double_pass_geometric_depth_um",
        "optical_roundtrip_path_um",
        "single_pass_depth_from_reference_n_um",
        "double_pass_depth_from_reference_n_um",
        "lambda_nm",
        "sample_arm_spectral_cube",
        "axial_field",
        "raw_envelope_xz",
        "raw_intensity_xz",
        "envelope_xz",
        "intensity_xz",
        "centerline_axial_envelope",
        "centerline_axial_intensity",
        "peakline_axial_envelope",
        "peakline_axial_intensity",
        "centerline_raw_axial_envelope",
        "centerline_raw_axial_intensity",
        "peakline_raw_axial_envelope",
        "peakline_raw_axial_intensity",
    }
    return {key: value for key, value in result.items() if key not in array_keys}


def save_npz(path: Path, result: dict) -> None:
    keys = [
        "x_um",
        "opd_um",
        "geometric_roundtrip_um",
        "single_pass_geometric_depth_um",
        "double_pass_geometric_depth_um",
        "optical_roundtrip_path_um",
        "single_pass_depth_from_reference_n_um",
        "double_pass_depth_from_reference_n_um",
        "lambda_nm",
        "sample_arm_spectral_cube",
        "envelope_xz",
        "intensity_xz",
        "raw_envelope_xz",
        "raw_intensity_xz",
        "centerline_axial_envelope",
        "centerline_axial_intensity",
        "peakline_axial_envelope",
        "peakline_axial_intensity",
        "centerline_raw_axial_envelope",
        "centerline_raw_axial_intensity",
        "peakline_raw_axial_envelope",
        "peakline_raw_axial_intensity",
    ]
    payload = {key: np.asarray(result[key]) for key in keys if key in result}
    np.savez_compressed(path, **payload)


def _finite_or_none(value):
    if value is None:
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return numeric if np.isfinite(numeric) else None


def extract_row(diameter_nm: float, args: argparse.Namespace, result: dict) -> dict:
    metrics = result.get("axial_intensity_metrics") or {}
    sidelobe_to_main_db = _finite_or_none(metrics.get("sidelobe_to_main_db", metrics.get("psr_db")))
    main_to_sidelobe_rejection_db = _finite_or_none(metrics.get("main_to_sidelobe_rejection_db"))
    if main_to_sidelobe_rejection_db is None and sidelobe_to_main_db is not None:
        main_to_sidelobe_rejection_db = -sidelobe_to_main_db
    return {
        "diameter_nm": diameter_nm,
        "status": "ok",
        "mode_requested": args.mode,
        "mode_returned": result.get("mode"),
        "tmatrix_used": result.get("tmatrix_used"),
        "paper_safe": result.get("paper_safe"),
        "fwhm_opd_um": metrics.get("fwhm_opd_um"),
        "peak_opd_um": metrics.get("peak_opd_um"),
        "centroid_opd_um": metrics.get("centroid_opd_um"),
        "psr_definition": metrics.get("psr_definition", "sidelobe_to_main_db"),
        "sidelobe_to_main_db": sidelobe_to_main_db,
        "main_to_sidelobe_rejection_db": main_to_sidelobe_rejection_db,
        "strongest_sidelobe_value": metrics.get("strongest_sidelobe_value"),
        "sidelobe_energy_fraction": metrics.get("sidelobe_energy_fraction"),
        "raw_peak_intensity": result.get("raw_peak_intensity"),
        "raw_peak_envelope": result.get("raw_peak_envelope"),
        "peakline_x_um": result.get("peakline_x_um"),
        "lateral_response_model": result.get("lateral_response_model"),
        "particle_lateral_scattering_enters_profile": result.get("particle_lateral_scattering_enters_profile"),
        "na": args.na,
        "eps": args.eps,
        "beta_deg": args.beta_deg,
        "particle_material": args.particle_material,
        "medium_material": args.medium_material,
        "notes": result.get("baseline_scope_note") or result.get("approximation_label") or "",
    }


def failed_row(diameter_nm: float, args: argparse.Namespace, error: BaseException) -> dict:
    row = {
        key: ""
        for key in (
            "mode_returned",
            "tmatrix_used",
            "paper_safe",
            "fwhm_opd_um",
            "peak_opd_um",
            "centroid_opd_um",
            "psr_definition",
            "sidelobe_to_main_db",
            "main_to_sidelobe_rejection_db",
            "strongest_sidelobe_value",
            "sidelobe_energy_fraction",
            "raw_peak_intensity",
            "raw_peak_envelope",
            "peakline_x_um",
            "lateral_response_model",
            "particle_lateral_scattering_enters_profile",
        )
    }
    row.update(
        {
            "diameter_nm": diameter_nm,
            "status": "failed",
            "mode_requested": args.mode,
            "na": args.na,
            "eps": args.eps,
            "beta_deg": args.beta_deg,
            "particle_material": args.particle_material,
            "medium_material": args.medium_material,
            "notes": f"{type(error).__name__}: {error}",
        }
    )
    return row


def write_summary_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _safe_float_values(rows: list[dict], key: str) -> list[float]:
    values = []
    for row in rows:
        value = row.get(key)
        if value in ("", None):
            continue
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            continue
        if np.isfinite(numeric):
            values.append(numeric)
    return values


def _min_max_or_none(rows: list[dict], key: str) -> list[float] | None:
    values = _safe_float_values(rows, key)
    if not values:
        return None
    return [float(min(values)), float(max(values))]


def build_particle_size_sweep_package(args: argparse.Namespace, rows: list[dict]) -> dict:
    """Build the machine-readable evidence package for a particle-size sweep."""
    diameter_values = [float(row["diameter_nm"]) for row in rows if row.get("diameter_nm") not in ("", None)]
    ok_rows = [row for row in rows if row.get("status") == "ok"]
    failed_rows = [row for row in rows if row.get("status") != "ok"]
    mode_requested = getattr(args, "mode", "unknown")
    is_low_na_surrogate = str(mode_requested).startswith("low_na")
    failed_count = len(failed_rows)
    if rows and failed_count == len(rows):
        sweep_status = "all_failed"
        recommended_next_action = "inspect_particle_size_sweep_failures"
    elif failed_count:
        sweep_status = "partial_failures"
        recommended_next_action = "inspect_particle_size_sweep_failures"
    elif is_low_na_surrogate:
        sweep_status = "complete"
        recommended_next_action = "use_sweep_as_axial_spectral_smoke_not_lateral_truth"
    else:
        sweep_status = "complete"
        recommended_next_action = "compare_particle_size_sweep_against_bridge_or_measurement_protocol"
    backend_provenance = getattr(args, "_backend_provenance", None) or {}
    backend_provenance_path = getattr(args, "_backend_provenance_path", None)
    return {
        "report_version_tag": "round6p1",
        "report_kind": "particle_size_sweep",
        "sweep_schema_version": SWEEP_SCHEMA_VERSION,
        "sweep_status": sweep_status,
        "recommended_next_action": recommended_next_action,
        "particle_size_sweep_guidance_status": "explicit_report_used",
        "mode_requested": mode_requested,
        "diameter_nm_values": diameter_values,
        "diameter_range_nm": [float(min(diameter_values)), float(max(diameter_values))] if diameter_values else None,
        "sweep_case_count": len(rows),
        "ok_count": len(ok_rows),
        "failed_count": failed_count,
        "na": getattr(args, "na", None),
        "eps": getattr(args, "eps", None),
        "beta_deg": getattr(args, "beta_deg", None),
        "particle_material": getattr(args, "particle_material", None),
        "medium_material": getattr(args, "medium_material", None),
        "lambda0_nm": getattr(args, "lambda0_nm", None),
        "fwhm_nm": getattr(args, "fwhm_nm", None),
        "n_lambda": getattr(args, "n_lambda", None),
        "n_z": getattr(args, "n_z", None),
        "n_x": getattr(args, "n_x", None),
        "tmatrix_backend_requested_id": backend_provenance.get(
            "requested_backend_id",
            getattr(args, "tmatrix_backend", "auto"),
        ),
        "tmatrix_backend_available": backend_provenance.get("backend_available"),
        "tmatrix_backend_id": backend_provenance.get("backend_id"),
        "tmatrix_backend_library_path": backend_provenance.get("library_path"),
        "tmatrix_backend_reason": backend_provenance.get("reason"),
        "tmatrix_backend_provenance_path": str(backend_provenance_path) if backend_provenance_path else None,
        "tmatrix_backend_provenance": backend_provenance or None,
        "particle_lateral_scattering_scope_note": (
            LOW_NA_LATERAL_SCOPE_NOTE
            if is_low_na_surrogate
            else "The selected mode may include particle-aware lateral structure; interpret against the solver mode contract."
        ),
        "metric_ranges": {
            "fwhm_opd_um": _min_max_or_none(ok_rows, "fwhm_opd_um"),
            "peak_opd_um": _min_max_or_none(ok_rows, "peak_opd_um"),
            "centroid_opd_um": _min_max_or_none(ok_rows, "centroid_opd_um"),
            "main_to_sidelobe_rejection_db": _min_max_or_none(ok_rows, "main_to_sidelobe_rejection_db"),
            "raw_peak_intensity": _min_max_or_none(ok_rows, "raw_peak_intensity"),
            "peakline_x_um": _min_max_or_none(ok_rows, "peakline_x_um"),
        },
        "rows": rows,
    }


def render_particle_size_sweep_markdown(package: dict) -> str:
    lines = [
        "# Round 6p1 Particle Size Sweep",
        "",
        f"Status: `{package.get('sweep_status')}`",
        f"Recommended next action: `{package.get('recommended_next_action')}`",
        f"Mode: `{package.get('mode_requested')}`",
        f"Diameter range (nm): `{package.get('diameter_range_nm')}`",
        f"Cases: `{package.get('ok_count')}` ok / `{package.get('failed_count')}` failed",
        "",
        "Scope note:",
        package.get("particle_lateral_scattering_scope_note", ""),
        "",
        "| diameter_nm | status | fwhm_opd_um | peak_opd_um | centroid_opd_um | main_to_sidelobe_rejection_db | peakline_x_um |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in package.get("rows", []):
        lines.append(
            "| "
            + " | ".join(
                str(row.get(key, ""))
                for key in (
                    "diameter_nm",
                    "status",
                    "fwhm_opd_um",
                    "peak_opd_um",
                    "centroid_opd_um",
                    "main_to_sidelobe_rejection_db",
                    "peakline_x_um",
                )
            )
            + " |"
        )
    return "\n".join(lines)


def plot_metric(rows: list[dict], key: str, ylabel: str, output_path: Path) -> None:
    try:  # Plotting is useful, but the sweep CSV/NPZ artifacts are the contract.
        import matplotlib.pyplot as plt
    except Exception:  # pragma: no cover - environment-dependent optional path
        return
    ok_rows = [row for row in rows if row.get("status") == "ok" and row.get(key) not in ("", None)]
    if not ok_rows:
        return
    x = [float(row["diameter_nm"]) for row in ok_rows]
    y = [float(row[key]) for row in ok_rows]
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.plot(x, y, marker="o")
    ax.set_xlabel("diameter (nm)")
    ax.set_ylabel(ylabel)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a particle-size sweep for the OCT Mie/T-matrix PSF solver.")
    parser.add_argument("--project-root", default=str(PROJECT_ROOT))
    parser.add_argument("--output-dir", default=str(PROJECT_ROOT / "reports" / "particle_size_sweep"))
    parser.add_argument("--diameters", default="200,300,400,500,600,700,800,900,1000")
    parser.add_argument("--no-plots", action="store_true", help="Write CSV/NPZ/JSON only; skip matplotlib plots.")
    parser.add_argument(
        "--allow-failed-cases",
        action="store_true",
        help="Return exit 0 even when one or more sweep cases fail. By default failures make the CLI fail.",
    )
    parser.add_argument("--mode", default="low_na")
    parser.add_argument("--particle-material", default="TiO2-anatase")
    parser.add_argument("--medium-material", default="PDMS")
    parser.add_argument("--eps", type=float, default=0.0)
    parser.add_argument("--beta-deg", type=float, default=0.0)
    parser.add_argument("--amp-component", default="S22")
    parser.add_argument("--incident-mode", default="linear_x")
    parser.add_argument("--detection-mode", default="co_pol")
    parser.add_argument("--lambda0-nm", type=float, default=855.0)
    parser.add_argument("--fwhm-nm", type=float, default=56.0)
    parser.add_argument("--n-lambda", type=int, default=201)
    parser.add_argument("--z-span-um", type=float, default=40.0)
    parser.add_argument("--n-z", type=int, default=2001)
    parser.add_argument("--x-span-um", type=float, default=8.0)
    parser.add_argument("--n-x", type=int, default=129)
    parser.add_argument("--na", type=float, default=0.05)
    parser.add_argument("--n-bfp-dense", type=int, default=129)
    parser.add_argument("--n-bfp-sparse", type=int, default=11)
    parser.add_argument("--strict-material-range", action="store_true")
    parser.add_argument("--force-tmatrix", action="store_true")
    parser.add_argument("--lib-path")
    parser.add_argument(
        "--tmatrix-backend",
        default="auto",
        choices=list(TMATRIX_BACKEND_IDS),
        help="Select the T-matrix backend contract to probe before the sweep.",
    )
    parser.add_argument(
        "--tmatrix-lib-path",
        help="Alias for --lib-path used by the backend registry/provenance contract.",
    )
    parser.add_argument(
        "--require-tmatrix-backend",
        action="store_true",
        help="Fail the sweep structurally when the requested T-matrix backend is unavailable.",
    )
    parser.add_argument(
        "--backend-provenance-out",
        help="Write T-matrix backend provenance to this JSON path.",
    )
    parser.add_argument("--second-order-model", default="tensor_closure")
    parser.add_argument("--mu2-wavelength-model", default="frozen_at_lambda0")
    parser.add_argument("--lateral-shift-model", default="none")
    parser.add_argument("--lateral-shift-coupling", default="envelope_only")
    parser.add_argument("--lateral-shift-impl", default="interp")
    parser.add_argument("--coefficient-map-model-id", default="identity_slice_projected_rendered_basis")
    parser.add_argument("--coefficient-map-runtime-mode", default="native_branch_assembly")
    parser.add_argument("--coefficient-map-artifact-path")
    parser.add_argument("--rendered-basis-shift-target", default="baseline_envelope_ratio")
    return parser


def effective_tmatrix_library_path(args: argparse.Namespace) -> str | None:
    return getattr(args, "tmatrix_lib_path", None) or getattr(args, "lib_path", None)


def prepare_backend_provenance(
    args: argparse.Namespace,
    output_dir: Path,
    *,
    write_artifacts: bool,
) -> tuple[dict, Path | None]:
    library_path = effective_tmatrix_library_path(args)
    provenance = build_backend_provenance(
        getattr(args, "tmatrix_backend", "auto"),
        library_path=library_path,
    )
    provenance_path = None
    if write_artifacts:
        provenance_path = Path(getattr(args, "backend_provenance_out", "") or output_dir / "backend_provenance.json")
        write_backend_provenance(provenance_path, provenance)
    args._backend_provenance = provenance
    args._backend_provenance_path = provenance_path
    return provenance, provenance_path


def backend_requirement_failed_rows(
    diameters: list[float],
    args: argparse.Namespace,
    error: Exception,
) -> list[dict]:
    rows = []
    for diameter_nm in diameters:
        row = failed_row(diameter_nm, args, error)
        row["failure_stage"] = "tmatrix_backend_preflight"
        rows.append(row)
    return rows


def run_particle_size_sweep(
    args: argparse.Namespace,
    *,
    solver=None,
    write_artifacts: bool = True,
    make_plots: bool | None = None,
) -> tuple[dict, str]:
    project_root = Path(args.project_root).resolve()
    output_dir = Path(args.output_dir).resolve()
    if write_artifacts:
        output_dir.mkdir(parents=True, exist_ok=True)

    if solver is None:
        solver = load_solver(project_root)
    diameters = parse_diameters(args.diameters)
    provenance, _provenance_path = prepare_backend_provenance(args, output_dir, write_artifacts=write_artifacts)
    try:
        selected_backend = getattr(args, "tmatrix_backend", "auto")
        if getattr(args, "require_tmatrix_backend", False) or selected_backend != "auto":
            require_backend_available(provenance)
    except RuntimeError as error:
        rows = backend_requirement_failed_rows(diameters, args, error)
        package = build_particle_size_sweep_package(args, rows)
        markdown = render_particle_size_sweep_markdown(package)
        if write_artifacts:
            write_summary_csv(output_dir / "sweep_summary.csv", rows)
            (output_dir / "particle_size_sweep_summary.json").write_text(
                json.dumps(package, indent=2) + "\n",
                encoding="utf-8",
            )
            (output_dir / "particle_size_sweep_summary.md").write_text(markdown + "\n", encoding="utf-8")
            (output_dir / "tmatrix_backend_preflight_ERROR.txt").write_text(str(error) + "\n", encoding="utf-8")
        return package, markdown

    rows: list[dict] = []
    for diameter_nm in diameters:
        stem = f"{args.mode}_d{int(round(diameter_nm)):04d}nm"
        try:
            source = solver.SourceConfig(lambda0_nm=args.lambda0_nm, fwhm_nm=args.fwhm_nm, n_lambda=args.n_lambda)
            grid = solver.GridConfig(
                z_span_um=args.z_span_um,
                n_z=args.n_z,
                x_span_um=args.x_span_um,
                n_x=args.n_x,
                na=args.na,
                n_bfp_dense=args.n_bfp_dense,
                n_bfp_sparse=args.n_bfp_sparse,
            )
            config = solver.SolverConfig(
                mode=args.mode,
                particle_material=args.particle_material,
                medium_material=args.medium_material,
                diameter_nm=diameter_nm,
                eps=args.eps,
                beta_deg=args.beta_deg,
                amp_component=args.amp_component,
                ideal=False,
                force_tmatrix=args.force_tmatrix,
                library_path=effective_tmatrix_library_path(args),
                strict_material_range=args.strict_material_range,
                incident_mode=args.incident_mode,
                detection_mode=args.detection_mode,
                second_order_model=args.second_order_model,
                mu2_wavelength_model=args.mu2_wavelength_model,
                lateral_shift_model=args.lateral_shift_model,
                lateral_shift_coupling=args.lateral_shift_coupling,
                lateral_shift_impl=args.lateral_shift_impl,
                coefficient_map_model_id=args.coefficient_map_model_id,
                coefficient_map_runtime_mode=args.coefficient_map_runtime_mode,
                coefficient_map_artifact_path=args.coefficient_map_artifact_path,
                rendered_basis_shift_target=args.rendered_basis_shift_target,
            )
            result = solver.solve_oct_particle_response(source, grid, config)
            if write_artifacts:
                save_npz(output_dir / f"{stem}.npz", result)
                (output_dir / f"{stem}.json").write_text(
                    json.dumps(compact_json_result(result), indent=2, default=json_default) + "\n",
                    encoding="utf-8",
                )
            rows.append(extract_row(diameter_nm, args, result))
            if write_artifacts:
                print(f"OK diameter={diameter_nm:g} nm -> {stem}")
        except Exception as error:
            rows.append(failed_row(diameter_nm, args, error))
            if write_artifacts:
                (output_dir / f"{stem}_ERROR.txt").write_text(
                    "".join(traceback.format_exception(type(error), error, error.__traceback__)),
                    encoding="utf-8",
                )
                print(f"FAILED diameter={diameter_nm:g} nm: {type(error).__name__}: {error}", file=sys.stderr)

    package = build_particle_size_sweep_package(args, rows)
    markdown = render_particle_size_sweep_markdown(package)
    if write_artifacts:
        write_summary_csv(output_dir / "sweep_summary.csv", rows)
        (output_dir / "particle_size_sweep_summary.json").write_text(
            json.dumps(package, indent=2) + "\n",
            encoding="utf-8",
        )
        (output_dir / "particle_size_sweep_summary.md").write_text(markdown + "\n", encoding="utf-8")
    should_plot = (not args.no_plots) if make_plots is None else make_plots
    if write_artifacts and should_plot:
        plot_metric(rows, "raw_peak_intensity", "raw peak intensity (arb.)", output_dir / "raw_peak_intensity_vs_diameter.png")
        plot_metric(rows, "fwhm_opd_um", "axial FWHM in OPD (um)", output_dir / "axial_fwhm_opd_vs_diameter.png")
        plot_metric(rows, "peak_opd_um", "peak OPD (um)", output_dir / "peak_opd_vs_diameter.png")
        plot_metric(rows, "centroid_opd_um", "centroid OPD (um)", output_dir / "centroid_opd_vs_diameter.png")
        plot_metric(rows, "main_to_sidelobe_rejection_db", "main-to-sidelobe rejection (dB)", output_dir / "main_to_sidelobe_rejection_vs_diameter.png")
        plot_metric(rows, "peakline_x_um", "peakline x (um)", output_dir / "peakline_x_vs_diameter.png")
    return package, markdown


def exit_code_for_sweep_package(package: dict, *, allow_failed_cases: bool = False) -> int:
    failed_count = int(package.get("failed_count") or 0)
    return 2 if failed_count and not allow_failed_cases else 0


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    package, _markdown = run_particle_size_sweep(args, write_artifacts=True)
    print(f"Wrote {Path(args.output_dir).resolve() / 'sweep_summary.csv'}")
    failed_count = int(package.get("failed_count") or 0)
    exit_code = exit_code_for_sweep_package(package, allow_failed_cases=args.allow_failed_cases)
    if exit_code:
        print(
            f"Particle-size sweep had {failed_count} failed case(s); "
            "use --allow-failed-cases only when this is an expected diagnostic artifact.",
            file=sys.stderr,
        )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
