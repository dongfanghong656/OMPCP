from __future__ import annotations

from typing import Any

import numpy as np

REQUIRED_EFFECTIVE_COEFFICIENT_RESULT_KEYS = (
    "lambda_nm",
    "B_k",
    "D1_vector_k",
    "D1_slice_k",
    "C2_tensor_k",
    "C2_slice_k",
    "lateral_slice_axis",
    "fit_diagnostics",
)

REQUIRED_EFFECTIVE_FIT_DIAGNOSTIC_KEYS = (
    "fit_strategy",
    "relative_fit_residual_model",
    "C2_tensor_basis",
    "D1_tensor_basis",
)

ALLOWED_EFFECTIVE_FIT_STRATEGIES = {"split_even_odd", "joint_low_order"}
ALLOWED_EFFECTIVE_RESIDUAL_MODELS = {"ideal_mode_constant", "even", "low_order"}
ALLOWED_EFFECTIVE_TENSOR_BASES = {"local_backscatter_angle_components_alpha_beta"}


def complex_alignment(reference: np.ndarray, candidate: np.ndarray) -> dict[str, float]:
    reference = np.asarray(reference, dtype=np.complex128)
    candidate = np.asarray(candidate, dtype=np.complex128)
    scale = np.vdot(reference, candidate) / (np.vdot(reference, reference) + 1e-30)
    residual = np.linalg.norm(candidate - scale * reference) / (np.linalg.norm(candidate) + 1e-30)
    return {
        "scale_abs": float(np.abs(scale)),
        "scale_phase_rad": float(np.angle(scale)),
        "relative_residual": float(residual),
    }


def mean_abs_ratio(reference: np.ndarray, candidate: np.ndarray) -> float:
    reference = np.asarray(reference, dtype=np.complex128)
    candidate = np.asarray(candidate, dtype=np.complex128)
    return float(np.mean(np.abs(candidate)) / (np.mean(np.abs(reference)) + 1e-30))


def shared_scale_component_diagnostics(
    asymptotic_coeffs: np.ndarray,
    recovered_coeffs: np.ndarray,
    component_names: tuple[str, ...],
) -> dict[str, Any]:
    asymptotic_coeffs = np.asarray(asymptotic_coeffs, dtype=np.complex128)
    recovered_coeffs = np.asarray(recovered_coeffs, dtype=np.complex128)
    alignment = complex_alignment(asymptotic_coeffs.reshape(-1), recovered_coeffs.reshape(-1))
    shared_scale = alignment["scale_abs"] * np.exp(1j * alignment["scale_phase_rad"])
    component_residuals: dict[str, float] = {}
    component_mean_abs_ratios: dict[str, float] = {}
    for idx, name in enumerate(component_names):
        scaled_asymptotic = shared_scale * asymptotic_coeffs[:, idx]
        component_residuals[name] = float(
            np.linalg.norm(recovered_coeffs[:, idx] - scaled_asymptotic)
            / (np.linalg.norm(recovered_coeffs[:, idx]) + 1e-30)
        )
        component_mean_abs_ratios[name] = float(
            np.mean(np.abs(recovered_coeffs[:, idx]))
            / (np.mean(np.abs(scaled_asymptotic)) + 1e-30)
        )
    return {
        "scale_abs": alignment["scale_abs"],
        "scale_phase_rad": alignment["scale_phase_rad"],
        "relative_residual": alignment["relative_residual"],
        "component_relative_residuals": component_residuals,
        "component_mean_abs_ratio_under_shared_scale": component_mean_abs_ratios,
    }


def basis_gram_diagnostics(basis_matrix: np.ndarray) -> dict[str, Any]:
    basis_matrix = np.asarray(basis_matrix, dtype=np.complex128)
    gram = basis_matrix.conj().T @ basis_matrix
    return {
        "gram_matrix_real": gram.real.tolist(),
        "gram_matrix_imag": gram.imag.tolist(),
        "gram_condition_number": float(np.linalg.cond(gram)),
    }


