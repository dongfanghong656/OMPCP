from __future__ import annotations

import argparse
import json

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


VALIDATOR_PATH = resolve_script_path(
    "validate_oct_nonspherical_psf_solver.py",
    "04_validate_oct_nonspherical_psf_solver.py",
)


def _load_solver_module():
    return load_solver_module()


_SOLVER = _load_solver_module()


def _build_injected_result(
    bridge_context: dict[str, object],
    basis_matrix: np.ndarray,
    recovered_coeffs: np.ndarray,
    *,
    mode_label: str = "bridge_coefficient_injected_directional_field_expansion_first_order",
):
    validator = load_module(VALIDATOR_PATH, "round6p1_validator_injection_api")
    source_power = np.asarray(bridge_context["source_power"], dtype=float)
    lambda_nm = np.asarray(bridge_context["lambda_nm"], dtype=float)
    opd_um = np.asarray(bridge_context["opd_um"], dtype=float)
    x_um = np.asarray(bridge_context["x_um"], dtype=float)
    medium_material = bridge_context["solver"].medium_material
    injected_lateral_field = np.zeros_like(bridge_context["lateral_field"], dtype=np.complex128)
    for idx, coeffs in enumerate(recovered_coeffs):
        injected_lateral_field[idx] = basis_matrix @ coeffs
    bridge_module = load_module(BASIS_PROJECTION_PATH, "round6p1_basis_projection_injection_api")
    api = load_module(bridge_module.BRIDGE_PATH, "round6_injection_bridge_api")._solver_api()
    field_xz = api.spectral_cube_to_xz(lambda_nm, source_power[:, None] * injected_lateral_field, opd_um, medium_material)
    raw_envelope_xz = np.abs(field_xz)
    raw_intensity_xz = raw_envelope_xz**2
    envelope_xz, _ = api.normalize_intensity(raw_envelope_xz, return_scale=True)
    intensity_xz, _ = api.normalize_intensity(raw_intensity_xz, return_scale=True)
    axial_views = api.build_full_na_axial_views(x_um, opd_um, raw_intensity_xz, raw_envelope_xz)
    return {
        "mode": mode_label,
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
    }


def _extract_row(result: dict[str, object], bridge_result: dict[str, object], validator) -> dict[str, float]:
    row = validator.image_difference_diagnostics(
        f"{result['mode']}_vs_bridge",
        validator.snapshot_for_comparison(result),
        validator.snapshot_for_comparison(bridge_result),
    )
    row["peakline_x_um"] = float(result["peakline_x_um"])
    row["centroid_opd_um"] = float(result["axial_intensity_metrics"]["centroid_opd_um"])
    row["raw_peak_intensity"] = float(result["raw_peak_intensity"])
    return row


