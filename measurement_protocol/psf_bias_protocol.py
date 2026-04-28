from __future__ import annotations

from typing import Any

import numpy as np
from oct_forward import (
    build_fd_oct_interference_spectrum,
    extract_solver_result_contract,
    reconstruct_fd_oct_a_scan,
)


MEASUREMENT_EXTRACTION_MODES = ("self_peak", "reference_peak_plane")
MEASUREMENT_PIPELINE_MODES = (
    "fd_oct_reconstruction",
    "solver_output_peak_slice_adapter",
)


def _normalize_profile(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    vmax = float(np.max(values)) if values.size else 0.0
    if vmax <= 0.0:
        return np.zeros_like(values, dtype=float)
    return values / vmax


def _interp_crossing(x: np.ndarray, y: np.ndarray, level: float, *, left: bool) -> float:
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    if x.size < 2:
        return float(x[0]) if x.size else 0.0
    idx = np.where(y < level)[0]
    if len(idx) == 0:
        return float(x[0] if left else x[-1])
    if left:
        pos = idx[-1]
        if pos >= len(x) - 1:
            return float(x[-1])
        x1, x2, y1, y2 = x[pos], x[pos + 1], y[pos], y[pos + 1]
    else:
        pos = idx[0]
        if pos <= 0:
            return float(x[0])
        x1, x2, y1, y2 = x[pos - 1], x[pos], y[pos - 1], y[pos]
    return float(x1 + (level - y1) * (x2 - x1) / (y2 - y1 + 1e-30))


def _profile_geometry(axis: np.ndarray, profile: np.ndarray) -> dict[str, float]:
    axis = np.asarray(axis, dtype=float)
    profile = _normalize_profile(profile)
    peak_idx = int(np.argmax(profile)) if profile.size else 0
    peak_axis = float(axis[peak_idx]) if axis.size else 0.0
    if profile.size == 0:
        return {
            "peak_axis_um": 0.0,
            "centroid_um": 0.0,
            "fwhm_um": 0.0,
            "peak_value": 0.0,
        }
    left = _interp_crossing(axis[: peak_idx + 1], profile[: peak_idx + 1], 0.5, left=True)
    right = _interp_crossing(axis[peak_idx:], profile[peak_idx:], 0.5, left=False)
    centroid = float(np.sum(axis * profile) / (np.sum(profile) + 1e-30))
    return {
        "peak_axis_um": peak_axis,
        "centroid_um": centroid,
        "fwhm_um": float(right - left),
        "peak_value": float(profile[peak_idx]),
    }


def _profile_sideband_metrics(axis: np.ndarray, profile: np.ndarray) -> dict[str, float]:
    axis = np.asarray(axis, dtype=float)
    profile = _normalize_profile(profile)
    if profile.size == 0:
        return {
            "peak_opd_um": 0.0,
            "centroid_opd_um": 0.0,
            "fwhm_opd_um": 0.0,
            "psr_db": 0.0,
            "psr_definition": "main_to_sidelobe_rejection_db",
            "sidelobe_to_main_db": 0.0,
            "main_to_sidelobe_rejection_db": 0.0,
            "sidelobe_energy_fraction": 0.0,
        }
    peak_idx = int(np.argmax(profile))
    left_cross = _interp_crossing(axis[: peak_idx + 1], profile[: peak_idx + 1], 0.5, left=True)
    right_cross = _interp_crossing(axis[peak_idx:], profile[peak_idx:], 0.5, left=False)
    main_lobe_mask = (axis >= left_cross) & (axis <= right_cross)
    sidelobe_profile = np.where(main_lobe_mask, 0.0, profile)
    sidelobe_peak = float(np.max(sidelobe_profile)) if sidelobe_profile.size else 0.0
    psr_db = 0.0 if sidelobe_peak <= 0.0 else float(10.0 * np.log10(1.0 / sidelobe_peak))
    sidelobe_to_main_db = 0.0 if sidelobe_peak <= 0.0 else float(10.0 * np.log10(sidelobe_peak))
    sidelobe_energy_fraction = float(np.sum(sidelobe_profile) / (np.sum(profile) + 1e-30))
    centroid = float(np.sum(axis * profile) / (np.sum(profile) + 1e-30))
    return {
        "peak_opd_um": float(axis[peak_idx]),
        "centroid_opd_um": centroid,
        "fwhm_opd_um": float(right_cross - left_cross),
        "psr_db": psr_db,
        "psr_definition": "main_to_sidelobe_rejection_db",
        "sidelobe_to_main_db": sidelobe_to_main_db,
        "main_to_sidelobe_rejection_db": psr_db,
        "sidelobe_energy_fraction": sidelobe_energy_fraction,
    }


def _resolve_extraction_plane_index(
    snapshot_contract: dict[str, Any],
    *,
    extraction_mode: str,
    reference_peak_index: tuple[int, int] | None,
) -> int:
    if extraction_mode == "self_peak":
        return int(snapshot_contract["global_peak_index"][1])
    if extraction_mode == "reference_peak_plane":
        if reference_peak_index is None:
            raise ValueError("reference_peak_index is required for extraction_mode='reference_peak_plane'.")
        reference_plane_idx = int(reference_peak_index[1])
        if not (0 <= reference_plane_idx < snapshot_contract["raw_intensity_xz"].shape[1]):
            raise ValueError(
                "reference_peak_index plane "
                f"{reference_plane_idx} is outside raw_intensity_xz shape {snapshot_contract['raw_intensity_xz'].shape}."
            )
        return reference_plane_idx
    raise ValueError(f"Unsupported extraction_mode: {extraction_mode}")


def _peak_index(raw_intensity_xz: np.ndarray) -> tuple[int, int]:
    flat_idx = int(np.argmax(raw_intensity_xz))
    return tuple(int(v) for v in np.unravel_index(flat_idx, raw_intensity_xz.shape))


def _build_solver_output_snapshot_contract(solver_result: dict[str, Any]) -> dict[str, Any]:
    return {
        "raw_intensity_xz": solver_result["raw_intensity_xz"],
        "x_um": solver_result["x_um"],
        "opd_um": solver_result["opd_um"],
        "global_peak_index": solver_result["global_peak_index"],
        "peakline_x_um": solver_result["peakline_x_um"],
        "axial_intensity_metrics": solver_result["axial_intensity_metrics"],
        "raw_peak_intensity": solver_result["raw_peak_intensity"],
        "measurement_protocol_kind": "solver_output_peak_slice_protocol",
        "measurement_protocol_note": (
            "This protocol measures the lateral line on directly reconstructed solver output. "
            "It is useful as a shared extraction-rule adapter, but it is not a raw-domain FD-OCT acquisition model."
        ),
    }


def _build_fd_oct_snapshot_contract(solver_result: dict[str, Any]) -> dict[str, Any]:
    if not solver_result["fd_oct_measurement_ready"]:
        raise ValueError("FD-OCT reconstruction pipeline requires lambda_nm and sample_arm_spectral_cube.")
    lambda_nm = np.asarray(solver_result["lambda_nm"], dtype=float)
    sample_arm_spectral_cube = np.asarray(solver_result["sample_arm_spectral_cube"], dtype=np.complex128)
    reconstructed_rows = []
    reconstructed_opd = None
    reference_arm_field = solver_result.get("measurement_reference_arm_field")
    fd_oct_medium_index = solver_result.get("fd_oct_medium_index", 1.0)
    reference_delay_opd_um = float(solver_result.get("measurement_reference_delay_opd_um", 0.0))
    reconstruction_contract = None
    spectrum_contract = None
    for x_idx in range(sample_arm_spectral_cube.shape[1]):
        spectrum = build_fd_oct_interference_spectrum(
            lambda_nm,
            sample_arm_spectral_cube[:, x_idx],
            medium_index=fd_oct_medium_index,
            reference_arm_field=reference_arm_field,
            reference_delay_opd_um=reference_delay_opd_um,
            remove_dc=True,
        )
        reconstruction = reconstruct_fd_oct_a_scan(
            lambda_nm,
            spectrum["interference_spectrum"],
            medium_index=fd_oct_medium_index,
            window="hann",
        )
        reconstructed_rows.append(np.asarray(reconstruction["reconstruction_intensity"], dtype=float))
        if reconstructed_opd is None:
            reconstructed_opd = np.asarray(reconstruction["geometric_roundtrip_um"], dtype=float)
            reconstruction_contract = reconstruction
            spectrum_contract = spectrum
    raw_intensity_xz = np.asarray(reconstructed_rows, dtype=float)
    global_peak_index = _peak_index(raw_intensity_xz)
    peakline_x_um = float(solver_result["x_um"][global_peak_index[0]])
    raw_peak_intensity = float(raw_intensity_xz[global_peak_index])
    axial_metrics = _profile_sideband_metrics(reconstructed_opd, raw_intensity_xz[global_peak_index[0], :])
    return {
        "raw_intensity_xz": raw_intensity_xz,
        "x_um": solver_result["x_um"],
        "opd_um": reconstructed_opd,
        "global_peak_index": global_peak_index,
        "peakline_x_um": peakline_x_um,
        "axial_intensity_metrics": axial_metrics,
        "raw_peak_intensity": raw_peak_intensity,
        "measurement_protocol_kind": "fd_oct_reconstruction_peak_slice_protocol",
        "measurement_protocol_note": (
            "This protocol reconstructs a minimal FD-OCT interferogram per lateral sample, then measures the resulting "
            "A-scan/lateral stack. It is still a scaffold, but it more closely matches the intended Fourier-domain "
            "measurement chain than direct solver-output peak slicing."
        ),
        "fd_oct_k_axis_kind": reconstruction_contract.get("k_axis_kind") if reconstruction_contract else "unknown",
        "fd_oct_depth_convention": reconstruction_contract.get("fd_oct_depth_convention") if reconstruction_contract else "unknown",
        "fd_oct_depth_axis_note": reconstruction_contract.get("fd_oct_depth_axis_note") if reconstruction_contract else "unknown",
        "fd_oct_medium_index_policy": solver_result.get("fd_oct_medium_index_policy", "unknown"),
        "fd_oct_reference_n_medium": float(solver_result.get("reference_n_medium", 1.0)),
        "fd_oct_reference_delay_opd_um": reference_delay_opd_um,
        "fd_oct_reference_arm_policy": spectrum_contract.get("reference_arm_policy") if spectrum_contract else "unknown",
        "fd_oct_geometric_roundtrip_um": (
            reconstruction_contract.get("geometric_roundtrip_um") if reconstruction_contract else None
        ),
        "fd_oct_single_pass_geometric_depth_um": (
            reconstruction_contract.get("single_pass_geometric_depth_um") if reconstruction_contract else None
        ),
        "fd_oct_double_pass_geometric_depth_um": (
            reconstruction_contract.get("double_pass_geometric_depth_um") if reconstruction_contract else None
        ),
        "fd_oct_optical_roundtrip_path_um": (
            reconstruction_contract.get("optical_roundtrip_path_um") if reconstruction_contract else None
        ),
        "fd_oct_single_pass_depth_from_reference_n_um": (
            reconstruction_contract.get("single_pass_depth_from_reference_n_um") if reconstruction_contract else None
        ),
        "fd_oct_double_pass_depth_from_reference_n_um": (
            reconstruction_contract.get("double_pass_depth_from_reference_n_um") if reconstruction_contract else None
        ),
    }


def _build_measurement_snapshot_contract(
    result: dict[str, Any],
    *,
    pipeline_mode: str,
) -> dict[str, Any]:
    solver_result = extract_solver_result_contract(result)
    if pipeline_mode == "solver_output_peak_slice_adapter":
        return _build_solver_output_snapshot_contract(solver_result)
    if pipeline_mode == "fd_oct_reconstruction":
        return _build_fd_oct_snapshot_contract(solver_result)
    raise ValueError(f"Unsupported pipeline_mode: {pipeline_mode}")


def extract_measurement_snapshot(
    result: dict[str, Any],
    *,
    extraction_mode: str = "self_peak",
    reference_peak_index: tuple[int, int] | None = None,
    pipeline_mode: str = "solver_output_peak_slice_adapter",
) -> dict[str, Any]:
    solver_result = extract_solver_result_contract(result)
    snapshot_contract = _build_measurement_snapshot_contract(result, pipeline_mode=pipeline_mode)
    x_um = np.asarray(snapshot_contract["x_um"], dtype=float)
    opd_um = np.asarray(snapshot_contract["opd_um"], dtype=float)
    raw_intensity_xz = np.asarray(snapshot_contract["raw_intensity_xz"], dtype=float)
    peak_x_idx, peak_z_idx = tuple(int(v) for v in snapshot_contract["global_peak_index"])
    extraction_plane_idx = _resolve_extraction_plane_index(
        snapshot_contract,
        extraction_mode=extraction_mode,
        reference_peak_index=reference_peak_index,
    )
    lateral_raw_profile = raw_intensity_xz[:, extraction_plane_idx]
    lateral_profile = _normalize_profile(lateral_raw_profile)
    lateral_geometry = _profile_geometry(x_um, lateral_profile)
    axial_metrics = dict(snapshot_contract["axial_intensity_metrics"])
    protocol_kind = snapshot_contract["measurement_protocol_kind"]
    protocol_note = snapshot_contract["measurement_protocol_note"]
    if extraction_mode == "self_peak":
        extraction_note = (
            "This extraction compares each candidate on its own global peak plane. "
            "It is useful for shared-rule comparisons, but it still entangles lateral differences with axial peak migration."
        )
    else:
        extraction_note = (
            "This extraction compares all candidates on the reference global peak plane. "
            "It reduces axial-plane confounding relative to self-peak extraction."
        )
    return {
        "mode": solver_result["mode"],
        "lateral_slice_axis": solver_result["lateral_slice_axis"],
        "measurement_pipeline_mode": pipeline_mode,
        "measurement_protocol_kind": protocol_kind,
        "measurement_protocol_note": protocol_note,
        "fd_oct_k_axis_kind": snapshot_contract.get("fd_oct_k_axis_kind"),
        "fd_oct_depth_convention": snapshot_contract.get("fd_oct_depth_convention"),
        "fd_oct_depth_axis_note": snapshot_contract.get("fd_oct_depth_axis_note"),
        "fd_oct_medium_index_policy": snapshot_contract.get("fd_oct_medium_index_policy"),
        "fd_oct_reference_n_medium": snapshot_contract.get("fd_oct_reference_n_medium"),
        "fd_oct_reference_delay_opd_um": snapshot_contract.get("fd_oct_reference_delay_opd_um"),
        "fd_oct_reference_arm_policy": snapshot_contract.get("fd_oct_reference_arm_policy"),
        "fd_oct_single_pass_geometric_depth_um": snapshot_contract.get("fd_oct_single_pass_geometric_depth_um"),
        "fd_oct_double_pass_geometric_depth_um": snapshot_contract.get("fd_oct_double_pass_geometric_depth_um"),
        "fd_oct_optical_roundtrip_path_um": snapshot_contract.get("fd_oct_optical_roundtrip_path_um"),
        "measurement_extraction_mode": extraction_mode,
        "measurement_extraction_note": extraction_note,
        "global_peak_index": [peak_x_idx, peak_z_idx],
        "global_peak_x_um": float(x_um[peak_x_idx]),
        "global_peak_opd_um": float(opd_um[peak_z_idx]),
        "extraction_plane_index": int(extraction_plane_idx),
        "extraction_plane_opd_um": float(opd_um[extraction_plane_idx]),
        "measured_peakline_x_um": float(snapshot_contract["peakline_x_um"]),
        "measured_lateral_peak_x_um": lateral_geometry["peak_axis_um"],
        "measured_lateral_centroid_um": lateral_geometry["centroid_um"],
        "measured_lateral_fwhm_um": lateral_geometry["fwhm_um"],
        "measured_axial_peak_opd_um": float(axial_metrics["peak_opd_um"]),
        "measured_axial_centroid_opd_um": float(axial_metrics["centroid_opd_um"]),
        "measured_axial_fwhm_opd_um": float(axial_metrics["fwhm_opd_um"]),
        "measured_psr_db": float(axial_metrics["psr_db"]),
        "measured_psr_definition": axial_metrics.get("psr_definition", "main_to_sidelobe_rejection_db"),
        "measured_sidelobe_to_main_db": float(axial_metrics.get("sidelobe_to_main_db", -float(axial_metrics["psr_db"]))),
        "measured_main_to_sidelobe_rejection_db": float(
            axial_metrics.get("main_to_sidelobe_rejection_db", axial_metrics["psr_db"])
        ),
        "measured_sidelobe_energy_fraction": float(axial_metrics["sidelobe_energy_fraction"]),
        "raw_peak_intensity": float(snapshot_contract["raw_peak_intensity"]),
    }


def compare_measurement_snapshots(
    candidate: dict[str, Any],
    reference: dict[str, Any],
    *,
    extraction_mode: str = "self_peak",
    pipeline_mode: str = "solver_output_peak_slice_adapter",
) -> dict[str, Any]:
    reference_self_peak = extract_measurement_snapshot(
        reference,
        extraction_mode="self_peak",
        pipeline_mode=pipeline_mode,
    )
    if extraction_mode == "reference_peak_plane":
        reference_peak_index = tuple(int(v) for v in reference_self_peak["global_peak_index"])
        candidate_snapshot = extract_measurement_snapshot(
            candidate,
            extraction_mode="reference_peak_plane",
            reference_peak_index=reference_peak_index,
            pipeline_mode=pipeline_mode,
        )
        reference_snapshot = extract_measurement_snapshot(
            reference,
            extraction_mode="reference_peak_plane",
            reference_peak_index=reference_peak_index,
            pipeline_mode=pipeline_mode,
        )
    else:
        candidate_snapshot = extract_measurement_snapshot(
            candidate,
            extraction_mode="self_peak",
            pipeline_mode=pipeline_mode,
        )
        reference_snapshot = reference_self_peak
    return {
        "candidate_mode": candidate_snapshot["mode"],
        "reference_mode": reference_snapshot["mode"],
        "measurement_pipeline_mode": pipeline_mode,
        "measurement_protocol_kind": reference_snapshot["measurement_protocol_kind"],
        "measurement_protocol_note": reference_snapshot["measurement_protocol_note"],
        "measurement_extraction_mode": extraction_mode,
        "candidate_snapshot": candidate_snapshot,
        "reference_snapshot": reference_snapshot,
        "measured_lateral_width_bias_um": float(
            candidate_snapshot["measured_lateral_fwhm_um"] - reference_snapshot["measured_lateral_fwhm_um"]
        ),
        "measured_axial_width_bias_um": float(
            candidate_snapshot["measured_axial_fwhm_opd_um"] - reference_snapshot["measured_axial_fwhm_opd_um"]
        ),
        "measured_peak_shift_um": float(
            candidate_snapshot["measured_lateral_peak_x_um"] - reference_snapshot["measured_lateral_peak_x_um"]
        ),
        "measured_centroid_shift_um": float(
            candidate_snapshot["measured_lateral_centroid_um"] - reference_snapshot["measured_lateral_centroid_um"]
        ),
        "measured_axial_centroid_shift_um": float(
            candidate_snapshot["measured_axial_centroid_opd_um"] - reference_snapshot["measured_axial_centroid_opd_um"]
        ),
        "measured_sidelobe_distortion": float(
            candidate_snapshot["measured_sidelobe_energy_fraction"] - reference_snapshot["measured_sidelobe_energy_fraction"]
        ),
        "measured_raw_peak_relative_delta": float(
            abs(candidate_snapshot["raw_peak_intensity"] - reference_snapshot["raw_peak_intensity"])
            / (abs(reference_snapshot["raw_peak_intensity"]) + 1e-30)
        ),
    }


__all__ = [
    "MEASUREMENT_EXTRACTION_MODES",
    "MEASUREMENT_PIPELINE_MODES",
    "compare_measurement_snapshots",
    "extract_measurement_snapshot",
]
