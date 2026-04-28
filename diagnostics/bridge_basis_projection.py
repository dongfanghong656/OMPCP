from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from diagnostics._runtime import (
    REPORTS_DIR,
    load_module,
    load_solver_module,
    probe_backend_or_write_skip,
    resolve_script_path,
)
from solvers import coefficient_path_bundle as _COEFF_BUNDLE_CORE


VALIDATOR_PATH = resolve_script_path(
    "validate_oct_nonspherical_psf_solver.py",
    "04_validate_oct_nonspherical_psf_solver.py",
)
BASIS_PROJECTION_PATH = resolve_script_path(
    "14_bridge_basis_projection_diagnostics.py",
    "06_bridge_basis_projection_diagnostics.py",
)
BRIDGE_PATH = resolve_script_path(
    "10_vector_pupil_overlap_bridge.py",
    "02_vector_pupil_overlap_bridge.py",
)


def _load_solver_module():
    return load_solver_module()


_SOLVER = _load_solver_module()
_load_module = load_module


def _relative_l2(reference: np.ndarray, estimate: np.ndarray) -> float:
    return float(np.linalg.norm(estimate - reference) / (np.linalg.norm(reference) + 1e-30))


def _get_nested(mapping: dict[str, Any], *candidates: str) -> Any:
    for candidate in candidates:
        if candidate in mapping:
            return mapping[candidate]
    diagnostics = mapping.get("diagnostics")
    if isinstance(diagnostics, dict):
        for candidate in candidates:
            if candidate in diagnostics:
                return diagnostics[candidate]
    return None


@dataclass
class ProjectionFamily:
    name: str
    basis_labels: tuple[str, ...]
    basis_matrix: np.ndarray


def _case_context(
    validator,
    case_definition: dict[str, Any],
    tmatrix_path: str,
    *,
    lateral_slice_axis: str | None = None,
):
    source = validator.SourceConfig(**case_definition["source"])
    grid = validator.GridConfig(**case_definition["grid"])
    solver_kwargs = dict(case_definition["solver"])
    solver_kwargs["library_path"] = tmatrix_path
    if lateral_slice_axis is not None:
        solver_kwargs["lateral_slice_axis"] = lateral_slice_axis
    solver = validator.SolverConfig(mode=validator.VECTOR_BRIDGE_MODE, **solver_kwargs)
    return source, grid, solver


def _build_bridge_lateral_field(
    validator,
    bridge_module,
    case_definition: dict[str, Any],
    tmatrix_path: str,
    *,
    lateral_slice_axis: str | None = None,
) -> dict[str, Any]:
    source, grid, solver = _case_context(
        validator,
        case_definition,
        tmatrix_path,
        lateral_slice_axis=lateral_slice_axis,
    )
    api = bridge_module._solver_api()
    lambda_nm, source_power = api.source_spectrum_lambda(source.lambda0_nm, source.fwhm_nm, source.n_lambda)
    x_um = np.linspace(-0.5 * grid.x_span_um, 0.5 * grid.x_span_um, grid.n_x)
    opd_um = np.linspace(-grid.z_span_um, grid.z_span_um, grid.n_z)
    geometry = api.derive_na_geometry_series(lambda_nm, solver.medium_material, grid.na)
    bundle = bridge_module._build_bridge_bfp_field(
        diameter_nm=solver.diameter_nm,
        eps=solver.eps,
        beta_deg=solver.beta_deg,
        particle_material=solver.particle_material,
        medium_material=solver.medium_material,
        lambda_nm=lambda_nm,
        sin_theta_max=geometry["sin_theta_max"],
        n_bfp_dense=grid.n_bfp_dense,
        n_bfp_sparse=grid.n_bfp_sparse,
        incident_mode=solver.incident_mode,
        detection_mode=solver.detection_mode,
        library_path=tmatrix_path,
    )
    lateral_slice_axis = str(getattr(solver, "lateral_slice_axis", "x")).strip().lower()
    lateral_field = api.pupil_field_to_lateral_line(
        bundle,
        lambda_nm,
        x_um,
        geometry["sin_theta_max"],
        solver.medium_material,
        lateral_slice_axis=lateral_slice_axis,
    )
    spectral_cube = source_power[:, None] * lateral_field
    field_xz = api.spectral_cube_to_xz(lambda_nm, spectral_cube, opd_um, solver.medium_material)
    raw_envelope_xz = np.abs(field_xz)
    raw_intensity_xz = raw_envelope_xz**2
    envelope_xz, _ = api.normalize_intensity(raw_envelope_xz, return_scale=True)
    intensity_xz, _ = api.normalize_intensity(raw_intensity_xz, return_scale=True)
    axial_views = api.build_full_na_axial_views(x_um, opd_um, raw_intensity_xz, raw_envelope_xz)
    return {
        "source": source,
        "grid": grid,
        "solver": solver,
        "lateral_slice_axis": lateral_slice_axis,
        "lambda_nm": lambda_nm,
        "source_power": source_power,
        "x_um": x_um,
        "opd_um": opd_um,
        "lateral_field": lateral_field,
        "field_xz": field_xz,
        "raw_intensity_xz": raw_intensity_xz,
        "intensity_xz": intensity_xz,
        "raw_envelope_xz": raw_envelope_xz,
        "envelope_xz": envelope_xz,
        "axial_views": axial_views,
        "peakline_x_um": float(axial_views["peakline_x_um"]),
        "centroid_opd_um": float(axial_views["peakline_axial_intensity_metrics"]["centroid_opd_um"]),
    }


