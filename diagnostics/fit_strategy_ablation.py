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
from diagnostics.basis_coefficient_recovery import (
    _component_summary,
    _fit_coefficients,
    _shared_scale_component_diagnostics,
)
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


FIT_STRATEGIES = [
    {"name": "split_even_odd", "solver_overrides": {"effective_channel_fit_strategy": "split_even_odd"}},
    {"name": "joint_low_order", "solver_overrides": {"effective_channel_fit_strategy": "joint_low_order"}},
]


def _build_case_variant_report(
    *,
    case_definition: dict[str, Any],
    strategy_name: str,
    solver_overrides: dict[str, Any],
    validator,
    basis_module,
    tmatrix_path: str,
    coefficient_map_model_id: str,
    reference_rendered_coefficients_source: str,
) -> dict[str, Any]:
    bridge_result = validator.run_round6p1_case(case_definition, mode=validator.VECTOR_BRIDGE_MODE, library_path=tmatrix_path)
    asym_result = validator.run_round6p1_case(
        case_definition,
        mode=validator.LOW_NA_ASYMPTOTIC_MODE,
        library_path=tmatrix_path,
        second_order_model="directional_field_expansion_first_order",
        **solver_overrides,
    )
    identity_bundle = _COEFF_BUNDLE_CORE.build_coefficient_path_bundle(asym_result)
    diagnostics = validator.image_difference_diagnostics(
        f"{strategy_name}_vs_bridge",
        validator.snapshot_for_comparison(asym_result),
        validator.snapshot_for_comparison(bridge_result),
    )
    bridge_context = _build_bridge_lateral_field(
        validator,
        load_module(basis_module.BRIDGE_PATH, f"round6_fit_strategy_bridge_{strategy_name}"),
        case_definition,
        tmatrix_path,
    )
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
    shared_scale = _shared_scale_component_diagnostics(
        asym_coeffs,
        recovered_coeffs,
        ("a0_vs_B_k", "a1_vs_D1_slice_k", "a2_vs_C2_slice_k"),
    )
    fit_diag = asym_result["fit_diagnostics"]
    return {
        "fit_strategy": strategy_name,
        "effective_channel_fit_strategy": asym_result.get("effective_channel_fit_strategy"),
        "peakline_x_delta_um": float(diagnostics["peakline_x_delta_um"]),
        "image_relative_l2": float(diagnostics["image_relative_l2"]),
        "centroid_opd_delta_um": float(diagnostics["centroid_opd_delta_um"]),
        "raw_peak_relative_delta": float(diagnostics.get("raw_peak_relative_delta", 0.0)),
        "effective_fit_residual_model": fit_diag["relative_fit_residual_model"],
        "effective_fit_residual_max": float(np.max(np.asarray(fit_diag["relative_fit_residual"], dtype=float))),
        "effective_fit_residual_even_max": float(np.max(np.asarray(fit_diag["relative_fit_residual_even"], dtype=float))),
        "effective_fit_residual_low_order_max": float(np.max(np.asarray(fit_diag["relative_fit_residual_low_order"], dtype=float))),
        "a1_vs_D1_slice_k_relative_residual": _component_summary("a1_vs_D1_slice_k", recovered_coeffs[:, 1], asym_coeffs[:, 1])["relative_residual"],
        "a2_vs_C2_slice_k_relative_residual": _component_summary("a2_vs_C2_slice_k", recovered_coeffs[:, 2], asym_coeffs[:, 2])["relative_residual"],
        "shared_scale_relative_residual": float(shared_scale["relative_residual"]),
        "shared_scale_component_relative_residuals": shared_scale["component_relative_residuals"],
        "effective_channel_theta_fit_max_rad": float(asym_result["effective_channel_theta_fit_max_rad"]),
        "effective_channel_n_theta_fit": int(asym_result["effective_channel_n_theta_fit"]),
        "effective_channel_n_azimuth_fit": int(asym_result["effective_channel_n_azimuth_fit"]),
        "field_assembly_model_id": coefficient_bundle.field_basis_state.field_assembly_model_id,
        "coefficient_map_model_id": coefficient_bundle.comparison_state.coefficient_map_model_id,
        "reference_rendered_coefficients_source": reference_rendered_coefficients_source,
    }


