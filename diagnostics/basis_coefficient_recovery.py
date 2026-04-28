from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from diagnostics._runtime import (
    REPORTS_DIR,
    load_module,
    load_solver_module,
    probe_backend_or_write_skip,
    resolve_script_path,
)
from diagnostics.bridge_basis_projection import BASIS_PROJECTION_PATH, _build_projection_families
from solvers import coefficient_path_bundle as _COEFF_BUNDLE_CORE
from solvers import effective_channel_coefficients as _COEFF_CORE


VALIDATOR_PATH = resolve_script_path(
    "validate_oct_nonspherical_psf_solver.py",
    "04_validate_oct_nonspherical_psf_solver.py",
)


def _load_solver_module():
    return load_solver_module()


_SOLVER = _load_solver_module()


_complex_alignment = _COEFF_CORE.complex_alignment
_mean_abs_ratio = _COEFF_CORE.mean_abs_ratio
_shared_scale_component_diagnostics = _COEFF_CORE.shared_scale_component_diagnostics
_basis_gram_diagnostics = _COEFF_CORE.basis_gram_diagnostics
_orthonormalized_coefficients = _COEFF_CORE.orthonormalized_coefficients
_component_summary = _COEFF_CORE.component_summary
_recommend_next_action = _COEFF_CORE.recommend_next_action
_basis_conditioning_status = _COEFF_CORE.basis_conditioning_status
_coefficient_interpretability_status = _COEFF_CORE.coefficient_interpretability_status
_shared_scale_consistency_status = _COEFF_CORE.shared_scale_consistency_status
def _fit_coefficients(target_field_kx: np.ndarray, basis_matrix: np.ndarray) -> np.ndarray:
    target_field_kx = np.asarray(target_field_kx, dtype=np.complex128)
    basis_matrix = np.asarray(basis_matrix, dtype=np.complex128)
    coeffs = np.zeros((target_field_kx.shape[0], basis_matrix.shape[1]), dtype=np.complex128)
    for idx, target_row in enumerate(target_field_kx):
        fitted, *_ = np.linalg.lstsq(basis_matrix, target_row, rcond=None)
        coeffs[idx] = fitted
    return coeffs


def _summarize_case(
    case_name: str,
    target_field_kx: np.ndarray,
    recovered_coeffs: np.ndarray,
    coefficient_bundle,
) -> dict[str, object]:
    basis_matrix = np.asarray(coefficient_bundle.field_basis_state.basis_matrix, dtype=np.complex128)
    asym_coeffs = np.asarray(coefficient_bundle.comparison_state.rendered_coefficients_raw, dtype=np.complex128)
    component_names = ("a0_vs_B_k", "a1_vs_D1_slice_k", "a2_vs_C2_slice_k")
    vector_alignment = _complex_alignment(asym_coeffs.reshape(-1), recovered_coeffs.reshape(-1))
    shared_scale_consistency = _shared_scale_component_diagnostics(asym_coeffs, recovered_coeffs, component_names)
    gram_diagnostics = _basis_gram_diagnostics(basis_matrix)
    component_summaries = [
        _component_summary(component_names[0], recovered_coeffs[:, 0], asym_coeffs[:, 0]),
        _component_summary(component_names[1], recovered_coeffs[:, 1], asym_coeffs[:, 1]),
        _component_summary(component_names[2], recovered_coeffs[:, 2], asym_coeffs[:, 2]),
    ]
    orthonormalized_recovered = _orthonormalized_coefficients(target_field_kx, basis_matrix)
    return {
        "case_name": case_name,
        "vector_alignment": vector_alignment,
        "shared_scale_consistency": shared_scale_consistency,
        "component_summaries": component_summaries,
        "basis_gram_diagnostics": gram_diagnostics,
        "recovered_coefficient_energy_ratio": {
            "abs_a1_over_abs_a0": _mean_abs_ratio(recovered_coeffs[:, 0], recovered_coeffs[:, 1]),
            "abs_a2_over_abs_a0": _mean_abs_ratio(recovered_coeffs[:, 0], recovered_coeffs[:, 2]),
        },
        "orthonormalized_recovered_coefficient_energy_ratio": orthonormalized_recovered["coefficient_energy_ratio"],
        "orthonormalized_basis_diagnostics": {
            "r_condition_number": orthonormalized_recovered["r_condition_number"],
            "r_matrix_real": orthonormalized_recovered["r_matrix_real"],
            "r_matrix_imag": orthonormalized_recovered["r_matrix_imag"],
        },
        "rendered_coefficient_labels": list(coefficient_bundle.comparison_state.rendered_coefficient_labels),
        "asymptotic_coefficient_energy_ratio": {
            "abs_D1_over_abs_B": _mean_abs_ratio(asym_coeffs[:, 0], asym_coeffs[:, 1]),
            "abs_C2_over_abs_B": _mean_abs_ratio(asym_coeffs[:, 0], asym_coeffs[:, 2]),
        },
    }


