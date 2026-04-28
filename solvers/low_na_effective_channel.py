from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:
    from oct_nonspherical_psf_solver import GridConfig, SolverConfig, SourceConfig


def _solver_api():
    module = sys.modules.get("oct_nonspherical_psf_solver")
    if module is not None and hasattr(module, "solve_oct_particle_response"):
        return module
    main_module = sys.modules.get("__main__")
    if main_module is not None and hasattr(main_module, "solve_oct_particle_response"):
        return main_module
    script_dir = Path(__file__).resolve().parent.parent / "scripts"
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


def _cart_to_angles(direction: np.ndarray) -> tuple[float, float]:
    unit = np.asarray(direction, dtype=float)
    unit /= np.linalg.norm(unit)
    theta = np.rad2deg(np.arccos(np.clip(unit[2], -1.0, 1.0)))
    phi = np.rad2deg(np.arctan2(unit[1], unit[0])) % 360.0
    return float(theta), float(phi)


def _load_bridge_module():
    return _solver_api().load_round6_extension("10_vector_pupil_overlap_bridge.py", "round6_vector_pupil_overlap_bridge")


def estimate_effective_channel_B_C2(
    wavelengths_um: np.ndarray,
    material_particle: Any,
    material_medium: Any,
    particle_geometry: Any,
    *,
    incident_mode: str,
    detection_mode: str,
    theta_fit_max_rad: float,
    n_theta_fit: int,
    n_azimuth_fit: int = 4,
    fit_strategy: str = "split_even_odd",
) -> dict:
    api = _solver_api()
    bridge = _load_bridge_module()
    library_path = particle_geometry.get("library_path")
    backscatter, tangent_u, tangent_v = api._backscatter_basis()
    theta_samples = np.linspace(0.0, theta_fit_max_rad, n_theta_fit)
    azimuth_samples = np.linspace(0.0, 2.0 * np.pi, n_azimuth_fit, endpoint=False)
    local_alpha = np.zeros((n_theta_fit, n_azimuth_fit), dtype=float)
    local_beta = np.zeros((n_theta_fit, n_azimuth_fit), dtype=float)
    theta_quadrature = np.asarray(api.trapezoid_weights(theta_samples), dtype=float)
    B_k = np.zeros(len(wavelengths_um), dtype=np.complex128)
    C2_k = np.zeros(len(wavelengths_um), dtype=np.complex128)
    C2_trace_summary_k = np.zeros(len(wavelengths_um), dtype=np.complex128)
    C2_tensor_k = np.zeros((len(wavelengths_um), 2, 2), dtype=np.complex128)
    D1_vector_k = np.zeros((len(wavelengths_um), 2), dtype=np.complex128)
    C2_azimuth_weights_k = np.zeros((len(wavelengths_um), n_azimuth_fit), dtype=float)
    residuals = np.zeros(len(wavelengths_um), dtype=float)
    residuals_even = np.zeros(len(wavelengths_um), dtype=float)
    residuals_low_order = np.zeros(len(wavelengths_um), dtype=float)
    per_azimuth_residuals = np.zeros((len(wavelengths_um), n_azimuth_fit), dtype=float)
    per_azimuth_residuals_even = np.zeros((len(wavelengths_um), n_azimuth_fit), dtype=float)
    per_azimuth_residuals_low_order = np.zeros((len(wavelengths_um), n_azimuth_fit), dtype=float)
    per_azimuth_B = np.zeros((len(wavelengths_um), n_azimuth_fit), dtype=np.complex128)
    per_azimuth_C2 = np.zeros((len(wavelengths_um), n_azimuth_fit), dtype=np.complex128)
    theta_deg_grid = np.zeros((n_theta_fit, n_azimuth_fit), dtype=float)
    phi_deg_grid = np.zeros((n_theta_fit, n_azimuth_fit), dtype=float)
    for azimuth_idx, azimuth in enumerate(azimuth_samples):
        tangent = np.cos(azimuth) * tangent_u + np.sin(azimuth) * tangent_v
        for theta_idx, vartheta in enumerate(theta_samples):
            direction = backscatter * np.cos(vartheta) + tangent * np.sin(vartheta)
            theta_deg_grid[theta_idx, azimuth_idx], phi_deg_grid[theta_idx, azimuth_idx] = _cart_to_angles(direction)
            local_alpha[theta_idx, azimuth_idx] = vartheta * np.cos(azimuth)
            local_beta[theta_idx, azimuth_idx] = vartheta * np.sin(azimuth)
    tensor_design = np.stack(
        [
            np.ones(local_alpha.size, dtype=float),
            (local_alpha**2).reshape(-1),
            (2.0 * local_alpha * local_beta).reshape(-1),
            (local_beta**2).reshape(-1),
        ],
        axis=1,
    )
    low_order_design = np.stack(
        [
            np.ones(local_alpha.size, dtype=float),
            local_alpha.reshape(-1),
            local_beta.reshape(-1),
            (local_alpha**2).reshape(-1),
            (2.0 * local_alpha * local_beta).reshape(-1),
            (local_beta**2).reshape(-1),
        ],
        axis=1,
    )
    effective_channel = bridge.sample_effective_channel(
        wavelengths_um=np.asarray(wavelengths_um, dtype=float),
        theta_deg=theta_deg_grid,
        phi_deg=phi_deg_grid,
        particle_geometry=particle_geometry,
        particle_material=material_particle,
        medium_material=material_medium,
        incident_mode=incident_mode,
        detection_mode=detection_mode,
        library_path=library_path,
    )
    fit_residual_model = "even" if fit_strategy == "split_even_odd" else "low_order"
    for idx in range(len(wavelengths_um)):
        amplitudes = effective_channel[idx]
        if fit_strategy == "split_even_odd":
            coeffs, _, _, _ = np.linalg.lstsq(tensor_design, amplitudes.reshape(-1), rcond=None)
            low_order_coeffs, _, _, _ = np.linalg.lstsq(low_order_design, amplitudes.reshape(-1), rcond=None)
            B_k[idx] = coeffs[0]
            C2_tensor_k[idx, 0, 0] = coeffs[1]
            C2_tensor_k[idx, 0, 1] = coeffs[2]
            C2_tensor_k[idx, 1, 0] = coeffs[2]
            C2_tensor_k[idx, 1, 1] = coeffs[3]
            D1_vector_k[idx, 0] = low_order_coeffs[1]
            D1_vector_k[idx, 1] = low_order_coeffs[2]
            C2_trace_summary_k[idx] = 0.5 * (coeffs[1] + coeffs[3])
            modeled_even_flat = tensor_design @ coeffs
            modeled_low_order_flat = low_order_design @ np.array(
                [coeffs[0], low_order_coeffs[1], low_order_coeffs[2], coeffs[1], coeffs[2], coeffs[3]],
                dtype=np.complex128,
            )
        elif fit_strategy == "joint_low_order":
            low_order_coeffs, _, _, _ = np.linalg.lstsq(low_order_design, amplitudes.reshape(-1), rcond=None)
            B_k[idx] = low_order_coeffs[0]
            D1_vector_k[idx, 0] = low_order_coeffs[1]
            D1_vector_k[idx, 1] = low_order_coeffs[2]
            C2_tensor_k[idx, 0, 0] = low_order_coeffs[3]
            C2_tensor_k[idx, 0, 1] = low_order_coeffs[4]
            C2_tensor_k[idx, 1, 0] = low_order_coeffs[4]
            C2_tensor_k[idx, 1, 1] = low_order_coeffs[5]
            C2_trace_summary_k[idx] = 0.5 * (low_order_coeffs[3] + low_order_coeffs[5])
            modeled_even_flat = tensor_design @ np.array(
                [low_order_coeffs[0], low_order_coeffs[3], low_order_coeffs[4], low_order_coeffs[5]],
                dtype=np.complex128,
            )
            modeled_low_order_flat = low_order_design @ low_order_coeffs
        else:
            raise ValueError(f"Unsupported effective-channel fit strategy: {fit_strategy}")
        modeled_even = modeled_even_flat.reshape(n_theta_fit, n_azimuth_fit)
        modeled_low_order = modeled_low_order_flat.reshape(n_theta_fit, n_azimuth_fit)
        residuals_even[idx] = float(np.linalg.norm(modeled_even - amplitudes) / (np.linalg.norm(amplitudes) + 1e-30))
        residuals_low_order[idx] = float(np.linalg.norm(modeled_low_order - amplitudes) / (np.linalg.norm(amplitudes) + 1e-30))
        residuals[idx] = residuals_even[idx] if fit_residual_model == "even" else residuals_low_order[idx]
        for azimuth_idx, azimuth in enumerate(azimuth_samples):
            cos_azimuth = np.cos(azimuth)
            sin_azimuth = np.sin(azimuth)
            per_azimuth_B[idx, azimuth_idx] = B_k[idx]
            per_azimuth_C2[idx, azimuth_idx] = (
                C2_tensor_k[idx, 0, 0] * cos_azimuth**2
                + 2.0 * C2_tensor_k[idx, 0, 1] * cos_azimuth * sin_azimuth
                + C2_tensor_k[idx, 1, 1] * sin_azimuth**2
            )
            d1_azimuth = D1_vector_k[idx, 0] * cos_azimuth + D1_vector_k[idx, 1] * sin_azimuth
            modeled_azimuth_even = B_k[idx] + per_azimuth_C2[idx, azimuth_idx] * theta_samples**2
            modeled_azimuth_low_order = modeled_azimuth_even + d1_azimuth * theta_samples
            per_azimuth_residuals_even[idx, azimuth_idx] = float(
                np.linalg.norm(modeled_azimuth_even - amplitudes[:, azimuth_idx]) / (np.linalg.norm(amplitudes[:, azimuth_idx]) + 1e-30)
            )
            per_azimuth_residuals_low_order[idx, azimuth_idx] = float(
                np.linalg.norm(modeled_azimuth_low_order - amplitudes[:, azimuth_idx])
                / (np.linalg.norm(amplitudes[:, azimuth_idx]) + 1e-30)
            )
            per_azimuth_residuals[idx, azimuth_idx] = (
                per_azimuth_residuals_even[idx, azimuth_idx]
                if fit_residual_model == "even"
                else per_azimuth_residuals_low_order[idx, azimuth_idx]
            )
        azimuth_energy = np.sum(theta_quadrature[:, None] * np.abs(amplitudes) ** 2, axis=0)
        energy_sum = float(np.sum(azimuth_energy))
        if energy_sum > 1e-30:
            C2_azimuth_weights_k[idx] = azimuth_energy / energy_sum
        else:
            C2_azimuth_weights_k[idx] = np.full(n_azimuth_fit, 1.0 / max(n_azimuth_fit, 1), dtype=float)
        C2_k[idx] = np.sum(C2_azimuth_weights_k[idx] * per_azimuth_C2[idx])
    return {
        "B_k": B_k,
        "C2_k": C2_k,
        "fit_diagnostics": {
            "theta_fit_max_rad": float(theta_fit_max_rad),
            "n_theta_fit": int(n_theta_fit),
            "n_azimuth_fit": int(n_azimuth_fit),
            "fit_strategy": fit_strategy,
            "theta_samples_rad": theta_samples,
            "theta_quadrature_weights": theta_quadrature,
            "azimuth_samples_rad": azimuth_samples,
            "local_alpha_samples_rad": local_alpha,
            "local_beta_samples_rad": local_beta,
            "relative_fit_residual": residuals,
            "relative_fit_residual_model": fit_residual_model,
            "relative_fit_residual_even": residuals_even,
            "relative_fit_residual_low_order": residuals_low_order,
            "per_azimuth_relative_fit_residual": per_azimuth_residuals,
            "per_azimuth_relative_fit_residual_even": per_azimuth_residuals_even,
            "per_azimuth_relative_fit_residual_low_order": per_azimuth_residuals_low_order,
            "per_azimuth_B_k": per_azimuth_B,
            "shared_B_k_repeated_over_azimuth": per_azimuth_B,
            "B_k_assumed_azimuth_invariant": True,
            "per_azimuth_B_k_semantics_note": (
                "per_azimuth_B_k is currently a repeated copy of the shared B_k intercept, not an independently fit "
                "azimuth-specific intercept. Keep using it only as a compatibility view of the azimuth-invariant leading term."
            ),
            "per_azimuth_C2_k": per_azimuth_C2,
            "C2_trace_summary_k": C2_trace_summary_k,
            "C2_tensor_k": C2_tensor_k,
            "C2_tensor_basis": "local_backscatter_angle_components_alpha_beta",
            "D1_vector_k": D1_vector_k,
            "D1_tensor_basis": "local_backscatter_angle_components_alpha_beta",
            "C2_azimuth_weights_k": C2_azimuth_weights_k,
            "C2_scalar_weighting_kind": "effective_channel_energy_weighted_over_theta",
            "C2_abs_std_over_azimuth": np.std(np.abs(per_azimuth_C2), axis=1),
            "fit_window_kind": "explicit_parameters",
        },
    }


