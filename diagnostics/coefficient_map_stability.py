from __future__ import annotations

import argparse
import json
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
from diagnostics.basis_coefficient_recovery import _fit_coefficients
from diagnostics.bridge_basis_projection import BASIS_PROJECTION_PATH
from diagnostics.coefficient_map_audit import _build_rendered_result, _extract_row
from solvers import coefficient_path_bundle as _COEFF_BUNDLE_CORE


VALIDATOR_PATH = resolve_script_path(
    "validate_oct_nonspherical_psf_solver.py",
    "04_validate_oct_nonspherical_psf_solver.py",
)


def _load_solver_module():
    return load_solver_module()


_SOLVER = _load_solver_module()


def _fit_train_map(
    model_id: str,
    train_cases: list[dict[str, Any]],
) -> _COEFF_BUNDLE_CORE.FittedCoefficientMap:
    projected = np.concatenate(
        [
            np.asarray(
                case["identity_bundle"].rendered_coefficient_state.projected_coefficients_raw,
                dtype=np.complex128,
            )
            for case in train_cases
        ],
        axis=0,
    )
    recovered = np.concatenate(
        [np.asarray(case["recovered_coefficients"], dtype=np.complex128) for case in train_cases],
        axis=0,
    )
    return _COEFF_BUNDLE_CORE.fit_projected_to_rendered_map(
        projected,
        model_id=model_id,
        reference_rendered_coefficients_raw=recovered,
    )


def _residual(reference: np.ndarray, estimate: np.ndarray) -> float:
    reference = np.asarray(reference, dtype=np.complex128)
    estimate = np.asarray(estimate, dtype=np.complex128)
    return float(np.linalg.norm(estimate - reference) / (np.linalg.norm(reference) + 1e-30))


def _normalized_frobenius_distance(a: np.ndarray, b: np.ndarray) -> float:
    a = np.asarray(a, dtype=np.complex128)
    b = np.asarray(b, dtype=np.complex128)
    return float(np.linalg.norm(a - b) / (np.linalg.norm(b) + 1e-30))


