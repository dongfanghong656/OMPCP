"""Angle-resolved sphere-only pupil branch for round6 OCT simulations.

This module builds a BFP field cube for spherical particles using pure Mie
S1/S2 amplitudes. It replaces the T-matrix call only when the particle is
exactly spherical (eps=0) and force_tmatrix=False.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Callable

import numpy as np

from .mie_sphere import mie_s1_s2, mie_size_parameter, select_mie_channel


@dataclass(frozen=True)
class SphereMiePupilMetadata:
    branch_id: str
    convention_id: str
    channel: str
    diameter_nm: float
    n_lambda: int
    n_bfp_dense: int
    central_scattering_angle_deg: float
    max_collection_angle_deg: float
    particle_lateral_scattering_enters_profile: bool
    tmatrix_backend_required: bool
    warning: str | None = None


def unit_pupil_grid(n_bfp: int = 129) -> dict[str, np.ndarray]:
    axis = np.linspace(-1.0, 1.0, int(n_bfp))
    u, v = np.meshgrid(axis, axis)
    valid = (u * u + v * v) <= 1.0
    return {"pupil_axis": axis, "u_pupil": u, "v_pupil": v, "valid_mask": valid}


def spherical_to_cart(theta_deg: float, phi_deg: float) -> np.ndarray:
    theta = np.deg2rad(float(theta_deg))
    phi = np.deg2rad(float(phi_deg))
    return np.array(
        [np.sin(theta) * np.cos(phi), np.sin(theta) * np.sin(phi), np.cos(theta)],
        dtype=float,
    )


def backscatter_tangent_basis(
    thet0_deg: float = 90.0,
    phi0_deg: float = 0.0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    incident = spherical_to_cart(thet0_deg, phi0_deg)
    central_backscatter = -incident
    reference = np.array([0.0, 0.0, 1.0], dtype=float)
    if abs(np.dot(reference, central_backscatter)) > 0.99:
        reference = np.array([0.0, 1.0, 0.0], dtype=float)
    tangent_u = np.cross(reference, central_backscatter)
    tangent_u /= np.linalg.norm(tangent_u)
    tangent_v = np.cross(central_backscatter, tangent_u)
    tangent_v /= np.linalg.norm(tangent_v)
    return incident, central_backscatter, tangent_u, tangent_v


def direction_cosines_for_pupil(
    u_pupil: np.ndarray,
    v_pupil: np.ndarray,
    sin_theta_max: float,
    *,
    thet0_deg: float = 90.0,
    phi0_deg: float = 0.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Return outgoing directions and cos(scattering_angle) for each pupil point."""

    incident, central_backscatter, tangent_u, tangent_v = backscatter_tangent_basis(thet0_deg, phi0_deg)
    smax = float(sin_theta_max)
    tx = smax * np.asarray(u_pupil, dtype=float)
    ty = smax * np.asarray(v_pupil, dtype=float)
    tz = np.sqrt(np.clip(1.0 - tx * tx - ty * ty, 0.0, None))
    directions = (
        central_backscatter[None, None, :] * tz[..., None]
        + tangent_u[None, None, :] * tx[..., None]
        + tangent_v[None, None, :] * ty[..., None]
    )
    directions /= np.linalg.norm(directions, axis=-1, keepdims=True)
    mu_scat = np.sum(directions * incident[None, None, :], axis=-1)
    return directions, np.clip(mu_scat, -1.0, 1.0)


def _sin_theta_series(sin_theta_max: float | np.ndarray, n_lambda: int) -> np.ndarray:
    values = np.asarray(sin_theta_max, dtype=float)
    if values.ndim == 0:
        values = np.full(int(n_lambda), float(values), dtype=float)
    if values.shape != (int(n_lambda),):
        raise ValueError("sin_theta_max must be scalar or match lambda_nm length.")
    if not np.all(np.isfinite(values)):
        raise ValueError("sin_theta_max contains non-finite values.")
    if np.any(values < 0.0) or np.any(values >= 1.0):
        raise ValueError("sin_theta_max values must lie in [0, 1).")
    return values