def project_quadratic_tensor_to_direction(tensor_k: np.ndarray, direction_local: np.ndarray) -> np.ndarray:
    direction = np.asarray(direction_local, dtype=float)
    norm = np.linalg.norm(direction)
    if norm <= 1e-30:
        raise ValueError("direction_local must be non-zero.")
    unit = direction / norm
    return np.einsum("i,kij,j->k", unit, np.asarray(tensor_k, dtype=np.complex128), unit)


def project_vector_to_direction(vector_k: np.ndarray, direction_local: np.ndarray) -> np.ndarray:
    direction = np.asarray(direction_local, dtype=float)
    norm = np.linalg.norm(direction)
    if norm <= 1e-30:
        raise ValueError("direction_local must be non-zero.")
    unit = direction / norm
    return np.einsum("ki,i->k", np.asarray(vector_k, dtype=np.complex128), unit)


def project_vector_profile_to_direction(vector_profile_xi: np.ndarray, direction_local: np.ndarray) -> np.ndarray:
    direction = np.asarray(direction_local, dtype=float)
    norm = np.linalg.norm(direction)
    if norm <= 1e-30:
        raise ValueError("direction_local must be non-zero.")
    unit = direction / norm
    return np.einsum("xi,i->x", np.asarray(vector_profile_xi, dtype=np.complex128), unit)


