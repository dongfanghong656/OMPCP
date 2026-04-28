from __future__ import annotations

from typing import Any

import numpy as np


REQUIRED_SOLVER_RESULT_KEYS = (
    "mode",
    "lateral_slice_axis",
    "x_um",
    "opd_um",
    "raw_intensity_xz",
    "global_peak_index",
    "peakline_x_um",
    "axial_intensity_metrics",
    "raw_peak_intensity",
)
REQUIRED_AXIAL_METRIC_KEYS = (
    "peak_opd_um",
    "centroid_opd_um",
    "fwhm_opd_um",
    "psr_db",
    "sidelobe_energy_fraction",
)
OPTIONAL_FD_OCT_KEYS = (
    "lambda_nm",
    "sample_arm_spectral_cube",
    "measurement_reference_arm_field",
    "reference_n_medium",
    "derived_geometry_series",
)


def _require_monotonic(axis: np.ndarray, *, name: str) -> None:
    if axis.ndim != 1:
        raise ValueError(f"{name} must be a 1D array.")
    if axis.size < 2:
        raise ValueError(f"{name} must contain at least 2 samples.")
    if not np.all(np.isfinite(axis)):
        raise ValueError(f"{name} must contain only finite values.")
    if not np.all(np.diff(axis) > 0.0):
        raise ValueError(f"{name} must be strictly increasing.")