def _recommend_next_action(case_reports: list[dict[str, Any]]) -> str:
    successful_cases = 0
    for case_report in case_reports:
        split = next(item for item in case_report["strategies"] if item["fit_strategy"] == "split_even_odd")
        joint = next(item for item in case_report["strategies"] if item["fit_strategy"] == "joint_low_order")
        a1_improved = joint["a1_vs_D1_slice_k_relative_residual"] < 0.9 * split["a1_vs_D1_slice_k_relative_residual"]
        low_order_fit_improved = joint["effective_fit_residual_low_order_max"] < 0.9 * split["effective_fit_residual_low_order_max"]
        peakline_improved = joint["peakline_x_delta_um"] < split["peakline_x_delta_um"]
        image_not_worse = joint["image_relative_l2"] <= split["image_relative_l2"] + 0.02
        raw_not_worse = joint["raw_peak_relative_delta"] <= split["raw_peak_relative_delta"] + 0.10
        if (
            a1_improved
            and low_order_fit_improved
            and (peakline_improved or joint["image_relative_l2"] < split["image_relative_l2"])
            and image_not_worse
            and raw_not_worse
        ):
            successful_cases += 1
    if successful_cases >= max(2, len(case_reports) // 2 + 1):
        return "promote_joint_low_order_fit_strategy"
    return "joint_low_order_fit_not_yet_decisive"


def build_fit_strategy_ablation_report(
    *,
    write_reports: bool = True,
    library_path: str | None = None,
    coefficient_map_model_id: str = "identity_slice_projected_rendered_basis",
    reference_rendered_coefficients_source: str = "none",
) -> dict[str, Any]:
    _backend_status, skipped = probe_backend_or_write_skip(
        title="Round 6p1 Effective-Channel Fit Strategy Ablation",
        json_filename="round6p1_effective_channel_fit_strategy_ablation.json",
        md_filename="round6p1_effective_channel_fit_strategy_ablation.md",
        write_reports=write_reports,
        library_path=library_path,
        recommended_next_action="configure_supported_tmatrix_backend_before_fit_strategy_ablation",
    )
    if skipped is not None:
        return skipped
    validator = load_module(VALIDATOR_PATH, "round6p1_validator_fit_strategy_ablation")
    basis_module = load_module(BASIS_PROJECTION_PATH, "round6p1_basis_projection_fit_strategy_ablation")
    tmatrix_path = validator.ensure_tmatrix_loaded(library_path)
    case_reports: list[dict[str, Any]] = []
    for case_definition in validator.ROUND6P1_REPRESENTATIVE_CASES:
        strategy_reports = [
            _build_case_variant_report(
                case_definition=case_definition,
                strategy_name=strategy["name"],
                solver_overrides=strategy["solver_overrides"],
                validator=validator,
                basis_module=basis_module,
                tmatrix_path=tmatrix_path,
                coefficient_map_model_id=coefficient_map_model_id,
                reference_rendered_coefficients_source=reference_rendered_coefficients_source,
            )
            for strategy in FIT_STRATEGIES
        ]
        case_reports.append(
            {
                "case_name": case_definition["name"],
                "description": case_definition["description"],
                "strategies": strategy_reports,
            }
        )
    recommended_action = _recommend_next_action(case_reports)
    report = {
        "effective_channel_fit_strategy_cases": case_reports,
        "effective_channel_fit_strategy_case_names": [case["case_name"] for case in case_reports],
        "effective_channel_fit_strategy_recommended_next_action": recommended_action,
        "recommended_next_action": recommended_action,
        "coefficient_map_model_id": coefficient_map_model_id,
        "reference_rendered_coefficients_source": reference_rendered_coefficients_source,
        "effective_channel_fit_strategy_status": (
            "joint_promising" if recommended_action == "promote_joint_low_order_fit_strategy" else "not_yet_decisive"
        ),
        "report_version_tag": validator.DEFAULT_REPORT_VERSION_TAG,
    }
    if write_reports:
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        json_path = REPORTS_DIR / "round6p1_effective_channel_fit_strategy_ablation.json"
        md_path = REPORTS_DIR / "round6p1_effective_channel_fit_strategy_ablation.md"
        json_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        lines = ["# Round 6p1 Effective-Channel Fit Strategy Ablation", ""]
        lines.append(f"Recommended next action: `{report['effective_channel_fit_strategy_recommended_next_action']}`")
        lines.append("")
        for case_report in case_reports:
            lines.append(f"## {case_report['case_name']}")
            lines.append(case_report["description"])
            lines.append("")
            lines.append("| Strategy | fit residual model | fit residual max | even fit residual max | low-order fit residual max | peakline_x_delta_um | image_relative_l2 | centroid_opd_delta_um | raw_peak_relative_delta | a1_vs_D1 residual | a2_vs_C2 residual | shared_scale residual |")
            lines.append("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
            for item in case_report["strategies"]:
                lines.append(
                    f"| {item['fit_strategy']} | {item['effective_fit_residual_model']} | {item['effective_fit_residual_max']:.6g} | "
                    f"{item['effective_fit_residual_even_max']:.6g} | {item['effective_fit_residual_low_order_max']:.6g} | "
                    f"{item['peakline_x_delta_um']:.6g} | {item['image_relative_l2']:.6g} | "
                    f"{item['centroid_opd_delta_um']:.6g} | {item['raw_peak_relative_delta']:.6g} | "
                    f"{item['a1_vs_D1_slice_k_relative_residual']:.6g} | {item['a2_vs_C2_slice_k_relative_residual']:.6g} | "
                    f"{item['shared_scale_relative_residual']:.6g} |"
                )
            lines.append("")
        md_path.write_text("\n".join(lines), encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare split_even_odd and joint_low_order effective-channel coefficient extraction strategies.")
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
    report = build_fit_strategy_ablation_report(
        write_reports=not args.no_write,
        library_path=args.library_path,
        coefficient_map_model_id=args.coefficient_map_model_id,
        reference_rendered_coefficients_source=args.reference_rendered_coefficients_source,
    )
    print(json.dumps(report, indent=2))
    return 0


__all__ = [
    "BASIS_PROJECTION_PATH",
    "FIT_STRATEGIES",
    "VALIDATOR_PATH",
    "_build_case_variant_report",
    "_load_module",
    "_load_solver_module",
    "_recommend_next_action",
    "build_fit_strategy_ablation_report",
    "main",
]