def project_quadratic_tensor_profile_to_direction(tensor_profile_xij: np.ndarray, direction_local: np.ndarray) -> np.ndarray:
    direction = np.asarray(direction_local, dtype=float)
    norm = np.linalg.norm(direction)
    if norm <= 1e-30:
        raise ValueError("direction_local must be non-zero.")
    unit = direction / norm
    return np.einsum("i,xij,j->x", unit, np.asarray(tensor_profile_xij, dtype=np.complex128), unit)


def resolve_lateral_slice_direction(solver: "SolverConfig") -> tuple[np.ndarray, str]:
    axis = str(getattr(solver, "lateral_slice_axis", "x")).strip().lower()
    if axis == "x":
        return np.array([1.0, 0.0], dtype=float), "x"
    if axis == "y":
        return np.array([0.0, 1.0], dtype=float), "y"
    raise ValueError(f"Unsupported lateral_slice_axis: {solver.lateral_slice_axis}")


def resolve_effective_channel_fit_config(
    *,
    source: "SourceConfig",
    grid: "GridConfig",
    solver: "SolverConfig",
) -> dict:
    api = _solver_api()
    theta_max_rad = float(
        api.derive_na_geometry(
            grid.na,
            api.resolve_material_model(solver.medium_material)(source.lambda0_nm / 1000.0),
        )["theta_max_rad"]
    )
    theta_fit_max_rad = getattr(solver, "effective_channel_theta_fit_max_rad", None)
    if theta_fit_max_rad is None:
        theta_fit_fraction = float(getattr(solver, "effective_channel_theta_fit_fraction", 0.35))
        theta_fit_cap_rad = float(getattr(solver, "effective_channel_theta_fit_cap_rad", 0.08))
        theta_fit_max_rad = min(theta_fit_fraction * theta_max_rad, theta_fit_cap_rad)
        fit_window_kind = "heuristic_fraction_cap"
    else:
        theta_fit_max_rad = float(theta_fit_max_rad)
        fit_window_kind = "explicit_override"
    return {
        "theta_max_rad": theta_max_rad,
        "theta_fit_max_rad": float(theta_fit_max_rad),
        "n_theta_fit": int(getattr(solver, "effective_channel_n_theta_fit", 9)),
        "n_azimuth_fit": int(getattr(solver, "effective_channel_n_azimuth_fit", 4)),
        "fit_strategy": str(getattr(solver, "effective_channel_fit_strategy", "split_even_odd")),
        "theta_fit_fraction": float(getattr(solver, "effective_channel_theta_fit_fraction", 0.35)),
        "theta_fit_cap_rad": float(getattr(solver, "effective_channel_theta_fit_cap_rad", 0.08)),
        "fit_window_kind": fit_window_kind,
    }


