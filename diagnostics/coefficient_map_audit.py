from __future__ import annotations

import argparse
import json
from typing import Any

import numpy as np

from diagnostics._runtime import (
    REPORTS_DIR,
    load_module,
    load_solver_module,
    probe_backend_or_write_skip,
    resolve_script_path,
)
from diagnostics.basis_coefficient_recovery import _fit_coefficients
from diagnostics.bridge_basis_projection import BASIS_PROJECTION_PATH
from solvers import coefficient_path_bundle as _COEFF_BUNDLE_CORE
from solvers import effective_channel_coefficients as _COEFF_CORE


VALIDATOR_PATH = resolve_script_path(
    "validate_oct_nonspherical_psf_solver.py",
    "04_validate_oct_nonspherical_psf_solver.py",
)


def _load_solver_module():
    return load_solver_module()


_SOLVER = _load_solver_module()


def _build_rendered_result(
    bridge_context: dict[str, Any],
    coefficient_bundle: _COEFF_BUNDLE_CORE.CoefficientPathBundle,
    *,
    rendered_coefficients_raw: np.ndarray | None = None,
    coefficient_map_model_id: str | None = None,
) -> dict[str, Any]:
    validator = load_module(VALIDATOR_PATH, "round6p1_validator_map_audit_api")
    source_power = np.asarray(bridge_context["source_power"], dtype=float)
    lambda_nm = np.asarray(bridge_context["lambda_nm"], dtype=float)
    opd_um = np.asarray(bridge_context["opd_um"], dtype=float)
    x_um = np.asarray(bridge_context["x_um"], dtype=float)
    medium_material = bridge_context["solver"].medium_material
    bridge_module = load_module(BASIS_PROJECTION_PATH, "round6p1_basis_projection_map_audit_api")
    api = load_module(bridge_module.BRIDGE_PATH, "round6_map_audit_bridge_api")._solver_api()
    rendered_coefficients = np.asarray(
        coefficient_bundle.rendered_coefficient_state.rendered_coefficients_raw
        if rendered_coefficients_raw is None
        else rendered_coefficients_raw,
        dtype=np.complex128,
    )
    basis_matrix = np.asarray(coefficient_bundle.field_basis_state.basis_matrix, dtype=np.complex128)
    lateral_field = _COEFF_BUNDLE_CORE.reconstruct_lateral_field_from_rendered_coefficients(
        coefficient_bundle,
        rendered_coefficients,
    )
    spectral_cube = source_power[:, None] * lateral_field
    field_xz = api.spectral_cube_to_xz(lambda_nm, spectral_cube, opd_um, medium_material)
    raw_envelope_xz = np.abs(field_xz)
    raw_intensity_xz = raw_envelope_xz**2
    envelope_xz, _ = api.normalize_intensity(raw_envelope_xz, return_scale=True)
    intensity_xz, _ = api.normalize_intensity(raw_intensity_xz, return_scale=True)
    axial_views = api.build_full_na_axial_views(x_um, opd_um, raw_intensity_xz, raw_envelope_xz)
    return {
        "mode": f"coefficient_map_audit::{coefficient_map_model_id or coefficient_bundle.rendered_coefficient_state.coefficient_map_model_id}",
        "x_um": x_um,
        "opd_um": opd_um,
        "field_xz": field_xz,
        "raw_envelope_xz": raw_envelope_xz,
        "raw_intensity_xz": raw_intensity_xz,
        "envelope_xz": envelope_xz,
        "intensity_xz": intensity_xz,
        "peakline_x_um": float(axial_views["peakline_x_um"]),
        "raw_peak_intensity": float(axial_views["raw_peak_intensity"]),
        "axial_intensity_metrics": axial_views["peakline_axial_intensity_metrics"],
        "basis_matrix_shape": list(basis_matrix.shape),
    }


def _extract_row(result: dict[str, Any], bridge_result: dict[str, Any], validator) -> dict[str, float]:
    row = validator.image_difference_diagnostics(
        f"{result['mode']}_vs_bridge",
        validator.snapshot_for_comparison(result),
        validator.snapshot_for_comparison(bridge_result),
    )
    row["peakline_x_um"] = float(result["peakline_x_um"])
    row["centroid_opd_um"] = float(result["axial_intensity_metrics"]["centroid_opd_um"])
    row["raw_peak_intensity"] = float(result["raw_peak_intensity"])
    return row


def _residual(reference: np.ndarray, estimate: np.ndarray) -> float:
    reference = np.asarray(reference, dtype=np.complex128)
    estimate = np.asarray(estimate, dtype=np.complex128)
    return float(np.linalg.norm(estimate - reference) / (np.linalg.norm(reference) + 1e-30))


def _component_best_complex_scale(
    rendered_coefficients: np.ndarray,
    recovered_coefficients: np.ndarray,
) -> dict[str, dict[str, float]]:
    summaries = {}
    for idx, label in enumerate(("a0", "a1", "a2")):
        summaries[label] = _COEFF_CORE.component_summary(
            label,
            recovered_coefficients[:, idx],
            rendered_coefficients[:, idx],
        )
    return summaries