def _build_projection_families(asym_result: dict[str, Any]) -> list[ProjectionFamily]:
    coefficient_bundle = _COEFF_BUNDLE_CORE.build_coefficient_path_bundle(asym_result)
    r0 = np.asarray(coefficient_bundle.field_basis_state.R0_x, dtype=np.complex128)
    r1 = np.asarray(coefficient_bundle.field_basis_state.R1_slice_x, dtype=np.complex128)
    r2 = np.asarray(coefficient_bundle.field_basis_state.R2_slice_x, dtype=np.complex128)
    families = [
        ProjectionFamily("R0", ("R0",), np.column_stack([r0])),
        ProjectionFamily("R0_plus_R2", ("R0", "R2"), np.column_stack([r0, r2])),
        ProjectionFamily("R0_plus_R1_plus_R2", ("R0", "R1", "R2"), np.column_stack([r0, r1, r2])),
    ]
    return families


def _build_projected_result(bridge_context: dict[str, Any], projected_lateral_field: np.ndarray) -> dict[str, Any]:
    validator = load_module(VALIDATOR_PATH, "round6p1_validator_projection_api")
    source_power = np.asarray(bridge_context["source_power"], dtype=float)
    lambda_nm = np.asarray(bridge_context["lambda_nm"], dtype=float)
    x_um = np.asarray(bridge_context["x_um"], dtype=float)
    opd_um = np.asarray(bridge_context["opd_um"], dtype=float)
    medium_material = bridge_context["solver"].medium_material
    field_xz = validator.solve_oct_particle_response(
        bridge_context["source"],
        bridge_context["grid"],
        bridge_context["solver"],
    )["field_xz"]
    api = load_module(BRIDGE_PATH, "round6_bridge_projection_api")._solver_api()
    projected_field_xz = api.spectral_cube_to_xz(lambda_nm, source_power[:, None] * projected_lateral_field, opd_um, medium_material)
    raw_envelope_xz = np.abs(projected_field_xz)
    raw_intensity_xz = raw_envelope_xz**2
    envelope_xz, _ = api.normalize_intensity(raw_envelope_xz, return_scale=True)
    intensity_xz, _ = api.normalize_intensity(raw_intensity_xz, return_scale=True)
    axial_views = api.build_full_na_axial_views(x_um, opd_um, raw_intensity_xz, raw_envelope_xz)
    return {
        "field_xz": projected_field_xz,
        "reference_field_xz": field_xz,
        "x_um": x_um,
        "opd_um": opd_um,
        "raw_intensity_xz": raw_intensity_xz,
        "intensity_xz": intensity_xz,
        "peakline_x_um": float(axial_views["peakline_x_um"]),
        "axial_intensity_metrics": axial_views["peakline_axial_intensity_metrics"],
        "raw_peak_intensity": float(axial_views["raw_peak_intensity"]),
    }


