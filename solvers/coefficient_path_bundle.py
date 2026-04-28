from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from .effective_channel_coefficients import complex_alignment, extract_effective_coefficient_contract


PROJECTED_COEFFICIENT_LABELS = ("B_k_projected", "D1_slice_k", "C2_slice_k")
RENDERED_COEFFICIENT_LABELS = ("a0", "a1", "a2")
COEFFICIENT_PATH_BUNDLE_SCHEMA_VERSION = "round6p1_coefficient_path_bundle_v3"
SHARED_COEFFICIENT_MAP_CANDIDATE_SCHEMA_VERSION = "round6p1_shared_coefficient_map_candidate_v1"
COEFFICIENT_BUNDLE_ARTIFACT_KINDS = (
    "native_identity",
    "shared_map_promoted",
    "case_specific_fitted_map_diagnostic",
)
COEFFICIENT_MAP_RUNTIME_MODES = (
    "native_branch_assembly",
    "rendered_basis_override",
)
RENDERED_BASIS_SHIFT_TARGETS = (
    "baseline_envelope_ratio",
    "rendered_field_interp",
)
COEFFICIENT_MAP_MODEL_IDS = (
    "identity_slice_projected_rendered_basis",
    "shared_complex_scale_map",
    "componentwise_complex_scale_map",
    "low_order_coupled_odd_even_map",
    "fitted_linear_map_3x3",
)
REFERENCE_RENDERED_COEFFICIENT_SOURCES = (
    "none",
    "bridge_recovered",
    "shared_scale_aligned_bridge",
)


@dataclass(frozen=True)
class AngularFitState:
    lambda_nm: np.ndarray
    B_k: np.ndarray
    D1_vector_k: np.ndarray
    C2_tensor_k: np.ndarray
    fit_strategy: str
    relative_fit_residual_model: str
    C2_tensor_basis: str
    D1_tensor_basis: str
    fit_diagnostics: dict[str, Any]
    wavelength_axis_kind: str


@dataclass(frozen=True)
class SliceProjectedState:
    B_k_projected: np.ndarray
    D1_slice_k: np.ndarray
    C2_slice_k: np.ndarray
    slice_direction_label: str
    slice_direction_local: np.ndarray
    projection_operator_vector: np.ndarray
    projection_operator_tensor: np.ndarray


@dataclass(frozen=True)
class FieldBasisState:
    x_um: np.ndarray
    R0_x: np.ndarray
    R1_slice_x: np.ndarray
    R2_slice_x: np.ndarray
    basis_labels: tuple[str, ...]
    basis_matrix: np.ndarray
    basis_column_norms: np.ndarray
    orthonormal_q_matrix: np.ndarray
    orthonormal_r_matrix: np.ndarray
    normalization_scale: float
    field_assembly_model_id: str


@dataclass(frozen=True)
class RenderedCoefficientState:
    projected_coefficient_labels: tuple[str, ...]
    projected_coefficients_raw: np.ndarray
    rendered_coefficient_labels: tuple[str, ...]
    rendered_coefficients_raw: np.ndarray
    coefficient_map_model_id: str
    coefficient_map_matrix: np.ndarray
    coefficient_map_note: str
    coefficient_map_parameters: dict[str, Any]


@dataclass(frozen=True)
class FittedCoefficientMap:
    coefficient_map_model_id: str
    map_matrix: np.ndarray
    coefficient_map_note: str
    coefficient_map_parameters: dict[str, Any]


@dataclass(frozen=True)
class CoefficientComparisonState:
    rendered_coefficient_labels: tuple[str, ...]
    rendered_coefficients_raw: np.ndarray
    rendered_coefficients_orthonormalized: np.ndarray
    coefficient_map_model_id: str
    coefficient_map_theory_claim: str
    coefficient_gauge_note: str


@dataclass(frozen=True)
class RuntimeFieldAssemblyPlan:
    requested_second_order_model: str
    coefficient_map_runtime_mode: str
    coefficient_map_model_id: str
    runtime_field_assembly_contract: str
    runtime_field_assembly_contract_note: str
    runtime_field_assembly_supported_lateral_shift_models: tuple[str, ...]
    runtime_field_assembly_lateral_shift_constraint: str
    coefficient_map_runtime_status: str
    coefficient_map_runtime_contract_status: str
    coefficient_map_runtime_note: str
    rendered_basis_shift_target: str | None
    lateral_shift_model: str
    lateral_shift_coupling: str
    lateral_shift_impl: str
    uses_rendered_basis: bool


@dataclass(frozen=True)
class CoefficientPathBundle:
    angular_fit_state: AngularFitState
    slice_projected_state: SliceProjectedState
    field_basis_state: FieldBasisState
    rendered_coefficient_state: RenderedCoefficientState
    comparison_state: CoefficientComparisonState


def _as_complex_array(name: str, value: Any, *, ndim: int, shape: tuple[int, ...] | None = None) -> np.ndarray:
    array = np.asarray(value, dtype=np.complex128)
    if array.ndim != ndim:
        raise ValueError(f"{name} must be {ndim}D, got shape {array.shape}.")
    if shape is not None and array.shape != shape:
        raise ValueError(f"{name} shape {array.shape} does not match expected {shape}.")
    if not np.all(np.isfinite(array.real)) or not np.all(np.isfinite(array.imag)):
        raise ValueError(f"{name} must be finite.")
    return array


def _get_required_key(mapping: dict[str, Any], key: str) -> Any:
    if key not in mapping:
        raise KeyError(f"Missing coefficient-path key: {key}")
    return mapping[key]


