from __future__ import annotations

import argparse
import json
from copy import deepcopy
from typing import Any

import numpy as np

from diagnostics._runtime import (
    REPORTS_DIR,
    load_module,
    load_solver_module,
    probe_backend_or_write_skip,
    resolve_script_path,
)
from diagnostics.basis_coefficient_recovery import _component_summary, _fit_coefficients
from diagnostics.bridge_basis_projection import BASIS_PROJECTION_PATH, _build_bridge_lateral_field, _build_projection_families
from solvers import coefficient_path_bundle as _COEFF_BUNDLE_CORE


VALIDATOR_PATH = resolve_script_path(
    "validate_oct_nonspherical_psf_solver.py",
    "04_validate_oct_nonspherical_psf_solver.py",
)
COEFFICIENT_RECOVERY_PATH = resolve_script_path(
    "15_bridge_basis_coefficient_recovery.py",
    "07_bridge_basis_coefficient_recovery.py",
)


def _load_solver_module():
    return load_solver_module()


_SOLVER = _load_solver_module()
_load_module = load_module


FIT_VARIANTS = [
    {"name": "default", "solver_overrides": {}},
    {
        "name": "wider_theta_window",
        "solver_overrides": {
            "effective_channel_theta_fit_fraction": 0.5,
            "effective_channel_theta_fit_cap_rad": 0.12,
            "effective_channel_n_theta_fit": 13,
            "effective_channel_n_azimuth_fit": 6,
        },
    },
    {
        "name": "denser_angular_sampling",
        "solver_overrides": {
            "effective_channel_n_theta_fit": 15,
            "effective_channel_n_azimuth_fit": 8,
        },
    },
]


EXTRA_CASES = [
    {
        "name": "mild_shape_higher_na",
        "description": "Intermediate case with the mild-shape geometry but a slightly higher NA to stress local angle fitting.",
        "source": {"lambda0_nm": 855.0, "fwhm_nm": 56.0, "n_lambda": 181},
        "grid": {"z_span_um": 18.0, "n_z": 601, "x_span_um": 4.0, "n_x": 41, "na": 0.06, "n_bfp_dense": 41, "n_bfp_sparse": 7},
        "solver": {
            "particle_material": 2.48,
            "medium_material": 1.40,
            "diameter_nm": 250.0,
            "eps": 0.08,
            "beta_deg": 20.0,
            "incident_mode": "linear_x",
            "detection_mode": "co_pol",
        },
    },
    {
        "name": "high_contrast_lower_tilt",
        "description": "Intermediate case with high contrast but lower tilt than the full failure-domain stress test.",
        "source": {"lambda0_nm": 855.0, "fwhm_nm": 56.0, "n_lambda": 181},
        "grid": {"z_span_um": 20.0, "n_z": 601, "x_span_um": 6.0, "n_x": 61, "na": 0.08, "n_bfp_dense": 41, "n_bfp_sparse": 7},
        "solver": {
            "particle_material": 2.48,
            "medium_material": 1.40,
            "diameter_nm": 300.0,
            "eps": 0.18,
            "beta_deg": 35.0,
            "incident_mode": "linear_x",
            "detection_mode": "co_pol",
        },
    },
]


def _mean_abs_ratio(reference: np.ndarray, candidate: np.ndarray) -> float:
    reference = np.asarray(reference, dtype=np.complex128)
    candidate = np.asarray(candidate, dtype=np.complex128)
    return float(np.mean(np.abs(candidate)) / (np.mean(np.abs(reference)) + 1e-30))


