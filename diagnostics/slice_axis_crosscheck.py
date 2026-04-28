from __future__ import annotations

import argparse
import json

from diagnostics._runtime import (
    REPORTS_DIR,
    load_module,
    load_solver_module,
    probe_backend_or_write_skip,
    resolve_script_path,
)
from diagnostics.basis_coefficient_recovery import _fit_coefficients, _summarize_case
from diagnostics.bridge_basis_projection import BASIS_PROJECTION_PATH, _build_bridge_lateral_field, _build_projection_families
from solvers import coefficient_path_bundle as _COEFF_BUNDLE_CORE


VALIDATOR_PATH = resolve_script_path(
    "validate_oct_nonspherical_psf_solver.py",
    "04_validate_oct_nonspherical_psf_solver.py",
)


def _load_solver_module():
    return load_solver_module()


_SOLVER = _load_solver_module()
_load_module = load_module


def _select_case(validator):
    return next(case for case in validator.ROUND6P1_REPRESENTATIVE_CASES if case["name"] == "mild_shape_medium_tilt")


def _axis_report(*, axis: str, case_definition: dict, validator, basis_module, tmatrix_path: str):
    bridge_impl = load_module(basis_module.BRIDGE_PATH, f"round6_slice_axis_bridge_{axis}")
    bridge_context = _build_bridge_lateral_field(
        validator,
        bridge_impl,
        case_definition,
        tmatrix_path,
        lateral_slice_axis=axis,
    )
    asym_result = validator.run_round6p1_case(
        case_definition,
        mode=validator.LOW_NA_ASYMPTOTIC_MODE,
        library_path=tmatrix_path,
        second_order_model="directional_field_expansion_first_order",
        lateral_slice_axis=axis,
    )
    families = _build_projection_families(asym_result)
    projection_fits = basis_module._project_bridge_field(validator, bridge_context, families)
    coefficient_bundle = _COEFF_BUNDLE_CORE.build_coefficient_path_bundle(asym_result)
    recovered_coeffs = _fit_coefficients(
        bridge_context["lateral_field"],
        coefficient_bundle.field_basis_state.basis_matrix,
    )
    coefficient_summary = _summarize_case(
        f"{case_definition['name']}_{axis}",
        bridge_context["lateral_field"],
        recovered_coeffs,
        coefficient_bundle,
    )
    family_map = {item["family"]: item for item in projection_fits}
    even_family = family_map["R0_plus_R2"]
    full = family_map["R0_plus_R1_plus_R2"]
    axis_requires_odd_basis = bool(even_family["peakline_x_delta_um_vs_bridge"] > 0.5)
    odd_basis_resolves_axis = bool(
        axis_requires_odd_basis
        and full["peakline_x_delta_um_vs_bridge"] <= 0.5
        and full["intensity_relative_l2"] <= even_family["intensity_relative_l2"] + 0.02
        and full["field_relative_l2"] <= even_family["field_relative_l2"] + 0.02
    )
    return {
        "axis": axis,
        "projection_fits": projection_fits,
        "axis_requires_odd_basis": axis_requires_odd_basis,
        "odd_basis_resolves_axis": odd_basis_resolves_axis,
        "full_family_beats_even_family": bool(
            full["peakline_x_delta_um_vs_bridge"] + 1e-9 < even_family["peakline_x_delta_um_vs_bridge"]
            and full["intensity_relative_l2"] <= even_family["intensity_relative_l2"] + 0.02
            and full["field_relative_l2"] <= even_family["field_relative_l2"] + 0.02
        ),
        "coefficient_recovery_recommended_focus": (
            "D1_dominant"
            if next(item for item in coefficient_summary["component_summaries"] if item["name"] == "a1_vs_D1_slice_k")["relative_residual"]
            > next(item for item in coefficient_summary["component_summaries"] if item["name"] == "a2_vs_C2_slice_k")["relative_residual"]
            else "mixed"
        ),
        "coefficient_summary": coefficient_summary,
    }


def _recommend_next_action(axis_reports: list[dict]) -> tuple[str, str]:
    if not axis_reports:
        return ("unknown", "slice_axis_crosscheck_not_supplied")
    required_axes = [report for report in axis_reports if report.get("axis_requires_odd_basis")]
    if required_axes and all(report.get("odd_basis_resolves_axis") for report in required_axes):
        return ("consistent", "coefficient_debug_generalizes_across_slice_axes")
    if not required_axes:
        return ("not_triggered", "slice_axis_crosscheck_not_triggered_for_selected_case")
    return ("axis_sensitive", "verify_slice_direction_dependence_before_usage_mapping")