def orthonormalized_coefficients(target_field_kx: np.ndarray, basis_matrix: np.ndarray) -> dict[str, Any]:
    target_field_kx = np.asarray(target_field_kx, dtype=np.complex128)
    basis_matrix = np.asarray(basis_matrix, dtype=np.complex128)
    q_matrix, r_matrix = np.linalg.qr(basis_matrix, mode="reduced")
    coeffs = target_field_kx @ np.conj(q_matrix)
    coeff_abs = np.mean(np.abs(coeffs), axis=0)
    return {
        "coefficients": coeffs,
        "r_matrix_real": r_matrix.real.tolist(),
        "r_matrix_imag": r_matrix.imag.tolist(),
        "r_condition_number": float(np.linalg.cond(r_matrix)),
        "coefficient_energy_ratio": {
            "abs_q1_over_abs_q0": float(coeff_abs[1] / (coeff_abs[0] + 1e-30)) if coeff_abs.shape[0] > 1 else 0.0,
            "abs_q2_over_abs_q0": float(coeff_abs[2] / (coeff_abs[0] + 1e-30)) if coeff_abs.shape[0] > 2 else 0.0,
        },
    }


def component_summary(name: str, recovered: np.ndarray, asymptotic: np.ndarray) -> dict[str, Any]:
    alignment = complex_alignment(asymptotic, recovered)
    return {
        "name": name,
        "relative_residual": alignment["relative_residual"],
        "scale_abs": alignment["scale_abs"],
        "scale_phase_rad": alignment["scale_phase_rad"],
        "mean_abs_ratio_recovered_over_asymptotic": mean_abs_ratio(asymptotic, recovered),
    }


