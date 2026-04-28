from __future__ import annotations

import argparse
import json
from typing import Any

import numpy as np

from diagnostics._runtime import (
    REPORTS_DIR,
    load_module,
    probe_backend_or_write_skip,
    resolve_script_path,
)
from diagnostics.basis_coefficient_recovery import _fit_coefficients
from diagnostics.bridge_basis_projection import BASIS_PROJECTION_PATH, _build_bridge_lateral_field, _build_projection_families
from diagnostics.coefficient_map_audit import _build_rendered_result, _extract_row
from solvers import coefficient_path_bundle as _COEFF_BUNDLE_CORE


VALIDATOR_PATH = resolve_script_path(
    "validate_oct_nonspherical_psf_solver.py",
    "04_validate_oct_nonspherical_psf_solver.py",
)

DEFAULT_REFERENCE_SOURCE = "bridge_recovered"
TRAIN_EVAL_SPLIT_KIND = "even_odd_wavelength_split"


def _split_wavelength_indices(n_lambda: int) -> tuple[np.ndarray, np.ndarray]:
    train_idx = np.arange(0, n_lambda, 2, dtype=int)
    eval_idx = np.arange(1, n_lambda, 2, dtype=int)
    if eval_idx.size == 0:
        eval_idx = train_idx.copy()
    return train_idx, eval_idx


def _residual(reference: np.ndarray, estimate: np.ndarray, indices: np.ndarray | None = None) -> float:
    reference = np.asarray(reference, dtype=np.complex128)
    estimate = np.asarray(estimate, dtype=np.complex128)
    if indices is not None:
        reference = reference[indices]
        estimate = estimate[indices]
    return float(np.linalg.norm(estimate - reference) / (np.linalg.norm(reference) + 1e-30))


def _fit_map_for_case(
    *,
    projected_coefficients_raw: np.ndarray,
    recovered_coefficients_raw: np.ndarray,
    model_id: str,
    reference_source: str,
) -> tuple[_COEFF_BUNDLE_CORE.FittedCoefficientMap, np.ndarray | None, np.ndarray, np.ndarray]:
    train_idx, eval_idx = _split_wavelength_indices(projected_coefficients_raw.shape[0])
    reference = _COEFF_BUNDLE_CORE.resolve_reference_rendered_coefficients(
        projected_coefficients_raw,
        recovered_coefficients_raw,
        source=reference_source,
    )
    if model_id == "identity_slice_projected_rendered_basis":
        fitted_map = _COEFF_BUNDLE_CORE.fit_projected_to_rendered_map(
            projected_coefficients_raw,
            model_id=model_id,
        )
    else:
        fitted_map = _COEFF_BUNDLE_CORE.fit_projected_to_rendered_map(
            projected_coefficients_raw[train_idx],
            model_id=model_id,
            reference_rendered_coefficients_raw=None if reference is None else reference[train_idx],
        )
    return fitted_map, reference, train_idx, eval_idx


def _relative_artifact_path(path: Path) -> str:
    try:
        return path.relative_to(REPORTS_DIR).as_posix()
    except ValueError:
        return path.name


