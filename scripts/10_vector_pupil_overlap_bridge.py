from __future__ import annotations

import importlib
import sys
from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:
    from oct_nonspherical_psf_solver import GridConfig, SolverConfig, SourceConfig


SUPPORTED_POLARIZATION_MODES = ("linear_x", "linear_y", "co_pol", "cross_pol")


def _solver_api():
    module = sys.modules.get("oct_nonspherical_psf_solver")
    if module is not None and hasattr(module, "solve_oct_particle_response"):
        return module
    main_module = sys.modules.get("__main__")
    if main_module is not None and hasattr(main_module, "solve_oct_particle_response"):
        return main_module
    return importlib.import_module("oct_nonspherical_psf_solver")


def _resolve_mode_label(mode: str, reference_mode: str | None = None) -> str:
    normalized = (mode or "linear_x").lower()
    if normalized == "co_pol":
        return (reference_mode or "linear_x").lower()
    if normalized == "cross_pol":
        reference = (reference_mode or "linear_x").lower()
        return "linear_y" if reference in {"linear_x", "co_pol"} else "linear_x"
    return normalized


def _project_lab_polarization(theta_deg: np.ndarray, phi_deg: np.ndarray, mode: str, *, reference_mode: str | None = None) -> np.ndarray:
    resolved = _resolve_mode_label(mode, reference_mode=reference_mode)
    if resolved == "linear_x":
        lab = np.array([1.0, 0.0, 0.0], dtype=float)
    elif resolved == "linear_y":
        lab = np.array([0.0, 1.0, 0.0], dtype=float)
    else:
        raise ValueError(f"Unsupported Jones mode: {mode}. Supported modes: {SUPPORTED_POLARIZATION_MODES!r}")
    theta = np.deg2rad(theta_deg)
    phi = np.deg2rad(phi_deg)
    e_theta = np.stack(
        [
            np.cos(theta) * np.cos(phi),
            np.cos(theta) * np.sin(phi),
            -np.sin(theta),
        ],
        axis=-1,
    )
    e_phi = np.stack(
        [
            -np.sin(phi),
            np.cos(phi),
            np.zeros_like(phi),
        ],
        axis=-1,
    )
    coeff_theta = np.tensordot(e_theta, lab, axes=([-1], [0]))
    coeff_phi = np.tensordot(e_phi, lab, axes=([-1], [0]))
    coeffs = np.stack([coeff_theta, coeff_phi], axis=-1).astype(np.complex128)
    norms = np.linalg.norm(coeffs, axis=-1, keepdims=True)
    normalized = coeffs.copy()
    valid = norms[..., 0] > 1e-12
    normalized[valid] /= norms[valid]
    normalized[~valid] = np.array([1.0 + 0.0j, 0.0 + 0.0j], dtype=np.complex128)
    return normalized


def build_local_jones_vectors(
    theta: np.ndarray,
    phi: np.ndarray,
    *,
    incident_mode: str,
    detection_mode: str,
) -> tuple[np.ndarray, np.ndarray]:
    """Return a_tx[...,2], a_rx[...,2]."""
    a_tx = _project_lab_polarization(theta, phi, incident_mode)
    a_rx = _project_lab_polarization(theta, phi, detection_mode, reference_mode=incident_mode)
    return a_tx, a_rx


def project_scattering_matrix_to_effective_channel(
    S11: np.ndarray,
    S12: np.ndarray,
    S21: np.ndarray,
    S22: np.ndarray,
    a_tx: np.ndarray,
    a_rx: np.ndarray,
) -> np.ndarray:
    """Return f_eff(theta, phi, k) = a_rx^H S a_tx."""
    matrix = np.empty(S11.shape + (2, 2), dtype=np.complex128)
    matrix[..., 0, 0] = S11
    matrix[..., 0, 1] = S12
    matrix[..., 1, 0] = S21
    matrix[..., 1, 1] = S22
    return np.einsum("...i,...ij,...j->...", np.conj(a_rx), matrix, a_tx)