def _recommend_next_action(case_reports: list[dict[str, object]]) -> str:
    improved_cases = 0
    for case_report in case_reports:
        if (
            case_report["native_vs_bridge"]["peakline_x_delta_um"] > case_report["injected_vs_bridge"]["peakline_x_delta_um"]
            and case_report["native_vs_bridge"]["image_relative_l2"] > case_report["injected_vs_bridge"]["image_relative_l2"]
        ):
            improved_cases += 1
    if improved_cases >= max(2, len(case_reports) // 2):
        return "debug_coefficient_extraction_or_usage_mapping"
    return "current_asymptotic_field_structure_insufficient_promote_higher_order_model"


def build_coefficient_injection_report(
    *,
    write_reports: bool = True,
    library_path: str | None = None,
    coefficient_map_model_id: str = "identity_slice_projected_rendered_basis",
    reference_rendered_coefficients_source: str = "none",
) -> dict[str, object]:
    _backend_status, skipped = probe_backend_or_write_skip(
        title="Round 6p1 Coefficient Injection Diagnostics",
        json_filename="round6p1_coefficient_injection_diagnostics.json",
        md_filename="round6p1_coefficient_injection_diagnostics.md",
        write_reports=write_reports,
        library_path=library_path,
        recommended_next_action="configure_supported_tmatrix_backend_before_coefficient_injection",
    )
    if skipped is not None:
        return skipped
    validator = load_module(VALIDATOR_PATH, "round6p1_validator_injection")
    basis_module = load_module(BASIS_PROJECTION_PATH, "round6p1_basis_projection_injection")
    tmatrix_path = validator.ensure_tmatrix_loaded(library_path)
    case_reports = []
    bridge_impl = load_module(basis_module.BRIDGE_PATH, "round6_injection_bridge")
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
        recovered_coeffs = _fit_coefficients(
            bridge_context["lateral_field"],
            identity_bundle.field_basis_state.basis_matrix,
        )
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
        mapped_rendered_result = _build_injected_result(
            bridge_context,
            coefficient_bundle.field_basis_state.basis_matrix,
            coefficient_bundle.comparison_state.rendered_coefficients_raw,
            mode_label=f"mapped_rendered::{coefficient_bundle.comparison_state.coefficient_map_model_id}",
        )
        injected_result = _build_injected_result(
            bridge_context,
            coefficient_bundle.field_basis_state.basis_matrix,
            recovered_coeffs,
            mode_label="bridge_recovered_coefficients_injected",
        )
        case_reports.append(
            {
                "case_name": case["name"],
                "native_vs_bridge": _extract_row(mapped_rendered_result, bridge_result, validator),
                "injected_vs_bridge": _extract_row(injected_result, bridge_result, validator),
                "field_assembly_model_id": coefficient_bundle.field_basis_state.field_assembly_model_id,
                "coefficient_map_model_id": coefficient_bundle.comparison_state.coefficient_map_model_id,
                "reference_rendered_coefficients_source": reference_rendered_coefficients_source,
            }
        )
    report = {
        "coefficient_injection_cases": case_reports,
        "coefficient_injection_case_names": [case["case_name"] for case in case_reports],
        "coefficient_injection_recommended_next_action": _recommend_next_action(case_reports),
        "recommended_next_action": _recommend_next_action(case_reports),
        "coefficient_map_model_id": coefficient_map_model_id,
        "reference_rendered_coefficients_source": reference_rendered_coefficients_source,
        "report_version_tag": validator.DEFAULT_REPORT_VERSION_TAG,
    }
    if write_reports:
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        (REPORTS_DIR / "round6p1_coefficient_injection_diagnostics.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        lines = ["# Round 6p1 Coefficient Injection Diagnostics", ""]
        lines.append(f"Recommended next action: `{report['coefficient_injection_recommended_next_action']}`")
        lines.append("")
        for case_report in case_reports:
            lines.append(f"## {case_report['case_name']}")
            lines.append("")
            lines.append("| Variant | image_relative_l2 | peakline_x_delta_um | centroid_opd_delta_um | raw_peak_relative_delta |")
            lines.append("|---|---:|---:|---:|---:|")
            for label, metrics in (
                ("native_asymptotic", case_report["native_vs_bridge"]),
                ("bridge_recovered_coefficients_injected", case_report["injected_vs_bridge"]),
            ):
                lines.append(
                    f"| {label} | {metrics['image_relative_l2']:.6g} | {metrics['peakline_x_delta_um']:.6g} | "
                    f"{metrics['centroid_opd_delta_um']:.6g} | {metrics.get('raw_peak_relative_delta', float('nan')):.6g} |"
                )
            lines.append("")
        (REPORTS_DIR / "round6p1_coefficient_injection_diagnostics.md").write_text("\n".join(lines), encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Inject bridge-recovered coefficients into the current directional asymptotic field structure.")
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
    report = build_coefficient_injection_report(
        write_reports=not args.no_write,
        library_path=args.library_path,
        coefficient_map_model_id=args.coefficient_map_model_id,
        reference_rendered_coefficients_source=args.reference_rendered_coefficients_source,
    )
    print(json.dumps(report, indent=2))
    return 0


__all__ = [
    "VALIDATOR_PATH",
    "_build_injected_result",
    "_extract_row",
    "build_coefficient_injection_report",
    "main",
]