def compute_second_order_correction(
    *,
    second_order_model: str,
    C2_tensor_k: np.ndarray,
    mu2_tensor_profile: np.ndarray,
    C2_slice_k: np.ndarray,
    mu2_profile: np.ndarray,
) -> np.ndarray:
    if second_order_model == "tensor_closure":
        return np.einsum("kij,xij->kx", np.asarray(C2_tensor_k, dtype=np.complex128), np.asarray(mu2_tensor_profile, dtype=np.complex128))
    if second_order_model == "slice_projected":
        return np.asarray(C2_slice_k, dtype=np.complex128)[:, None] * np.asarray(mu2_profile, dtype=np.complex128)[None, :]
    raise ValueError(f"Unsupported second_order_model: {second_order_model}")


def build_directional_field_expansion_profiles(mu2_profile_diagnostics: dict) -> dict:
    reference_field_profile = np.asarray(mu2_profile_diagnostics["reference_pupil_field_profile"], dtype=np.complex128)
    second_order_field_tensor = np.asarray(mu2_profile_diagnostics["reference_second_order_field_tensor"], dtype=np.complex128)
    scale = float(np.max(np.abs(reference_field_profile))) + 1e-30
    return {
        "reference_field_profile": reference_field_profile / scale,
        "second_order_field_tensor": second_order_field_tensor / scale,
        "normalization_scale": float(scale),
        "note": (
            "directional_field_expansion uses the reference pupil field denominator and second-order numerator tensor "
            "directly as x-dependent basis functions, instead of applying a scalar correction on top of the Gaussian surrogate envelope."
        ),
    }


def build_first_order_field_profile(mu2_profile_diagnostics: dict, direction_local: np.ndarray) -> dict:
    reference_field_profile = np.asarray(mu2_profile_diagnostics["reference_pupil_field_profile"], dtype=np.complex128)
    first_order_field_vector = np.asarray(mu2_profile_diagnostics["reference_first_order_field_vector"], dtype=np.complex128)
    scale = float(np.max(np.abs(reference_field_profile))) + 1e-30
    direction = np.asarray(direction_local, dtype=float)
    norm = np.linalg.norm(direction)
    if norm <= 1e-30:
        raise ValueError("direction_local must be non-zero.")
    unit = direction / norm
    projected_profile = project_vector_profile_to_direction(first_order_field_vector, unit)
    return {
        "first_order_field_profile": projected_profile / scale,
        "normalization_scale": float(scale),
        "direction_local": unit.tolist(),
        "note": (
            "directional_field_expansion_first_order uses the reference pupil first-order numerator vector as an odd x-dependent "
            "basis function, projected onto the current slice direction and normalized by the shared denominator-field scale."
        ),
    }