def recommend_next_action(case_reports: list[dict[str, Any]]) -> str:
    if not case_reports:
        return "run_bridge_basis_coefficient_recovery"
    problematic_cases = 0
    for report in case_reports:
        vector_residual = float(report["vector_alignment"]["relative_residual"])
        a1_residual = float(next(item["relative_residual"] for item in report["component_summaries"] if item["name"] == "a1_vs_D1_slice_k"))
        a2_residual = float(next(item["relative_residual"] for item in report["component_summaries"] if item["name"] == "a2_vs_C2_slice_k"))
        a1_ratio = float(report["recovered_coefficient_energy_ratio"]["abs_a1_over_abs_a0"] / (report["asymptotic_coefficient_energy_ratio"]["abs_D1_over_abs_B"] + 1e-30))
        if vector_residual > 0.1 or a1_residual > 0.15 or a2_residual > 0.25 or a1_ratio > 1e3:
            problematic_cases += 1
    if problematic_cases >= max(2, len(case_reports) // 2 + 1):
        return "debug_coefficient_extraction_or_usage_mapping"
    return "coefficient_mapping_consistent_consider_higher_order_model"


def basis_conditioning_status(case_reports: list[dict[str, Any]]) -> tuple[str, str]:
    if not case_reports:
        return "unknown", "No coefficient-recovery cases were available."
    max_gram_condition = max(float(case["basis_gram_diagnostics"]["gram_condition_number"]) for case in case_reports)
    max_r_condition = max(float(case["orthonormalized_basis_diagnostics"]["r_condition_number"]) for case in case_reports)
    worst_condition = max(max_gram_condition, max_r_condition)
    if worst_condition > 1.0e8:
        return "poor", "Basis conditioning is poor enough that raw coefficient magnitudes are not directly interpretable."
    if worst_condition > 1.0e5:
        return "caution", "Basis conditioning is moderate-to-poor; interpret raw coefficient ratios cautiously."
    return "acceptable", "Basis conditioning is acceptable for qualitative coefficient comparisons."


def coefficient_interpretability_status(case_reports: list[dict[str, Any]]) -> tuple[str, str]:
    if not case_reports:
        return "unknown", "No coefficient-recovery cases were available."
    worst_ratio_distortion = 1.0
    for case in case_reports:
        raw = case["recovered_coefficient_energy_ratio"]
        orth = case["orthonormalized_recovered_coefficient_energy_ratio"]
        for raw_key, orth_key in (
            ("abs_a1_over_abs_a0", "abs_q1_over_abs_q0"),
            ("abs_a2_over_abs_a0", "abs_q2_over_abs_q0"),
        ):
            raw_value = max(float(raw[raw_key]), 1.0e-30)
            orth_value = max(float(orth[orth_key]), 1.0e-30)
            worst_ratio_distortion = max(worst_ratio_distortion, raw_value / orth_value, orth_value / raw_value)
    if worst_ratio_distortion > 1.0e3:
        return "ill_conditioned", "Raw coefficient ratios are strongly distorted by basis scaling or conditioning."
    if worst_ratio_distortion > 10.0:
        return "caution", "Raw coefficient ratios remain informative, but basis normalization still changes their apparent balance."
    return "usable", "Raw and orthonormalized coefficient ratios are broadly consistent."


def shared_scale_consistency_status(case_reports: list[dict[str, Any]]) -> tuple[str, str]:
    if not case_reports:
        return "unknown", "No coefficient-recovery cases were available."
    worst_component_residuals = {"a0_vs_B_k": 0.0, "a1_vs_D1_slice_k": 0.0, "a2_vs_C2_slice_k": 0.0}
    for case in case_reports:
        component_residuals = case["shared_scale_consistency"]["component_relative_residuals"]
        for name in worst_component_residuals:
            worst_component_residuals[name] = max(worst_component_residuals[name], float(component_residuals.get(name, 0.0)))
    a0_residual = worst_component_residuals["a0_vs_B_k"]
    a1_residual = worst_component_residuals["a1_vs_D1_slice_k"]
    a2_residual = worst_component_residuals["a2_vs_C2_slice_k"]
    if a1_residual > max(a0_residual, a2_residual) + 0.2:
        if max(a0_residual, a2_residual) > 0.3:
            return (
                "d1_primary_with_bc2_caution",
                "Shared-scale consistency shows D1 is the largest mismatch, but B/C2 still carry non-trivial residuals and should not be treated as already cleanly aligned.",
            )
        return (
            "d1_primary",
            "Shared-scale consistency points to D1 as the dominant mismatch while B/C2 remain comparatively better aligned.",
        )
    if max(a0_residual, a2_residual) > 0.3:
        return (
            "mixed_bc2_caution",
            "Shared-scale consistency shows that B/C2 also retain substantial mismatch, so coefficient debugging should not focus on D1 alone.",
        )
    return (
        "roughly_consistent",
        "Shared-scale consistency does not expose a single dominant component mismatch under the current thresholding.",
    )


def extract_effective_coefficient_contract(result: dict[str, Any]) -> dict[str, Any]:
    missing = [key for key in REQUIRED_EFFECTIVE_COEFFICIENT_RESULT_KEYS if key not in result]
    if missing:
        raise KeyError(f"Missing effective coefficient result keys: {', '.join(missing)}")
    fit_diagnostics = result["fit_diagnostics"]
    if not isinstance(fit_diagnostics, dict):
        raise TypeError("fit_diagnostics must be a mapping.")
    missing_fit = [key for key in REQUIRED_EFFECTIVE_FIT_DIAGNOSTIC_KEYS if key not in fit_diagnostics]
    if missing_fit:
        raise KeyError(f"Missing fit_diagnostics keys: {', '.join(missing_fit)}")

    lambda_nm = np.asarray(result["lambda_nm"], dtype=float)
    if lambda_nm.ndim != 1 or lambda_nm.size < 2:
        raise ValueError("lambda_nm must be a 1D wavelength axis with at least two samples.")
    if not np.all(np.isfinite(lambda_nm)):
        raise ValueError("lambda_nm must be finite.")
    if not np.all(np.diff(lambda_nm) > 0.0):
        raise ValueError("lambda_nm must be strictly increasing.")

    b_k = np.asarray(result["B_k"], dtype=np.complex128)
    d1_vector_k = np.asarray(result["D1_vector_k"], dtype=np.complex128)
    d1_slice_k = np.asarray(result["D1_slice_k"], dtype=np.complex128)
    c2_tensor_k = np.asarray(result["C2_tensor_k"], dtype=np.complex128)
    c2_slice_k = np.asarray(result["C2_slice_k"], dtype=np.complex128)
    expected_shape = lambda_nm.shape
    for name, array in (("B_k", b_k), ("D1_slice_k", d1_slice_k), ("C2_slice_k", c2_slice_k)):
        if array.ndim != 1:
            raise ValueError(f"{name} must be 1D.")
        if array.shape != expected_shape:
            raise ValueError(f"{name} shape {array.shape} does not match lambda_nm shape {expected_shape}.")
        if not np.all(np.isfinite(array.real)) or not np.all(np.isfinite(array.imag)):
            raise ValueError(f"{name} must be finite.")
    if d1_vector_k.ndim != 2 or d1_vector_k.shape != (expected_shape[0], 2):
        raise ValueError(f"D1_vector_k shape {d1_vector_k.shape} does not match expected {(expected_shape[0], 2)}.")
    if c2_tensor_k.ndim != 3 or c2_tensor_k.shape != (expected_shape[0], 2, 2):
        raise ValueError(
            f"C2_tensor_k shape {c2_tensor_k.shape} does not match expected {(expected_shape[0], 2, 2)}."
        )
    if not np.all(np.isfinite(d1_vector_k.real)) or not np.all(np.isfinite(d1_vector_k.imag)):
        raise ValueError("D1_vector_k must be finite.")
    if not np.all(np.isfinite(c2_tensor_k.real)) or not np.all(np.isfinite(c2_tensor_k.imag)):
        raise ValueError("C2_tensor_k must be finite.")

    slice_direction_label = str(result["lateral_slice_axis"]).strip().lower()
    if slice_direction_label not in {"x", "y"}:
        raise ValueError(f"Unsupported lateral_slice_axis: {result['lateral_slice_axis']!r}")
    fit_strategy = str(fit_diagnostics["fit_strategy"])
    if fit_strategy not in ALLOWED_EFFECTIVE_FIT_STRATEGIES:
        raise ValueError(f"Unsupported fit_strategy: {fit_strategy!r}")
    residual_model = str(fit_diagnostics["relative_fit_residual_model"])
    if residual_model not in ALLOWED_EFFECTIVE_RESIDUAL_MODELS:
        raise ValueError(f"Unsupported relative_fit_residual_model: {residual_model!r}")
    c2_tensor_basis = str(fit_diagnostics["C2_tensor_basis"])
    d1_tensor_basis = str(fit_diagnostics["D1_tensor_basis"])
    if c2_tensor_basis not in ALLOWED_EFFECTIVE_TENSOR_BASES:
        raise ValueError(f"Unsupported C2_tensor_basis: {c2_tensor_basis!r}")
    if d1_tensor_basis not in ALLOWED_EFFECTIVE_TENSOR_BASES:
        raise ValueError(f"Unsupported D1_tensor_basis: {d1_tensor_basis!r}")

    return {
        "lambda_nm": lambda_nm,
        "B_k": b_k,
        "D1_slice_k": d1_slice_k,
        "C2_slice_k": c2_slice_k,
        "fit_diagnostics": fit_diagnostics,
        "fit_strategy": fit_strategy,
        "relative_fit_residual_model": residual_model,
        "C2_tensor_basis": c2_tensor_basis,
        "D1_tensor_basis": d1_tensor_basis,
        "slice_direction_label": slice_direction_label,
        "wavelength_axis_kind": "vacuum_wavelength_nm",
        "coefficient_units_note": "B_k, D1_slice_k, and C2_slice_k are complex effective-channel field coefficients indexed by wavelength, not intensity-domain observables.",
        "normalization_semantics": "These coefficients inherit the bridge/asymptotic field normalization used during effective-channel fitting and must be compared under explicit shared-scale diagnostics.",
        "phase_convention": "Coefficient phase follows the complex field convention of the solver output at the current wavelength ordering; no additional phase gauge fixing is implied.",
        "field_vs_intensity_semantics": "All coefficient diagnostics operate in the complex field domain. Intensity comparisons must be performed only after field reconstruction or coefficient injection.",
        "shared_scale_interpretation_note": "Shared-scale diagnostics test whether recovered and asymptotic coefficient vectors are related by one global complex scale. Failure means component-wise usage mapping may still be inconsistent.",
    }
