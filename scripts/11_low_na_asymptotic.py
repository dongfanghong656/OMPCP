from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from solvers import coefficient_path_bundle as _COEFF_BUNDLE
from solvers import low_na_effective_channel as _EFFECTIVE_CHANNEL

if TYPE_CHECKING:
    from oct_nonspherical_psf_solver import GridConfig, SolverConfig, SourceConfig


SUPPORTED_POLARIZATION_MODES = ("linear_x", "linear_y", "co_pol", "cross_pol")


LOW_NA_ASYMPTOTIC_APPROXIMATION_LABEL = "backscatter-curvature low-NA asymptotic approximation"
LOW_NA_ASYMPTOTIC_NOTE = (
    "This mode retains a low-NA confocal surrogate but augments the exact backscatter term B(k) "
    "with a second-order angular-tensor correction obtained by contracting a fitted C2 tensor "
    "against a coherent spatial second-moment tensor profile. Scalar mu2 and C2(k) are kept as "
    "trace summaries for compatibility. It now shares the same Jones-projected effective channel "
    "definition as vector_pupil_overlap_bridge, but it is still approximate."
)

estimate_effective_channel_B_C2 = _EFFECTIVE_CHANNEL.estimate_effective_channel_B_C2
_project_quadratic_tensor_to_direction = _EFFECTIVE_CHANNEL.project_quadratic_tensor_to_direction
_project_vector_to_direction = _EFFECTIVE_CHANNEL.project_vector_to_direction
_project_vector_profile_to_direction = _EFFECTIVE_CHANNEL.project_vector_profile_to_direction
_project_quadratic_tensor_profile_to_direction = _EFFECTIVE_CHANNEL.project_quadratic_tensor_profile_to_direction
resolve_lateral_slice_direction = _EFFECTIVE_CHANNEL.resolve_lateral_slice_direction
resolve_effective_channel_fit_config = _EFFECTIVE_CHANNEL.resolve_effective_channel_fit_config
compute_second_order_correction = _EFFECTIVE_CHANNEL.compute_second_order_correction
build_directional_field_expansion_profiles = _EFFECTIVE_CHANNEL.build_directional_field_expansion_profiles
build_first_order_field_profile = _EFFECTIVE_CHANNEL.build_first_order_field_profile


def _solver_api():
    module = sys.modules.get("oct_nonspherical_psf_solver")
    if module is not None and hasattr(module, "solve_oct_particle_response"):
        return module
    main_module = sys.modules.get("__main__")
    if main_module is not None and hasattr(main_module, "solve_oct_particle_response"):
        return main_module
    script_dir = Path(__file__).resolve().parent
    for candidate in ("oct_nonspherical_psf_solver.py", "01_oct_nonspherical_psf_solver.py"):
        candidate_path = script_dir / candidate
        if candidate_path.exists():
            spec = importlib.util.spec_from_file_location("oct_nonspherical_psf_solver", candidate_path)
            if spec is None or spec.loader is None:
                continue
            module = importlib.util.module_from_spec(spec)
            sys.modules["oct_nonspherical_psf_solver"] = module
            spec.loader.exec_module(module)
            return module
    return importlib.import_module("oct_nonspherical_psf_solver")


def _load_bridge_module():
    return _solver_api().load_round6_extension("10_vector_pupil_overlap_bridge.py", "round6_vector_pupil_overlap_bridge")