def _collect_case_variants(
    case_definition: dict[str, Any],
    *,
    validator,
    basis_module,
    tmatrix_path: str,
    coefficient_map_model_id: str,
    reference_rendered_coefficients_source: str,
):
    bridge_context = _build_bridge_lateral_field(
        validator,
        load_module(basis_module.BRIDGE_PATH, "round6_fit_sensitivity_bridge"),
        case_definition,
        tmatrix_path,
    )
    all_reports = []
    for variant in FIT_VARIANTS:
        asym_result = validator.run_round6p1_case(
            case_definition,
            mode=validator.LOW_NA_ASYMPTOTIC_MODE,
            library_path=tmatrix_path,
            second_order_model="directional_field_expansion_first_order",
            **variant["solver_overrides"],
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
        asym_coeffs = np.asarray(coefficient_bundle.comparison_state.rendered_coefficients_raw, dtype=np.complex128)
        all_reports.append(
            {
                "variant": variant["name"],
                "fit_window": {
                    "theta_fit_max_rad": float(asym_result["effective_channel_theta_fit_max_rad"]),
                    "theta_max_rad": float(asym_result["effective_channel_theta_max_rad"]),
                    "theta_fit_fraction": float(asym_result["effective_channel_theta_fit_fraction"]),
                    "theta_fit_cap_rad": float(asym_result["effective_channel_theta_fit_cap_rad"]),
                    "n_theta_fit": int(asym_result["effective_channel_n_theta_fit"]),
                    "n_azimuth_fit": int(asym_result["effective_channel_n_azimuth_fit"]),
                    "fit_window_kind": asym_result["effective_channel_fit_window_kind"],
                },
                "field_assembly_model_id": coefficient_bundle.field_basis_state.field_assembly_model_id,
                "coefficient_map_model_id": coefficient_bundle.comparison_state.coefficient_map_model_id,
                "reference_rendered_coefficients_source": reference_rendered_coefficients_source,
                "abs_D1_over_abs_B": _mean_abs_ratio(asym_coeffs[:, 0], asym_coeffs[:, 1]),
                "abs_C2_over_abs_B": _mean_abs_ratio(asym_coeffs[:, 0], asym_coeffs[:, 2]),
                "a1_vs_D1_slice_k_relative_residual": _component_summary("a1_vs_D1_slice_k", recovered_coeffs[:, 1], asym_coeffs[:, 1])["relative_residual"],
                "a2_vs_C2_slice_k_relative_residual": _component_summary("a2_vs_C2_slice_k", recovered_coeffs[:, 2], asym_coeffs[:, 2])["relative_residual"],
            }
        )
    default = next(item for item in all_reports if item["variant"] == "default")
    sensitivity_summary = {
        "max_abs_D1_over_abs_B_ratio_vs_default": float(
            max(item["abs_D1_over_abs_B"] / (default["abs_D1_over_abs_B"] + 1e-30) for item in all_reports)
        ),
        "max_abs_C2_over_abs_B_ratio_vs_default": float(
            max(item["abs_C2_over_abs_B"] / (default["abs_C2_over_abs_B"] + 1e-30) for item in all_reports)
        ),
        "max_a1_residual_delta_vs_default": float(
            max(abs(item["a1_vs_D1_slice_k_relative_residual"] - default["a1_vs_D1_slice_k_relative_residual"]) for item in all_reports)
        ),
        "max_a2_residual_delta_vs_default": float(
            max(abs(item["a2_vs_C2_slice_k_relative_residual"] - default["a2_vs_C2_slice_k_relative_residual"]) for item in all_reports)
        ),
    }
    return {
        "case_name": case_definition["name"],
        "variants": all_reports,
        "sensitivity_summary": sensitivity_summary,
    }


def _recommend_next_action(case_reports: list[dict[str, Any]]) -> str:
    unstable_cases = 0
    for report in case_reports:
        summary = report["sensitivity_summary"]
        if (
            summary["max_abs_D1_over_abs_B_ratio_vs_default"] > 2.0
            or summary["max_a1_residual_delta_vs_default"] > 0.1
            or summary["max_a2_residual_delta_vs_default"] > 0.1
        ):
            unstable_cases += 1
    if unstable_cases >= max(2, len(case_reports) // 2):
        return "debug_effective_channel_fit_window_before_usage_mapping"
    return "fit_window_sensitivity_not_dominant"


def build_fit_sensitivity_report(
    *,
    write_reports: bool = True,
    library_path: str | None = None,
    coefficient_map_model_id: str = "identity_slice_projected_rendered_basis",
    reference_rendered_coefficients_source: str = "none",
) -> dict[str, Any]:
    _backend_status, skipped = probe_backend_or_write_skip(
        title="Round 6p1 Effective-Channel Fit Sensitivity",
        json_filename="round6p1_effective_channel_fit_sensitivity.json",
        md_filename="round6p1_effective_channel_fit_sensitivity.md",
        write_reports=write_reports,
        library_path=library_path,
        recommended_next_action="configure_supported_tmatrix_backend_before_fit_sensitivity",
    )
    if skipped is not None:
        return skipped
    validator = load_module(VALIDATOR_PATH, "round6p1_validator_fit_sensitivity")
    basis_module = load_module(BASIS_PROJECTION_PATH, "round6p1_basis_projection_fit_sensitivity")
    tmatrix_path = validator.ensure_tmatrix_loaded(library_path)
    cases = [deepcopy(case) for case in validator.ROUND6P1_REPRESENTATIVE_CASES] + deepcopy(EXTRA_CASES)
    case_reports = [
        _collect_case_variants(
            case,
            validator=validator,
            basis_module=basis_module,
            tmatrix_path=tmatrix_path,
            coefficient_map_model_id=coefficient_map_model_id,
            reference_rendered_coefficients_source=reference_rendered_coefficients_source,
        )
        for case in cases
    ]
    recommended_action = _recommend_next_action(case_reports)
    report = {
        "fit_sensitivity_cases": case_reports,
        "fit_sensitivity_case_names": [case["case_name"] for case in case_reports],
        "fit_sensitivity_recommended_next_action": recommended_action,
        "recommended_next_action": recommended_action,
        "coefficient_map_model_id": coefficient_map_model_id,
        "reference_rendered_coefficients_source": reference_rendered_coefficients_source,
        "fit_window_sensitivity_status": (
            "dominant" if recommended_action == "debug_effective_channel_fit_window_before_usage_mapping" else "not_dominant"
        ),
        "report_version_tag": validator.DEFAULT_REPORT_VERSION_TAG,
    }
    if write_reports:
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        (REPORTS_DIR / "round6p1_effective_channel_fit_sensitivity.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        lines = ["# Round 6p1 Effective-Channel Fit Sensitivity", ""]
        lines.append(f"Recommended next action: `{report['fit_sensitivity_recommended_next_action']}`")
        lines.append("")
        for case_report in case_reports:
            lines.append(f"## {case_report['case_name']}")
            lines.append("")
            lines.append("| Variant | theta_fit_max_rad | n_theta_fit | n_azimuth_fit | |D1|/|B| | |C2|/|B| | a1_vs_D1 residual | a2_vs_C2 residual |")
            lines.append("|---|---:|---:|---:|---:|---:|---:|---:|")
            for variant in case_report["variants"]:
                lines.append(
                    f"| {variant['variant']} | {variant['fit_window']['theta_fit_max_rad']:.6g} | {variant['fit_window']['n_theta_fit']} | "
                    f"{variant['fit_window']['n_azimuth_fit']} | {variant['abs_D1_over_abs_B']:.6g} | {variant['abs_C2_over_abs_B']:.6g} | "
                    f"{variant['a1_vs_D1_slice_k_relative_residual']:.6g} | {variant['a2_vs_C2_slice_k_relative_residual']:.6g} |"
                )
            summary = case_report["sensitivity_summary"]
            lines.append("")
            lines.append(
                f"Sensitivity summary: max `|D1|/|B|` ratio vs default `{summary['max_abs_D1_over_abs_B_ratio_vs_default']:.6g}`, "
                f"max `|C2|/|B|` ratio vs default `{summary['max_abs_C2_over_abs_B_ratio_vs_default']:.6g}`, "
                f"max `a1` residual delta `{summary['max_a1_residual_delta_vs_default']:.6g}`, "
                f"max `a2` residual delta `{summary['max_a2_residual_delta_vs_default']:.6g}`."
            )
            lines.append("")
        (REPORTS_DIR / "round6p1_effective_channel_fit_sensitivity.md").write_text("\n".join(lines), encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Sweep effective-channel local-fit hyperparameters and summarize B/D1/C2 sensitivity.")
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
    report = build_fit_sensitivity_report(
        write_reports=not args.no_write,
        library_path=args.library_path,
        coefficient_map_model_id=args.coefficient_map_model_id,
        reference_rendered_coefficients_source=args.reference_rendered_coefficients_source,
    )
    print(json.dumps(report, indent=2))
    return 0


__all__ = [
    "BASIS_PROJECTION_PATH",
    "COEFFICIENT_RECOVERY_PATH",
    "EXTRA_CASES",
    "FIT_VARIANTS",
    "VALIDATOR_PATH",
    "_collect_case_variants",
    "_load_module",
    "_load_solver_module",
    "_mean_abs_ratio",
    "_recommend_next_action",
    "build_fit_sensitivity_report",
    "main",
]