def build_sphere_mie_bfp_field(
    *,
    diameter_nm: float,
    particle_index_fn: Callable[[float], complex],
    medium_index_fn: Callable[[float], complex],
    lambda_nm: np.ndarray,
    sin_theta_max: float | np.ndarray,
    n_bfp_dense: int = 129,
    amp_component: str = "S22",
    thet0_deg: float = 90.0,
    phi0_deg: float = 0.0,
) -> dict[str, object]:
    """Build an angle-resolved BFP field cube for a homogeneous sphere."""

    lambda_arr = np.asarray(lambda_nm, dtype=float)
    if lambda_arr.ndim != 1 or lambda_arr.size < 2:
        raise ValueError("lambda_nm must be a one-dimensional wavelength grid with at least two samples.")
    if not np.all(np.isfinite(lambda_arr)) or not np.all(np.diff(lambda_arr) > 0.0):
        raise ValueError("lambda_nm must be finite and strictly increasing.")
    diameter_nm = float(diameter_nm)
    if diameter_nm <= 0.0:
        raise ValueError("diameter_nm must be positive.")

    grid = unit_pupil_grid(n_bfp_dense)
    smax_values = _sin_theta_series(sin_theta_max, lambda_arr.size)
    field_cube = np.zeros((n_bfp_dense, n_bfp_dense, lambda_arr.size), dtype=np.complex128)
    mu_max = -1.0
    nmax_values: list[int] = []
    warning = None
    channel = str(amp_component).strip().upper()
    if channel in {"AVG_DIAG", "CO_POL"}:
        warning = (
            "AVG_DIAG/CO_POL may cancel near exact sphere backscatter because S1=-S2 under the "
            "Bohren-Huffman convention; use S22 as the default scalar fixed-basis channel unless "
            "a calibrated Jones projection is available."
        )

    radius_um = diameter_nm / 2000.0
    for k, lam_nm in enumerate(lambda_arr):
        _, mu_scat = direction_cosines_for_pupil(
            grid["u_pupil"],
            grid["v_pupil"],
            smax_values[k],
            thet0_deg=thet0_deg,
            phi0_deg=phi0_deg,
        )
        valid_mu = mu_scat[grid["valid_mask"]]
        mu_max = max(mu_max, float(np.max(valid_mu)))
        lam_um = float(lam_nm) / 1000.0
        n_medium = complex(medium_index_fn(lam_um))
        n_particle = complex(particle_index_fn(lam_um))
        m_rel = n_particle / n_medium
        x = mie_size_parameter(radius_um, lam_um, n_medium)
        mie = mie_s1_s2(m_rel, x, valid_mu)
        nmax_values.append(mie.nmax)
        local_field = np.zeros_like(mu_scat, dtype=np.complex128)
        local_field[grid["valid_mask"]] = select_mie_channel(mie.s1, mie.s2, channel)
        field_cube[:, :, k] = local_field

    max_collection_angle_deg = float(180.0 - np.rad2deg(np.arccos(np.clip(mu_max, -1.0, 1.0))))
    metadata = SphereMiePupilMetadata(
        branch_id="sphere_mie_angle_resolved_pupil_field_v1",
        convention_id="bohren_huffman_s1_s2_s22_matches_round6_backscatter",
        channel=channel,
        diameter_nm=diameter_nm,
        n_lambda=int(lambda_arr.size),
        n_bfp_dense=int(n_bfp_dense),
        central_scattering_angle_deg=180.0,
        max_collection_angle_deg=float(abs(max_collection_angle_deg)),
        particle_lateral_scattering_enters_profile=True,
        tmatrix_backend_required=False,
        warning=warning,
    )
    return {
        "field_cube": field_cube,
        "pupil_axis": grid["pupil_axis"],
        "u_pupil": grid["u_pupil"],
        "v_pupil": grid["v_pupil"],
        "valid_mask": grid["valid_mask"],
        "sphere_mie_metadata": asdict(metadata),
        "sphere_mie_nmax_min": int(min(nmax_values)) if nmax_values else None,
        "sphere_mie_nmax_max": int(max(nmax_values)) if nmax_values else None,
    }