def _pairwise_map_distances(case_specific_maps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for i, left in enumerate(case_specific_maps):
        for right in case_specific_maps[i + 1 :]:
            rows.append(
                {
                    "case_a": left["case_name"],
                    "case_b": right["case_name"],
                    "normalized_frobenius_distance": _normalized_frobenius_distance(
                        left["map_matrix"],
                        right["map_matrix"],
                    ),
                }
            )
    return rows


def _mean_metric(entries: list[dict[str, Any]], key: str) -> float:
    if not entries:
        return float("nan")
    return float(np.mean([float(entry[key]) for entry in entries]))


def _summarize_leave_one_out_case(
    *,
    case: dict[str, Any],
    fitted_map: _COEFF_BUNDLE_CORE.FittedCoefficientMap,
    bridge_result: dict[str, Any],
    validator,
) -> dict[str, Any]:
    identity_bundle = case["identity_bundle"]
    rendered_state = _COEFF_BUNDLE_CORE.apply_fitted_coefficient_map(
        identity_bundle.rendered_coefficient_state.projected_coefficients_raw,
        fitted_map,
    )
    rendered_result = _build_rendered_result(
        case["bridge_context"],
        identity_bundle,
        rendered_coefficients_raw=rendered_state.rendered_coefficients_raw,
        coefficient_map_model_id=fitted_map.coefficient_map_model_id,
    )
    injected_vs_bridge = _extract_row(rendered_result, bridge_result, validator)
    recovered_coefficients = np.asarray(case["recovered_coefficients"], dtype=np.complex128)
    recovered_orth = _COEFF_BUNDLE_CORE.project_coefficients_to_orthonormal_basis(
        recovered_coefficients,
        identity_bundle.field_basis_state.orthonormal_r_matrix,
    )
    rendered_orth = _COEFF_BUNDLE_CORE.project_coefficients_to_orthonormal_basis(
        rendered_state.rendered_coefficients_raw,
        identity_bundle.field_basis_state.orthonormal_r_matrix,
    )
    return {
        "held_out_case_name": case["case_name"],
        "raw_rendered_relative_residual": _residual(
            recovered_coefficients,
            rendered_state.rendered_coefficients_raw,
        ),
        "orthonormalized_relative_residual": _residual(recovered_orth, rendered_orth),
        "injected_vs_bridge": injected_vs_bridge,
        "improves_identity_peakline": bool(
            injected_vs_bridge["peakline_x_delta_um"]
            < case["identity_metrics"]["peakline_x_delta_um"]
        ),
        "improves_identity_image_l2": bool(
            injected_vs_bridge["image_relative_l2"]
            < case["identity_metrics"]["image_relative_l2"]
        ),
    }


def _generalization_key(model_report: dict[str, Any]) -> tuple[float, float, float]:
    return (
        float(model_report["aggregate"]["mean_peakline_x_delta_um"]),
        float(model_report["aggregate"]["mean_image_relative_l2"]),
        float(model_report["aggregate"]["mean_raw_rendered_relative_residual"]),
    )


def _recommend_next_action(
    *,
    best_model_id: str,
    best_aggregate: dict[str, Any],
    identity_aggregate: dict[str, Any] | None,
    pairwise_case_map_distances: list[dict[str, Any]],
    ) -> str:
    if best_model_id == "identity_slice_projected_rendered_basis" or identity_aggregate is None:
        return "identity_map_generalization_not_yet_falsified"

    if (
        best_aggregate["cases_improving_peakline"] == best_aggregate["total_cases"]
        and best_aggregate["cases_improving_image_l2"] >= max(2, best_aggregate["total_cases"] - 1)
        and best_aggregate["mean_peakline_x_delta_um"] <= 1.0
        and best_aggregate["mean_image_relative_l2"] < identity_aggregate["mean_image_relative_l2"]
    ):
        median_distance = float(
            np.median([row["normalized_frobenius_distance"] for row in pairwise_case_map_distances])
        ) if pairwise_case_map_distances else 0.0
        if median_distance <= 0.5:
            return "prototype_shared_coefficient_map_candidate_before_measurement_wrapper"
    return "audit_coefficient_map_generalization_before_production"


def _fit_full_panel_candidates(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    panel_case_names = [case["case_name"] for case in cases]
    candidates: list[dict[str, Any]] = []
    for model_id in _COEFF_BUNDLE_CORE.COEFFICIENT_MAP_MODEL_IDS:
        if model_id == "identity_slice_projected_rendered_basis":
            fitted_map = _COEFF_BUNDLE_CORE.fit_projected_to_rendered_map(
                cases[0]["identity_bundle"].rendered_coefficient_state.projected_coefficients_raw,
                model_id=model_id,
            )
        else:
            fitted_map = _fit_train_map(model_id, cases)
        artifact_path = _COEFF_BUNDLE_CORE.shared_coefficient_map_candidate_report_path(
            REPORTS_DIR,
            model_id,
        )
        _COEFF_BUNDLE_CORE.write_shared_coefficient_map_candidate_npz(
            artifact_path,
            fitted_map=fitted_map,
            panel_case_names=panel_case_names,
        )
        candidates.append(
            {
                "coefficient_map_model_id": model_id,
                "artifact_filename": artifact_path.name,
                "artifact_relative_path": artifact_path.name,
                "map_matrix_real": fitted_map.map_matrix.real.tolist(),
                "map_matrix_imag": fitted_map.map_matrix.imag.tolist(),
                "map_matrix_frobenius_norm": float(np.linalg.norm(fitted_map.map_matrix)),
                "coefficient_map_note": fitted_map.coefficient_map_note,
                "coefficient_map_parameters": fitted_map.coefficient_map_parameters,
            }
        )
    return candidates


def _relative_artifact_path(path: Path) -> str:
    try:
        return path.relative_to(REPORTS_DIR).as_posix()
    except ValueError:
        return path.name


def _write_promoted_shared_map_bundles(
    *,
    representative_cases: list[dict[str, Any]],
    promoted_model_id: str,
    shared_map_artifact_path: Path,
    validator,
    tmatrix_path: str | None,
) -> list[dict[str, Any]]:
    if promoted_model_id == "identity_slice_projected_rendered_basis":
        return []
    promoted_runtime_map = _COEFF_BUNDLE_CORE.resolve_runtime_fitted_coefficient_map(
        coefficient_map_model_id=promoted_model_id,
        artifact_path=shared_map_artifact_path,
    )
    artifacts: list[dict[str, Any]] = []
    for case in representative_cases:
        promoted_result = validator.run_round6p1_case(
            case["case_definition"],
            mode=validator.LOW_NA_ASYMPTOTIC_MODE,
            library_path=tmatrix_path,
            second_order_model="directional_field_expansion_first_order",
            coefficient_map_model_id=promoted_model_id,
            coefficient_map_artifact_path=str(shared_map_artifact_path),
        )
        promoted_bundle = _COEFF_BUNDLE_CORE.build_coefficient_path_bundle(
            promoted_result,
            coefficient_map_model_id=promoted_model_id,
            fitted_coefficient_map=promoted_runtime_map,
        )
        artifact_path = _COEFF_BUNDLE_CORE.write_coefficient_path_bundle_npz(
            _COEFF_BUNDLE_CORE.coefficient_bundle_report_path(
                REPORTS_DIR,
                case["case_name"],
                artifact_kind="shared_map_promoted",
                coefficient_map_model_id=promoted_model_id,
            ),
            promoted_bundle,
            case_name=case["case_name"],
            artifact_kind="shared_map_promoted",
            recovered_coefficients_raw=np.asarray(case["recovered_coefficients"], dtype=np.complex128),
        )
        _COEFF_BUNDLE_CORE.read_coefficient_path_bundle_npz(artifact_path)
        artifacts.append(
            {
                "case_name": case["case_name"],
                "coefficient_map_model_id": promoted_model_id,
                "artifact_filename": artifact_path.name,
                "artifact_relative_path": _relative_artifact_path(artifact_path),
                "artifact_kind": "shared_map_promoted",
            }
        )
    return artifacts


def build_coefficient_map_stability_report(
    *,
    write_reports: bool = True,
    library_path: str | None = None,
) -> dict[str, Any]:
    _backend_status, skipped = probe_backend_or_write_skip(
        title="Round 6p1 Coefficient Map Stability",
        json_filename="round6p1_coefficient_map_stability.json",
        md_filename="round6p1_coefficient_map_stability.md",
        write_reports=write_reports,
        library_path=library_path,
        recommended_next_action="configure_supported_tmatrix_backend_before_coefficient_map_stability",
    )
    if skipped is not None:
        return skipped

    validator = load_module(VALIDATOR_PATH, "round6p1_validator_map_stability")
    basis_module = load_module(BASIS_PROJECTION_PATH, "round6p1_basis_projection_map_stability")
    bridge_impl = load_module(basis_module.BRIDGE_PATH, "round6_map_stability_bridge")
    tmatrix_path = validator.ensure_tmatrix_loaded(library_path)

    panel_cases = getattr(
        validator,
        "ROUND6P1_COEFFICIENT_MAP_GENERALIZATION_CASES",
        validator.ROUND6P1_REPRESENTATIVE_CASES,
    )
    representative_cases: list[dict[str, Any]] = []
    for case in panel_cases:
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
        identity_rendered_result = _build_rendered_result(
            bridge_context,
            identity_bundle,
            rendered_coefficients_raw=identity_bundle.rendered_coefficient_state.rendered_coefficients_raw,
            coefficient_map_model_id=identity_bundle.rendered_coefficient_state.coefficient_map_model_id,
        )
        representative_cases.append(
            {
                "case_definition": case,
                "case_name": case["name"],
                "bridge_context": bridge_context,
                "bridge_result": bridge_result,
                "asym_result": asym_result,
                "identity_bundle": identity_bundle,
                "recovered_coefficients": recovered_coefficients,
                "identity_metrics": _extract_row(identity_rendered_result, bridge_result, validator),
            }
        )

    case_specific_linear_maps = []
    for case in representative_cases:
        fitted_map = _COEFF_BUNDLE_CORE.fit_projected_to_rendered_map(
            case["identity_bundle"].rendered_coefficient_state.projected_coefficients_raw,
            model_id="fitted_linear_map_3x3",
            reference_rendered_coefficients_raw=case["recovered_coefficients"],
        )
        case_specific_linear_maps.append(
            {
                "case_name": case["case_name"],
                "map_matrix": fitted_map.map_matrix,
                "map_matrix_real": fitted_map.map_matrix.real.tolist(),
                "map_matrix_imag": fitted_map.map_matrix.imag.tolist(),
                "map_matrix_frobenius_norm": float(np.linalg.norm(fitted_map.map_matrix)),
            }
        )

    pairwise_case_map_distances = _pairwise_map_distances(case_specific_linear_maps)

    model_reports = []
    for model_id in _COEFF_BUNDLE_CORE.COEFFICIENT_MAP_MODEL_IDS:
        held_out_cases = []
        for held_out_case in representative_cases:
            train_cases = [case for case in representative_cases if case["case_name"] != held_out_case["case_name"]]
            if model_id == "identity_slice_projected_rendered_basis":
                fitted_map = _COEFF_BUNDLE_CORE.fit_projected_to_rendered_map(
                    held_out_case["identity_bundle"].rendered_coefficient_state.projected_coefficients_raw,
                    model_id=model_id,
                )
            else:
                fitted_map = _fit_train_map(model_id, train_cases)
            held_out_cases.append(
                _summarize_leave_one_out_case(
                    case=held_out_case,
                    fitted_map=fitted_map,
                    bridge_result=held_out_case["bridge_result"],
                    validator=validator,
                )
            )
        aggregate = {
            "mean_peakline_x_delta_um": _mean_metric(
                [entry["injected_vs_bridge"] for entry in held_out_cases],
                "peakline_x_delta_um",
            ),
            "mean_image_relative_l2": _mean_metric(
                [entry["injected_vs_bridge"] for entry in held_out_cases],
                "image_relative_l2",
            ),
            "mean_raw_rendered_relative_residual": _mean_metric(
                held_out_cases,
                "raw_rendered_relative_residual",
            ),
            "mean_orthonormalized_relative_residual": _mean_metric(
                held_out_cases,
                "orthonormalized_relative_residual",
            ),
            "cases_improving_peakline": int(sum(1 for entry in held_out_cases if entry["improves_identity_peakline"])),
            "cases_improving_image_l2": int(sum(1 for entry in held_out_cases if entry["improves_identity_image_l2"])),
            "total_cases": len(held_out_cases),
        }
        model_reports.append(
            {
                "coefficient_map_model_id": model_id,
                "leave_one_out_cases": held_out_cases,
                "aggregate": aggregate,
            }
        )

    full_panel_shared_map_candidates = _fit_full_panel_candidates(representative_cases)
    best_model = min(model_reports, key=_generalization_key)
    identity_report = next(
        (entry for entry in model_reports if entry["coefficient_map_model_id"] == "identity_slice_projected_rendered_basis"),
        None,
    )
    promoted_shared_map_artifacts = []
    if write_reports:
        candidate_entry = next(
            (
                entry
                for entry in full_panel_shared_map_candidates
                if entry["coefficient_map_model_id"] == best_model["coefficient_map_model_id"]
            ),
            None,
        )
        if candidate_entry is not None and best_model["coefficient_map_model_id"] != "identity_slice_projected_rendered_basis":
            promoted_shared_map_artifacts = _write_promoted_shared_map_bundles(
                representative_cases=representative_cases,
                promoted_model_id=best_model["coefficient_map_model_id"],
                shared_map_artifact_path=REPORTS_DIR / candidate_entry["artifact_filename"],
                validator=validator,
                tmatrix_path=tmatrix_path,
            )
    promoted_runtime_plan = _COEFF_BUNDLE_CORE.plan_runtime_field_assembly_contract(
        requested_second_order_model="tensor_closure",
        coefficient_map_runtime_mode="rendered_basis_override",
        coefficient_map_model_id=best_model["coefficient_map_model_id"],
        coefficient_map_artifact_path="shared_map_candidate",
        lateral_shift_model="first_order",
        lateral_shift_coupling="envelope_only",
        lateral_shift_impl="analytic_gaussian",
        rendered_basis_shift_target="baseline_envelope_ratio",
    )
    report = {
        "coefficient_map_stability_case_names": [case["case_name"] for case in representative_cases],
        "coefficient_map_generalization_panel_size": len(representative_cases),
        "coefficient_map_models": list(_COEFF_BUNDLE_CORE.COEFFICIENT_MAP_MODEL_IDS),
        "full_panel_shared_map_candidates": full_panel_shared_map_candidates,
        "case_specific_linear_maps": [
            {
                key: value
                for key, value in entry.items()
                if key != "map_matrix"
            }
            for entry in case_specific_linear_maps
        ],
        "pairwise_case_map_distances": pairwise_case_map_distances,
        "generalization_models": model_reports,
        "best_generalizing_model_id": best_model["coefficient_map_model_id"],
        "promoted_shared_map_model_id": best_model["coefficient_map_model_id"],
        "promoted_shared_map_runtime_scope": "general_asymptotic_rendered_basis_override",
        "promoted_shared_map_runtime_contract_status": promoted_runtime_plan.coefficient_map_runtime_contract_status,
        "promoted_shared_map_runtime_supported_lateral_shift_models": list(
            promoted_runtime_plan.runtime_field_assembly_supported_lateral_shift_models
        ),
        "promoted_shared_map_runtime_lateral_shift_constraint": promoted_runtime_plan.runtime_field_assembly_lateral_shift_constraint,
        "promoted_shared_map_runtime_shift_target": promoted_runtime_plan.rendered_basis_shift_target,
        "promoted_shared_map_artifacts": promoted_shared_map_artifacts,
        "coefficient_map_stability_recommended_next_action": _recommend_next_action(
            best_model_id=best_model["coefficient_map_model_id"],
            best_aggregate=best_model["aggregate"],
            identity_aggregate=None if identity_report is None else identity_report["aggregate"],
            pairwise_case_map_distances=pairwise_case_map_distances,
        ),
        "recommended_next_action": _recommend_next_action(
            best_model_id=best_model["coefficient_map_model_id"],
            best_aggregate=best_model["aggregate"],
            identity_aggregate=None if identity_report is None else identity_report["aggregate"],
            pairwise_case_map_distances=pairwise_case_map_distances,
        ),
        "report_kind": "coefficient_map_stability",
        "report_version_tag": validator.DEFAULT_REPORT_VERSION_TAG,
    }

    if write_reports:
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        json_path = REPORTS_DIR / "round6p1_coefficient_map_stability.json"
        md_path = REPORTS_DIR / "round6p1_coefficient_map_stability.md"
        json_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        lines = [
            "# Round 6p1 Coefficient Map Stability",
            "",
            f"Recommended next action: `{report['coefficient_map_stability_recommended_next_action']}`",
            "",
            f"Best generalizing model: `{report['best_generalizing_model_id']}`",
            "",
            f"Generalization panel size: `{report['coefficient_map_generalization_panel_size']}`",
            "",
            f"Promoted shared-map runtime model: `{report['promoted_shared_map_model_id']}`",
            "",
            f"Promoted shared-map runtime scope: `{report['promoted_shared_map_runtime_scope']}`",
            "",
            f"Promoted shared-map contract status: `{report['promoted_shared_map_runtime_contract_status']}`",
            "",
            "Promoted shared-map supported lateral-shift models: "
            f"`{', '.join(report['promoted_shared_map_runtime_supported_lateral_shift_models'])}`",
            "",
            "Promoted shared-map lateral-shift constraint: "
            f"`{report['promoted_shared_map_runtime_lateral_shift_constraint']}`",
            "",
            "Promoted shared-map shift target: "
            f"`{report['promoted_shared_map_runtime_shift_target']}`",
            "",
            "## Full-panel shared map candidates",
            "",
            "| model | artifact | Frobenius norm |",
            "|---|---|---:|",
        ]
        for candidate in full_panel_shared_map_candidates:
            lines.append(
                f"| {candidate['coefficient_map_model_id']} | "
                f"{candidate['artifact_relative_path']} | "
                f"{candidate['map_matrix_frobenius_norm']:.6g} |"
            )
        if promoted_shared_map_artifacts:
            lines.extend(
                [
                    "",
                    "## Promoted shared-map runtime bundles",
                    "",
                    "| case | model | artifact |",
                    "|---|---|---|",
                ]
            )
            for artifact in promoted_shared_map_artifacts:
                lines.append(
                    f"| {artifact['case_name']} | {artifact['coefficient_map_model_id']} | {artifact['artifact_relative_path']} |"
                )
        lines.extend(
            [
                "",
            "## Pairwise fitted-linear map distances",
            "",
            "| case A | case B | normalized Frobenius distance |",
            "|---|---|---:|",
            ]
        )
        for row in pairwise_case_map_distances:
            lines.append(
                f"| {row['case_a']} | {row['case_b']} | {row['normalized_frobenius_distance']:.6g} |"
            )
        lines.append("")
        for model_report in model_reports:
            aggregate = model_report["aggregate"]
            lines.extend(
                [
                    f"## {model_report['coefficient_map_model_id']}",
                    "",
                    (
                        f"Mean peakline delta `{aggregate['mean_peakline_x_delta_um']:.6g}`, "
                        f"mean image L2 `{aggregate['mean_image_relative_l2']:.6g}`, "
                        f"mean raw coeff residual `{aggregate['mean_raw_rendered_relative_residual']:.6g}`."
                    ),
                    "",
                    "| held-out case | image L2 | peakline delta | raw coeff residual | orth coeff residual | improves identity peakline | improves identity image L2 |",
                    "|---|---:|---:|---:|---:|---|---|",
                ]
            )
            for held_out in model_report["leave_one_out_cases"]:
                injected = held_out["injected_vs_bridge"]
                lines.append(
                    f"| {held_out['held_out_case_name']} | "
                    f"{injected['image_relative_l2']:.6g} | "
                    f"{injected['peakline_x_delta_um']:.6g} | "
                    f"{held_out['raw_rendered_relative_residual']:.6g} | "
                    f"{held_out['orthonormalized_relative_residual']:.6g} | "
                    f"{'yes' if held_out['improves_identity_peakline'] else 'no'} | "
                    f"{'yes' if held_out['improves_identity_image_l2'] else 'no'} |"
                )
            lines.append("")
        md_path.write_text("\n".join(lines), encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit coefficient-map stability and leave-one-out generalization across representative cases.")
    parser.add_argument("--no-write", action="store_true", help="Do not write report artifacts.")
    parser.add_argument("--library-path", default=None, help="Optional explicit TMATRIX library path.")
    args = parser.parse_args()
    report = build_coefficient_map_stability_report(write_reports=not args.no_write, library_path=args.library_path)
    print(json.dumps(report, indent=2))
    return 0


__all__ = [
    "VALIDATOR_PATH",
    "build_coefficient_map_stability_report",
    "main",
]
