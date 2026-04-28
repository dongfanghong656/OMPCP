from __future__ import annotations

from typing import Any

import numpy as np


def _require_monotonic(axis: np.ndarray, *, name: str) -> None:
    if axis.ndim != 1:
        raise ValueError(f"{name} must be a 1D array.")
    if axis.size < 2:
        raise ValueError(f"{name} must contain at least two samples.")
    if not np.all(np.isfinite(axis)):
        raise ValueError(f"{name} must contain only finite values.")
    if not np.all(np.diff(axis) > 0.0):
        raise ValueError(f"{name} must be strictly increasing.")


def _medium_index_array(lambda_nm: np.ndarray, medium_index: float | np.ndarray = 1.0) -> np.ndarray:
    medium = np.asarray(medium_index, dtype=float)
    if medium.ndim == 0:
        medium = np.full(lambda_nm.shape, float(medium), dtype=float)
    if medium.shape != lambda_nm.shape:
        raise ValueError(f"medium_index shape {medium.shape} does not match lambda_nm shape {lambda_nm.shape}.")
    if not np.all(np.isfinite(medium)):
        raise ValueError("medium_index must contain only finite values.")
    if np.any(medium <= 0.0):
        raise ValueError("medium_index must be positive.")
    return medium


def _k_axis_from_lambda_nm(lambda_nm: np.ndarray, *, medium_index: float | np.ndarray = 1.0) -> np.ndarray:
    lambda_nm = np.asarray(lambda_nm, dtype=float)
    _require_monotonic(lambda_nm, name="lambda_nm")
    medium = _medium_index_array(lambda_nm, medium_index)
    return 2.0 * np.pi * medium / (lambda_nm / 1000.0)