def sample_effective_channel(
    *,
    wavelengths_um: np.ndarray,
    theta_deg: np.ndarray,
    phi_deg: np.ndarray,
    particle_geometry: dict[str, Any],
    particle_material: Any,
    medium_material: Any,
    incident_mode: str,
    detection_mode: str,
    library_path: str | None,
    valid_mask: np.ndarray | None = None,
) -> np.ndarray:
    """
    Return f_eff(theta, phi, k) = a_rx^H S a_tx with shape [n_lambda, *theta.shape].
    """
    api = _solver_api()
    particle_fn = api.resolve_material_model(particle_material)
    medium_fn = api.resolve_material_model(medium_material)
    theta_deg = np.asarray(theta_deg, dtype=float)
    phi_deg = np.asarray(phi_deg, dtype=float)
    if theta_deg.shape != phi_deg.shape:
        raise ValueError("theta_deg and phi_deg must have the same shape.")
    if valid_mask is not None:
        valid_mask = np.asarray(valid_mask, dtype=bool)
        if valid_mask.shape != theta_deg.shape:
            raise ValueError("valid_mask must match theta_deg/phi_deg shape.")
    radius_um = float(particle_geometry["diameter_nm"]) / 2000.0
    eps = float(particle_geometry.get("eps", 0.0))
    beta_deg = float(particle_geometry.get("beta_deg", 0.0))
    a_tx, a_rx = build_local_jones_vectors(
        theta_deg,
        phi_deg,
        incident_mode=incident_mode,
        detection_mode=detection_mode,
    )
    effective = np.zeros((len(wavelengths_um),) + theta_deg.shape, dtype=np.complex128)
    for wavelength_idx, lam_um in enumerate(np.asarray(wavelengths_um, dtype=float)):
        n_medium = medium_fn(float(lam_um))
        S11 = np.zeros(theta_deg.shape, dtype=np.complex128)
        S12 = np.zeros(theta_deg.shape, dtype=np.complex128)
        S21 = np.zeros(theta_deg.shape, dtype=np.complex128)
        S22 = np.zeros(theta_deg.shape, dtype=np.complex128)
        for idx in np.ndindex(theta_deg.shape):
            if valid_mask is not None and not valid_mask[idx]:
                continue
            s_matrix, _ = api.calc_sz(
                radius_um,
                float(lam_um) / float(np.real(n_medium)),
                particle_fn(float(lam_um)) / n_medium,
                1.0 + eps,
                thet=float(theta_deg[idx]),
                phi=float(phi_deg[idx]),
                beta=beta_deg,
                library_path=library_path,
            )
            S11[idx] = s_matrix[0, 0]
            S12[idx] = s_matrix[0, 1]
            S21[idx] = s_matrix[1, 0]
            S22[idx] = s_matrix[1, 1]
        effective[wavelength_idx] = project_scattering_matrix_to_effective_channel(S11, S12, S21, S22, a_tx, a_rx)
    return effective


def _build_bridge_bfp_field(
    diameter_nm: float,
    eps: float,
    beta_deg: float,
    particle_material: Any,
    medium_material: Any,
    lambda_nm: np.ndarray,
    *,
    sin_theta_max: np.ndarray,
    n_bfp_dense: int,
    n_bfp_sparse: int,
    incident_mode: str,
    detection_mode: str,
    library_path: str | None,
) -> dict[str, Any]:
    api = _solver_api()
    dense_grid = api._build_unit_pupil_grid(n_bfp=n_bfp_dense)
    sparse_grid = api._build_unit_pupil_grid(n_bfp=n_bfp_sparse)
    field_dense = np.zeros((n_bfp_dense, n_bfp_dense, len(lambda_nm)), dtype=np.complex128)
    wavelengths_um = np.asarray(lambda_nm, dtype=float) / 1000.0
    for k, lam_nm in enumerate(lambda_nm):
        sparse_map = api.build_bfp_angle_map(sin_theta_max=sin_theta_max[k], n_bfp=n_bfp_sparse)
        effective_sparse = sample_effective_channel(
            wavelengths_um=wavelengths_um[k : k + 1],
            theta_deg=sparse_map["theta_deg"],
            phi_deg=sparse_map["phi_deg"],
            particle_geometry={
                "diameter_nm": diameter_nm,
                "eps": eps,
                "beta_deg": beta_deg,
            },
            particle_material=particle_material,
            medium_material=medium_material,
            incident_mode=incident_mode,
            detection_mode=detection_mode,
            library_path=library_path,
            valid_mask=sparse_grid["valid_mask"],
        )[0]
        field_dense[:, :, k] = api._interpolate_sparse_complex_grid(
            effective_sparse,
            sparse_grid["pupil_axis"],
            dense_grid["pupil_axis"],
            dense_grid["valid_mask"],
        )
    return {
        "field_cube": field_dense,
        "pupil_axis": dense_grid["pupil_axis"],
        "u_pupil": dense_grid["u_pupil"],
        "v_pupil": dense_grid["v_pupil"],
        "valid_mask": dense_grid["valid_mask"],
    }