def _evaluate_map_model(
    model_id: str,
    *,
    asym_result: dict[str, Any],
    recovered_coefficients: np.ndarray,
    bridge_context: dict[str, Any],
    bridge_result: dict[str, Any],
    validator,
) -> dict[str, Any]:
    coefficient_bundle = _COEFF_BUNDLE_CORE.build_coefficient_path_bundle(
        asym_result,
        coefficient_map_model_id=model_id,
        reference_rendered_coefficients_raw=recovered_coefficients,
    )
    comparison_views = _COEFF_BUNDLE_CORE.build_external_comparison_views(
        coefficient_bundle,
        recovered_coefficients,
    )
    rendered_result = _build_rendered_result(bridge_context, coefficient_bundle)
    injected_vs_bridge = _extract_row(rendered_result, bridge_result, validator)
    raw_rendered = np.asarray(coefficient_bundle.rendered_coefficient_state.rendered_coefficients_raw, dtype=np.complex128)
    orth_rendered = np.asarray(coefficient_bundle.comparison_state.rendered_coefficients_orthonormalized, dtype=np.complex128)
    recovered_orth = np.asarray(comparison_views["external_coefficients_orthonormalized"], dtype=np.complex128)
    shared_scale = comparison_views["shared_scale_alignment"]
    shared_component = _COEFF_CORE.shared_scale_component_diagnostics(
        raw_rendered,
        recovered_coefficients,
        ("a0", "a1", "a2"),
    )
    return {
        "coefficient_map_model_id": model_id,
        "raw_rendered_relative_residual": _residual(recovered_coefficients, raw_rendered),
        "orthonormalized_relative_residual": _residual(recovered_orth, orth_rendered),
        "shared_scale_relative_residual": float(shared_scale["relative_residual"]),
        "shared_scale_component_residuals": shared_component["component_relative_residuals"],
        "component_best_complex_scale": _component_best_complex_scale(raw_rendered, recovered_coefficients),
        "injected_vs_bridge": injected_vs_bridge,
        "field_assembly_model_id": coefficient_bundle.field_basis_state.field_assembly_model_id,
        "basis_condition_number": float(np.linalg.cond(coefficient_bundle.field_basis_state.orthonormal_r_matrix)),
        "coefficient_bundle_artifact_candidate": _COEFF_BUNDLE_CORE.coefficient_bundle_report_path(
            REPORTS_DIR,
            bridge_context["solver"].name if hasattr(bridge_context["solver"], "name") else bridge_result.get("mode", "unknown"),
        ).name,
    }


def _best_model_key(model_report: dict[str, Any]) -> tuple[float, float, float]:
    injected = model_report["injected_vs_bridge"]
    return (
        float(injected["peakline_x_delta_um"]),
        float(injected["image_relative_l2"]),
        float(model_report["raw_rendered_relative_residual"]),
    )