def _sanitize_case_name(case_name: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", case_name).strip("_").lower()


def _validate_model_id(model_id: str) -> str:
    model_id = str(model_id)
    if model_id not in COEFFICIENT_MAP_MODEL_IDS:
        raise ValueError(f"Unsupported coefficient_map_model_id: {model_id!r}")
    return model_id


def _validate_runtime_mode(runtime_mode: str) -> str:
    runtime_mode = str(runtime_mode)
    if runtime_mode not in COEFFICIENT_MAP_RUNTIME_MODES:
        raise ValueError(f"Unsupported coefficient_map_runtime_mode: {runtime_mode!r}")
    return runtime_mode


def _validate_rendered_basis_shift_target(shift_target: str) -> str:
    shift_target = str(shift_target)
    if shift_target not in RENDERED_BASIS_SHIFT_TARGETS:
        raise ValueError(f"Unsupported rendered_basis_shift_target: {shift_target!r}")
    return shift_target


def _validate_reference_source(source: str) -> str:
    source = str(source)
    if source not in REFERENCE_RENDERED_COEFFICIENT_SOURCES:
        raise ValueError(f"Unsupported reference_rendered_coefficients_source: {source!r}")
    return source


def _validate_artifact_kind(artifact_kind: str) -> str:
    artifact_kind = str(artifact_kind)
    if artifact_kind not in COEFFICIENT_BUNDLE_ARTIFACT_KINDS:
        raise ValueError(f"Unsupported coefficient_bundle_artifact_kind: {artifact_kind!r}")
    return artifact_kind


def _fit_global_linear_map(projected: np.ndarray, target: np.ndarray) -> np.ndarray:
    projected = np.asarray(projected, dtype=np.complex128)
    target = np.asarray(target, dtype=np.complex128)
    map_matrix, *_ = np.linalg.lstsq(projected, target, rcond=None)
    return np.asarray(map_matrix, dtype=np.complex128)


def _fit_low_order_coupled_odd_even_map(projected: np.ndarray, target: np.ndarray) -> np.ndarray:
    projected = np.asarray(projected, dtype=np.complex128)
    target = np.asarray(target, dtype=np.complex128)
    map_matrix = np.zeros((3, 3), dtype=np.complex128)
    even_sources = projected[:, [0, 2]]
    map_matrix[[0, 2], 0] = np.linalg.lstsq(even_sources, target[:, 0], rcond=None)[0]
    map_matrix[1, 1] = np.linalg.lstsq(projected[:, [1]], target[:, 1], rcond=None)[0][0]
    map_matrix[[0, 2], 2] = np.linalg.lstsq(even_sources, target[:, 2], rcond=None)[0]
    return map_matrix


def _map_note(model_id: str, *, reference_supplied: bool) -> str:
    if model_id == "identity_slice_projected_rendered_basis":
        return "Rendered coefficients equal the slice-projected angular-fit coefficients."
    if model_id == "shared_complex_scale_map":
        return (
            "A single shared complex scale is applied to all projected coefficients before rendering."
            if reference_supplied
            else "Shared complex scale map fell back to identity because no reference rendered coefficients were supplied."
        )
    if model_id == "componentwise_complex_scale_map":
        return (
            "Each rendered coefficient receives its own best-fit complex scale relative to the projected coefficients."
            if reference_supplied
            else "Componentwise complex scale map fell back to identity because no reference rendered coefficients were supplied."
        )
    if model_id == "low_order_coupled_odd_even_map":
        return (
            "Even channels are allowed to mix into rendered even coefficients while the odd channel remains self-coupled."
            if reference_supplied
            else "Low-order odd/even map fell back to identity because no reference rendered coefficients were supplied."
        )
    return (
        "A fitted global complex 3x3 linear map converts projected coefficients into rendered coefficients."
        if reference_supplied
        else "Fitted global 3x3 map fell back to identity because no reference rendered coefficients were supplied."
    )


def project_coefficients_to_orthonormal_basis(
    raw_coefficients: np.ndarray,
    orthonormal_r_matrix: np.ndarray,
) -> np.ndarray:
    raw_coefficients = np.asarray(raw_coefficients, dtype=np.complex128)
    orthonormal_r_matrix = np.asarray(orthonormal_r_matrix, dtype=np.complex128)
    if raw_coefficients.ndim != 2:
        raise ValueError("raw_coefficients must be 2D with shape (n_lambda, n_components).")
    return raw_coefficients @ orthonormal_r_matrix.T


def resolve_reference_rendered_coefficients(
    projected_coefficients_raw: np.ndarray,
    recovered_coefficients_raw: np.ndarray | None,
    *,
    source: str = "none",
) -> np.ndarray | None:
    source = _validate_reference_source(source)
    if source == "none":
        return None
    if recovered_coefficients_raw is None:
        raise ValueError(
            "recovered_coefficients_raw is required when reference_rendered_coefficients_source is not 'none'."
        )
    projected_coefficients_raw = np.asarray(projected_coefficients_raw, dtype=np.complex128)
    recovered_coefficients_raw = np.asarray(recovered_coefficients_raw, dtype=np.complex128)
    if recovered_coefficients_raw.shape != projected_coefficients_raw.shape:
        raise ValueError(
            "recovered_coefficients_raw must match projected_coefficients_raw shape when used as a reference source."
        )
    if source == "bridge_recovered":
        return recovered_coefficients_raw
    alignment = complex_alignment(projected_coefficients_raw.reshape(-1), recovered_coefficients_raw.reshape(-1))
    shared_scale = alignment["scale_abs"] * np.exp(1j * alignment["scale_phase_rad"])
    return recovered_coefficients_raw / (shared_scale + 1e-30)


def reconstruct_lateral_field_from_rendered_coefficients(
    bundle: CoefficientPathBundle,
    rendered_coefficients_raw: np.ndarray,
) -> np.ndarray:
    rendered_coefficients_raw = np.asarray(rendered_coefficients_raw, dtype=np.complex128)
    expected_shape = bundle.rendered_coefficient_state.rendered_coefficients_raw.shape
    if rendered_coefficients_raw.shape != expected_shape:
        raise ValueError(
            f"rendered_coefficients_raw shape {rendered_coefficients_raw.shape} does not match expected {expected_shape}."
        )
    basis_matrix = np.asarray(bundle.field_basis_state.basis_matrix, dtype=np.complex128)
    return rendered_coefficients_raw @ basis_matrix.T


def _shift_complex_profile_interp(
    x_um: np.ndarray,
    profile_x: np.ndarray,
    shift_um: float,
    *,
    boundary_mode: str = "zero_pad",
) -> np.ndarray:
    x_um = np.asarray(x_um, dtype=float)
    profile_x = np.asarray(profile_x, dtype=np.complex128)
    if boundary_mode == "zero_pad":
        left_real = right_real = 0.0
        left_imag = right_imag = 0.0
    elif boundary_mode == "edge_hold":
        left_real = float(np.real(profile_x[0]))
        right_real = float(np.real(profile_x[-1]))
        left_imag = float(np.imag(profile_x[0]))
        right_imag = float(np.imag(profile_x[-1]))
    else:
        raise ValueError(f"Unsupported boundary_mode: {boundary_mode}")
    return (
        np.interp(x_um - shift_um, x_um, np.real(profile_x), left=left_real, right=right_real)
        + 1j * np.interp(x_um - shift_um, x_um, np.imag(profile_x), left=left_imag, right=right_imag)
    )


def plan_runtime_field_assembly_contract(
    *,
    requested_second_order_model: str,
    coefficient_map_runtime_mode: str,
    coefficient_map_model_id: str,
    coefficient_map_artifact_path: str | Path | None = None,
    lateral_shift_model: str = "none",
    lateral_shift_coupling: str = "envelope_only",
    lateral_shift_impl: str = "interp",
    rendered_basis_shift_target: str = "baseline_envelope_ratio",
) -> RuntimeFieldAssemblyPlan:
    requested_second_order_model = str(requested_second_order_model)
    coefficient_map_runtime_mode = _validate_runtime_mode(coefficient_map_runtime_mode)
    coefficient_map_model_id = _validate_model_id(coefficient_map_model_id)
    rendered_basis_shift_target = _validate_rendered_basis_shift_target(rendered_basis_shift_target)
    non_identity_requested = (
        coefficient_map_model_id != "identity_slice_projected_rendered_basis"
        or coefficient_map_artifact_path is not None
    )
    if coefficient_map_runtime_mode == "native_branch_assembly":
        if (
            requested_second_order_model != "directional_field_expansion_first_order"
            and non_identity_requested
        ):
            raise ValueError(
                "Runtime coefficient-map promotion in native_branch_assembly is currently supported only for "
                "requested_second_order_model='directional_field_expansion_first_order'. Use "
                "coefficient_map_runtime_mode='rendered_basis_override' for general asymptotic promotion."
            )
        if requested_second_order_model in {"directional_field_expansion", "directional_field_expansion_first_order"}:
            if lateral_shift_model != "none":
                raise ValueError(
                    f"{requested_second_order_model} currently supports only lateral_shift_model='none' under native branch assembly."
                )
            supported_shift_models = ("none",)
            shift_constraint = f"{requested_second_order_model}_requires_none"
        else:
            supported_shift_models = ("none", "first_order")
            shift_constraint = "native_tensor_and_slice_projected_support_first_order"
        runtime_status = (
            "artifact_promoted" if coefficient_map_artifact_path else "builtin_identity"
        )
        contract_status = (
            "branch_limited_runtime_contract"
            if requested_second_order_model == "directional_field_expansion_first_order"
            else "native_branch_runtime_contract"
        )
        runtime_note = (
            "Runtime assembly keeps the requested native asymptotic branch semantics. Non-identity coefficient maps "
            "are only allowed for directional_field_expansion_first_order in this mode."
        )
        contract_note = (
            "The runtime field is assembled through the requested native asymptotic branch semantics."
        )
        return RuntimeFieldAssemblyPlan(
            requested_second_order_model=requested_second_order_model,
            coefficient_map_runtime_mode=coefficient_map_runtime_mode,
            coefficient_map_model_id=coefficient_map_model_id,
            runtime_field_assembly_contract=requested_second_order_model,
            runtime_field_assembly_contract_note=contract_note,
            runtime_field_assembly_supported_lateral_shift_models=supported_shift_models,
            runtime_field_assembly_lateral_shift_constraint=shift_constraint,
            coefficient_map_runtime_status=runtime_status,
            coefficient_map_runtime_contract_status=contract_status,
            coefficient_map_runtime_note=runtime_note,
            rendered_basis_shift_target=None,
            lateral_shift_model=lateral_shift_model,
            lateral_shift_coupling=lateral_shift_coupling,
            lateral_shift_impl=lateral_shift_impl,
            uses_rendered_basis=requested_second_order_model == "directional_field_expansion_first_order",
        )

    if lateral_shift_model == "none":
        supported_shift_models = ("none", "first_order")
        shift_constraint = (
            "rendered_basis_override_supports_first_order_only_with_envelope_only_analytic_gaussian_or_rendered_interp"
        )
        active_rendered_basis_shift_target = None
    else:
        valid_first_order = (
            lateral_shift_model == "first_order"
            and lateral_shift_coupling == "envelope_only"
            and (
                (rendered_basis_shift_target == "baseline_envelope_ratio" and lateral_shift_impl == "analytic_gaussian")
                or (rendered_basis_shift_target == "rendered_field_interp" and lateral_shift_impl in {"interp", "interp_edge_hold"})
            )
        )
        if not valid_first_order:
            raise ValueError(
                "rendered_basis_override currently supports lateral_shift_model='first_order' only with "
                "lateral_shift_coupling='envelope_only' plus either "
                "(rendered_basis_shift_target='baseline_envelope_ratio', lateral_shift_impl='analytic_gaussian') or "
                "(rendered_basis_shift_target='rendered_field_interp', lateral_shift_impl in {'interp','interp_edge_hold'})."
            )
        supported_shift_models = ("none", "first_order")
        shift_constraint = (
            "rendered_basis_override_supports_first_order_only_with_envelope_only_analytic_gaussian_or_rendered_interp"
        )
        active_rendered_basis_shift_target = rendered_basis_shift_target
    runtime_status = (
        "artifact_promoted_override" if coefficient_map_artifact_path else "builtin_identity_override"
    )
    runtime_note = (
        "Runtime low_na_asymptotic is using the explicit rendered-basis override contract: projected coefficients are "
        "mapped into canonical rendered R0/R1/R2 coefficients before field assembly, independent of the native branch semantics."
    )
    contract_note = (
        "The runtime field is assembled from the canonical rendered R0/R1/R2 basis after applying the configured "
        "projected-to-rendered coefficient map, regardless of requested_second_order_model."
    )
    return RuntimeFieldAssemblyPlan(
        requested_second_order_model=requested_second_order_model,
        coefficient_map_runtime_mode=coefficient_map_runtime_mode,
        coefficient_map_model_id=coefficient_map_model_id,
        runtime_field_assembly_contract="rendered_basis_override",
        runtime_field_assembly_contract_note=contract_note,
        runtime_field_assembly_supported_lateral_shift_models=supported_shift_models,
        runtime_field_assembly_lateral_shift_constraint=shift_constraint,
        coefficient_map_runtime_status=runtime_status,
        coefficient_map_runtime_contract_status="explicit_rendered_basis_override_contract",
        coefficient_map_runtime_note=runtime_note,
        rendered_basis_shift_target=active_rendered_basis_shift_target,
        lateral_shift_model=lateral_shift_model,
        lateral_shift_coupling=lateral_shift_coupling,
        lateral_shift_impl=lateral_shift_impl,
        uses_rendered_basis=True,
    )


def assemble_runtime_lateral_field(
    plan: RuntimeFieldAssemblyPlan,
    *,
    source_power: np.ndarray,
    B_k: np.ndarray,
    second_order_tensor_correction: np.ndarray | None = None,
    lateral_envelope_k: np.ndarray | None = None,
    reference_field_profile: np.ndarray | None = None,
    directional_second_order_field: np.ndarray | None = None,
    coefficient_path_bundle: CoefficientPathBundle | None = None,
    rendered_coefficients_raw: np.ndarray | None = None,
    x_um: np.ndarray | None = None,
    delta_x_k_um: np.ndarray | None = None,
) -> dict[str, Any]:
    source_power = np.asarray(source_power, dtype=np.complex128)
    if source_power.ndim != 1:
        raise ValueError("source_power must be 1D.")

    if plan.runtime_field_assembly_contract == "directional_field_expansion":
        if reference_field_profile is None or directional_second_order_field is None:
            raise ValueError("directional_field_expansion assembly requires reference_field_profile and directional_second_order_field.")
        reference_field_profile = np.asarray(reference_field_profile, dtype=np.complex128)
        directional_second_order_field = np.asarray(directional_second_order_field, dtype=np.complex128)
        spectral_cube = source_power[:, None] * (
            np.asarray(B_k, dtype=np.complex128)[:, None] * reference_field_profile[None, :]
            + directional_second_order_field
        )
        return {"spectral_cube": spectral_cube, "runtime_lateral_field_kx": spectral_cube / source_power[:, None]}

    if plan.runtime_field_assembly_contract in {"directional_field_expansion_first_order", "rendered_basis_override"}:
        if coefficient_path_bundle is None:
            raise ValueError(f"{plan.runtime_field_assembly_contract} requires coefficient_path_bundle.")
        if rendered_coefficients_raw is None:
            rendered_coefficients_raw = coefficient_path_bundle.rendered_coefficient_state.rendered_coefficients_raw
        rendered_lateral_field = reconstruct_lateral_field_from_rendered_coefficients(
            coefficient_path_bundle,
            rendered_coefficients_raw,
        )
        if plan.lateral_shift_model == "none":
            final_lateral_field = rendered_lateral_field
        elif plan.rendered_basis_shift_target == "baseline_envelope_ratio":
            if lateral_envelope_k is None:
                raise ValueError("baseline_envelope_ratio shift target requires lateral_envelope_k.")
            baseline_envelope = np.asarray(coefficient_path_bundle.field_basis_state.R0_x, dtype=np.complex128)
            denominator = np.where(np.abs(baseline_envelope) > 1e-12, baseline_envelope, 1.0 + 0.0j)
            final_lateral_field = rendered_lateral_field * (np.asarray(lateral_envelope_k, dtype=np.complex128) / denominator[None, :])
        else:
            if x_um is None or delta_x_k_um is None:
                raise ValueError("rendered_field_interp shift target requires x_um and delta_x_k_um.")
            boundary_mode = "edge_hold" if plan.lateral_shift_impl == "interp_edge_hold" else "zero_pad"
            shifted = np.zeros_like(rendered_lateral_field)
            x_um = np.asarray(x_um, dtype=float)
            delta_x_k_um = np.asarray(delta_x_k_um, dtype=float)
            for idx, shift_um in enumerate(delta_x_k_um):
                shifted[idx] = _shift_complex_profile_interp(
                    x_um,
                    rendered_lateral_field[idx],
                    shift_um,
                    boundary_mode=boundary_mode,
                )
            final_lateral_field = shifted
        spectral_cube = source_power[:, None] * final_lateral_field
        return {
            "spectral_cube": spectral_cube,
            "runtime_lateral_field_kx": final_lateral_field,
            "rendered_lateral_field_kx": rendered_lateral_field,
        }

    if second_order_tensor_correction is None or lateral_envelope_k is None:
        raise ValueError("native asymptotic runtime assembly requires second_order_tensor_correction and lateral_envelope_k.")
    spectral_cube = source_power[:, None] * np.asarray(lateral_envelope_k, dtype=np.complex128) * (
        np.asarray(B_k, dtype=np.complex128)[:, None] + np.asarray(second_order_tensor_correction, dtype=np.complex128)
    )
    return {"spectral_cube": spectral_cube, "runtime_lateral_field_kx": spectral_cube / source_power[:, None]}


def map_projected_to_rendered_coefficients(
    projected_coefficients_raw: np.ndarray,
    *,
    model_id: str = "identity_slice_projected_rendered_basis",
    reference_rendered_coefficients_raw: np.ndarray | None = None,
) -> RenderedCoefficientState:
    fitted_map = fit_projected_to_rendered_map(
        projected_coefficients_raw,
        model_id=model_id,
        reference_rendered_coefficients_raw=reference_rendered_coefficients_raw,
    )
    return apply_fitted_coefficient_map(projected_coefficients_raw, fitted_map)


def fit_projected_to_rendered_map(
    projected_coefficients_raw: np.ndarray,
    *,
    model_id: str = "identity_slice_projected_rendered_basis",
    reference_rendered_coefficients_raw: np.ndarray | None = None,
) -> FittedCoefficientMap:
    projected_coefficients_raw = np.asarray(projected_coefficients_raw, dtype=np.complex128)
    if projected_coefficients_raw.ndim != 2 or projected_coefficients_raw.shape[1] != 3:
        raise ValueError(
            "projected_coefficients_raw must have shape (n_lambda, 3) for (B_k_projected, D1_slice_k, C2_slice_k)."
        )
    model_id = _validate_model_id(model_id)
    reference = None if reference_rendered_coefficients_raw is None else np.asarray(
        reference_rendered_coefficients_raw,
        dtype=np.complex128,
    )
    if reference is not None and reference.shape != projected_coefficients_raw.shape:
        raise ValueError(
            f"reference_rendered_coefficients_raw shape {reference.shape} does not match projected shape {projected_coefficients_raw.shape}."
        )

    identity = np.eye(3, dtype=np.complex128)
    map_matrix = identity
    reference_supplied = reference is not None
    parameters: dict[str, Any] = {"reference_supplied": bool(reference_supplied)}

    if model_id == "identity_slice_projected_rendered_basis":
        map_matrix = identity
    elif reference is None:
        parameters["fallback_to_identity"] = True
        map_matrix = identity
    elif model_id == "shared_complex_scale_map":
        alignment = complex_alignment(projected_coefficients_raw.reshape(-1), reference.reshape(-1))
        scale = alignment["scale_abs"] * np.exp(1j * alignment["scale_phase_rad"])
        map_matrix = scale * identity
        parameters["shared_alignment"] = alignment
    elif model_id == "componentwise_complex_scale_map":
        scales: list[complex] = []
        for idx in range(3):
            alignment = complex_alignment(projected_coefficients_raw[:, idx], reference[:, idx])
            scales.append(alignment["scale_abs"] * np.exp(1j * alignment["scale_phase_rad"]))
            parameters[f"component_alignment_{idx}"] = alignment
        map_matrix = np.diag(np.asarray(scales, dtype=np.complex128))
    elif model_id == "low_order_coupled_odd_even_map":
        map_matrix = _fit_low_order_coupled_odd_even_map(projected_coefficients_raw, reference)
    else:
        map_matrix = _fit_global_linear_map(projected_coefficients_raw, reference)

    return FittedCoefficientMap(
        coefficient_map_model_id=model_id,
        map_matrix=np.asarray(map_matrix, dtype=np.complex128),
        coefficient_map_note=_map_note(model_id, reference_supplied=reference_supplied),
        coefficient_map_parameters=parameters,
    )


def shared_coefficient_map_candidate_payload(
    fitted_map: FittedCoefficientMap,
    *,
    panel_case_names: list[str] | tuple[str, ...],
) -> dict[str, Any]:
    map_matrix = np.asarray(fitted_map.map_matrix, dtype=np.complex128)
    if map_matrix.shape != (3, 3):
        raise ValueError(f"shared candidate map_matrix must have shape (3, 3), got {map_matrix.shape}.")
    panel_case_names = [str(name) for name in panel_case_names]
    return {
        "schema_version": np.asarray(SHARED_COEFFICIENT_MAP_CANDIDATE_SCHEMA_VERSION),
        "coefficient_map_model_id": np.asarray(fitted_map.coefficient_map_model_id),
        "map_matrix": map_matrix,
        "coefficient_map_note": np.asarray(fitted_map.coefficient_map_note),
        "coefficient_map_parameters_json": np.asarray(
            json.dumps(fitted_map.coefficient_map_parameters, sort_keys=True)
        ),
        "panel_case_names": np.asarray(panel_case_names),
        "panel_case_count": np.asarray(len(panel_case_names)),
        "map_matrix_frobenius_norm": np.asarray(float(np.linalg.norm(map_matrix))),
        "map_matrix_condition_number": np.asarray(float(np.linalg.cond(map_matrix))),
        "map_matrix_rank": np.asarray(int(np.linalg.matrix_rank(map_matrix))),
    }


def validate_shared_coefficient_map_candidate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    required = (
        "schema_version",
        "coefficient_map_model_id",
        "map_matrix",
        "coefficient_map_note",
        "coefficient_map_parameters_json",
        "panel_case_names",
        "panel_case_count",
        "map_matrix_frobenius_norm",
        "map_matrix_condition_number",
        "map_matrix_rank",
    )
    missing = [key for key in required if key not in payload]
    if missing:
        raise KeyError(f"Missing shared coefficient-map candidate payload keys: {', '.join(missing)}")
    if str(np.asarray(payload["schema_version"]).item()) != SHARED_COEFFICIENT_MAP_CANDIDATE_SCHEMA_VERSION:
        raise ValueError("Unsupported shared coefficient-map candidate schema version.")
    model_id = _validate_model_id(str(np.asarray(payload["coefficient_map_model_id"]).item()))
    map_matrix = _as_complex_array("map_matrix", payload["map_matrix"], ndim=2, shape=(3, 3))
    panel_case_names = [str(item) for item in np.asarray(payload["panel_case_names"]).tolist()]
    panel_case_count = int(np.asarray(payload["panel_case_count"]).item())
    if panel_case_count != len(panel_case_names):
        raise ValueError("panel_case_count does not match panel_case_names length.")
    parameters = json.loads(str(np.asarray(payload["coefficient_map_parameters_json"]).item()))
    fro_norm = float(np.asarray(payload["map_matrix_frobenius_norm"]).item())
    cond_number = float(np.asarray(payload["map_matrix_condition_number"]).item())
    matrix_rank = int(np.asarray(payload["map_matrix_rank"]).item())
    if not np.isclose(fro_norm, float(np.linalg.norm(map_matrix)), rtol=1e-10, atol=1e-10):
        raise ValueError("map_matrix_frobenius_norm does not match map_matrix.")
    if not np.isclose(cond_number, float(np.linalg.cond(map_matrix)), rtol=1e-10, atol=1e-10):
        raise ValueError("map_matrix_condition_number does not match map_matrix.")
    if matrix_rank != int(np.linalg.matrix_rank(map_matrix)):
        raise ValueError("map_matrix_rank does not match map_matrix.")
    fitted_map = FittedCoefficientMap(
        coefficient_map_model_id=model_id,
        map_matrix=map_matrix,
        coefficient_map_note=str(np.asarray(payload["coefficient_map_note"]).item()),
        coefficient_map_parameters=parameters,
    )
    return {
        "coefficient_map_model_id": model_id,
        "map_matrix": map_matrix,
        "panel_case_names": panel_case_names,
        "panel_case_count": panel_case_count,
        "fitted_map": fitted_map,
    }


def write_shared_coefficient_map_candidate_npz(
    output_path: str | Path,
    fitted_map: FittedCoefficientMap,
    *,
    panel_case_names: list[str] | tuple[str, ...],
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = shared_coefficient_map_candidate_payload(
        fitted_map,
        panel_case_names=panel_case_names,
    )
    np.savez(output_path, **payload)
    return output_path


def read_shared_coefficient_map_candidate_npz(path: str | Path) -> dict[str, Any]:
    path = Path(path)
    with np.load(path, allow_pickle=False) as loaded:
        payload = {key: loaded[key] for key in loaded.files}
    payload["validated"] = validate_shared_coefficient_map_candidate_payload(payload)
    payload["artifact_path"] = str(path)
    return payload


def shared_coefficient_map_candidate_report_path(
    reports_dir: str | Path,
    coefficient_map_model_id: str,
) -> Path:
    reports_dir = Path(reports_dir)
    model_id = _validate_model_id(coefficient_map_model_id)
    return reports_dir / f"round6p1_shared_coefficient_map_candidate_{model_id}.npz"


def resolve_runtime_fitted_coefficient_map(
    *,
    coefficient_map_model_id: str,
    artifact_path: str | Path | None = None,
) -> FittedCoefficientMap:
    model_id = _validate_model_id(coefficient_map_model_id)
    if artifact_path is None:
        if model_id != "identity_slice_projected_rendered_basis":
            raise ValueError(
                "Non-identity runtime coefficient maps require a validated shared-map artifact path."
            )
        return FittedCoefficientMap(
            coefficient_map_model_id=model_id,
            map_matrix=np.eye(3, dtype=np.complex128),
            coefficient_map_note=_map_note(model_id, reference_supplied=False),
            coefficient_map_parameters={"runtime_source": "builtin_identity"},
        )
    loaded = read_shared_coefficient_map_candidate_npz(artifact_path)
    fitted_map = loaded["validated"]["fitted_map"]
    if fitted_map.coefficient_map_model_id != model_id:
        raise ValueError(
            f"Runtime coefficient-map artifact model {fitted_map.coefficient_map_model_id!r} "
            f"does not match requested model {model_id!r}."
        )
    merged_parameters = dict(fitted_map.coefficient_map_parameters)
    merged_parameters["runtime_source"] = "shared_candidate_artifact"
    merged_parameters["artifact_path"] = str(Path(artifact_path))
    return FittedCoefficientMap(
        coefficient_map_model_id=fitted_map.coefficient_map_model_id,
        map_matrix=fitted_map.map_matrix,
        coefficient_map_note=fitted_map.coefficient_map_note,
        coefficient_map_parameters=merged_parameters,
    )


def apply_fitted_coefficient_map(
    projected_coefficients_raw: np.ndarray,
    fitted_map: FittedCoefficientMap,
) -> RenderedCoefficientState:
    projected_coefficients_raw = np.asarray(projected_coefficients_raw, dtype=np.complex128)
    if projected_coefficients_raw.ndim != 2 or projected_coefficients_raw.shape[1] != 3:
        raise ValueError(
            "projected_coefficients_raw must have shape (n_lambda, 3) for (B_k_projected, D1_slice_k, C2_slice_k)."
        )
    map_matrix = np.asarray(fitted_map.map_matrix, dtype=np.complex128)
    if map_matrix.shape != (3, 3):
        raise ValueError(f"fitted_map.map_matrix must have shape (3, 3), got {map_matrix.shape}.")
    rendered_coefficients_raw = projected_coefficients_raw @ map_matrix
    coefficient_map_matrix = np.broadcast_to(map_matrix[None, :, :], (projected_coefficients_raw.shape[0], 3, 3)).copy()
    return RenderedCoefficientState(
        projected_coefficient_labels=PROJECTED_COEFFICIENT_LABELS,
        projected_coefficients_raw=projected_coefficients_raw,
        rendered_coefficient_labels=RENDERED_COEFFICIENT_LABELS,
        rendered_coefficients_raw=rendered_coefficients_raw,
        coefficient_map_model_id=fitted_map.coefficient_map_model_id,
        coefficient_map_matrix=coefficient_map_matrix,
        coefficient_map_note=fitted_map.coefficient_map_note,
        coefficient_map_parameters=fitted_map.coefficient_map_parameters,
    )


def build_external_comparison_views(
    bundle: CoefficientPathBundle,
    external_coefficients_raw: np.ndarray,
) -> dict[str, Any]:
    external_coefficients_raw = np.asarray(external_coefficients_raw, dtype=np.complex128)
    expected_shape = bundle.rendered_coefficient_state.rendered_coefficients_raw.shape
    if external_coefficients_raw.shape != expected_shape:
        raise ValueError(
            f"external_coefficients_raw shape {external_coefficients_raw.shape} does not match rendered shape {expected_shape}."
        )
    external_coefficients_orthonormalized = project_coefficients_to_orthonormal_basis(
        external_coefficients_raw,
        bundle.field_basis_state.orthonormal_r_matrix,
    )
    alignment = complex_alignment(
        bundle.rendered_coefficient_state.rendered_coefficients_raw.reshape(-1),
        external_coefficients_raw.reshape(-1),
    )
    shared_scale = alignment["scale_abs"] * np.exp(1j * alignment["scale_phase_rad"])
    rendered_shared_scale_aligned = shared_scale * bundle.rendered_coefficient_state.rendered_coefficients_raw
    rendered_shared_scale_aligned_orthonormalized = project_coefficients_to_orthonormal_basis(
        rendered_shared_scale_aligned,
        bundle.field_basis_state.orthonormal_r_matrix,
    )
    return {
        "external_coefficients_raw": external_coefficients_raw,
        "external_coefficients_orthonormalized": external_coefficients_orthonormalized,
        "shared_scale_alignment": alignment,
        "rendered_coefficients_shared_scale_aligned_raw": rendered_shared_scale_aligned,
        "rendered_coefficients_shared_scale_aligned_orthonormalized": rendered_shared_scale_aligned_orthonormalized,
    }


def build_coefficient_path_bundle(
    result: dict[str, Any],
    *,
    coefficient_map_model_id: str = "identity_slice_projected_rendered_basis",
    reference_rendered_coefficients_raw: np.ndarray | None = None,
    fitted_coefficient_map: FittedCoefficientMap | None = None,
) -> CoefficientPathBundle:
    coefficient_contract = extract_effective_coefficient_contract(result)
    lambda_nm = coefficient_contract["lambda_nm"]
    expected_lambda_shape = lambda_nm.shape

    d1_vector_k = _as_complex_array(
        "D1_vector_k",
        _get_required_key(result, "D1_vector_k"),
        ndim=2,
        shape=(expected_lambda_shape[0], 2),
    )
    c2_tensor_k = _as_complex_array(
        "C2_tensor_k",
        _get_required_key(result, "C2_tensor_k"),
        ndim=3,
        shape=(expected_lambda_shape[0], 2, 2),
    )

    x_um = np.asarray(_get_required_key(result, "x_um"), dtype=float)
    if x_um.ndim != 1 or x_um.size == 0:
        raise ValueError("x_um must be a non-empty 1D axis.")
    if not np.all(np.isfinite(x_um)) or not np.all(np.diff(x_um) > 0.0):
        raise ValueError("x_um must be finite and strictly increasing.")

    slice_direction_local = np.asarray(_get_required_key(result, "C2_slice_local_direction"), dtype=float)
    if slice_direction_local.shape != (2,):
        raise ValueError(f"C2_slice_local_direction must have shape (2,), got {slice_direction_local.shape}.")
    norm = float(np.linalg.norm(slice_direction_local))
    if norm <= 1e-30:
        raise ValueError("C2_slice_local_direction must be non-zero.")
    slice_direction_local = slice_direction_local / norm
    projection_operator_tensor = np.outer(slice_direction_local, slice_direction_local)

    R0_x = _as_complex_array(
        "reference_pupil_field_profile",
        _get_required_key(result, "reference_pupil_field_profile"),
        ndim=1,
        shape=x_um.shape,
    )
    R1_slice_x = _as_complex_array(
        "directional_first_order_field_profile",
        _get_required_key(result, "directional_first_order_field_profile"),
        ndim=1,
        shape=x_um.shape,
    )
    R2_slice_x = _as_complex_array(
        "directional_second_order_slice_field_profile",
        _get_required_key(result, "directional_second_order_slice_field_profile"),
        ndim=1,
        shape=x_um.shape,
    )
    basis_matrix = np.column_stack([R0_x, R1_slice_x, R2_slice_x])
    basis_column_norms = np.linalg.norm(basis_matrix, axis=0)
    orthonormal_q_matrix, orthonormal_r_matrix = np.linalg.qr(basis_matrix, mode="reduced")

    projected_coefficients_raw = np.column_stack(
        [
            coefficient_contract["B_k"],
            coefficient_contract["D1_slice_k"],
            coefficient_contract["C2_slice_k"],
        ]
    )
    if fitted_coefficient_map is not None:
        if (
            coefficient_map_model_id != "identity_slice_projected_rendered_basis"
            and fitted_coefficient_map.coefficient_map_model_id != coefficient_map_model_id
        ):
            raise ValueError(
                "Explicit fitted_coefficient_map does not match requested coefficient_map_model_id."
            )
        rendered_coefficient_state = apply_fitted_coefficient_map(
            projected_coefficients_raw,
            fitted_coefficient_map,
        )
    else:
        rendered_coefficient_state = map_projected_to_rendered_coefficients(
            projected_coefficients_raw,
            model_id=coefficient_map_model_id,
            reference_rendered_coefficients_raw=reference_rendered_coefficients_raw,
        )
    rendered_coefficients_orthonormalized = project_coefficients_to_orthonormal_basis(
        rendered_coefficient_state.rendered_coefficients_raw,
        orthonormal_r_matrix,
    )

    angular_fit_state = AngularFitState(
        lambda_nm=lambda_nm,
        B_k=coefficient_contract["B_k"],
        D1_vector_k=d1_vector_k,
        C2_tensor_k=c2_tensor_k,
        fit_strategy=coefficient_contract["fit_strategy"],
        relative_fit_residual_model=coefficient_contract["relative_fit_residual_model"],
        C2_tensor_basis=coefficient_contract["C2_tensor_basis"],
        D1_tensor_basis=coefficient_contract["D1_tensor_basis"],
        fit_diagnostics=coefficient_contract["fit_diagnostics"],
        wavelength_axis_kind=coefficient_contract["wavelength_axis_kind"],
    )
    slice_projected_state = SliceProjectedState(
        B_k_projected=coefficient_contract["B_k"],
        D1_slice_k=coefficient_contract["D1_slice_k"],
        C2_slice_k=coefficient_contract["C2_slice_k"],
        slice_direction_label=coefficient_contract["slice_direction_label"],
        slice_direction_local=slice_direction_local,
        projection_operator_vector=slice_direction_local,
        projection_operator_tensor=projection_operator_tensor,
    )
    field_basis_state = FieldBasisState(
        x_um=x_um,
        R0_x=R0_x,
        R1_slice_x=R1_slice_x,
        R2_slice_x=R2_slice_x,
        basis_labels=RENDERED_COEFFICIENT_LABELS,
        basis_matrix=basis_matrix,
        basis_column_norms=basis_column_norms,
        orthonormal_q_matrix=orthonormal_q_matrix,
        orthonormal_r_matrix=orthonormal_r_matrix,
        normalization_scale=float(_get_required_key(result, "directional_field_expansion_scale")),
        field_assembly_model_id=str(_get_required_key(result, "second_order_model")),
    )
    comparison_state = CoefficientComparisonState(
        rendered_coefficient_labels=RENDERED_COEFFICIENT_LABELS,
        rendered_coefficients_raw=rendered_coefficient_state.rendered_coefficients_raw,
        rendered_coefficients_orthonormalized=rendered_coefficients_orthonormalized,
        coefficient_map_model_id=rendered_coefficient_state.coefficient_map_model_id,
        coefficient_map_theory_claim=(
            "Current production theory obtains rendered field-basis coefficients through the configured "
            "coefficient-map stage applied to the slice-projected angular-fit coefficients."
        ),
        coefficient_gauge_note=(
            "Raw rendered coefficients are basis-dependent. Orthonormalized coefficients should be used "
            "for conditioning-aware comparisons, while shared-scale alignment should be used before "
            "interpreting component-wise mismatch."
        ),
    )
    return CoefficientPathBundle(
        angular_fit_state=angular_fit_state,
        slice_projected_state=slice_projected_state,
        field_basis_state=field_basis_state,
        rendered_coefficient_state=rendered_coefficient_state,
        comparison_state=comparison_state,
    )


def _serialize_fit_diagnostics(payload: dict[str, Any], fit_diagnostics: dict[str, Any]) -> None:
    payload["fit_diagnostics_key_names"] = np.asarray(sorted(fit_diagnostics.keys()))
    for key, value in fit_diagnostics.items():
        field_name = f"fitdiag__{key}"
        if isinstance(value, np.ndarray):
            payload[field_name] = value
        elif np.isscalar(value):
            payload[field_name] = np.asarray(value)
        elif isinstance(value, (list, tuple)):
            payload[field_name] = np.asarray(value)
        else:
            payload[field_name] = np.asarray(json.dumps(value, sort_keys=True))


def _deserialize_fit_diagnostics(loaded: dict[str, Any]) -> dict[str, Any]:
    fit_diagnostics: dict[str, Any] = {}
    for key, value in loaded.items():
        if key.startswith("fitdiag__"):
            fit_diagnostics[key.removeprefix("fitdiag__")] = value
    return fit_diagnostics


def coefficient_path_bundle_npz_payload(
    bundle: CoefficientPathBundle,
    *,
    case_name: str,
    artifact_kind: str = "native_identity",
    recovered_coefficients_raw: np.ndarray | None = None,
    recovered_source_label: str = "bridge_recovered",
) -> dict[str, Any]:
    artifact_kind = _validate_artifact_kind(artifact_kind)
    payload: dict[str, Any] = {
        "case_name": np.asarray(case_name),
        "bundle_schema_version": np.asarray(COEFFICIENT_PATH_BUNDLE_SCHEMA_VERSION),
        "coefficient_bundle_artifact_kind": np.asarray(artifact_kind),
        "lambda_nm": bundle.angular_fit_state.lambda_nm,
        "B_k": bundle.angular_fit_state.B_k,
        "D1_vector_k": bundle.angular_fit_state.D1_vector_k,
        "C2_tensor_k": bundle.angular_fit_state.C2_tensor_k,
        "B_k_projected": bundle.slice_projected_state.B_k_projected,
        "D1_slice_k": bundle.slice_projected_state.D1_slice_k,
        "C2_slice_k": bundle.slice_projected_state.C2_slice_k,
        "projected_coefficient_labels": np.asarray(bundle.rendered_coefficient_state.projected_coefficient_labels),
        "projected_coefficients_raw": bundle.rendered_coefficient_state.projected_coefficients_raw,
        "slice_direction_label": np.asarray(bundle.slice_projected_state.slice_direction_label),
        "slice_direction_local": bundle.slice_projected_state.slice_direction_local,
        "projection_operator_vector": bundle.slice_projected_state.projection_operator_vector,
        "projection_operator_tensor": bundle.slice_projected_state.projection_operator_tensor,
        "x_um": bundle.field_basis_state.x_um,
        "R0_x": bundle.field_basis_state.R0_x,
        "R1_slice_x": bundle.field_basis_state.R1_slice_x,
        "R2_slice_x": bundle.field_basis_state.R2_slice_x,
        "basis_matrix": bundle.field_basis_state.basis_matrix,
        "basis_column_norms": bundle.field_basis_state.basis_column_norms,
        "orthonormal_q_matrix": bundle.field_basis_state.orthonormal_q_matrix,
        "orthonormal_r_matrix": bundle.field_basis_state.orthonormal_r_matrix,
        "normalization_scale": np.asarray(bundle.field_basis_state.normalization_scale),
        "field_assembly_model_id": np.asarray(bundle.field_basis_state.field_assembly_model_id),
        "rendered_coefficients_raw": bundle.rendered_coefficient_state.rendered_coefficients_raw,
        "rendered_coefficients_orthonormalized": bundle.comparison_state.rendered_coefficients_orthonormalized,
        "rendered_coefficient_labels": np.asarray(bundle.comparison_state.rendered_coefficient_labels),
        "coefficient_map_matrix": bundle.rendered_coefficient_state.coefficient_map_matrix,
        "fit_strategy": np.asarray(bundle.angular_fit_state.fit_strategy),
        "relative_fit_residual_model": np.asarray(bundle.angular_fit_state.relative_fit_residual_model),
        "C2_tensor_basis": np.asarray(bundle.angular_fit_state.C2_tensor_basis),
        "D1_tensor_basis": np.asarray(bundle.angular_fit_state.D1_tensor_basis),
        "coefficient_map_model_id": np.asarray(bundle.rendered_coefficient_state.coefficient_map_model_id),
    }
    metadata = {
        "coefficient_map_theory_claim": bundle.comparison_state.coefficient_map_theory_claim,
        "coefficient_gauge_note": bundle.comparison_state.coefficient_gauge_note,
        "coefficient_map_note": bundle.rendered_coefficient_state.coefficient_map_note,
        "coefficient_map_parameters": bundle.rendered_coefficient_state.coefficient_map_parameters,
        "wavelength_axis_kind": bundle.angular_fit_state.wavelength_axis_kind,
        "coefficient_map_matrix_condition_number": float(
            np.linalg.cond(bundle.rendered_coefficient_state.coefficient_map_matrix[0])
        ),
        "coefficient_map_matrix_rank": int(
            np.linalg.matrix_rank(bundle.rendered_coefficient_state.coefficient_map_matrix[0])
        ),
    }
    payload["metadata_json"] = np.asarray(json.dumps(metadata, sort_keys=True))
    _serialize_fit_diagnostics(payload, bundle.angular_fit_state.fit_diagnostics)
    if recovered_coefficients_raw is not None:
        comparison_views = build_external_comparison_views(bundle, recovered_coefficients_raw)
        payload["recovered_source_label"] = np.asarray(recovered_source_label)
        payload["recovered_coefficients_raw"] = comparison_views["external_coefficients_raw"]
        payload["recovered_coefficients_orthonormalized"] = comparison_views["external_coefficients_orthonormalized"]
        payload["rendered_coefficients_shared_scale_aligned_raw"] = comparison_views[
            "rendered_coefficients_shared_scale_aligned_raw"
        ]
        payload["rendered_coefficients_shared_scale_aligned_orthonormalized"] = comparison_views[
            "rendered_coefficients_shared_scale_aligned_orthonormalized"
        ]
        payload["shared_scale_alignment_json"] = np.asarray(
            json.dumps(comparison_views["shared_scale_alignment"], sort_keys=True)
        )
    return payload


def write_coefficient_path_bundle_npz(
    output_path: str | Path,
    bundle: CoefficientPathBundle,
    *,
    case_name: str,
    artifact_kind: str = "native_identity",
    recovered_coefficients_raw: np.ndarray | None = None,
    recovered_source_label: str = "bridge_recovered",
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = coefficient_path_bundle_npz_payload(
        bundle,
        case_name=case_name,
        artifact_kind=artifact_kind,
        recovered_coefficients_raw=recovered_coefficients_raw,
        recovered_source_label=recovered_source_label,
    )
    np.savez(output_path, **payload)
    return output_path


def validate_coefficient_path_bundle_payload(payload: dict[str, Any]) -> dict[str, Any]:
    required_keys = (
        "bundle_schema_version",
        "case_name",
        "coefficient_bundle_artifact_kind",
        "lambda_nm",
        "x_um",
        "B_k",
        "D1_vector_k",
        "D1_slice_k",
        "C2_tensor_k",
        "C2_slice_k",
        "projected_coefficients_raw",
        "basis_matrix",
        "orthonormal_r_matrix",
        "rendered_coefficients_raw",
        "rendered_coefficients_orthonormalized",
        "coefficient_map_matrix",
        "coefficient_map_model_id",
    )
    missing = [key for key in required_keys if key not in payload]
    if missing:
        raise KeyError(f"Missing coefficient bundle payload keys: {', '.join(missing)}")
    if str(np.asarray(payload["bundle_schema_version"]).item()) != COEFFICIENT_PATH_BUNDLE_SCHEMA_VERSION:
        raise ValueError("Unsupported coefficient bundle schema version.")

    lambda_nm = np.asarray(payload["lambda_nm"], dtype=float)
    if lambda_nm.ndim != 1 or lambda_nm.size < 2 or not np.all(np.diff(lambda_nm) > 0.0):
        raise ValueError("lambda_nm must be 1D, length >= 2, and strictly increasing.")
    x_um = np.asarray(payload["x_um"], dtype=float)
    if x_um.ndim != 1 or x_um.size < 2 or not np.all(np.diff(x_um) > 0.0):
        raise ValueError("x_um must be 1D, length >= 2, and strictly increasing.")

    n_lambda = lambda_nm.shape[0]
    basis_matrix = _as_complex_array("basis_matrix", payload["basis_matrix"], ndim=2)
    if basis_matrix.shape[1] != 3:
        raise ValueError("basis_matrix must have exactly three rendered basis columns.")
    if basis_matrix.shape[0] != x_um.shape[0]:
        raise ValueError("basis_matrix row count must match x_um size.")
    orthonormal_r_matrix = _as_complex_array("orthonormal_r_matrix", payload["orthonormal_r_matrix"], ndim=2, shape=(3, 3))
    projected_coefficients_raw = _as_complex_array(
        "projected_coefficients_raw",
        payload["projected_coefficients_raw"],
        ndim=2,
        shape=(n_lambda, 3),
    )
    rendered_coefficients_raw = _as_complex_array(
        "rendered_coefficients_raw",
        payload["rendered_coefficients_raw"],
        ndim=2,
        shape=(n_lambda, 3),
    )
    rendered_coefficients_orthonormalized = _as_complex_array(
        "rendered_coefficients_orthonormalized",
        payload["rendered_coefficients_orthonormalized"],
        ndim=2,
        shape=(n_lambda, 3),
    )
    coefficient_map_matrix = _as_complex_array(
        "coefficient_map_matrix",
        payload["coefficient_map_matrix"],
        ndim=3,
        shape=(n_lambda, 3, 3),
    )
    artifact_kind = _validate_artifact_kind(str(np.asarray(payload["coefficient_bundle_artifact_kind"]).item()))
    coefficient_map_model_id = _validate_model_id(str(np.asarray(payload["coefficient_map_model_id"]).item()))
    projected_labels = tuple(str(item) for item in np.asarray(payload.get("projected_coefficient_labels", ())).tolist())
    rendered_labels = tuple(str(item) for item in np.asarray(payload.get("rendered_coefficient_labels", ())).tolist())
    if projected_labels != PROJECTED_COEFFICIENT_LABELS:
        raise ValueError(
            f"projected_coefficient_labels must match {PROJECTED_COEFFICIENT_LABELS}, got {projected_labels!r}."
        )
    if rendered_labels != RENDERED_COEFFICIENT_LABELS:
        raise ValueError(
            f"rendered_coefficient_labels must match {RENDERED_COEFFICIENT_LABELS}, got {rendered_labels!r}."
        )

    fit_diagnostics = _deserialize_fit_diagnostics(payload)
    if not fit_diagnostics:
        raise ValueError("Coefficient bundle payload must include serialized fit diagnostics.")
    if "metadata_json" not in payload:
        raise ValueError("Coefficient bundle payload must include metadata_json.")
    metadata = json.loads(str(np.asarray(payload["metadata_json"]).item()))
    required_metadata = {
        "coefficient_map_theory_claim",
        "coefficient_gauge_note",
        "coefficient_map_note",
        "coefficient_map_parameters",
        "wavelength_axis_kind",
        "coefficient_map_matrix_condition_number",
        "coefficient_map_matrix_rank",
    }
    missing_metadata = sorted(required_metadata.difference(metadata))
    if missing_metadata:
        raise ValueError(f"Coefficient bundle metadata_json missing required keys: {missing_metadata}.")

    rendered_from_map = np.einsum("ni,nij->nj", projected_coefficients_raw, coefficient_map_matrix)
    if not np.allclose(rendered_from_map, rendered_coefficients_raw, rtol=1e-8, atol=1e-8):
        raise ValueError("rendered_coefficients_raw must equal projected_coefficients_raw @ coefficient_map_matrix.")
    orth_from_raw = rendered_coefficients_raw @ orthonormal_r_matrix.T
    if not np.allclose(orth_from_raw, rendered_coefficients_orthonormalized, rtol=1e-8, atol=1e-8):
        raise ValueError(
            "rendered_coefficients_orthonormalized must equal rendered_coefficients_raw @ orthonormal_r_matrix.T."
        )
    first_map = coefficient_map_matrix[0]
    matrix_rank = int(np.linalg.matrix_rank(first_map))
    if matrix_rank != int(metadata["coefficient_map_matrix_rank"]):
        raise ValueError("coefficient_map_matrix_rank metadata does not match coefficient_map_matrix[0].")
    matrix_condition = float(np.linalg.cond(first_map))
    if not np.isclose(matrix_condition, float(metadata["coefficient_map_matrix_condition_number"]), rtol=1e-8, atol=1e-8):
        raise ValueError(
            "coefficient_map_matrix_condition_number metadata does not match coefficient_map_matrix[0]."
        )

    return {
        "lambda_nm": lambda_nm,
        "x_um": x_um,
        "basis_matrix": basis_matrix,
        "orthonormal_r_matrix": orthonormal_r_matrix,
        "projected_coefficients_raw": projected_coefficients_raw,
        "rendered_coefficients_raw": rendered_coefficients_raw,
        "rendered_coefficients_orthonormalized": rendered_coefficients_orthonormalized,
        "coefficient_map_matrix": coefficient_map_matrix,
        "projected_coefficient_labels": projected_labels,
        "rendered_coefficient_labels": rendered_labels,
        "coefficient_bundle_artifact_kind": artifact_kind,
        "coefficient_map_model_id": coefficient_map_model_id,
        "fit_diagnostics": fit_diagnostics,
        "metadata": metadata,
    }


def read_coefficient_path_bundle_npz(path: str | Path) -> dict[str, Any]:
    path = Path(path)
    with np.load(path, allow_pickle=False) as loaded:
        payload = {key: loaded[key] for key in loaded.files}
    payload["fit_diagnostics"] = _deserialize_fit_diagnostics(payload)
    if "metadata_json" in payload:
        payload["metadata"] = json.loads(str(np.asarray(payload["metadata_json"]).item()))
    payload["validated"] = validate_coefficient_path_bundle_payload(payload)
    payload["artifact_path"] = str(path)
    return payload


def coefficient_bundle_report_path(
    reports_dir: str | Path,
    case_name: str,
    *,
    artifact_kind: str = "native_identity",
    coefficient_map_model_id: str | None = None,
) -> Path:
    reports_dir = Path(reports_dir)
    artifact_kind = _validate_artifact_kind(artifact_kind)
    case_stub = _sanitize_case_name(case_name)
    if artifact_kind == "native_identity":
        filename = f"round6p1_{case_stub}_native_identity_coefficient_bundle.npz"
    elif artifact_kind == "shared_map_promoted":
        if coefficient_map_model_id is None:
            raise ValueError("shared_map_promoted coefficient bundles require coefficient_map_model_id.")
        model_id = _validate_model_id(coefficient_map_model_id)
        filename = f"round6p1_{case_stub}_shared_map_promoted_{model_id}_coefficient_bundle.npz"
    else:
        filename = f"round6p1_{case_stub}_case_specific_fitted_map_diagnostic_bundle.npz"
    return reports_dir / filename


__all__ = [
    "AngularFitState",
    "assemble_runtime_lateral_field",
    "COEFFICIENT_MAP_MODEL_IDS",
    "COEFFICIENT_MAP_RUNTIME_MODES",
    "COEFFICIENT_BUNDLE_ARTIFACT_KINDS",
    "CoefficientComparisonState",
    "FittedCoefficientMap",
    "CoefficientPathBundle",
    "FieldBasisState",
    "PROJECTED_COEFFICIENT_LABELS",
    "RENDERED_COEFFICIENT_LABELS",
    "REFERENCE_RENDERED_COEFFICIENT_SOURCES",
    "RenderedCoefficientState",
    "SliceProjectedState",
    "apply_fitted_coefficient_map",
    "build_coefficient_path_bundle",
    "build_external_comparison_views",
    "COEFFICIENT_PATH_BUNDLE_SCHEMA_VERSION",
    "coefficient_bundle_report_path",
    "coefficient_path_bundle_npz_payload",
    "fit_projected_to_rendered_map",
    "map_projected_to_rendered_coefficients",
    "plan_runtime_field_assembly_contract",
    "project_coefficients_to_orthonormal_basis",
    "read_shared_coefficient_map_candidate_npz",
    "resolve_reference_rendered_coefficients",
    "resolve_runtime_fitted_coefficient_map",
    "reconstruct_lateral_field_from_rendered_coefficients",
    "read_coefficient_path_bundle_npz",
    "SHARED_COEFFICIENT_MAP_CANDIDATE_SCHEMA_VERSION",
    "RENDERED_BASIS_SHIFT_TARGETS",
    "RuntimeFieldAssemblyPlan",
    "shared_coefficient_map_candidate_payload",
    "shared_coefficient_map_candidate_report_path",
    "validate_shared_coefficient_map_candidate_payload",
    "validate_coefficient_path_bundle_payload",
    "write_shared_coefficient_map_candidate_npz",
    "write_coefficient_path_bundle_npz",
]