def _fd_depth_convention(medium_index: np.ndarray) -> dict[str, Any]:
    reference_n = float(np.real(medium_index[medium_index.size // 2]))
    if np.allclose(medium_index, 1.0):
        k_axis_kind = "vacuum_wavenumber_rad_per_um"
        policy = "vacuum_default"
    elif np.allclose(medium_index, reference_n):
        k_axis_kind = "constant_medium_effective_wavenumber_rad_per_um"
        policy = "constant_reference_n_medium"
    else:
        k_axis_kind = "dispersive_medium_effective_wavenumber_rad_per_um"
        policy = "per_wavelength_medium_index"
    return {
        "k_axis_kind": k_axis_kind,
        "medium_index_policy": policy,
        "reference_n_medium": reference_n,
        "fd_oct_depth_convention": "geometric_roundtrip_conjugate_to_medium_effective_wavenumber",
        "fd_oct_depth_axis_note": (
            "The Fourier axis conjugate to k_medium = 2*pi*n/lambda0 is geometric roundtrip distance. "
            "Single-pass geometric depth is geometric_roundtrip_um / 2; optical roundtrip path is "
            "reference_n_medium * geometric_roundtrip_um."
        ),
        "single_pass_depth_from_reference_n_note": (
            "Deprecated compatibility alias for single_pass_geometric_depth_um; do not divide by n again."
        ),
        "double_pass_depth_from_reference_n_note": (
            "Deprecated compatibility alias for double_pass_geometric_depth_um; optical path is reported separately."
        ),
    }


def build_fd_oct_interference_spectrum(
    lambda_nm: np.ndarray,
    sample_arm_field: np.ndarray,
    *,
    medium_index: float | np.ndarray = 1.0,
    reference_arm_field: np.ndarray | None = None,
    reference_amplitude: float = 1.0,
    reference_phase_rad: float = 0.0,
    reference_delay_opd_um: float = 0.0,
    remove_dc: bool = True,
) -> dict[str, Any]:
    lambda_nm = np.asarray(lambda_nm, dtype=float)
    medium = _medium_index_array(lambda_nm, medium_index)
    k_axis = _k_axis_from_lambda_nm(lambda_nm, medium_index=medium)
    depth_contract = _fd_depth_convention(medium)
    sample_arm_field = np.asarray(sample_arm_field, dtype=np.complex128)
    if sample_arm_field.shape != lambda_nm.shape:
        raise ValueError(
            f"sample_arm_field shape {sample_arm_field.shape} does not match lambda_nm shape {lambda_nm.shape}."
        )
    if reference_arm_field is None:
        reference_phase = reference_phase_rad + k_axis * float(reference_delay_opd_um)
        reference_arm_field = np.full(
            lambda_nm.shape,
            complex(reference_amplitude),
            dtype=np.complex128,
        ) * np.exp(1j * reference_phase)
        reference_arm_policy = "synthetic_flat_amplitude_reference_with_optional_delay"
    else:
        reference_arm_field = np.asarray(reference_arm_field, dtype=np.complex128)
        if reference_arm_field.shape != lambda_nm.shape:
            raise ValueError(
                f"reference_arm_field shape {reference_arm_field.shape} does not match lambda_nm shape {lambda_nm.shape}."
            )
        reference_arm_policy = "explicit_reference_arm_field"

    total_field = sample_arm_field + reference_arm_field
    total_intensity = np.abs(total_field) ** 2
    sample_intensity = np.abs(sample_arm_field) ** 2
    reference_intensity = np.abs(reference_arm_field) ** 2
    cross_term = total_intensity - sample_intensity - reference_intensity
    interference_spectrum = cross_term if remove_dc else total_intensity
    return {
        "lambda_nm": lambda_nm,
        "k_rad_per_um": k_axis,
        "medium_index": medium,
        **depth_contract,
        "reference_delay_opd_um": float(reference_delay_opd_um),
        "reference_delay_axis_note": (
            "reference_delay_opd_um is retained as a legacy parameter name; with k_medium it is interpreted "
            "as a geometric roundtrip delay on the reconstruction axis."
        ),
        "reference_arm_policy": reference_arm_policy,
        "sample_arm_field": sample_arm_field,
        "reference_arm_field": reference_arm_field,
        "sample_intensity_spectrum": sample_intensity,
        "reference_intensity_spectrum": reference_intensity,
        "cross_term_spectrum": cross_term,
        "interference_spectrum": interference_spectrum,
        "dc_removed": bool(remove_dc),
    }


def k_linearize_interference_spectrum(
    lambda_nm: np.ndarray,
    spectrum: np.ndarray,
    *,
    medium_index: float | np.ndarray = 1.0,
) -> dict[str, Any]:
    lambda_nm = np.asarray(lambda_nm, dtype=float)
    spectrum = np.asarray(spectrum)
    if spectrum.shape != lambda_nm.shape:
        raise ValueError(f"spectrum shape {spectrum.shape} does not match lambda_nm shape {lambda_nm.shape}.")
    medium = _medium_index_array(lambda_nm, medium_index)
    k_axis = _k_axis_from_lambda_nm(lambda_nm, medium_index=medium)
    depth_contract = _fd_depth_convention(medium)
    order = np.argsort(k_axis)
    k_sorted = k_axis[order]
    spectrum_sorted = spectrum[order]
    k_uniform = np.linspace(k_sorted[0], k_sorted[-1], k_sorted.size)
    if np.iscomplexobj(spectrum_sorted):
        spectrum_uniform = (
            np.interp(k_uniform, k_sorted, np.real(spectrum_sorted))
            + 1j * np.interp(k_uniform, k_sorted, np.imag(spectrum_sorted))
        )
    else:
        spectrum_uniform = np.interp(k_uniform, k_sorted, np.asarray(spectrum_sorted, dtype=float))
    return {
        "k_sorted_rad_per_um": k_sorted,
        "k_uniform_rad_per_um": k_uniform,
        "medium_index": medium,
        **depth_contract,
        "spectrum_sorted": spectrum_sorted,
        "spectrum_k_linearized": spectrum_uniform,
    }


def reconstruct_fd_oct_a_scan(
    lambda_nm: np.ndarray,
    interference_spectrum: np.ndarray,
    *,
    medium_index: float | np.ndarray = 1.0,
    dispersion_phase_rad: np.ndarray | None = None,
    window: str = "hann",
) -> dict[str, Any]:
    linearized = k_linearize_interference_spectrum(lambda_nm, interference_spectrum, medium_index=medium_index)
    spectrum = np.asarray(linearized["spectrum_k_linearized"], dtype=np.complex128)
    if dispersion_phase_rad is not None:
        dispersion_phase_rad = np.asarray(dispersion_phase_rad, dtype=float)
        if dispersion_phase_rad.shape != spectrum.shape:
            raise ValueError(
                f"dispersion_phase_rad shape {dispersion_phase_rad.shape} does not match spectrum shape {spectrum.shape}."
            )
        spectrum = spectrum * np.exp(-1j * dispersion_phase_rad)
    if window == "hann":
        spectrum = spectrum * np.hanning(spectrum.size)
    elif window != "none":
        raise ValueError(f"Unsupported window: {window!r}")
    reconstruction = np.fft.fftshift(np.fft.ifft(spectrum))
    dk = float(np.mean(np.diff(linearized["k_uniform_rad_per_um"])))
    geometric_roundtrip_um = np.fft.fftshift(2.0 * np.pi * np.fft.fftfreq(spectrum.size, d=dk))
    reference_n = float(linearized["reference_n_medium"])
    single_pass_geometric_depth_um = geometric_roundtrip_um / 2.0
    double_pass_geometric_depth_um = geometric_roundtrip_um
    optical_roundtrip_path_um = reference_n * geometric_roundtrip_um
    return {
        **linearized,
        "dispersion_phase_rad": dispersion_phase_rad,
        "window": window,
        "reconstruction_complex": reconstruction,
        "reconstruction_intensity": np.abs(reconstruction) ** 2,
        "geometric_roundtrip_um": geometric_roundtrip_um,
        "single_pass_geometric_depth_um": single_pass_geometric_depth_um,
        "double_pass_geometric_depth_um": double_pass_geometric_depth_um,
        "optical_roundtrip_path_um": optical_roundtrip_path_um,
        "single_pass_optical_path_um": optical_roundtrip_path_um / 2.0,
        "opd_um": geometric_roundtrip_um,
        "opd_um_legacy_alias_note": (
            "Deprecated alias retained for older consumers; for k_medium reconstructions this is geometric "
            "roundtrip distance, not optical path difference."
        ),
        "single_pass_depth_from_reference_n_um": single_pass_geometric_depth_um,
        "double_pass_depth_from_reference_n_um": double_pass_geometric_depth_um,
    }


__all__ = [
    "build_fd_oct_interference_spectrum",
    "k_linearize_interference_spectrum",
    "reconstruct_fd_oct_a_scan",
]