def _evaluate_model_for_case(
    *,
    case_definition: dict[str, Any],
    bridge_context: dict[str, Any],
    bridge_result: dict[str, Any],
    asym_result: dict[str, Any],
    recovered_coefficients_raw: np.ndarray,
    model_id: str,
    reference_source: str,
    validator,
) -> dict[str, Any]:
    identity_bundle = _COEFF_BUNDLE_CORE.build_coefficient_path_bundle(asym_result)
    projected_coefficients_raw = np.asarray(
        identity_bundle.rendered_coefficient_state.projected_coefficients_raw,
        dtype=np.complex128,
    )
    fitted_map, reference_coefficients_raw, train_idx, eval_idx = _fit_map_for_case(
        projected_coefficients_raw=projected_coefficients_raw,
        recovered_coefficients_raw=recovered_coefficients_raw,
        model_id=model_id,
        reference_source=reference_source,
    )
    rendered_state = _COEFF_BUNDLE_CORE.apply_fitted_coefficient_map(projected_coefficients_raw, fitted_map)
    rendered_result = _build_rendered_result(
        bridge_context,
        identity_bundle,
        rendered_coefficients_raw=rendered_state.rendered_coefficients_raw,
        coefficient_map_model_id=model_id,
    )
    injected_vs_bridge = _extract_row(rendered_result, bridge_result, validator)
    orth_rendered = _COEFF_BUNDLE_CORE.project_coefficients_to_orthonormal_basis(
        rendered_state.rendered_coefficients_raw,
        identity_bundle.field_basis_state.orthonormal_r_matrix,
    )

    if reference_coefficients_raw is None:
        full_raw_residual = float("nan")
        train_raw_residual = float("nan")
        eval_raw_residual = float("nan")
        full_orth_residual = float("nan")
        train_orth_residual = float("nan")
        eval_orth_residual = float("nan")
        shared_scale_residual = float("nan")
    else:
        orth_reference = _COEFF_BUNDLE_CORE.project_coefficients_to_orthonormal_basis(
            reference_coefficients_raw,
            identity_bundle.field_basis_state.orthonormal_r_matrix,
        )
        comparison_views = _COEFF_BUNDLE_CORE.build_external_comparison_views(
            identity_bundle,
            reference_coefficients_raw,
        )
        full_raw_residual = _residual(reference_coefficients_raw, rendered_state.rendered_coefficients_raw)
        train_raw_residual = _residual(reference_coefficients_raw, rendered_state.rendered_coefficients_raw, train_idx)
        eval_raw_residual = _residual(reference_coefficients_raw, rendered_state.rendered_coefficients_raw, eval_idx)
        full_orth_residual = _residual(orth_reference, orth_rendered)
        train_orth_residual = _residual(orth_reference, orth_rendered, train_idx)
        eval_orth_residual = _residual(orth_reference, orth_rendered, eval_idx)
        shared_scale_residual = float(comparison_views["shared_scale_alignment"]["relative_residual"])

    map_matrix = np.asarray(fitted_map.map_matrix, dtype=np.complex128)
    return {
        "coefficient_map_model_id": model_id,
        "reference_rendered_coefficients_source": reference_source,
        "train_eval_split_kind": TRAIN_EVAL_SPLIT_KIND,
        "train_lambda_count": int(train_idx.size),
        "eval_lambda_count": int(eval_idx.size),
        "raw_rendered_relative_residual": full_raw_residual,
        "train_raw_rendered_relative_residual": train_raw_residual,
        "eval_raw_rendered_relative_residual": eval_raw_residual,
        "orthonormalized_relative_residual": full_orth_residual,
        "train_orthonormalized_relative_residual": train_orth_residual,
        "eval_orthonormalized_relative_residual": eval_orth_residual,
        "shared_scale_relative_residual": shared_scale_residual,
        "injected_vs_bridge": injected_vs_bridge,
        "map_matrix_condition_number": float(np.linalg.cond(map_matrix)),
        "map_matrix_rank": int(np.linalg.matrix_rank(map_matrix)),
        "map_matrix_real": map_matrix.real.tolist(),
        "map_matrix_imag": map_matrix.imag.tolist(),
        "field_assembly_model_id": identity_bundle.field_basis_state.field_assembly_model_id,
    }


def _best_model_key(model_report: dict[str, Any]) -> tuple[float, float, float]:
    injected = model_report["injected_vs_bridge"]
    eval_residual = model_report["eval_raw_rendered_relative_residual"]
    if not np.isfinite(eval_residual):
        eval_residual = float("inf")
    return (
        float(injected["peakline_x_delta_um"]),
        float(injected["image_relative_l2"]),
        float(eval_residual),
    )


def _mean_metric(model_reports: list[dict[str, Any]], key: str) -> float:
    values: list[float] = []
    for report in model_reports:
        value = report
        for part in key.split("."):
            value = value[part]
        value = float(value)
        if np.isfinite(value):
            values.append(value)
    if not values:
        return float("nan")
    return float(np.mean(values))