def solve_vector_pupil_overlap_bridge_slice(
    source: SourceConfig,
    grid: GridConfig,
    solver: SolverConfig,
    *,
    strict_material_range: bool = False,
) -> dict:
    api = _solver_api()
    lambda_nm, source_power = api.source_spectrum_lambda(source.lambda0_nm, source.fwhm_nm, source.n_lambda)
    x_um = np.linspace(-0.5 * grid.x_span_um, 0.5 * grid.x_span_um, grid.n_x)
    opd_um = np.linspace(-grid.z_span_um, grid.z_span_um, grid.n_z)
    geometry = api.derive_na_geometry_series(lambda_nm, solver.medium_material, grid.na)
    material_support = {
        "medium_material": api.validate_material_support(
            solver.medium_material,
            lambda_nm,
            strict_material_range=strict_material_range,
            role="medium_material",
        ),
    }
    if solver.ideal:
        bundle = api.build_ideal_bfp_field(lambda_nm, n_bfp_dense=grid.n_bfp_dense)
        tmatrix_used = False
        material_support["particle_material"] = {"role": "particle_material", "status": "skipped_ideal_mode"}
    else:
        material_support["particle_material"] = api.validate_material_support(
            solver.particle_material,
            lambda_nm,
            strict_material_range=strict_material_range,
            role="particle_material",
        )
        bundle = _build_bridge_bfp_field(
            solver.diameter_nm,
            solver.eps,
            solver.beta_deg,
            solver.particle_material,
            solver.medium_material,
            lambda_nm,
            sin_theta_max=geometry["sin_theta_max"],
            n_bfp_dense=grid.n_bfp_dense,
            n_bfp_sparse=grid.n_bfp_sparse,
            incident_mode=solver.incident_mode,
            detection_mode=solver.detection_mode,
            library_path=solver.library_path,
        )
        tmatrix_used = True
    lateral_slice_axis = str(getattr(solver, "lateral_slice_axis", "x")).strip().lower()
    lateral_field = api.pupil_field_to_lateral_line(
        bundle,
        lambda_nm,
        x_um,
        geometry["sin_theta_max"],
        solver.medium_material,
        lateral_slice_axis=lateral_slice_axis,
    )
    sample_arm_spectral_cube = source_power[:, None] * lateral_field
    field_xz = api.spectral_cube_to_xz(lambda_nm, sample_arm_spectral_cube, opd_um, solver.medium_material)
    raw_envelope_xz = np.abs(field_xz)
    raw_intensity_xz = raw_envelope_xz ** 2
    envelope_xz, envelope_xz_scale = api.normalize_intensity(raw_envelope_xz, return_scale=True)
    intensity_xz, intensity_xz_scale = api.normalize_intensity(raw_intensity_xz, return_scale=True)
    axial_views = api.build_full_na_axial_views(x_um, opd_um, raw_intensity_xz, raw_envelope_xz)
    return {
        "mode": api.VECTOR_BRIDGE_MODE,
        "display_mode_label": api.VECTOR_BRIDGE_DISPLAY_LABEL,
        "lateral_slice_axis": lateral_slice_axis,
        "x_um": x_um,
        "opd_um": opd_um,
        "lambda_nm": lambda_nm,
        "sample_arm_spectral_cube": sample_arm_spectral_cube,
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
        "primary_axial_metrics_note": axial_views["primary_axial_metrics_note"],
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
        "pupil_shape": list(bundle["field_cube"].shape),
        "channel_projection_kind": "local_jones_projection",
        "incident_mode": solver.incident_mode,
        "detection_mode": solver.detection_mode,
        "supported_polarization_modes": list(SUPPORTED_POLARIZATION_MODES),
        "channel_definition": "effective_jones_projected_channel",
        "polarization_model_kind": "lab_to_local_jones_surrogate",
        "polarization_projection_level": "lab_to_local_jones_surrogate",
        "projection_semantics_note": (
            "The effective pupil channel uses a local Jones projection f_eff = a_rx^H S a_tx at each pupil direction. "
            "This is a bridge approximation and not a full c_rx^H T c_tx OCT overlap model."
        ),
        "propagation_note": api.FULL_NA_PROPAGATION_NOTE,
        "shape_parameterization_note": api.SHAPE_PARAMETERIZATION_NOTE,
        "spectral_model_note": api.SPECTRAL_MODEL_NOTE,
        "depth_axis_note": api.OPD_AXIS_NOTE,
        "obliquity_model": "sqrt_cos_theta_scalar",
        "material_range_notes": {
            "particle_material": api.MATERIAL_RANGE_NOTES.get(str(solver.particle_material)),
            "medium_material": api.MATERIAL_RANGE_NOTES.get(str(solver.medium_material)),
        },
        "material_support": material_support,
        **api.build_base_result_metadata(
            approximation_label=api.VECTOR_BRIDGE_APPROXIMATION_LABEL,
            paper_safe=strict_material_range,
        ),
    }