def _compute_first_order_raw_shift_um(
    *,
    D1_slice_k: np.ndarray,
    B_k: np.ndarray,
    k_medium_rad_per_um: np.ndarray,
) -> np.ndarray:
    D1_slice_k = np.asarray(D1_slice_k, dtype=np.complex128)
    B_k = np.asarray(B_k, dtype=np.complex128)
    k_medium_rad_per_um = np.asarray(k_medium_rad_per_um, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.real(1j * D1_slice_k / (k_medium_rad_per_um * B_k))


def summarize_first_order_shift_validity(
    *,
    D1_slice_k: np.ndarray,
    B_k: np.ndarray,
    k_medium_rad_per_um: np.ndarray,
    relative_b_floor: float = 1e-6,
) -> dict:
    raw_shift_um = _compute_first_order_raw_shift_um(
        D1_slice_k=D1_slice_k,
        B_k=B_k,
        k_medium_rad_per_um=k_medium_rad_per_um,
    )
    abs_B = np.abs(np.asarray(B_k, dtype=np.complex128))
    max_abs_B = float(np.max(abs_B)) if len(abs_B) else 0.0
    B_k_small_threshold = max(relative_b_floor * max_abs_B, 1e-30)
    B_k_small_mask = abs_B <= B_k_small_threshold
    finite_mask = np.isfinite(raw_shift_um)
    valid_mask = finite_mask & ~B_k_small_mask
    return {
        "first_order_validity_mask": valid_mask,
        "first_order_invalid_fraction": float(1.0 - np.mean(valid_mask.astype(float))) if len(valid_mask) else 0.0,
        "first_order_finite_fraction": float(np.mean(finite_mask.astype(float))) if len(finite_mask) else 1.0,
        "first_order_B_k_small_fraction": float(np.mean(B_k_small_mask.astype(float))) if len(B_k_small_mask) else 0.0,
        "first_order_B_k_small_threshold": float(B_k_small_threshold),
        "first_order_raw_shift_um": raw_shift_um,
        "first_order_validity_note": (
            "These diagnostics expose wavelength samples where the experimental first-order shift estimate i D1_slice_k / (k_medium B_k) "
            "is ill-conditioned because |B_k| is too small or the raw shift becomes non-finite. estimate_first_order_lateral_shift_um "
            "still nan-to-num clips the shift for branch-compatibility, so inspect invalid_fraction before interpreting small delta_x values."
        ),
    }


def estimate_first_order_lateral_shift_um(
    *,
    D1_slice_k: np.ndarray,
    B_k: np.ndarray,
    k_medium_rad_per_um: np.ndarray,
) -> np.ndarray:
    shift_um = _compute_first_order_raw_shift_um(
        D1_slice_k=D1_slice_k,
        B_k=np.asarray(B_k, dtype=np.complex128) + 1e-30,
        k_medium_rad_per_um=k_medium_rad_per_um,
    )
    return np.nan_to_num(shift_um, nan=0.0, posinf=0.0, neginf=0.0)


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


def build_shifted_lateral_envelope(
    x_um: np.ndarray,
    lateral_envelope: np.ndarray,
    delta_x_um_k: np.ndarray,
    *,
    shift_impl: str,
    lambda0_nm: float | None = None,
    na: float | None = None,
) -> np.ndarray:
    x_um = np.asarray(x_um, dtype=float)
    lateral_envelope = np.asarray(lateral_envelope, dtype=np.complex128)
    delta_x_um_k = np.asarray(delta_x_um_k, dtype=float)
    shifted = np.zeros((len(delta_x_um_k), len(x_um)), dtype=np.complex128)
    if shift_impl == "interp":
        for idx, shift_um in enumerate(delta_x_um_k):
            shifted[idx] = _shift_complex_profile_interp(x_um, lateral_envelope, shift_um, boundary_mode="zero_pad")
        return shifted
    if shift_impl == "interp_edge_hold":
        for idx, shift_um in enumerate(delta_x_um_k):
            shifted[idx] = _shift_complex_profile_interp(x_um, lateral_envelope, shift_um, boundary_mode="edge_hold")
        return shifted
    if shift_impl == "analytic_gaussian":
        if lambda0_nm is None or na is None:
            raise ValueError("analytic_gaussian shift_impl requires lambda0_nm and na.")
        api = _solver_api()
        for idx, shift_um in enumerate(delta_x_um_k):
            shifted[idx] = np.sqrt(api.gaussian_lateral_intensity(x_um - shift_um, lambda0_nm, na))
        return shifted
    raise ValueError(f"Unsupported shift_impl: {shift_impl}")


def shift_second_order_correction(
    x_um: np.ndarray,
    second_order_correction_kx: np.ndarray,
    delta_x_um_k: np.ndarray,
    *,
    lateral_shift_coupling: str,
    shift_impl: str = "interp",
) -> np.ndarray:
    second_order_correction_kx = np.asarray(second_order_correction_kx, dtype=np.complex128)
    if lateral_shift_coupling == "envelope_only":
        return second_order_correction_kx
    if lateral_shift_coupling == "shift_envelope_and_mu2":
        boundary_mode = "edge_hold" if shift_impl == "interp_edge_hold" else "zero_pad"
        shifted = np.zeros_like(second_order_correction_kx)
        for idx, shift_um in enumerate(np.asarray(delta_x_um_k, dtype=float)):
            shifted[idx] = _shift_complex_profile_interp(
                x_um,
                second_order_correction_kx[idx],
                shift_um,
                boundary_mode=boundary_mode,
            )
        return shifted
    raise ValueError(f"Unsupported lateral_shift_coupling: {lateral_shift_coupling}")


def summarize_lateral_shift_delta(delta_x_um_k: np.ndarray) -> dict:
    delta_x_um_k = np.asarray(delta_x_um_k, dtype=float)
    return {
        "min_um": float(np.min(delta_x_um_k)) if len(delta_x_um_k) else 0.0,
        "max_um": float(np.max(delta_x_um_k)) if len(delta_x_um_k) else 0.0,
        "mean_abs_um": float(np.mean(np.abs(delta_x_um_k))) if len(delta_x_um_k) else 0.0,
    }


def compute_mu2_from_pupil_weight(
    sin_theta_max_ref: float,
    *,
    obliquity_kind: str = "sqrt_cos",
    n_theta: int,
    n_phi: int,
) -> float:
    """Return second angular moment mu2."""
    if sin_theta_max_ref <= 0:
        return 0.0
    rho = np.linspace(0.0, 1.0, n_theta)
    phi = np.linspace(0.0, 2.0 * np.pi, n_phi, endpoint=False)
    rho_grid, _ = np.meshgrid(rho, phi, indexing="ij")
    sin_theta = np.clip(sin_theta_max_ref * rho_grid, 0.0, 1.0)
    theta = np.arcsin(sin_theta)
    cos_theta = np.sqrt(np.clip(1.0 - sin_theta**2, 0.0, None))
    if obliquity_kind == "sqrt_cos":
        angular_weight = np.sqrt(cos_theta)
    elif obliquity_kind == "cos":
        angular_weight = cos_theta
    else:
        angular_weight = np.ones_like(theta)
    rho_weight = _solver_api().trapezoid_weights(rho)[:, None]
    phi_weight = np.full((1, n_phi), 2.0 * np.pi / n_phi, dtype=float)
    weights = rho_weight * phi_weight * rho_grid * angular_weight
    return float(np.sum(weights * theta**2) / (np.sum(weights) + 1e-30))


def compute_mu2_profile_from_pupil_weight(
    x_um: np.ndarray,
    lambda0_nm: float,
    medium_material: Any,
    sin_theta_max_ref: float,
    *,
    obliquity_kind: str = "sqrt_cos",
    n_pupil: int,
) -> dict:
    """Compute a coherent 2x2 second-moment tensor profile and its trace summary."""
    api = _solver_api()
    x_um = np.asarray(x_um, dtype=float)
    if sin_theta_max_ref <= 0:
        zeros = np.zeros_like(x_um, dtype=np.complex128)
        tensor_zeros = np.zeros((len(x_um), 2, 2), dtype=np.complex128)
        tensor_ref = np.zeros((2, 2), dtype=np.complex128)
        return _build_mu2_profile_payload(
            mu2_reference_tensor=tensor_ref,
            mu2_tensor_profile=tensor_zeros,
            denominator=zeros,
            numerator_x=zeros,
            numerator_y=zeros,
            numerator_xx=zeros,
            numerator_xy=zeros,
            numerator_yy=zeros,
        )
    dense_grid = api._build_unit_pupil_grid(n_bfp=n_pupil)
    weights_1d = api.trapezoid_weights(dense_grid["pupil_axis"])
    weights_2d = np.outer(weights_1d, weights_1d)
    mask = dense_grid["valid_mask"]
    u_flat = dense_grid["u_pupil"][mask]
    v_flat = dense_grid["v_pupil"][mask]
    radial_sq = u_flat**2 + v_flat**2
    rho_flat = np.sqrt(radial_sq)
    sin_theta = np.clip(sin_theta_max_ref * rho_flat, 0.0, 1.0)
    theta = np.arcsin(sin_theta)
    theta_direction_scale = np.zeros_like(theta)
    nonzero_rho = rho_flat > 1e-12
    theta_direction_scale[nonzero_rho] = theta[nonzero_rho] / rho_flat[nonzero_rho]
    theta_alpha = theta_direction_scale * u_flat
    theta_beta = theta_direction_scale * v_flat
    cos_theta = np.sqrt(np.clip(1.0 - sin_theta**2, 0.0, None))
    if obliquity_kind == "sqrt_cos":
        angular_weight = np.sqrt(cos_theta)
    elif obliquity_kind == "cos":
        angular_weight = cos_theta
    else:
        angular_weight = np.ones_like(theta)
    coherent_base = weights_2d[mask] * angular_weight
    total_weight = np.sum(coherent_base) + 1e-30
    mu2_reference_tensor = np.array(
        [
            [
                np.sum(coherent_base * theta_alpha**2) / total_weight,
                np.sum(coherent_base * theta_alpha * theta_beta) / total_weight,
            ],
            [
                np.sum(coherent_base * theta_alpha * theta_beta) / total_weight,
                np.sum(coherent_base * theta_beta**2) / total_weight,
            ],
        ],
        dtype=np.complex128,
    )
    mu2_reference = np.trace(mu2_reference_tensor)
    medium_fn = api.resolve_material_model(medium_material)
    n_medium_ref = float(np.real(medium_fn(lambda0_nm / 1000.0)))
    k_medium_ref = 2.0 * np.pi * n_medium_ref / (lambda0_nm / 1000.0)
    phase = np.exp(1j * k_medium_ref * sin_theta_max_ref * np.outer(x_um, u_flat))
    denominator = phase @ coherent_base
    numerator_x = phase @ (coherent_base * theta_alpha)
    numerator_y = phase @ (coherent_base * theta_beta)
    numerator_xx = phase @ (coherent_base * theta_alpha**2)
    numerator_xy = phase @ (coherent_base * theta_alpha * theta_beta)
    numerator_yy = phase @ (coherent_base * theta_beta**2)
    denom_abs = np.abs(denominator)
    threshold = max(float(np.max(denom_abs)), 1e-30) * 1e-9
    mu2_tensor_profile = np.zeros((len(x_um), 2, 2), dtype=np.complex128)
    mu2_tensor_profile[:, 0, 0] = mu2_reference_tensor[0, 0]
    mu2_tensor_profile[:, 0, 1] = mu2_reference_tensor[0, 1]
    mu2_tensor_profile[:, 1, 0] = mu2_reference_tensor[1, 0]
    mu2_tensor_profile[:, 1, 1] = mu2_reference_tensor[1, 1]
    valid = denom_abs > threshold
    mu2_tensor_profile[valid, 0, 0] = numerator_xx[valid] / denominator[valid]
    mu2_tensor_profile[valid, 0, 1] = numerator_xy[valid] / denominator[valid]
    mu2_tensor_profile[valid, 1, 0] = numerator_xy[valid] / denominator[valid]
    mu2_tensor_profile[valid, 1, 1] = numerator_yy[valid] / denominator[valid]
    return _build_mu2_profile_payload(
        mu2_reference_tensor=mu2_reference_tensor,
        mu2_tensor_profile=mu2_tensor_profile,
        denominator=denominator,
        numerator_x=numerator_x,
        numerator_y=numerator_y,
        numerator_xx=numerator_xx,
        numerator_xy=numerator_xy,
        numerator_yy=numerator_yy,
    )


def _summarize_mu2_profile_complexity(mu2_profile: np.ndarray, denominator_abs: np.ndarray) -> dict:
    mu2_profile = np.asarray(mu2_profile, dtype=np.complex128)
    denominator_abs = np.asarray(denominator_abs, dtype=float)
    if denominator_abs.size:
        threshold = max(float(np.max(denominator_abs)), 1e-30) * 1e-9
        valid = denominator_abs > threshold
    else:
        valid = np.zeros_like(mu2_profile, dtype=bool)
    profile_valid = valid & (np.abs(mu2_profile) > (float(np.max(np.abs(mu2_profile))) + 1e-30) * 1e-12)
    if np.count_nonzero(profile_valid) >= 2:
        mu2_phase = np.unwrap(np.angle(mu2_profile[profile_valid]))
        mu2_profile_phase_span_rad = float(np.max(mu2_phase) - np.min(mu2_phase))
    else:
        mu2_profile_phase_span_rad = 0.0
    real_norm = float(np.linalg.norm(np.real(mu2_profile)))
    imag_norm = float(np.linalg.norm(np.imag(mu2_profile)))
    mu2_profile_real_imag_ratio = real_norm / (imag_norm + 1e-30)
    mu2_profile_valid_fraction = float(np.mean(valid.astype(float))) if len(valid) else 1.0
    return {
        "mu2_profile_phase_span_rad": mu2_profile_phase_span_rad,
        "mu2_profile_real_imag_ratio": mu2_profile_real_imag_ratio,
        "mu2_profile_valid_fraction": mu2_profile_valid_fraction,
        "mu2_profile_complexity_summary": {
            "phase_span_rad": mu2_profile_phase_span_rad,
            "real_imag_ratio": mu2_profile_real_imag_ratio,
            "valid_fraction": mu2_profile_valid_fraction,
            "note": "Large phase span or a substantial imaginary component means mu2_profile behaves more like a coherent effective kernel than a simple scalar moment surrogate.",
        },
    }


def _build_mu2_profile_payload(
    *,
    mu2_reference_tensor: np.ndarray,
    mu2_tensor_profile: np.ndarray,
    denominator: np.ndarray,
    numerator_x: np.ndarray,
    numerator_y: np.ndarray,
    numerator_xx: np.ndarray,
    numerator_xy: np.ndarray,
    numerator_yy: np.ndarray,
) -> dict:
    mu2_reference_tensor = np.asarray(mu2_reference_tensor, dtype=np.complex128)
    mu2_tensor_profile = np.asarray(mu2_tensor_profile, dtype=np.complex128)
    denominator = np.asarray(denominator, dtype=np.complex128)
    numerator_x = np.asarray(numerator_x, dtype=np.complex128)
    numerator_y = np.asarray(numerator_y, dtype=np.complex128)
    numerator_xx = np.asarray(numerator_xx, dtype=np.complex128)
    numerator_xy = np.asarray(numerator_xy, dtype=np.complex128)
    numerator_yy = np.asarray(numerator_yy, dtype=np.complex128)
    denominator_abs = np.abs(denominator)
    reference_first_order_field_vector = np.zeros((len(denominator), 2), dtype=np.complex128)
    reference_first_order_field_vector[:, 0] = numerator_x
    reference_first_order_field_vector[:, 1] = numerator_y
    reference_second_order_field_tensor = np.zeros((len(denominator), 2, 2), dtype=np.complex128)
    reference_second_order_field_tensor[:, 0, 0] = numerator_xx
    reference_second_order_field_tensor[:, 0, 1] = numerator_xy
    reference_second_order_field_tensor[:, 1, 0] = numerator_xy
    reference_second_order_field_tensor[:, 1, 1] = numerator_yy
    mu2_profile = mu2_tensor_profile[:, 0, 0] + mu2_tensor_profile[:, 1, 1]
    complexity = _summarize_mu2_profile_complexity(mu2_profile, denominator_abs)
    mu2_reference = complex(np.trace(mu2_reference_tensor))
    return {
        "mu2_reference": mu2_reference,
        "mu2_reference_trace": mu2_reference,
        "mu2_reference_tensor": mu2_reference_tensor,
        "mu2_profile": mu2_profile,
        "mu2_tensor_profile": mu2_tensor_profile,
        "reference_pupil_field_profile": denominator,
        "reference_first_order_field_vector": reference_first_order_field_vector,
        "reference_second_order_field_tensor": reference_second_order_field_tensor,
        "profile_weight_denominator_abs": denominator_abs,
        **complexity,
    }


def summarize_mu2_wavelength_freeze_sensitivity(
    *,
    lambda0_nm: float,
    fwhm_nm: float,
    medium_material: Any,
    na: float,
    obliquity_kind: str,
    n_pupil: int,
) -> dict:
    api = _solver_api()
    half_band_nm = max(float(fwhm_nm) * 0.5, 0.0)
    wavelength_samples_nm = np.array(
        [
            max(float(lambda0_nm) - half_band_nm, 1e-9),
            float(lambda0_nm),
            float(lambda0_nm) + half_band_nm,
        ],
        dtype=float,
    )
    tensors = []
    traces = []
    for wavelength_nm in wavelength_samples_nm:
        n_medium = api.resolve_material_model(medium_material)(wavelength_nm / 1000.0)
        geometry = api.derive_na_geometry(na, n_medium)
        diagnostics = compute_mu2_profile_from_pupil_weight(
            np.array([0.0], dtype=float),
            wavelength_nm,
            medium_material,
            geometry["sin_theta_max"],
            obliquity_kind=obliquity_kind,
            n_pupil=n_pupil,
        )
        tensor = np.asarray(diagnostics["mu2_reference_tensor"], dtype=np.complex128)
        tensors.append(tensor)
        traces.append(complex(diagnostics["mu2_reference_trace"]))
    center_tensor = tensors[1]
    center_trace = traces[1]
    center_tensor_norm = float(np.linalg.norm(center_tensor)) + 1e-30
    center_trace_abs = float(np.abs(center_trace)) + 1e-30
    relative_tensor_delta_vs_lambda0 = [
        float(np.linalg.norm(tensor - center_tensor) / center_tensor_norm) for tensor in tensors
    ]
    relative_trace_delta_vs_lambda0 = [
        float(np.abs(trace - center_trace) / center_trace_abs) for trace in traces
    ]
    return {
        "wavelength_samples_nm": wavelength_samples_nm.tolist(),
        "relative_reference_tensor_delta_vs_lambda0": relative_tensor_delta_vs_lambda0,
        "relative_reference_trace_delta_vs_lambda0": relative_trace_delta_vs_lambda0,
        "max_relative_reference_tensor_delta": float(max(relative_tensor_delta_vs_lambda0)),
        "max_relative_reference_trace_delta": float(max(relative_trace_delta_vs_lambda0)),
        "note": "mu2_tensor_profile is currently frozen at lambda0; these edge-of-band diagnostics estimate how much the reference mu2 tensor would move if recomputed at the band edges.",
    }


def build_mu2_profile_wavelength_model(
    x_um: np.ndarray,
    source: SourceConfig,
    medium_material: Any,
    na: float,
    *,
    mu2_wavelength_model: str,
    obliquity_kind: str,
    n_pupil: int,
) -> tuple[dict, dict]:
    api = _solver_api()
    medium_fn = api.resolve_material_model(medium_material)
    reference_geometry = api.derive_na_geometry(na, medium_fn(source.lambda0_nm / 1000.0))
    frozen = compute_mu2_profile_from_pupil_weight(
        x_um,
        source.lambda0_nm,
        medium_material,
        reference_geometry["sin_theta_max"],
        obliquity_kind=obliquity_kind,
        n_pupil=n_pupil,
    )
    sensitivity = summarize_mu2_wavelength_freeze_sensitivity(
        lambda0_nm=source.lambda0_nm,
        fwhm_nm=source.fwhm_nm,
        medium_material=medium_material,
        na=na,
        obliquity_kind=obliquity_kind,
        n_pupil=n_pupil,
    )
    if mu2_wavelength_model == "frozen_at_lambda0":
        frozen["mu2_wavelength_samples_nm"] = [float(source.lambda0_nm)]
        frozen["mu2_wavelength_model_note"] = "Reference pupil weighting and coherent mu2 tensor profile are frozen at the source center wavelength lambda0."
        return frozen, sensitivity
    if mu2_wavelength_model == "endpoint_refit":
        half_band_nm = max(float(source.fwhm_nm) * 0.5, 0.0)
        endpoint_samples_nm = np.array(
            [
                max(float(source.lambda0_nm) - half_band_nm, 1e-9),
                float(source.lambda0_nm) + half_band_nm,
            ],
            dtype=float,
        )
        endpoint_diagnostics = []
        for wavelength_nm in endpoint_samples_nm:
            geometry = api.derive_na_geometry(na, medium_fn(wavelength_nm / 1000.0))
            endpoint_diagnostics.append(
                compute_mu2_profile_from_pupil_weight(
                    x_um,
                    wavelength_nm,
                    medium_material,
                    geometry["sin_theta_max"],
                    obliquity_kind=obliquity_kind,
                    n_pupil=n_pupil,
                )
            )
        endpoint_reference_tensor = 0.5 * (
            np.asarray(endpoint_diagnostics[0]["mu2_reference_tensor"], dtype=np.complex128)
            + np.asarray(endpoint_diagnostics[1]["mu2_reference_tensor"], dtype=np.complex128)
        )
        endpoint_tensor_profile = 0.5 * (
            np.asarray(endpoint_diagnostics[0]["mu2_tensor_profile"], dtype=np.complex128)
            + np.asarray(endpoint_diagnostics[1]["mu2_tensor_profile"], dtype=np.complex128)
        )
        endpoint_reference_field_profile = 0.5 * (
            np.asarray(endpoint_diagnostics[0]["reference_pupil_field_profile"], dtype=np.complex128)
            + np.asarray(endpoint_diagnostics[1]["reference_pupil_field_profile"], dtype=np.complex128)
        )
        endpoint_first_order_field_vector = 0.5 * (
            np.asarray(endpoint_diagnostics[0]["reference_first_order_field_vector"], dtype=np.complex128)
            + np.asarray(endpoint_diagnostics[1]["reference_first_order_field_vector"], dtype=np.complex128)
        )
        endpoint_second_order_field_tensor = 0.5 * (
            np.asarray(endpoint_diagnostics[0]["reference_second_order_field_tensor"], dtype=np.complex128)
            + np.asarray(endpoint_diagnostics[1]["reference_second_order_field_tensor"], dtype=np.complex128)
        )
        endpoint_refit = _build_mu2_profile_payload(
            mu2_reference_tensor=endpoint_reference_tensor,
            mu2_tensor_profile=endpoint_tensor_profile,
            denominator=endpoint_reference_field_profile,
            numerator_x=endpoint_first_order_field_vector[:, 0],
            numerator_y=endpoint_first_order_field_vector[:, 1],
            numerator_xx=endpoint_second_order_field_tensor[:, 0, 0],
            numerator_xy=endpoint_second_order_field_tensor[:, 0, 1],
            numerator_yy=endpoint_second_order_field_tensor[:, 1, 1],
        )
        endpoint_refit["mu2_wavelength_samples_nm"] = endpoint_samples_nm.tolist()
        endpoint_refit["mu2_wavelength_model_note"] = (
            "Cheap band-edge refit surrogate: recompute the reference pupil-weighted mu2 tensor profile at lambda0 - fwhm/2 and lambda0 + fwhm/2, then average those endpoint tensor profiles. This is not a full x,k-dependent closure."
        )
        return endpoint_refit, sensitivity
    raise ValueError(f"Unsupported mu2_wavelength_model: {mu2_wavelength_model}")


def solve_low_na_asymptotic_slice(
    source: SourceConfig,
    grid: GridConfig,
    solver: SolverConfig,
    *,
    strict_material_range: bool = False,
) -> dict:
    api = _solver_api()
    bridge = _load_bridge_module()
    second_order_model = getattr(solver, "second_order_model", "tensor_closure")
    mu2_wavelength_model = getattr(solver, "mu2_wavelength_model", "frozen_at_lambda0")
    lateral_shift_model = getattr(solver, "lateral_shift_model", "none")
    lateral_shift_coupling = getattr(solver, "lateral_shift_coupling", "envelope_only")
    lateral_shift_impl = getattr(solver, "lateral_shift_impl", "interp")
    requested_coefficient_map_model_id = getattr(
        solver,
        "coefficient_map_model_id",
        "identity_slice_projected_rendered_basis",
    )
    requested_coefficient_map_runtime_mode = getattr(
        solver,
        "coefficient_map_runtime_mode",
        "native_branch_assembly",
    )
    rendered_basis_shift_target = getattr(
        solver,
        "rendered_basis_shift_target",
        "baseline_envelope_ratio",
    )
    if requested_coefficient_map_runtime_mode not in {"native_branch_assembly", "rendered_basis_override"}:
        raise ValueError(
            f"Unsupported coefficient_map_runtime_mode: {requested_coefficient_map_runtime_mode!r}"
        )
    requested_coefficient_map_artifact_path = getattr(solver, "coefficient_map_artifact_path", None)
    if requested_coefficient_map_artifact_path is not None:
        requested_coefficient_map_artifact_path = str(Path(requested_coefficient_map_artifact_path))
    requested_second_order_model = second_order_model
    coefficient_path_bundle = None
    coefficient_map_runtime_status = "not_used"
    coefficient_map_runtime_contract_status = "native_branch_contract"
    coefficient_map_runtime_note = (
        "coefficient_map stage follows the native asymptotic branch assembly unless coefficient_map_runtime_mode="
        "'rendered_basis_override' is explicitly requested."
    )
    runtime_field_assembly_contract = requested_second_order_model
    runtime_field_assembly_contract_note = (
        "The runtime field is assembled using the native branch family selected by requested_second_order_model."
    )
    lambda_nm, source_power = api.source_spectrum_lambda(source.lambda0_nm, source.fwhm_nm, source.n_lambda)
    wavelengths_um = lambda_nm / 1000.0
    x_um = np.linspace(-0.5 * grid.x_span_um, 0.5 * grid.x_span_um, grid.n_x)
    opd_um = np.linspace(-grid.z_span_um, grid.z_span_um, grid.n_z)
    material_support = {
        "medium_material": api.validate_material_support(
            solver.medium_material,
            lambda_nm,
            strict_material_range=strict_material_range,
            role="medium_material",
        ),
    }
    if solver.ideal:
        B_k = np.ones_like(wavelengths_um, dtype=np.complex128)
        C2_k = np.zeros_like(wavelengths_um, dtype=np.complex128)
        C2_tensor_k = np.zeros((len(wavelengths_um), 2, 2), dtype=np.complex128)
        fit_diagnostics = {
            "theta_fit_max_rad": 0.0,
            "n_theta_fit": 0,
            "n_azimuth_fit": 0,
            "fit_strategy": str(getattr(solver, "effective_channel_fit_strategy", "split_even_odd")),
            "theta_samples_rad": np.zeros(1, dtype=float),
            "theta_quadrature_weights": np.ones(1, dtype=float),
            "azimuth_samples_rad": np.zeros(1, dtype=float),
            "local_alpha_samples_rad": np.zeros((1, 1), dtype=float),
            "local_beta_samples_rad": np.zeros((1, 1), dtype=float),
            "relative_fit_residual": np.zeros_like(wavelengths_um, dtype=float),
            "relative_fit_residual_model": "ideal_mode_constant",
            "relative_fit_residual_even": np.zeros_like(wavelengths_um, dtype=float),
            "relative_fit_residual_low_order": np.zeros_like(wavelengths_um, dtype=float),
            "per_azimuth_relative_fit_residual": np.zeros((len(wavelengths_um), 1), dtype=float),
            "per_azimuth_relative_fit_residual_even": np.zeros((len(wavelengths_um), 1), dtype=float),
            "per_azimuth_relative_fit_residual_low_order": np.zeros((len(wavelengths_um), 1), dtype=float),
            "per_azimuth_B_k": np.ones((len(wavelengths_um), 1), dtype=np.complex128),
            "shared_B_k_repeated_over_azimuth": np.ones((len(wavelengths_um), 1), dtype=np.complex128),
            "B_k_assumed_azimuth_invariant": True,
            "per_azimuth_B_k_semantics_note": (
                "per_azimuth_B_k is currently a repeated copy of the shared B_k intercept, not an independently fit "
                "azimuth-specific intercept. Keep using it only as a compatibility view of the azimuth-invariant leading term."
            ),
            "per_azimuth_C2_k": np.zeros((len(wavelengths_um), 1), dtype=np.complex128),
            "C2_trace_summary_k": np.zeros_like(wavelengths_um, dtype=np.complex128),
            "C2_tensor_k": C2_tensor_k,
            "C2_tensor_basis": "local_backscatter_angle_components_alpha_beta",
            "D1_tensor_basis": "local_backscatter_angle_components_alpha_beta",
            "C2_azimuth_weights_k": np.ones((len(wavelengths_um), 1), dtype=float),
            "C2_scalar_weighting_kind": "effective_channel_energy_weighted_over_theta",
            "C2_abs_std_over_azimuth": np.zeros_like(wavelengths_um, dtype=float),
            "fit_window_kind": "ideal_mode_constant",
            "theta_fit_fraction": 0.0,
            "theta_fit_cap_rad": 0.0,
            "theta_max_rad": 0.0,
        }
        tmatrix_used = False
        material_support["particle_material"] = {"role": "particle_material", "status": "skipped_ideal_mode"}
    else:
        material_support["particle_material"] = api.validate_material_support(
            solver.particle_material,
            lambda_nm,
            strict_material_range=strict_material_range,
            role="particle_material",
        )
        fit_config = resolve_effective_channel_fit_config(
            source=source,
            grid=grid,
            solver=solver,
        )
        estimate = estimate_effective_channel_B_C2(
            wavelengths_um,
            solver.particle_material,
            solver.medium_material,
            {
                "diameter_nm": solver.diameter_nm,
                "eps": solver.eps,
                "beta_deg": solver.beta_deg,
                "library_path": solver.library_path,
            },
            incident_mode=solver.incident_mode,
            detection_mode=solver.detection_mode,
            theta_fit_max_rad=fit_config["theta_fit_max_rad"],
            n_theta_fit=fit_config["n_theta_fit"],
            n_azimuth_fit=fit_config["n_azimuth_fit"],
            fit_strategy=fit_config["fit_strategy"],
        )
        B_k = estimate["B_k"]
        C2_k = estimate["C2_k"]
        fit_diagnostics = estimate["fit_diagnostics"]
        fit_diagnostics.update(
            {
                "theta_fit_fraction": fit_config["theta_fit_fraction"],
                "theta_fit_cap_rad": fit_config["theta_fit_cap_rad"],
                "theta_max_rad": fit_config["theta_max_rad"],
                "fit_window_kind": fit_config["fit_window_kind"],
                "fit_strategy": fit_config["fit_strategy"],
            }
        )
        C2_tensor_k = fit_diagnostics["C2_tensor_k"]
        tmatrix_used = True
    reference_geometry = api.derive_na_geometry(grid.na, api.resolve_material_model(solver.medium_material)(source.lambda0_nm / 1000.0))
    mu2_profile_diagnostics, mu2_wavelength_freeze_summary = build_mu2_profile_wavelength_model(
        x_um,
        source,
        solver.medium_material,
        grid.na,
        mu2_wavelength_model=mu2_wavelength_model,
        obliquity_kind="sqrt_cos",
        n_pupil=max(grid.n_bfp_dense, 49),
    )
    lateral_intensity = api.gaussian_lateral_intensity(x_um, source.lambda0_nm, grid.na)
    lateral_envelope = np.sqrt(lateral_intensity)
    mu2_reference = mu2_profile_diagnostics["mu2_reference_trace"]
    mu2_profile = mu2_profile_diagnostics["mu2_profile"]
    mu2_tensor_profile = mu2_profile_diagnostics["mu2_tensor_profile"]
    directional_field_profiles = build_directional_field_expansion_profiles(mu2_profile_diagnostics)
    slice_direction_local, slice_axis_label = resolve_lateral_slice_direction(solver)
    first_order_field_profiles = build_first_order_field_profile(mu2_profile_diagnostics, slice_direction_local)
    directional_second_order_slice_profile = _project_quadratic_tensor_profile_to_direction(
        directional_field_profiles["second_order_field_tensor"],
        slice_direction_local,
    )
    C2_slice_k = _project_quadratic_tensor_to_direction(C2_tensor_k, slice_direction_local)
    D1_vector_k = np.asarray(fit_diagnostics.get("D1_vector_k", np.zeros((len(wavelengths_um), 2), dtype=np.complex128)))
    D1_slice_k = _project_vector_to_direction(D1_vector_k, slice_direction_local)
    medium_fn = api.resolve_material_model(solver.medium_material)
    n_medium_k = np.array([float(np.real(medium_fn(lam_um))) for lam_um in wavelengths_um], dtype=float)
    k_medium_rad_per_um = 2.0 * np.pi * n_medium_k / wavelengths_um
    first_order_shift_validity = summarize_first_order_shift_validity(
        D1_slice_k=D1_slice_k,
        B_k=B_k,
        k_medium_rad_per_um=k_medium_rad_per_um,
    )
    if lateral_shift_model == "first_order":
        delta_x_k_um = estimate_first_order_lateral_shift_um(
            D1_slice_k=D1_slice_k,
            B_k=B_k,
            k_medium_rad_per_um=k_medium_rad_per_um,
        )
        max_shift = 0.25 * float(grid.x_span_um)
        delta_x_k_um = np.clip(delta_x_k_um, -max_shift, max_shift)
    elif lateral_shift_model == "none":
        delta_x_k_um = np.zeros(len(wavelengths_um), dtype=float)
    else:
        raise ValueError(f"Unsupported lateral_shift_model: {lateral_shift_model}")
    runtime_field_plan = _COEFF_BUNDLE.plan_runtime_field_assembly_contract(
        requested_second_order_model=second_order_model,
        coefficient_map_runtime_mode=requested_coefficient_map_runtime_mode,
        coefficient_map_model_id=requested_coefficient_map_model_id,
        coefficient_map_artifact_path=requested_coefficient_map_artifact_path,
        lateral_shift_model=lateral_shift_model,
        lateral_shift_coupling=lateral_shift_coupling,
        lateral_shift_impl=lateral_shift_impl,
        rendered_basis_shift_target=rendered_basis_shift_target,
    )
    reference_field_profile = np.asarray(directional_field_profiles["reference_field_profile"], dtype=np.complex128)
    first_order_field_profile = np.asarray(first_order_field_profiles["first_order_field_profile"], dtype=np.complex128)

    def _build_runtime_bundle(*, fitted_map, field_assembly_model_id: str):
        return _COEFF_BUNDLE.build_coefficient_path_bundle(
            {
                "lambda_nm": lambda_nm,
                "x_um": x_um,
                "B_k": B_k,
                "D1_vector_k": D1_vector_k,
                "D1_slice_k": D1_slice_k,
                "C2_tensor_k": C2_tensor_k,
                "C2_slice_k": C2_slice_k,
                "lateral_slice_axis": slice_axis_label,
                "C2_slice_local_direction": slice_direction_local,
                "reference_pupil_field_profile": reference_field_profile,
                "directional_first_order_field_profile": first_order_field_profile,
                "directional_second_order_slice_field_profile": directional_second_order_slice_profile,
                "directional_field_expansion_scale": directional_field_profiles["normalization_scale"],
                "second_order_model": field_assembly_model_id,
                "fit_diagnostics": fit_diagnostics,
            },
            coefficient_map_model_id=fitted_map.coefficient_map_model_id,
            fitted_coefficient_map=fitted_map,
        )

    runtime_fitted_map = None
    if runtime_field_plan.uses_rendered_basis:
        runtime_fitted_map = _COEFF_BUNDLE.resolve_runtime_fitted_coefficient_map(
            coefficient_map_model_id=requested_coefficient_map_model_id,
            artifact_path=requested_coefficient_map_artifact_path,
        )
        coefficient_path_bundle = _build_runtime_bundle(
            fitted_map=runtime_fitted_map,
            field_assembly_model_id=runtime_field_plan.runtime_field_assembly_contract,
        )
    reference_second_order_field_tensor = np.asarray(
        directional_field_profiles["second_order_field_tensor"],
        dtype=np.complex128,
    )
    directional_second_order_field = np.einsum(
        "kij,xij->kx",
        np.asarray(C2_tensor_k, dtype=np.complex128),
        reference_second_order_field_tensor,
    )
    second_order_tensor_correction = None
    lateral_envelope_k = None
    if runtime_field_plan.runtime_field_assembly_contract not in {
        "rendered_basis_override",
        "directional_field_expansion",
        "directional_field_expansion_first_order",
    }:
        second_order_tensor_correction = compute_second_order_correction(
            second_order_model=second_order_model,
            C2_tensor_k=C2_tensor_k,
            mu2_tensor_profile=mu2_tensor_profile,
            C2_slice_k=C2_slice_k,
            mu2_profile=mu2_profile,
        )
        lateral_envelope_k = build_shifted_lateral_envelope(
            x_um,
            lateral_envelope,
            delta_x_k_um,
            shift_impl=lateral_shift_impl,
            lambda0_nm=source.lambda0_nm,
            na=grid.na,
        )
        second_order_tensor_correction = shift_second_order_correction(
            x_um,
            second_order_tensor_correction,
            delta_x_k_um,
            lateral_shift_coupling=lateral_shift_coupling,
            shift_impl=lateral_shift_impl,
        )
    elif runtime_field_plan.runtime_field_assembly_contract == "rendered_basis_override" and lateral_shift_model == "first_order":
        if runtime_field_plan.rendered_basis_shift_target == "baseline_envelope_ratio":
            lateral_envelope_k = build_shifted_lateral_envelope(
                x_um,
                lateral_envelope,
                delta_x_k_um,
                shift_impl=lateral_shift_impl,
                lambda0_nm=source.lambda0_nm,
                na=grid.na,
            )
    assembly_payload = _COEFF_BUNDLE.assemble_runtime_lateral_field(
        runtime_field_plan,
        source_power=source_power,
        B_k=B_k,
        second_order_tensor_correction=second_order_tensor_correction,
        lateral_envelope_k=lateral_envelope_k,
        reference_field_profile=reference_field_profile,
        directional_second_order_field=directional_second_order_field,
        coefficient_path_bundle=coefficient_path_bundle,
        rendered_coefficients_raw=(
            coefficient_path_bundle.rendered_coefficient_state.rendered_coefficients_raw
            if coefficient_path_bundle is not None
            else None
        ),
        x_um=x_um,
        delta_x_k_um=delta_x_k_um,
    )
    spectral_cube = assembly_payload["spectral_cube"]
    coefficient_map_runtime_status = runtime_field_plan.coefficient_map_runtime_status
    coefficient_map_runtime_contract_status = runtime_field_plan.coefficient_map_runtime_contract_status
    coefficient_map_runtime_note = runtime_field_plan.coefficient_map_runtime_note
    runtime_field_assembly_contract = runtime_field_plan.runtime_field_assembly_contract
    runtime_field_assembly_contract_note = runtime_field_plan.runtime_field_assembly_contract_note
    field_xz = api.spectral_cube_to_xz(lambda_nm, spectral_cube, opd_um, solver.medium_material)
    raw_envelope_xz = np.abs(field_xz)
    raw_intensity_xz = raw_envelope_xz ** 2
    envelope_xz, envelope_xz_scale = api.normalize_intensity(raw_envelope_xz, return_scale=True)
    intensity_xz, intensity_xz_scale = api.normalize_intensity(raw_intensity_xz, return_scale=True)
    axial_views = api.build_full_na_axial_views(x_um, opd_um, raw_intensity_xz, raw_envelope_xz)
    scalar_na_threshold = 0.5
    requires_vector_diffraction = bool(grid.na > scalar_na_threshold)
    na_scalar_validity_status = "requires_vector_diffraction" if requires_vector_diffraction else "within_scalar_guard"
    na_scalar_validity_note = (
        "Current low_na_asymptotic scalar field-assembly contract is being used beyond the conservative NA<=0.5 guard and should be treated as a heuristic until a vector-diffraction baseline is available."
        if requires_vector_diffraction
        else "Current low_na_asymptotic scalar field-assembly contract remains within the conservative NA<=0.5 guard."
    )
    coefficient_map_model_id = (
        coefficient_path_bundle.rendered_coefficient_state.coefficient_map_model_id
        if coefficient_path_bundle is not None
        else None
    )
    projected_coefficients_raw = (
        coefficient_path_bundle.rendered_coefficient_state.projected_coefficients_raw
        if coefficient_path_bundle is not None
        else None
    )
    rendered_coefficients_raw = (
        coefficient_path_bundle.rendered_coefficient_state.rendered_coefficients_raw
        if coefficient_path_bundle is not None
        else None
    )
    rendered_coefficients_orthonormalized = (
        coefficient_path_bundle.comparison_state.rendered_coefficients_orthonormalized
        if coefficient_path_bundle is not None
        else None
    )
    coefficient_map_matrix = (
        coefficient_path_bundle.rendered_coefficient_state.coefficient_map_matrix
        if coefficient_path_bundle is not None
        else None
    )
    coefficient_map_note = (
        coefficient_path_bundle.rendered_coefficient_state.coefficient_map_note
        if coefficient_path_bundle is not None
        else None
    )
    coefficient_map_parameters = (
        coefficient_path_bundle.rendered_coefficient_state.coefficient_map_parameters
        if coefficient_path_bundle is not None
        else None
    )
    coefficient_map_matrix_condition_number = (
        float(np.linalg.cond(coefficient_map_matrix[0]))
        if coefficient_map_matrix is not None
        else None
    )
    coefficient_map_matrix_rank = (
        int(np.linalg.matrix_rank(coefficient_map_matrix[0]))
        if coefficient_map_matrix is not None
        else None
    )
    return {
        "mode": api.LOW_NA_ASYMPTOTIC_MODE,
        "display_mode_label": api.LOW_NA_ASYMPTOTIC_DISPLAY_LABEL,
        "lateral_slice_axis": slice_axis_label,
        "x_um": x_um,
        "opd_um": opd_um,
        "lambda_nm": lambda_nm,
        "sample_arm_spectral_cube": spectral_cube,
        "field_xz": field_xz,
        "raw_envelope_xz": raw_envelope_xz,
        "raw_intensity_xz": raw_intensity_xz,
        "envelope_xz": envelope_xz,
        "intensity_xz": intensity_xz,
        "centerline_raw_axial_envelope": axial_views["centerline_raw_axial_envelope"],
        "centerline_raw_axial_intensity": axial_views["centerline_raw_axial_intensity"],
        "peakline_raw_axial_envelope": axial_views["peakline_raw_axial_envelope"],
        "peakline_raw_axial_intensity": axial_views["peakline_raw_axial_intensity"],
        "centerline_axial_envelope": axial_views["centerline_axial_envelope"],
        "centerline_axial_intensity": axial_views["centerline_axial_intensity"],
        "peakline_axial_envelope": axial_views["peakline_axial_envelope"],
        "peakline_axial_intensity": axial_views["peakline_axial_intensity"],
        "centerline_axial_envelope_metrics": axial_views["centerline_axial_envelope_metrics"],
        "centerline_axial_intensity_metrics": axial_views["centerline_axial_intensity_metrics"],
        "peakline_axial_envelope_metrics": axial_views["peakline_axial_envelope_metrics"],
        "peakline_axial_intensity_metrics": axial_views["peakline_axial_intensity_metrics"],
        "axial_envelope_metrics": axial_views["peakline_axial_envelope_metrics"],
        "axial_intensity_metrics": axial_views["peakline_axial_intensity_metrics"],
        "global_peak_index": axial_views["global_peak_index"],
        "raw_peak_intensity": axial_views["raw_peak_intensity"],
        "raw_peak_envelope": axial_views["raw_peak_envelope"],
        "centerline_x_index": axial_views["centerline_x_index"],
        "centerline_x_um": axial_views["centerline_x_um"],
        "peakline_x_index": axial_views["peakline_x_index"],
        "peakline_x_um": axial_views["peakline_x_um"],
        "primary_axial_metrics_line": axial_views["primary_axial_metrics_line"],
        "primary_axial_metrics_note": "low_na_asymptotic reports primary axial metrics on the peakline to match the round6 solver schema.",
        "normalization": {
            **api.build_normalization_metadata(
                normalized_fields=[
                    "envelope_xz",
                    "intensity_xz",
                    "centerline_axial_envelope",
                    "centerline_axial_intensity",
                    "peakline_axial_envelope",
                    "peakline_axial_intensity",
                ],
                raw_fields=[
                    "field_xz",
                    "raw_envelope_xz",
                    "raw_intensity_xz",
                    "centerline_raw_axial_envelope",
                    "centerline_raw_axial_intensity",
                    "peakline_raw_axial_envelope",
                    "peakline_raw_axial_intensity",
                ],
                normalization_scope="per-array peak normalization",
                absolute_amplitude_supported=False,
            ),
            "scales": {
                "envelope_xz_peak": float(envelope_xz_scale),
                "intensity_xz_peak": float(intensity_xz_scale),
                "centerline_axial_envelope_peak": float(np.max(axial_views["centerline_raw_axial_envelope"])),
                "centerline_axial_intensity_peak": float(np.max(axial_views["centerline_raw_axial_intensity"])),
                "peakline_axial_envelope_peak": float(np.max(axial_views["peakline_raw_axial_envelope"])),
                "peakline_axial_intensity_peak": float(np.max(axial_views["peakline_raw_axial_intensity"])),
            },
        },
        "tmatrix_used": tmatrix_used,
        "tmatrix_library": api._TMATRIX_LIB_PATH if tmatrix_used else None,
        "B_k": B_k,
        "C2_k": C2_k,
        "C2_trace_summary_k": fit_diagnostics["C2_trace_summary_k"],
        "C2_scalar_weighting_kind": fit_diagnostics["C2_scalar_weighting_kind"],
        "C2_azimuth_weights_k": fit_diagnostics["C2_azimuth_weights_k"],
        "C2_tensor_k": C2_tensor_k,
        "C2_tensor_kind": "local_backscatter_quadratic_tensor",
        "C2_tensor_basis": fit_diagnostics["C2_tensor_basis"],
        "C2_tensor_components_k": {
            "xx": C2_tensor_k[:, 0, 0],
            "xy": C2_tensor_k[:, 0, 1],
            "yy": C2_tensor_k[:, 1, 1],
        },
        "C2_slice_k": C2_slice_k,
        "D1_vector_k": D1_vector_k,
        "D1_slice_k": D1_slice_k,
        "D1_slice_direction_label": slice_axis_label,
        "C2_slice_direction_label": slice_axis_label,
        "C2_slice_local_direction": slice_direction_local.tolist(),
        "C2_slice_projection_note": (
            f"For the current {slice_axis_label}-z slice, C2_slice_k is the quadratic-tensor projection onto the local {slice_axis_label}-directed backscatter tangent. The field model currently uses the full tensor closure Tr[C2_tensor_k * mu2_tensor_profile(x)]."
            if second_order_model == "tensor_closure"
            else (
                f"For the current {slice_axis_label}-z slice, C2_slice_k is the quadratic-tensor projection onto the local {slice_axis_label}-directed backscatter tangent and is actively used in the experimental slice_projected second-order model."
                if second_order_model == "slice_projected"
                else (
                    f"For the current {slice_axis_label}-z slice, C2_slice_k remains the directional scalar summary, but the experimental directional_field_expansion branch instead promotes the full reference-pupil denominator/numerator field components to the main second-order basis."
                    if second_order_model == "directional_field_expansion"
                    else f"For the current {slice_axis_label}-z slice, C2_slice_k is actively coupled to the projected second-order directional field basis R2_slice(x) in the experimental directional_field_expansion_first_order branch."
                )
            )
        ),
        "lateral_shift_model": lateral_shift_model,
        "lateral_shift_model_status": (
            "default_supported"
            if lateral_shift_model == "none"
            else "experimental_not_prioritized"
        ),
        "lateral_shift_delta_x_k_um": delta_x_k_um,
        "lateral_shift_delta_summary": summarize_lateral_shift_delta(delta_x_k_um),
        "first_order_validity_mask": first_order_shift_validity["first_order_validity_mask"],
        "first_order_invalid_fraction": first_order_shift_validity["first_order_invalid_fraction"],
        "first_order_finite_fraction": first_order_shift_validity["first_order_finite_fraction"],
        "first_order_B_k_small_fraction": first_order_shift_validity["first_order_B_k_small_fraction"],
        "first_order_B_k_small_threshold": first_order_shift_validity["first_order_B_k_small_threshold"],
        "first_order_raw_shift_um": first_order_shift_validity["first_order_raw_shift_um"],
        "first_order_shift_validity_summary": first_order_shift_validity,
        "lateral_shift_coupling": lateral_shift_coupling,
        "lateral_shift_impl": lateral_shift_impl,
        "lateral_shift_model_note": (
            "none keeps the shared Gaussian lateral envelope centered at x = 0 for every wavelength sample."
            if lateral_shift_model == "none"
            else f"first_order estimates a wavelength-dependent lateral shift delta_x_k from the slice-directed linear effective-channel term D1_slice_k along the {slice_axis_label} axis via Re[i D1_slice_k / (k_medium B_k)] and applies that shift to the shared lateral envelope."
        ),
        "lateral_shift_coupling_note": (
            "envelope_only shifts only the shared lateral envelope; the second-order correction remains evaluated on the original x grid."
            if lateral_shift_coupling == "envelope_only"
            else "shift_envelope_and_mu2 shifts both the shared lateral envelope and the second-order correction over x. For the current linear closures this is algebraically equivalent to shifting the underlying mu2-profile dependence before contraction."
        ),
        "lateral_shift_impl_note": (
            "interp shifts the shared lateral envelope with complex linear interpolation and zero padding outside the sampled x grid."
            if lateral_shift_impl == "interp"
            else (
                "interp_edge_hold shifts the shared lateral envelope with complex linear interpolation but holds the edge values outside the sampled x grid, exposing how much raw-amplitude sensitivity comes from zero-padding boundaries."
                if lateral_shift_impl == "interp_edge_hold"
                else "analytic_gaussian regenerates the Gaussian surrogate envelope at x - delta_x_k analytically, avoiding interpolation and edge clipping artifacts for the baseline lateral profile."
            )
        ),
        "requested_second_order_model": requested_second_order_model,
        "second_order_model": second_order_model,
        "runtime_field_assembly_contract": runtime_field_assembly_contract,
        "runtime_field_assembly_contract_note": runtime_field_assembly_contract_note,
        "runtime_field_assembly_supported_lateral_shift_models": list(
            runtime_field_plan.runtime_field_assembly_supported_lateral_shift_models
        ),
        "runtime_field_assembly_lateral_shift_constraint": runtime_field_plan.runtime_field_assembly_lateral_shift_constraint,
        "runtime_field_assembly_shift_target": runtime_field_plan.rendered_basis_shift_target,
        "runtime_field_assembly_shift_target_note": (
            "baseline_envelope_ratio applies the shift as a multiplicative ratio between the shifted Gaussian baseline envelope and the unshifted rendered-basis reference profile."
            if runtime_field_plan.rendered_basis_shift_target == "baseline_envelope_ratio"
            else (
                "rendered_field_interp applies the shift by directly interpolating the reconstructed rendered field over the lateral x grid."
                if runtime_field_plan.rendered_basis_shift_target == "rendered_field_interp"
                else "No rendered-basis-specific shift target is active for the current runtime field-assembly contract."
            )
        ),
        "coefficient_map_requested_model_id": requested_coefficient_map_model_id,
        "coefficient_map_runtime_mode": requested_coefficient_map_runtime_mode,
        "coefficient_map_model_id": coefficient_map_model_id,
        "coefficient_map_artifact_path": requested_coefficient_map_artifact_path,
        "rendered_basis_shift_target": rendered_basis_shift_target,
        "coefficient_map_runtime_status": coefficient_map_runtime_status,
        "coefficient_map_runtime_contract_status": coefficient_map_runtime_contract_status,
        "coefficient_map_runtime_note": coefficient_map_runtime_note,
        "coefficient_map_note": coefficient_map_note,
        "coefficient_map_parameters": coefficient_map_parameters,
        "coefficient_map_matrix": coefficient_map_matrix,
        "coefficient_map_matrix_condition_number": coefficient_map_matrix_condition_number,
        "coefficient_map_matrix_rank": coefficient_map_matrix_rank,
        "projected_coefficients_raw": projected_coefficients_raw,
        "rendered_coefficients_raw": rendered_coefficients_raw,
        "rendered_coefficients_orthonormalized": rendered_coefficients_orthonormalized,
        "na_scalar_validity_status": na_scalar_validity_status,
        "na_scalar_validity_note": na_scalar_validity_note,
        "requires_vector_diffraction": requires_vector_diffraction,
        "na_scalar_validity_threshold": scalar_na_threshold,
        "second_order_model_note": (
            "tensor_closure uses Tr[C2_tensor_k * mu2_tensor_profile(x)] as the default asymptotic second-order correction."
            if second_order_model == "tensor_closure"
            else (
                f"slice_projected uses C2_slice_k * mu2_profile(x) as an experimental {slice_axis_label}-z slice-matched surrogate for the second-order correction."
                if second_order_model == "slice_projected"
                else (
                    "directional_field_expansion uses the reference pupil denominator and second-order numerator tensor directly as the x-dependent field basis B_k * Psi0(x) + C2_tensor_k : Psi2(x), instead of a Gaussian envelope multiplied by a scalar correction ratio."
                    if second_order_model == "directional_field_expansion"
                    else "directional_field_expansion_first_order adds an explicit odd first-order directional field basis so the experimental field model becomes B_k * R0(x) + D1_slice_k * R1(x) + C2_slice_k * R2_slice(x)."
                )
            )
        ),
        "mu2": complex(mu2_reference),
        "mu2_profile": mu2_profile,
        "mu2_profile_real": np.real(mu2_profile),
        "mu2_profile_imag": np.imag(mu2_profile),
        "mu2_tensor_reference": mu2_profile_diagnostics["mu2_reference_tensor"],
        "mu2_tensor_profile": mu2_tensor_profile,
        "mu2_tensor_profile_xx": mu2_tensor_profile[:, 0, 0],
        "mu2_tensor_profile_xy": mu2_tensor_profile[:, 0, 1],
        "mu2_tensor_profile_yy": mu2_tensor_profile[:, 1, 1],
        "reference_pupil_field_profile": mu2_profile_diagnostics["reference_pupil_field_profile"],
        "reference_first_order_field_vector": mu2_profile_diagnostics["reference_first_order_field_vector"],
        "reference_second_order_field_tensor": mu2_profile_diagnostics["reference_second_order_field_tensor"],
        "directional_field_expansion_scale": directional_field_profiles["normalization_scale"],
        "directional_field_expansion_note": directional_field_profiles["note"],
        "directional_first_order_field_profile": first_order_field_profiles["first_order_field_profile"],
        "directional_first_order_field_note": first_order_field_profiles["note"],
        "directional_second_order_slice_field_profile": directional_second_order_slice_profile,
        "mu2_profile_weight_denominator_abs": mu2_profile_diagnostics["profile_weight_denominator_abs"],
        "mu2_profile_phase_span_rad": mu2_profile_diagnostics["mu2_profile_phase_span_rad"],
        "mu2_profile_real_imag_ratio": mu2_profile_diagnostics["mu2_profile_real_imag_ratio"],
        "mu2_profile_valid_fraction": mu2_profile_diagnostics["mu2_profile_valid_fraction"],
        "mu2_profile_complexity_summary": mu2_profile_diagnostics["mu2_profile_complexity_summary"],
        "mu2_profile_kind": "coherent_numeric_second_moment_tensor_trace",
        "mu2_profile_semantics_note": "mu2_profile is the trace summary of a complex-valued coherent effective 2x2 second-order angular-moment tensor derived from pupil-weighted field superposition, not a purely geometric positive-definite second moment.",
        "mu2_profile_complexity_note": "Interpret mu2_profile together with mu2_tensor_profile and the complexity diagnostics; the trace is a compatibility summary and should not be read as a standalone geometric angular variance.",
        "mu2_reference_wavelength_nm": float(source.lambda0_nm),
        "mu2_wavelength_model": mu2_wavelength_model,
        "mu2_wavelength_model_status": (
            "default_supported"
            if mu2_wavelength_model == "frozen_at_lambda0"
            else "experimental_not_prioritized"
        ),
        "mu2_wavelength_samples_nm": mu2_profile_diagnostics["mu2_wavelength_samples_nm"],
        "mu2_wavelength_model_note": mu2_profile_diagnostics["mu2_wavelength_model_note"],
        "mu2_dispersion_sensitivity": mu2_wavelength_freeze_summary,
        "channel_projection_kind": "local_jones_projection",
        "incident_mode": solver.incident_mode,
        "detection_mode": solver.detection_mode,
        "supported_polarization_modes": list(getattr(bridge, "SUPPORTED_POLARIZATION_MODES", SUPPORTED_POLARIZATION_MODES)),
        "channel_definition": "effective_jones_projected_channel",
        "channel_alignment_note": "low_na_asymptotic and vector_pupil_overlap_bridge now share the same effective channel definition f_eff = a_rx^H S a_tx.",
        "polarization_model_kind": "lab_to_local_jones_surrogate",
        "polarization_projection_level": "lab_to_local_jones_surrogate",
        "projection_semantics_note": "low_na_asymptotic extracts B_k and C2_k from the same local Jones-projected effective channel used by vector_pupil_overlap_bridge.",
        "c2_estimation_method": "local quadratic tensor fit around backscatter direction on the Jones-projected effective channel",
        "fit_diagnostics": fit_diagnostics,
        "effective_channel_fit_window_kind": fit_diagnostics["fit_window_kind"],
        "effective_channel_theta_fit_max_rad": float(fit_diagnostics["theta_fit_max_rad"]),
        "effective_channel_theta_max_rad": float(fit_diagnostics["theta_max_rad"]),
        "effective_channel_theta_fit_fraction": float(fit_diagnostics["theta_fit_fraction"]),
        "effective_channel_theta_fit_cap_rad": float(fit_diagnostics["theta_fit_cap_rad"]),
        "effective_channel_n_theta_fit": int(fit_diagnostics["n_theta_fit"]),
        "effective_channel_n_azimuth_fit": int(fit_diagnostics["n_azimuth_fit"]),
        "effective_channel_fit_strategy": fit_diagnostics["fit_strategy"],
        "effective_channel_relative_fit_residual": fit_diagnostics["relative_fit_residual"],
        "effective_channel_relative_fit_residual_model": fit_diagnostics["relative_fit_residual_model"],
        "effective_channel_relative_fit_residual_even": fit_diagnostics["relative_fit_residual_even"],
        "effective_channel_relative_fit_residual_low_order": fit_diagnostics["relative_fit_residual_low_order"],
        "per_azimuth_B_k": fit_diagnostics["per_azimuth_B_k"],
        "per_azimuth_C2_k": fit_diagnostics["per_azimuth_C2_k"],
        "per_azimuth_relative_fit_residual": fit_diagnostics["per_azimuth_relative_fit_residual"],
        "per_azimuth_relative_fit_residual_even": fit_diagnostics["per_azimuth_relative_fit_residual_even"],
        "per_azimuth_relative_fit_residual_low_order": fit_diagnostics["per_azimuth_relative_fit_residual_low_order"],
        "C2_abs_std_over_azimuth": fit_diagnostics["C2_abs_std_over_azimuth"],
        "C2_azimuth_variation_note": "C2_k is reported as an effective-channel-energy-weighted scalar summary of a fitted 2x2 second-order angular tensor; azimuthal variation is recovered by evaluating that tensor along sampled azimuths and summarized by C2_abs_std_over_azimuth.",
        "C2_azimuth_variation_summary": {
            "n_azimuth_fit": int(fit_diagnostics["n_azimuth_fit"]),
            "max_C2_abs_std_over_azimuth": float(np.max(np.asarray(fit_diagnostics["C2_abs_std_over_azimuth"], dtype=float))),
            "mean_C2_abs_std_over_azimuth": float(np.mean(np.asarray(fit_diagnostics["C2_abs_std_over_azimuth"], dtype=float))),
        },
        "C2_scalar_validity_indicator": "Use C2_tensor_k when anisotropy matters; scalar C2_k is only an effective-channel-energy-weighted summary and C2_abs_std_over_azimuth quantifies how much directional curvature survives.",
        "mu2_spatial_model": "coherent second angular moment tensor computed numerically from the reference pupil weight as a function of lateral position",
        "mu2_spatial_model_note": "mu2_tensor_profile is derived from the reference pupil weighting with obliquity and lateral phase, and the field model contracts that tensor against C2_tensor_k instead of using only a scalar mu2 times scalar C2.",
        "second_order_closure_note": (
            "The second-order correction now uses Tr[C2_tensor_k * mu2_tensor_profile(x)] while keeping scalar C2_k and mu2_profile as compatibility summaries."
            if second_order_model == "tensor_closure"
            else (
                "The second-order correction now uses the experimental slice-projected surrogate C2_slice_k * mu2_profile(x) while retaining C2_tensor_k and mu2_tensor_profile as the higher-fidelity tensor closure reference."
                if second_order_model == "slice_projected"
                else (
                    "The second-order correction now uses the experimental directional field expansion B_k * Psi0(x) + C2_tensor_k : Psi2(x), where Psi0 and Psi2 come directly from the reference pupil denominator/numerator field components instead of from a scalar correction ratio on top of the Gaussian surrogate envelope."
                    if second_order_model == "directional_field_expansion"
                    else f"The experimental directional_field_expansion_first_order branch adds an odd first-order field basis R1(x) from the slice-projected reference first-order numerator vector, so the {slice_axis_label}-dependent field expansion explicitly carries D1_slice_k alongside C2_slice_k * R2_slice(x)."
                )
            )
        ),
        "spectral_model_note": api.SPECTRAL_MODEL_NOTE,
        "depth_axis_note": api.OPD_AXIS_NOTE,
        "low_na_asymptotic_note": LOW_NA_ASYMPTOTIC_NOTE,
        "material_range_notes": {
            "particle_material": api.MATERIAL_RANGE_NOTES.get(str(solver.particle_material)),
            "medium_material": api.MATERIAL_RANGE_NOTES.get(str(solver.medium_material)),
        },
        "material_support": material_support,
        **api.build_base_result_metadata(
            approximation_label=LOW_NA_ASYMPTOTIC_APPROXIMATION_LABEL,
            paper_safe=strict_material_range,
        ),
    }