def build_slice_axis_crosscheck_report(*, write_reports: bool = True, library_path: str | None = None) -> dict:
    _backend_status, skipped = probe_backend_or_write_skip(
        title="Round 6p1 Lateral Slice Axis Crosscheck",
        json_filename="round6p1_lateral_slice_axis_crosscheck.json",
        md_filename="round6p1_lateral_slice_axis_crosscheck.md",
        write_reports=write_reports,
        library_path=library_path,
        recommended_next_action="configure_supported_tmatrix_backend_before_slice_axis_crosscheck",
    )
    if skipped is not None:
        return skipped
    validator = load_module(VALIDATOR_PATH, "round6p1_validator_slice_axis_crosscheck")
    basis_module = load_module(BASIS_PROJECTION_PATH, "round6p1_basis_projection_slice_axis_crosscheck")
    tmatrix_path = validator.ensure_tmatrix_loaded(library_path)
    case_definition = _select_case(validator)
    axis_reports = [
        _axis_report(
            axis=axis,
            case_definition=case_definition,
            validator=validator,
            basis_module=basis_module,
            tmatrix_path=tmatrix_path,
        )
        for axis in ("x", "y")
    ]
    status, action = _recommend_next_action(axis_reports)
    report = {
        "slice_axis_crosscheck_cases": [
            {
                "case_name": case_definition["name"],
                "description": case_definition["description"],
                "axis_reports": axis_reports,
            }
        ],
        "slice_axis_crosscheck_case_names": [case_definition["name"]],
        "slice_axis_crosscheck_status": status,
        "slice_axis_crosscheck_recommended_next_action": action,
        "recommended_next_action": action,
        "slice_axis_crosscheck_note": (
            "Cross-check one representative tilted non-spherical case on x and y lateral slices to confirm whether "
            "the current coefficient-debug recommendation is slice-direction robust."
        ),
        "report_version_tag": validator.DEFAULT_REPORT_VERSION_TAG,
    }
    if write_reports:
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        json_path = REPORTS_DIR / "round6p1_lateral_slice_axis_crosscheck.json"
        md_path = REPORTS_DIR / "round6p1_lateral_slice_axis_crosscheck.md"
        json_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        lines = ["# Round 6p1 Lateral Slice Axis Crosscheck", ""]
        lines.append(f"Status: `{status}`")
        lines.append(f"Recommended next action: `{action}`")
        lines.append("")
        for case_report in report["slice_axis_crosscheck_cases"]:
            lines.append(f"## {case_report['case_name']}")
            lines.append(case_report["description"])
            lines.append("")
            for axis_report in case_report["axis_reports"]:
                lines.append(f"### axis = {axis_report['axis']}")
                lines.append("")
                lines.append("| Family | field_relative_l2 | intensity_relative_l2 | peakline_x_delta_um_vs_bridge |")
                lines.append("|---|---:|---:|---:|")
                for item in axis_report["projection_fits"]:
                    lines.append(
                        f"| {item['family']} | {item['field_relative_l2']:.6g} | "
                        f"{item['intensity_relative_l2']:.6g} | {item['peakline_x_delta_um_vs_bridge']:.6g} |"
                    )
                lines.append("")
                lines.append(
                    f"axis requires odd basis: `{axis_report['axis_requires_odd_basis']}`; "
                    f"odd basis resolves axis: `{axis_report['odd_basis_resolves_axis']}`; "
                    f"`R0+R1+R2` beats `R0+R2`: `{axis_report['full_family_beats_even_family']}`; "
                    f"coefficient focus: `{axis_report['coefficient_recovery_recommended_focus']}`."
                )
                lines.append("")
        md_path.write_text("\n".join(lines), encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Cross-check whether coefficient-debug conclusions remain consistent across x/y lateral slices.")
    parser.add_argument("--no-write", action="store_true", help="Do not write report artifacts.")
    parser.add_argument("--library-path", default=None, help="Optional explicit TMATRIX library path.")
    args = parser.parse_args()
    report = build_slice_axis_crosscheck_report(write_reports=not args.no_write, library_path=args.library_path)
    print(json.dumps(report, indent=2))
    return 0


__all__ = [
    "BASIS_PROJECTION_PATH",
    "VALIDATOR_PATH",
    "_axis_report",
    "_load_module",
    "_load_solver_module",
    "_recommend_next_action",
    "_select_case",
    "build_slice_axis_crosscheck_report",
    "main",
]