def _recommend_next_action(case_reports: list[dict[str, Any]]) -> str:
    if not case_reports:
        return "run_coefficient_map_ablation"
    non_identity_wins = sum(
        case["best_model_id"] != "identity_slice_projected_rendered_basis"
        for case in case_reports
    )
    fitted_linear_wins = sum(
        case["best_model_id"] == "fitted_linear_map_3x3"
        for case in case_reports
    )
    if fitted_linear_wins >= max(2, len(case_reports) // 2 + 1):
        return "require_train_eval_generalization_before_promoting_fitted_map"
    if non_identity_wins >= max(2, len(case_reports) // 2):
        return "audit_coefficient_map_generalization_before_production"
    return "identity_map_not_yet_falsified_continue_coefficient_definition_audit"


def build_coefficient_map_ablation_report(
    *,
    write_reports: bool = True,
    library_path: str | None = None,
    reference_rendered_coefficients_source: str = DEFAULT_REFERENCE_SOURCE,
) -> dict[str, Any]:
    _backend_status, skipped = probe_backend_or_write_skip(
        title="Round 6p1 Coefficient Map Ablation",
        json_filename="round6p1_coefficient_map_ablation.json",
        md_filename="round6p1_coefficient_map_ablation.md",
        write_reports=write_reports,
        library_path=library_path,
        recommended_next_action="configure_supported_tmatrix_backend_before_coefficient_map_ablation",
    )
    if skipped is not None:
        return skipped

    validator = load_module(VALIDATOR_PATH, "round6p1_validator_map_ablation")
    basis_module = load_module(BASIS_PROJECTION_PATH, "round6p1_basis_projection_map_ablation")
    bridge_impl = load_module(basis_module.BRIDGE_PATH, "round6_map_ablation_bridge")
    tmatrix_path = validator.ensure_tmatrix_loaded(library_path)

    case_reports: list[dict[str, Any]] = []
    aggregate_by_model: dict[str, list[dict[str, Any]]] = {
        model_id: [] for model_id in _COEFF_BUNDLE_CORE.COEFFICIENT_MAP_MODEL_IDS
    }
    for case in validator.ROUND6P1_REPRESENTATIVE_CASES:
        bridge_context = _build_bridge_lateral_field(validator, bridge_impl, case, tmatrix_path)
        bridge_result = validator.run_round6p1_case(case, mode=validator.VECTOR_BRIDGE_MODE, library_path=tmatrix_path)
        asym_result = validator.run_round6p1_case(
            case,
            mode=validator.LOW_NA_ASYMPTOTIC_MODE,
            library_path=tmatrix_path,
            second_order_model="directional_field_expansion_first_order",
        )
        families = _build_projection_families(asym_result)
        full_family = next(family for family in families if family.name == "R0_plus_R1_plus_R2")
        recovered_coefficients_raw = _fit_coefficients(
            bridge_context["lateral_field"],
            full_family.basis_matrix,
        )
        case_specific_fitted_artifact = None
        if write_reports:
            fitted_diag_map, _, _, _ = _fit_map_for_case(
                projected_coefficients_raw=np.asarray(
                    _COEFF_BUNDLE_CORE.build_coefficient_path_bundle(asym_result)
                    .rendered_coefficient_state.projected_coefficients_raw,
                    dtype=np.complex128,
                ),
                recovered_coefficients_raw=recovered_coefficients_raw,
                model_id="fitted_linear_map_3x3",
                reference_source=reference_rendered_coefficients_source,
            )
            fitted_diag_bundle = _COEFF_BUNDLE_CORE.build_coefficient_path_bundle(
                asym_result,
                coefficient_map_model_id="fitted_linear_map_3x3",
                fitted_coefficient_map=fitted_diag_map,
            )
            fitted_diag_path = _COEFF_BUNDLE_CORE.write_coefficient_path_bundle_npz(
                _COEFF_BUNDLE_CORE.coefficient_bundle_report_path(
                    REPORTS_DIR,
                    case["name"],
                    artifact_kind="case_specific_fitted_map_diagnostic",
                ),
                fitted_diag_bundle,
                case_name=case["name"],
                artifact_kind="case_specific_fitted_map_diagnostic",
                recovered_coefficients_raw=recovered_coefficients_raw,
            )
            _COEFF_BUNDLE_CORE.read_coefficient_path_bundle_npz(fitted_diag_path)
            case_specific_fitted_artifact = {
                "artifact_filename": fitted_diag_path.name,
                "artifact_relative_path": _relative_artifact_path(fitted_diag_path),
                "artifact_kind": "case_specific_fitted_map_diagnostic",
                "coefficient_map_model_id": "fitted_linear_map_3x3",
            }
        model_reports: list[dict[str, Any]] = []
        for model_id in _COEFF_BUNDLE_CORE.COEFFICIENT_MAP_MODEL_IDS:
            model_report = _evaluate_model_for_case(
                case_definition=case,
                bridge_context=bridge_context,
                bridge_result=bridge_result,
                asym_result=asym_result,
                recovered_coefficients_raw=recovered_coefficients_raw,
                model_id=model_id,
                reference_source=reference_rendered_coefficients_source,
                validator=validator,
            )
            model_reports.append(model_report)
            aggregate_by_model[model_id].append(model_report)
        best_model = min(model_reports, key=_best_model_key)
        for model_report in model_reports:
            model_report["is_best_model"] = model_report["coefficient_map_model_id"] == best_model["coefficient_map_model_id"]
        case_reports.append(
            {
                "case_name": case["name"],
                "description": case["description"],
                "best_model_id": best_model["coefficient_map_model_id"],
                "case_specific_fitted_map_artifact": case_specific_fitted_artifact,
                "map_models": model_reports,
            }
        )

    aggregate_models = []
    for model_id, model_reports in aggregate_by_model.items():
        aggregate_models.append(
            {
                "coefficient_map_model_id": model_id,
                "mean_peakline_x_delta_um": _mean_metric(model_reports, "injected_vs_bridge.peakline_x_delta_um"),
                "mean_image_relative_l2": _mean_metric(model_reports, "injected_vs_bridge.image_relative_l2"),
                "mean_eval_raw_rendered_relative_residual": _mean_metric(model_reports, "eval_raw_rendered_relative_residual"),
                "mean_eval_orthonormalized_relative_residual": _mean_metric(model_reports, "eval_orthonormalized_relative_residual"),
                "mean_map_matrix_condition_number": _mean_metric(model_reports, "map_matrix_condition_number"),
                "cases_selected_as_best": int(
                    sum(report["is_best_model"] for report in model_reports)
                ),
            }
        )
    best_aggregate = min(
        aggregate_models,
        key=lambda row: (
            float(row["mean_peakline_x_delta_um"]),
            float(row["mean_image_relative_l2"]),
            float(row["mean_eval_raw_rendered_relative_residual"]),
        ),
    )
    recommended_action = _recommend_next_action(case_reports)
    report = {
        "coefficient_map_ablation_cases": case_reports,
        "coefficient_map_ablation_case_names": [case["case_name"] for case in case_reports],
        "coefficient_map_ablation_models": aggregate_models,
        "best_ablated_coefficient_map_model_id": best_aggregate["coefficient_map_model_id"],
        "coefficient_map_ablation_recommended_next_action": recommended_action,
        "recommended_next_action": recommended_action,
        "reference_rendered_coefficients_source": reference_rendered_coefficients_source,
        "train_eval_split_kind": TRAIN_EVAL_SPLIT_KIND,
        "case_specific_fitted_map_artifact_kind": "case_specific_fitted_map_diagnostic",
        "report_kind": "coefficient_map_ablation",
        "report_version_tag": validator.DEFAULT_REPORT_VERSION_TAG,
    }

    if write_reports:
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        json_path = REPORTS_DIR / "round6p1_coefficient_map_ablation.json"
        md_path = REPORTS_DIR / "round6p1_coefficient_map_ablation.md"
        json_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        lines = [
            "# Round 6p1 Coefficient Map Ablation",
            "",
            f"Recommended next action: `{recommended_action}`",
            "",
            f"Reference rendered coefficients source: `{reference_rendered_coefficients_source}`",
            "",
            f"Train/eval split kind: `{TRAIN_EVAL_SPLIT_KIND}`",
            "",
            f"Best ablated map model: `{best_aggregate['coefficient_map_model_id']}`",
            "",
            "Case-specific fitted-map diagnostic artifacts are written separately from native and shared promoted bundles.",
            "",
            "## Aggregate model comparison",
            "",
            "| model | mean peakline delta | mean image L2 | mean eval raw residual | mean eval orth residual | mean map cond | best-case wins |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
        for aggregate in aggregate_models:
            lines.append(
                f"| {aggregate['coefficient_map_model_id']} | "
                f"{aggregate['mean_peakline_x_delta_um']:.6g} | "
                f"{aggregate['mean_image_relative_l2']:.6g} | "
                f"{aggregate['mean_eval_raw_rendered_relative_residual']:.6g} | "
                f"{aggregate['mean_eval_orthonormalized_relative_residual']:.6g} | "
                f"{aggregate['mean_map_matrix_condition_number']:.6g} | "
                f"{aggregate['cases_selected_as_best']} |"
            )
        lines.append("")
        for case_report in case_reports:
            lines.append(f"## {case_report['case_name']}")
            lines.append(case_report["description"])
            lines.append("")
            if case_report["case_specific_fitted_map_artifact"] is not None:
                lines.append(
                    f"Case-specific fitted-map artifact: `{case_report['case_specific_fitted_map_artifact']['artifact_relative_path']}`"
                )
                lines.append("")
            lines.append(
                "| map model | train raw residual | eval raw residual | train orth residual | eval orth residual | image L2 | peakline delta | map cond | best |"
            )
            lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---|")
            for model_report in case_report["map_models"]:
                injected = model_report["injected_vs_bridge"]
                lines.append(
                    f"| {model_report['coefficient_map_model_id']} | "
                    f"{model_report['train_raw_rendered_relative_residual']:.6g} | "
                    f"{model_report['eval_raw_rendered_relative_residual']:.6g} | "
                    f"{model_report['train_orthonormalized_relative_residual']:.6g} | "
                    f"{model_report['eval_orthonormalized_relative_residual']:.6g} | "
                    f"{injected['image_relative_l2']:.6g} | "
                    f"{injected['peakline_x_delta_um']:.6g} | "
                    f"{model_report['map_matrix_condition_number']:.6g} | "
                    f"{'yes' if model_report['is_best_model'] else 'no'} |"
                )
            lines.append("")
        md_path.write_text("\n".join(lines), encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare executable projected-to-rendered coefficient-map models on the representative panel."
    )
    parser.add_argument("--no-write", action="store_true", help="Do not write report artifacts.")
    parser.add_argument("--library-path", default=None, help="Optional explicit TMATRIX library path.")
    parser.add_argument(
        "--reference-rendered-coefficients-source",
        default=DEFAULT_REFERENCE_SOURCE,
        choices=_COEFF_BUNDLE_CORE.REFERENCE_RENDERED_COEFFICIENT_SOURCES,
        help="Reference source used when fitting non-identity map models.",
    )
    args = parser.parse_args()
    report = build_coefficient_map_ablation_report(
        write_reports=not args.no_write,
        library_path=args.library_path,
        reference_rendered_coefficients_source=args.reference_rendered_coefficients_source,
    )
    print(json.dumps(report, indent=2))
    return 0


__all__ = [
    "DEFAULT_REFERENCE_SOURCE",
    "TRAIN_EVAL_SPLIT_KIND",
    "VALIDATOR_PATH",
    "build_coefficient_map_ablation_report",
    "main",
]