def build_coefficient_recovery_report(
    *,
    write_reports: bool = True,
    library_path: str | None = None,
    coefficient_map_model_id: str = "identity_slice_projected_rendered_basis",
    reference_rendered_coefficients_source: str = "none",
) -> dict[str, object]:
    _backend_status, skipped = probe_backend_or_write_skip(
        title="Round 6p1 Basis Coefficient Recovery",
        json_filename="round6p1_basis_coefficient_recovery.json",
        md_filename="round6p1_basis_coefficient_recovery.md",
        write_reports=write_reports,
        library_path=library_path,
        recommended_next_action="configure_supported_tmatrix_backend_before_coefficient_recovery",
    )
    if skipped is not None:
        return skipped
    validator = load_module(VALIDATOR_PATH, "round6p1_validator_coefficients")
    basis_module = load_module(BASIS_PROJECTION_PATH, "round6p1_basis_projection_coefficients")
    bridge_module = basis_module._load_module(basis_module.BRIDGE_PATH, "round6_bridge_projection_for_coefficients")
    representative_cases = getattr(validator, "ROUND6P1_REPRESENTATIVE_CASES")
    run_round6p1_case = getattr(validator, "run_round6p1_case")
    tmatrix_path = validator.ensure_tmatrix_loaded(library_path)

    case_reports: list[dict[str, object]] = []
    for case in representative_cases:
        bridge_context = basis_module._build_bridge_lateral_field(validator, bridge_module, case, tmatrix_path)
        asym_result = run_round6p1_case(
            case,
            mode=validator.LOW_NA_ASYMPTOTIC_MODE,
            library_path=tmatrix_path,
            second_order_model="directional_field_expansion_first_order",
        )
        identity_bundle = _COEFF_BUNDLE_CORE.build_coefficient_path_bundle(asym_result)
        families = _build_projection_families(asym_result)
        full_family = next(family for family in families if family.name == "R0_plus_R1_plus_R2")
        recovered_coeffs = _fit_coefficients(bridge_context["lateral_field"], full_family.basis_matrix)
        reference_rendered_coefficients_raw = _COEFF_BUNDLE_CORE.resolve_reference_rendered_coefficients(
            identity_bundle.rendered_coefficient_state.projected_coefficients_raw,
            recovered_coeffs,
            source=reference_rendered_coefficients_source,
        )
        coefficient_bundle = _COEFF_BUNDLE_CORE.build_coefficient_path_bundle(
            asym_result,
            coefficient_map_model_id=coefficient_map_model_id,
            reference_rendered_coefficients_raw=reference_rendered_coefficients_raw,
        )
        case_summary = _summarize_case(
            case["name"],
            bridge_context["lateral_field"],
            recovered_coeffs,
            coefficient_bundle,
        )
        artifact_path = None
        if write_reports:
            artifact_path = _COEFF_BUNDLE_CORE.write_coefficient_path_bundle_npz(
                _COEFF_BUNDLE_CORE.coefficient_bundle_report_path(
                    REPORTS_DIR,
                    case["name"],
                    artifact_kind="native_identity",
                ),
                coefficient_bundle,
                case_name=case["name"],
                artifact_kind="native_identity",
                recovered_coefficients_raw=recovered_coeffs,
            )
            _COEFF_BUNDLE_CORE.read_coefficient_path_bundle_npz(artifact_path)
        case_summary["coefficient_contract"] = {
            "fit_strategy": coefficient_bundle.angular_fit_state.fit_strategy,
            "relative_fit_residual_model": coefficient_bundle.angular_fit_state.relative_fit_residual_model,
            "slice_direction_label": coefficient_bundle.slice_projected_state.slice_direction_label,
            "wavelength_axis_kind": coefficient_bundle.angular_fit_state.wavelength_axis_kind,
            "field_assembly_model_id": coefficient_bundle.field_basis_state.field_assembly_model_id,
            "coefficient_map_model_id": coefficient_bundle.comparison_state.coefficient_map_model_id,
            "coefficient_map_theory_claim": coefficient_bundle.comparison_state.coefficient_map_theory_claim,
            "coefficient_gauge_note": coefficient_bundle.comparison_state.coefficient_gauge_note,
        }
        if artifact_path is not None:
            try:
                artifact_relative_path = artifact_path.relative_to(REPORTS_DIR).as_posix()
            except ValueError:
                artifact_relative_path = artifact_path.name
            case_summary["coefficient_bundle_artifact_filename"] = artifact_path.name
            case_summary["coefficient_bundle_artifact_relative_path"] = artifact_relative_path
            case_summary["coefficient_bundle_artifact_path"] = artifact_relative_path
        else:
            case_summary["coefficient_bundle_artifact_filename"] = None
            case_summary["coefficient_bundle_artifact_relative_path"] = None
            case_summary["coefficient_bundle_artifact_path"] = None
        case_reports.append(case_summary)

    basis_conditioning_status, basis_conditioning_note = _basis_conditioning_status(case_reports)
    coefficient_interpretability_status, coefficient_interpretability_note = _coefficient_interpretability_status(case_reports)
    shared_scale_consistency_status, shared_scale_consistency_note = _shared_scale_consistency_status(case_reports)
    report = {
        "coefficient_recovery_cases": case_reports,
        "coefficient_recovery_case_names": [case["case_name"] for case in case_reports],
        "coefficient_recovery_recommended_next_action": _recommend_next_action(case_reports),
        "recommended_next_action": _recommend_next_action(case_reports),
        "coefficient_map_model_id": coefficient_map_model_id,
        "reference_rendered_coefficients_source": reference_rendered_coefficients_source,
        "basis_conditioning_status": basis_conditioning_status,
        "basis_conditioning_note": basis_conditioning_note,
        "coefficient_interpretability_status": coefficient_interpretability_status,
        "coefficient_interpretability_note": coefficient_interpretability_note,
        "shared_scale_consistency_status": shared_scale_consistency_status,
        "shared_scale_consistency_note": shared_scale_consistency_note,
        "report_kind": "coefficient_recovery",
        "report_version_tag": validator.DEFAULT_REPORT_VERSION_TAG,
        "coefficient_bundle_artifact_pattern": "round6p1_<case>_native_identity_coefficient_bundle.npz",
    }

    if write_reports:
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        json_path = REPORTS_DIR / "round6p1_basis_coefficient_recovery.json"
        md_path = REPORTS_DIR / "round6p1_basis_coefficient_recovery.md"
        json_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

        lines = ["# Round 6p1 Basis Coefficient Recovery", ""]
        lines.append(f"Recommended next action: `{report['coefficient_recovery_recommended_next_action']}`")
        lines.append(f"Basis conditioning status: `{report['basis_conditioning_status']}`")
        lines.append(f"Coefficient interpretability status: `{report['coefficient_interpretability_status']}`")
        lines.append(f"Shared-scale consistency status: `{report['shared_scale_consistency_status']}`")
        lines.append("")
        for case_report in case_reports:
            lines.append(f"## {case_report['case_name']}")
            lines.append("")
            va = case_report["vector_alignment"]
            lines.append(
                f"Vector alignment residual: `{va['relative_residual']:.6g}`; "
                f"scale abs: `{va['scale_abs']:.6g}`; phase: `{va['scale_phase_rad']:.6g}` rad."
            )
            lines.append("")
            shared = case_report["shared_scale_consistency"]
            lines.append(
                f"Shared-scale consistency: residual `{shared['relative_residual']:.6g}`; "
                f"scale abs `{shared['scale_abs']:.6g}`; phase `{shared['scale_phase_rad']:.6g}` rad."
            )
            lines.append("")
            lines.append("| Component | relative_residual | scale_abs | scale_phase_rad | mean_abs_ratio_recovered_over_asymptotic |")
            lines.append("|---|---:|---:|---:|---:|")
            for item in case_report["component_summaries"]:
                lines.append(
                    f"| {item['name']} | {item['relative_residual']:.6g} | {item['scale_abs']:.6g} | "
                    f"{item['scale_phase_rad']:.6g} | {item['mean_abs_ratio_recovered_over_asymptotic']:.6g} |"
                )
            lines.append("")
            lines.append("| Component under shared scale | relative_residual | mean_abs_ratio |")
            lines.append("|---|---:|---:|")
            for name, residual in case_report["shared_scale_consistency"]["component_relative_residuals"].items():
                ratio = case_report["shared_scale_consistency"]["component_mean_abs_ratio_under_shared_scale"][name]
                lines.append(f"| {name} | {residual:.6g} | {ratio:.6g} |")
            lines.append("")
            lines.append(
                f"Recovered energy ratios: `|a1|/|a0| = {case_report['recovered_coefficient_energy_ratio']['abs_a1_over_abs_a0']:.6g}`, "
                f"`|a2|/|a0| = {case_report['recovered_coefficient_energy_ratio']['abs_a2_over_abs_a0']:.6g}`."
            )
            lines.append("")
            lines.append(
                f"Orthonormalized recovered energy ratios: "
                f"`|q1|/|q0| = {case_report['orthonormalized_recovered_coefficient_energy_ratio']['abs_q1_over_abs_q0']:.6g}`, "
                f"`|q2|/|q0| = {case_report['orthonormalized_recovered_coefficient_energy_ratio']['abs_q2_over_abs_q0']:.6g}`."
            )
            lines.append("")
            lines.append(
                f"Asymptotic energy ratios: `|D1|/|B| = {case_report['asymptotic_coefficient_energy_ratio']['abs_D1_over_abs_B']:.6g}`, "
                f"`|C2|/|B| = {case_report['asymptotic_coefficient_energy_ratio']['abs_C2_over_abs_B']:.6g}`."
            )
            lines.append("")
            lines.append(
                f"Basis Gram condition number: `{case_report['basis_gram_diagnostics']['gram_condition_number']:.6g}`; "
                f"R-factor condition number after orthonormalization: `{case_report['orthonormalized_basis_diagnostics']['r_condition_number']:.6g}`."
            )
            lines.append("")
            contract = case_report["coefficient_contract"]
            lines.append(
                f"Coefficient contract: fit strategy `{contract['fit_strategy']}`, residual model `{contract['relative_fit_residual_model']}`, "
                f"slice `{contract['slice_direction_label']}`, wavelength axis `{contract['wavelength_axis_kind']}`, "
                f"assembly `{contract['field_assembly_model_id']}`, map `{contract['coefficient_map_model_id']}`."
            )
            lines.append("")
            if case_report["coefficient_bundle_artifact_relative_path"]:
                lines.append(f"Coefficient bundle artifact: `{case_report['coefficient_bundle_artifact_relative_path']}`")
                lines.append("")
        md_path.write_text("\n".join(lines), encoding="utf-8")

    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare bridge-recovered basis coefficients against the current asymptotic coefficient extraction.")
    parser.add_argument("--no-write", action="store_true", help="Do not write report artifacts.")
    parser.add_argument("--library-path", default=None, help="Optional explicit TMATRIX library path.")
    parser.add_argument(
        "--coefficient-map-model-id",
        default="identity_slice_projected_rendered_basis",
        choices=_COEFF_BUNDLE_CORE.COEFFICIENT_MAP_MODEL_IDS,
        help="Projected-to-rendered coefficient map model used when constructing the canonical bundle.",
    )
    parser.add_argument(
        "--reference-rendered-coefficients-source",
        default="none",
        choices=_COEFF_BUNDLE_CORE.REFERENCE_RENDERED_COEFFICIENT_SOURCES,
        help="Reference source used when fitting non-identity rendered coefficient maps.",
    )
    args = parser.parse_args()
    report = build_coefficient_recovery_report(
        write_reports=not args.no_write,
        library_path=args.library_path,
        coefficient_map_model_id=args.coefficient_map_model_id,
        reference_rendered_coefficients_source=args.reference_rendered_coefficients_source,
    )
    print(json.dumps(report, indent=2))
    return 0


__all__ = [
    "BASIS_PROJECTION_PATH",
    "VALIDATOR_PATH",
    "_basis_conditioning_status",
    "_basis_gram_diagnostics",
    "_coefficient_interpretability_status",
    "_component_summary",
    "_complex_alignment",
    "_fit_coefficients",
    "_mean_abs_ratio",
    "_orthonormalized_coefficients",
    "_recommend_next_action",
    "_shared_scale_component_diagnostics",
    "_shared_scale_consistency_status",
    "_summarize_case",
    "build_coefficient_recovery_report",
    "main",
]