def _recommend_next_action(case_reports: list[dict[str, Any]]) -> str:
    if not case_reports:
        return "run_coefficient_map_audit"
    non_identity_better = 0
    for case in case_reports:
        if case["best_model_id"] != "identity_slice_projected_rendered_basis":
            non_identity_better += 1
    if non_identity_better >= max(2, len(case_reports) // 2):
        return "audit_coefficient_map_stage_before_basis_expansion"
    return "identity_map_not_yet_falsified_continue_coefficient_definition_audit"


def build_coefficient_map_audit_report(*, write_reports: bool = True, library_path: str | None = None) -> dict[str, Any]:
    _backend_status, skipped = probe_backend_or_write_skip(
        title="Round 6p1 Coefficient Map Audit",
        json_filename="round6p1_coefficient_map_audit.json",
        md_filename="round6p1_coefficient_map_audit.md",
        write_reports=write_reports,
        library_path=library_path,
        recommended_next_action="configure_supported_tmatrix_backend_before_coefficient_map_audit",
    )
    if skipped is not None:
        return skipped

    validator = load_module(VALIDATOR_PATH, "round6p1_validator_map_audit")
    basis_module = load_module(BASIS_PROJECTION_PATH, "round6p1_basis_projection_map_audit")
    bridge_impl = load_module(basis_module.BRIDGE_PATH, "round6_map_audit_bridge")
    tmatrix_path = validator.ensure_tmatrix_loaded(library_path)

    case_reports = []
    for case in validator.ROUND6P1_REPRESENTATIVE_CASES:
        bridge_context = basis_module._build_bridge_lateral_field(validator, bridge_impl, case, tmatrix_path)
        bridge_result = validator.run_round6p1_case(case, mode=validator.VECTOR_BRIDGE_MODE, library_path=tmatrix_path)
        asym_result = validator.run_round6p1_case(
            case,
            mode=validator.LOW_NA_ASYMPTOTIC_MODE,
            library_path=tmatrix_path,
            second_order_model="directional_field_expansion_first_order",
        )
        identity_bundle = _COEFF_BUNDLE_CORE.build_coefficient_path_bundle(asym_result)
        recovered_coefficients = _fit_coefficients(
            bridge_context["lateral_field"],
            identity_bundle.field_basis_state.basis_matrix,
        )
        native_asymptotic_vs_bridge = _extract_row(asym_result, bridge_result, validator)
        model_reports = []
        for model_id in _COEFF_BUNDLE_CORE.COEFFICIENT_MAP_MODEL_IDS:
            model_reports.append(
                _evaluate_map_model(
                    model_id,
                    asym_result=asym_result,
                    recovered_coefficients=recovered_coefficients,
                    bridge_context=bridge_context,
                    bridge_result=bridge_result,
                    validator=validator,
                )
            )
        best_model = min(model_reports, key=_best_model_key)
        for model_report in model_reports:
            model_report["is_best_model"] = model_report["coefficient_map_model_id"] == best_model["coefficient_map_model_id"]
            model_report["injection_improvement_vs_native"] = {
                "image_relative_l2_delta": float(native_asymptotic_vs_bridge["image_relative_l2"] - model_report["injected_vs_bridge"]["image_relative_l2"]),
                "peakline_x_delta_um_delta": float(native_asymptotic_vs_bridge["peakline_x_delta_um"] - model_report["injected_vs_bridge"]["peakline_x_delta_um"]),
                "centroid_opd_delta_um_delta": float(native_asymptotic_vs_bridge["centroid_opd_delta_um"] - model_report["injected_vs_bridge"]["centroid_opd_delta_um"]),
                "raw_peak_relative_delta_delta": float(
                    native_asymptotic_vs_bridge.get("raw_peak_relative_delta", 0.0)
                    - model_report["injected_vs_bridge"].get("raw_peak_relative_delta", 0.0)
                ),
            }
        case_reports.append(
            {
                "case_name": case["name"],
                "native_asymptotic_vs_bridge": native_asymptotic_vs_bridge,
                "best_model_id": best_model["coefficient_map_model_id"],
                "best_model_selection_metric": {
                    "peakline_x_delta_um": float(best_model["injected_vs_bridge"]["peakline_x_delta_um"]),
                    "image_relative_l2": float(best_model["injected_vs_bridge"]["image_relative_l2"]),
                    "raw_rendered_relative_residual": float(best_model["raw_rendered_relative_residual"]),
                },
                "map_models": model_reports,
            }
        )

    report = {
        "coefficient_map_audit_cases": case_reports,
        "coefficient_map_audit_case_names": [case["case_name"] for case in case_reports],
        "coefficient_map_models": list(_COEFF_BUNDLE_CORE.COEFFICIENT_MAP_MODEL_IDS),
        "coefficient_map_audit_recommended_next_action": _recommend_next_action(case_reports),
        "recommended_next_action": _recommend_next_action(case_reports),
        "report_kind": "coefficient_map_audit",
        "report_version_tag": validator.DEFAULT_REPORT_VERSION_TAG,
    }

    if write_reports:
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        json_path = REPORTS_DIR / "round6p1_coefficient_map_audit.json"
        md_path = REPORTS_DIR / "round6p1_coefficient_map_audit.md"
        json_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        lines = ["# Round 6p1 Coefficient Map Audit", ""]
        lines.append(f"Recommended next action: `{report['coefficient_map_audit_recommended_next_action']}`")
        lines.append("")
        for case_report in case_reports:
            lines.append(f"## {case_report['case_name']}")
            lines.append("")
            native = case_report["native_asymptotic_vs_bridge"]
            lines.append(
                f"Native asymptotic: image L2 `{native['image_relative_l2']:.6g}`, "
                f"peakline delta `{native['peakline_x_delta_um']:.6g}`."
            )
            lines.append("")
            lines.append("| map model | raw coeff residual | orth coeff residual | shared-scale residual | injected image L2 | injected peakline delta | best |")
            lines.append("|---|---:|---:|---:|---:|---:|---|")
            for model_report in case_report["map_models"]:
                injected = model_report["injected_vs_bridge"]
                lines.append(
                    f"| {model_report['coefficient_map_model_id']} | "
                    f"{model_report['raw_rendered_relative_residual']:.6g} | "
                    f"{model_report['orthonormalized_relative_residual']:.6g} | "
                    f"{model_report['shared_scale_relative_residual']:.6g} | "
                    f"{injected['image_relative_l2']:.6g} | "
                    f"{injected['peakline_x_delta_um']:.6g} | "
                    f"{'yes' if model_report['is_best_model'] else 'no'} |"
                )
            lines.append("")
        md_path.write_text("\n".join(lines), encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit projected-to-rendered coefficient map models against recovered bridge coefficients.")
    parser.add_argument("--no-write", action="store_true", help="Do not write report artifacts.")
    parser.add_argument("--library-path", default=None, help="Optional explicit TMATRIX library path.")
    args = parser.parse_args()
    report = build_coefficient_map_audit_report(write_reports=not args.no_write, library_path=args.library_path)
    print(json.dumps(report, indent=2))
    return 0


__all__ = [
    "VALIDATOR_PATH",
    "build_coefficient_map_audit_report",
    "main",
]