def _project_bridge_field(
    validator,
    bridge_context: dict[str, Any],
    families: list[ProjectionFamily],
) -> list[dict[str, Any]]:
    bridge_lateral_field = np.asarray(bridge_context["lateral_field"], dtype=np.complex128)
    bridge_snapshot = {
        "peakline_x_um": bridge_context["peakline_x_um"],
        "fwhm_opd_um": float(bridge_context["axial_views"]["peakline_axial_intensity_metrics"]["fwhm_opd_um"]),
        "psr_db": float(bridge_context["axial_views"]["peakline_axial_intensity_metrics"]["psr_db"]),
        "centroid_opd_um": bridge_context["centroid_opd_um"],
        "x_um": bridge_context["x_um"],
        "opd_um": bridge_context["opd_um"],
        "image": bridge_context["intensity_xz"],
        "raw_image": bridge_context["raw_intensity_xz"],
    }
    projections: list[dict[str, Any]] = []
    for family in families:
        projected_lateral_field = np.zeros_like(bridge_lateral_field, dtype=np.complex128)
        coeffs_per_k = np.zeros((bridge_lateral_field.shape[0], family.basis_matrix.shape[1]), dtype=np.complex128)
        for idx, bridge_row in enumerate(bridge_lateral_field):
            coeffs, *_ = np.linalg.lstsq(family.basis_matrix, bridge_row, rcond=None)
            coeffs_per_k[idx, :] = coeffs
            projected_lateral_field[idx, :] = family.basis_matrix @ coeffs

        projected_result = _build_projected_result(bridge_context, projected_lateral_field)
        diagnostics = validator.image_difference_diagnostics(
            f"bridge_basis_projection_{family.name}",
            validator.snapshot_for_comparison(projected_result),
            bridge_snapshot,
        )
        coeff_abs = np.mean(np.abs(coeffs_per_k), axis=0)
        ratio_map = {"abs_a1_over_abs_a0": 0.0, "abs_a2_over_abs_a0": 0.0}
        label_to_index = {label: idx for idx, label in enumerate(family.basis_labels)}
        if "R1" in label_to_index:
            ratio_map["abs_a1_over_abs_a0"] = float(
                coeff_abs[label_to_index["R1"]] / (coeff_abs[label_to_index["R0"]] + 1e-30)
            )
        if "R2" in label_to_index:
            ratio_map["abs_a2_over_abs_a0"] = float(
                coeff_abs[label_to_index["R2"]] / (coeff_abs[label_to_index["R0"]] + 1e-30)
            )
        projections.append(
            {
                "family": family.name,
                "basis_labels": list(family.basis_labels),
                "field_relative_l2": _relative_l2(bridge_lateral_field, projected_lateral_field),
                "intensity_relative_l2": diagnostics["image_relative_l2"],
                "peakline_x_um": float(projected_result["peakline_x_um"]),
                "peakline_x_delta_um_vs_bridge": diagnostics["peakline_x_delta_um"],
                "centroid_opd_um": float(projected_result["axial_intensity_metrics"]["centroid_opd_um"]),
                "centroid_opd_delta_um_vs_bridge": diagnostics["centroid_opd_delta_um"],
                "raw_peak_relative_delta": diagnostics.get("raw_peak_relative_delta"),
                "coefficient_energy_ratio": ratio_map,
            }
        )
    return projections


def _summarize_next_action(case_reports: list[dict[str, Any]]) -> str:
    improved_cases = []
    for case_report in case_reports:
        families = {item["family"]: item for item in case_report["projection_fits"]}
        if "R0_plus_R2" not in families or "R0_plus_R1_plus_R2" not in families:
            continue
        base = families["R0_plus_R2"]
        full = families["R0_plus_R1_plus_R2"]
        peakline_improved = full["peakline_x_delta_um_vs_bridge"] + 1e-9 < base["peakline_x_delta_um_vs_bridge"]
        field_not_worse = full["field_relative_l2"] <= base["field_relative_l2"] + 0.01
        intensity_not_worse = full["intensity_relative_l2"] <= base["intensity_relative_l2"] + 0.02
        improved_cases.append(peakline_improved and field_not_worse and intensity_not_worse)
    if improved_cases and sum(improved_cases) >= max(2, len(improved_cases)):
        return "debug_coefficient_extraction_or_promote_directional_basis"
    return "stop_expanding_current_asymptotic_basis_and_promote_higher_order_model"