def extract_solver_result_contract(result: dict[str, Any]) -> dict[str, Any]:
    missing = [key for key in REQUIRED_SOLVER_RESULT_KEYS if key not in result]
    if missing:
        raise KeyError(f"Solver result missing required keys: {', '.join(missing)}")
    x_um = np.asarray(result["x_um"], dtype=float)
    opd_um = np.asarray(result["opd_um"], dtype=float)
    raw_intensity_xz = np.asarray(result["raw_intensity_xz"], dtype=float)
    _require_monotonic(x_um, name="x_um")
    _require_monotonic(opd_um, name="opd_um")
    if raw_intensity_xz.ndim != 2:
        raise ValueError("raw_intensity_xz must be a 2D array.")
    expected_shape = (x_um.size, opd_um.size)
    if raw_intensity_xz.shape != expected_shape:
        raise ValueError(
            f"raw_intensity_xz shape {raw_intensity_xz.shape} does not match expected grid shape {expected_shape}."
        )
    if not np.all(np.isfinite(raw_intensity_xz)):
        raise ValueError("raw_intensity_xz must contain only finite values.")
    try:
        peak_x_idx, peak_z_idx = tuple(int(v) for v in result["global_peak_index"])
    except Exception as exc:  # pragma: no cover - defensive contract path
        raise ValueError("global_peak_index must be a length-2 integer-like sequence.") from exc
    if not (0 <= peak_x_idx < raw_intensity_xz.shape[0] and 0 <= peak_z_idx < raw_intensity_xz.shape[1]):
        raise ValueError(
            f"global_peak_index {(peak_x_idx, peak_z_idx)} is outside raw_intensity_xz shape {raw_intensity_xz.shape}."
        )
    axial_metrics = dict(result["axial_intensity_metrics"])
    missing_axial = [key for key in REQUIRED_AXIAL_METRIC_KEYS if key not in axial_metrics]
    if missing_axial:
        raise KeyError(f"axial_intensity_metrics missing required keys: {', '.join(missing_axial)}")
    lateral_slice_axis = str(result["lateral_slice_axis"]).strip().lower()
    if lateral_slice_axis not in {"x", "y"}:
        raise ValueError(f"lateral_slice_axis must be 'x' or 'y', got {result['lateral_slice_axis']!r}.")
    if not np.isfinite(float(result["peakline_x_um"])):
        raise ValueError("peakline_x_um must be finite.")
    raw_peak_intensity = float(result["raw_peak_intensity"])
    if not np.isfinite(raw_peak_intensity):
        raise ValueError("raw_peak_intensity must be finite.")
    lambda_nm = None
    sample_arm_spectral_cube = None
    measurement_reference_arm_field = None
    reference_n_medium = None
    fd_oct_medium_index = None
    fd_oct_medium_index_policy = "not_supplied"
    fd_oct_measurement_ready = False
    if any(key in result for key in OPTIONAL_FD_OCT_KEYS):
        missing_fd = [key for key in ("lambda_nm", "sample_arm_spectral_cube") if key not in result]
        if missing_fd:
            raise KeyError(
                "FD-OCT measurement path requires the full spectral contract when any spectral key is present; "
                f"missing: {', '.join(missing_fd)}"
            )
        lambda_nm = np.asarray(result["lambda_nm"], dtype=float)
        _require_monotonic(lambda_nm, name="lambda_nm")
        sample_arm_spectral_cube = np.asarray(result["sample_arm_spectral_cube"], dtype=np.complex128)
        expected_spectral_shape = (lambda_nm.size, x_um.size)
        if sample_arm_spectral_cube.shape != expected_spectral_shape:
            raise ValueError(
                "sample_arm_spectral_cube shape "
                f"{sample_arm_spectral_cube.shape} does not match expected spectral grid {expected_spectral_shape}."
            )
        if not np.all(np.isfinite(sample_arm_spectral_cube)):
            raise ValueError("sample_arm_spectral_cube must contain only finite values.")
        if "measurement_reference_arm_field" in result and result["measurement_reference_arm_field"] is not None:
            measurement_reference_arm_field = np.asarray(result["measurement_reference_arm_field"], dtype=np.complex128)
            if measurement_reference_arm_field.shape != lambda_nm.shape:
                raise ValueError(
                    "measurement_reference_arm_field shape "
                    f"{measurement_reference_arm_field.shape} does not match lambda_nm shape {lambda_nm.shape}."
                )
            if not np.all(np.isfinite(measurement_reference_arm_field)):
                raise ValueError("measurement_reference_arm_field must contain only finite values.")
        if "derived_geometry_series" in result and isinstance(result["derived_geometry_series"], dict):
            n_medium = result["derived_geometry_series"].get("n_medium")
            if n_medium is not None:
                fd_oct_medium_index = np.asarray(n_medium, dtype=float)
                if fd_oct_medium_index.shape != lambda_nm.shape:
                    raise ValueError(
                        "derived_geometry_series['n_medium'] shape "
                        f"{fd_oct_medium_index.shape} does not match lambda_nm shape {lambda_nm.shape}."
                    )
                if not np.all(np.isfinite(fd_oct_medium_index)):
                    raise ValueError("derived_geometry_series['n_medium'] must contain only finite values.")
                if np.any(fd_oct_medium_index <= 0.0):
                    raise ValueError("derived_geometry_series['n_medium'] must be positive.")
                fd_oct_medium_index_policy = "derived_geometry_series_n_medium"
        if fd_oct_medium_index is None and "reference_n_medium" in result and result["reference_n_medium"] is not None:
            reference_n_medium = float(result["reference_n_medium"])
            if not np.isfinite(reference_n_medium) or reference_n_medium <= 0.0:
                raise ValueError("reference_n_medium must be finite and positive.")
            fd_oct_medium_index = np.full(lambda_nm.shape, reference_n_medium, dtype=float)
            fd_oct_medium_index_policy = "constant_reference_n_medium"
        if fd_oct_medium_index is None:
            reference_n_medium = 1.0
            fd_oct_medium_index = np.ones(lambda_nm.shape, dtype=float)
            fd_oct_medium_index_policy = "vacuum_default_due_to_missing_reference_n"
        if reference_n_medium is None:
            reference_n_medium = float(fd_oct_medium_index[fd_oct_medium_index.size // 2])
        fd_oct_measurement_ready = True
    return {
        "mode": result["mode"],
        "lateral_slice_axis": lateral_slice_axis,
        "x_um": x_um,
        "opd_um": opd_um,
        "raw_intensity_xz": raw_intensity_xz,
        "global_peak_index": (peak_x_idx, peak_z_idx),
        "peakline_x_um": float(result["peakline_x_um"]),
        "axial_intensity_metrics": axial_metrics,
        "raw_peak_intensity": raw_peak_intensity,
        "lambda_nm": lambda_nm,
        "sample_arm_spectral_cube": sample_arm_spectral_cube,
        "measurement_reference_arm_field": measurement_reference_arm_field,
        "reference_n_medium": reference_n_medium,
        "fd_oct_medium_index": fd_oct_medium_index,
        "fd_oct_medium_index_policy": fd_oct_medium_index_policy,
        "fd_oct_measurement_ready": fd_oct_measurement_ready,
    }