def build_basis_projection_report(*, write_reports: bool = True, library_path: str | None = None) -> dict[str, Any]:
    _backend_status, skipped = probe_backend_or_write_skip(
        title="Round 6p1 Basis Projection Diagnostics",
        json_filename="round6p1_basis_projection_diagnostics.json",
        md_filename="round6p1_basis_projection_diagnostics.md",
        write_reports=write_reports,
        library_path=library_path,
        recommended_next_action="configure_supported_tmatrix_backend_before_basis_projection",
    )
    if skipped is not None:
        return skipped
    validator = load_module(VALIDATOR_PATH, "round6p1_validator")
    bridge_module = load_module(BRIDGE_PATH, "round6_bridge_projection")
    representative_cases = getattr(validator, "ROUND6P1_REPRESENTATIVE_CASES")
    run_round6p1_case = getattr(validator, "run_round6p1_case")
    tmatrix_path = validator.ensure_tmatrix_loaded(library_path)

    case_reports: list[dict[str, Any]] = []
    for case in representative_cases:
        bridge_context = _build_bridge_lateral_field(validator, bridge_module, case, tmatrix_path)
        asym_result = run_round6p1_case(
            case,
            mode=validator.LOW_NA_ASYMPTOTIC_MODE,
            library_path=tmatrix_path,
            second_order_model="directional_field_expansion_first_order",
        )
        families = _build_projection_families(asym_result)
        case_reports.append(
            {
                "case_name": case["name"],
                "bridge_peakline_x_um": bridge_context["peakline_x_um"],
                "bridge_centroid_opd_um": bridge_context["centroid_opd_um"],
                "lateral_slice_axis": bridge_context["lateral_slice_axis"],
                "projection_fits": _project_bridge_field(validator, bridge_context, families),
            }
        )

    report = {
        "basis_projection_cases": case_reports,
        "basis_projection_case_names": [case["case_name"] for case in case_reports],
        "basis_projection_recommended_next_action": _summarize_next_action(case_reports),
        "recommended_next_action": _summarize_next_action(case_reports),
        "report_version_tag": getattr(validator, "DEFAULT_REPORT_VERSION_TAG", "round6p1"),
    }
    if write_reports:
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        json_path = REPORTS_DIR / "round6p1_basis_projection_diagnostics.json"
        md_path = REPORTS_DIR / "round6p1_basis_projection_diagnostics.md"
        json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        lines = ["# Round6p1 Basis Projection Diagnostics", ""]
        lines.append(f"Recommended next action: `{report['basis_projection_recommended_next_action']}`")
        lines.append("")
        for case_report in case_reports:
            lines.append(f"## {case_report['case_name']}")
            lines.append("")
            lines.append(
                f"Bridge peakline_x_um: `{case_report['bridge_peakline_x_um']}`; "
                f"bridge centroid_opd_um: `{case_report['bridge_centroid_opd_um']}`"
                f"; lateral_slice_axis: `{case_report['lateral_slice_axis']}`"
            )
            lines.append("")
            lines.append(
                "| Family | field_relative_l2 | intensity_relative_l2 | peakline_x_um | peakline_x_delta_um_vs_bridge | "
                "centroid_opd_um | centroid_opd_delta_um_vs_bridge | raw_peak_relative_delta | |a1|/|a0| | |a2|/|a0| |"
            )
            lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
            for item in case_report["projection_fits"]:
                ratios = item["coefficient_energy_ratio"]
                lines.append(
                    f"| {item['family']} | {item['field_relative_l2']:.6f} | {item['intensity_relative_l2']:.6f} | "
                    f"{item['peakline_x_um']:.6f} | {item['peakline_x_delta_um_vs_bridge']:.6f} | "
                    f"{item['centroid_opd_um']:.6f} | {item['centroid_opd_delta_um_vs_bridge']:.6f} | "
                    f"{float(item['raw_peak_relative_delta']) if item['raw_peak_relative_delta'] is not None else float('nan'):.6f} | "
                    f"{ratios['abs_a1_over_abs_a0']:.6f} | {ratios['abs_a2_over_abs_a0']:.6f} |"
                )
            lines.append("")
        md_path.write_text("\n".join(lines), encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Project bridge lateral fields onto current asymptotic basis functions.")
    parser.add_argument("--no-write", action="store_true", help="Do not write report artifacts.")
    parser.add_argument("--library-path", default=None, help="Optional explicit TMATRIX library path.")
    args = parser.parse_args()
    report = build_basis_projection_report(write_reports=not args.no_write, library_path=args.library_path)
    print(json.dumps(report, indent=2))
    return 0


__all__ = [
    "BASIS_PROJECTION_PATH",
    "BRIDGE_PATH",
    "VALIDATOR_PATH",
    "ProjectionFamily",
    "_get_nested",
    "_build_bridge_lateral_field",
    "_build_projected_result",
    "_build_projection_families",
    "_load_module",
    "_load_solver_module",
    "_project_bridge_field",
    "_summarize_next_action",
    "build_basis_projection_report",
    "main",
]
