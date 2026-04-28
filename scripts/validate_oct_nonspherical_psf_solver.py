import argparse
import importlib.util
import json
import os
import sys
import warnings
from pathlib import Path

import numpy as np

SCRIPT_DIR = Path(__file__).resolve().parent


def _load_solver_module():
    module = sys.modules.get("oct_nonspherical_psf_solver")
    if module is not None:
        return module
    try:
        import oct_nonspherical_psf_solver as imported

        return imported
    except ModuleNotFoundError:
        for candidate_name in ("oct_nonspherical_psf_solver.py", "01_oct_nonspherical_psf_solver.py"):
            candidate_path = SCRIPT_DIR / candidate_name
            if candidate_path.exists():
                spec = importlib.util.spec_from_file_location("oct_nonspherical_psf_solver", candidate_path)
                if spec is None or spec.loader is None:
                    continue
                module = importlib.util.module_from_spec(spec)
                sys.modules["oct_nonspherical_psf_solver"] = module
                spec.loader.exec_module(module)
                return module
        raise


_SOLVER = _load_solver_module()
from apps.report_paths import build_report_path, resolve_reports_dir

FULL_NA_BASELINE_MODE = _SOLVER.FULL_NA_BASELINE_MODE
FULL_NA_DISPLAY_LABEL = _SOLVER.FULL_NA_DISPLAY_LABEL
GridConfig = _SOLVER.GridConfig
LOW_NA_ASYMPTOTIC_MODE = _SOLVER.LOW_NA_ASYMPTOTIC_MODE
LOW_NA_BASELINE_MODE = _SOLVER.LOW_NA_BASELINE_MODE
LOW_NA_DISPLAY_LABEL = _SOLVER.LOW_NA_DISPLAY_LABEL
SCHEMA_VERSION = _SOLVER.SCHEMA_VERSION
SolverConfig = _SOLVER.SolverConfig
SourceConfig = _SOLVER.SourceConfig
VECTOR_BRIDGE_DISPLAY_LABEL = _SOLVER.VECTOR_BRIDGE_DISPLAY_LABEL
VECTOR_BRIDGE_MODE = _SOLVER.VECTOR_BRIDGE_MODE
build_full_na_axial_views = _SOLVER.build_full_na_axial_views
build_bfp_angle_map = _SOLVER.build_bfp_angle_map
calc_sz = _SOLVER.calc_sz
derive_na_geometry_series = _SOLVER.derive_na_geometry_series
ensure_tmatrix_loaded = _SOLVER.ensure_tmatrix_loaded
load_round6_extension = _SOLVER.load_round6_extension
mie_backscatter_spectrum = _SOLVER.mie_backscatter_spectrum
normalize_intensity = _SOLVER.normalize_intensity
reset_material_support_warning_cache = _SOLVER.reset_material_support_warning_cache
resolve_material_model = _SOLVER.resolve_material_model
solve_oct_particle_response = _SOLVER.solve_oct_particle_response
tmatrix_backscatter_spectrum = _SOLVER.tmatrix_backscatter_spectrum
probe_tmatrix_backend = _SOLVER.probe_tmatrix_backend

def _resolve_legacy_milestone1_path():
    env_path = os.environ.get("OCT_LEGACY_MILESTONE1")
    if env_path:
        return Path(env_path)
    runtime_root = _SOLVER.resolve_runtime_root(__file__)
    for candidate in (
        runtime_root / "run_tmatrix_oct_direct_milestone1.py",
        runtime_root / "legacy" / "run_tmatrix_oct_direct_milestone1.py",
    ):
        if candidate.exists():
            return candidate
    return None


LEGACY_MILESTONE1 = _resolve_legacy_milestone1_path()
REPORTS_DIR = resolve_reports_dir(__file__)
DEFAULT_REPORT_VERSION_TAG = "round6p1"


DEFAULT_JSON_REPORT_PATH = build_report_path(DEFAULT_REPORT_VERSION_TAG, "validation_summary", "json", anchor_path=__file__)
DEFAULT_FAILURE_SUMMARY_PATH = build_report_path(DEFAULT_REPORT_VERSION_TAG, "validation_failure_summary", "txt", anchor_path=__file__)
DEFAULT_BASIS_PROJECTION_REPORT_PATH = REPORTS_DIR / "round6p1_basis_projection_diagnostics.json"
DEFAULT_COEFFICIENT_RECOVERY_REPORT_PATH = REPORTS_DIR / "round6p1_basis_coefficient_recovery.json"
DEFAULT_FIT_SENSITIVITY_REPORT_PATH = REPORTS_DIR / "round6p1_effective_channel_fit_sensitivity.json"
DEFAULT_COEFFICIENT_INJECTION_REPORT_PATH = REPORTS_DIR / "round6p1_coefficient_injection_diagnostics.json"
DEFAULT_COEFFICIENT_MAP_AUDIT_REPORT_PATH = REPORTS_DIR / "round6p1_coefficient_map_audit.json"
DEFAULT_COEFFICIENT_MAP_ABLATION_REPORT_PATH = REPORTS_DIR / "round6p1_coefficient_map_ablation.json"
DEFAULT_COEFFICIENT_MAP_STABILITY_REPORT_PATH = REPORTS_DIR / "round6p1_coefficient_map_stability.json"
DEFAULT_FIT_STRATEGY_ABLATION_REPORT_PATH = REPORTS_DIR / "round6p1_effective_channel_fit_strategy_ablation.json"
DEFAULT_SLICE_AXIS_CROSSCHECK_REPORT_PATH = REPORTS_DIR / "round6p1_lateral_slice_axis_crosscheck.json"
DEFAULT_MEASUREMENT_PROTOCOL_REPORT_PATH = REPORTS_DIR / "round6p1_measurement_protocol_bias.json"
DEFAULT_PARTICLE_SIZE_SWEEP_REPORT_PATH = REPORTS_DIR / "round6p1_particle_size_sweep.json"
DEFAULT_CP310_EVIDENCE_READINESS_REPORT_PATH = REPORTS_DIR / "round6p1_cp310_evidence_rebuild_readiness.json"
FORBIDDEN_SCHEMA_KEYS = {"metrics", "envelope_metrics", "axial_intensity", "axial_envelope", "z_um"}
REQUIRED_SCHEMA_KEYS = {
    "approximation_label",
    "solver_output_kind",
    "quantity_kind",
    "axial_axis_kind",
    "schema_version",
    "paper_safe",
}
ROUND6P1_REPRESENTATIVE_CASES = [
    {
        "name": "sphere_low_na_low_contrast",
        "description": "Sphere, low NA, low contrast. This should be the easiest alignment case.",
        "source": {"lambda0_nm": 855.0, "fwhm_nm": 56.0, "n_lambda": 121},
        "grid": {"z_span_um": 18.0, "n_z": 601, "x_span_um": 4.0, "n_x": 41, "na": 0.02, "n_bfp_dense": 41, "n_bfp_sparse": 7},
        "solver": {
            "particle_material": 1.45,
            "medium_material": 1.40,
            "diameter_nm": 220.0,
            "eps": 0.0,
            "beta_deg": 0.0,
            "incident_mode": "linear_x",
            "detection_mode": "co_pol",
        },
    },
    {
        "name": "mild_shape_medium_tilt",
        "description": "Small deformation with medium tilt. This is where bridge and asymptotic should start to separate.",
        "source": {"lambda0_nm": 855.0, "fwhm_nm": 56.0, "n_lambda": 181},
        "grid": {"z_span_um": 18.0, "n_z": 601, "x_span_um": 4.0, "n_x": 41, "na": 0.04, "n_bfp_dense": 41, "n_bfp_sparse": 7},
        "solver": {
            "particle_material": 2.48,
            "medium_material": 1.40,
            "diameter_nm": 250.0,
            "eps": 0.08,
            "beta_deg": 20.0,
            "incident_mode": "linear_x",
            "detection_mode": "co_pol",
        },
    },
    {
        "name": "failure_domain_high_tilt_high_contrast",
        "description": "Larger tilt and higher contrast. This should sit inside the asymptotic failure domain.",
        "source": {"lambda0_nm": 855.0, "fwhm_nm": 56.0, "n_lambda": 181},
        "grid": {"z_span_um": 20.0, "n_z": 601, "x_span_um": 6.0, "n_x": 61, "na": 0.08, "n_bfp_dense": 41, "n_bfp_sparse": 7},
        "solver": {
            "particle_material": 2.48,
            "medium_material": 1.40,
            "diameter_nm": 300.0,
            "eps": 0.18,
            "beta_deg": 50.0,
            "incident_mode": "linear_x",
            "detection_mode": "co_pol",
        },
    },
]

ROUND6P1_COEFFICIENT_MAP_GENERALIZATION_CASES = ROUND6P1_REPRESENTATIVE_CASES + [
    {
        "name": "mild_shape_higher_na_transition",
        "description": "Mild deformation with higher NA to test whether a shared coefficient map generalizes beyond the base representative panel.",
        "source": {"lambda0_nm": 855.0, "fwhm_nm": 56.0, "n_lambda": 181},
        "grid": {"z_span_um": 18.0, "n_z": 601, "x_span_um": 5.0, "n_x": 51, "na": 0.06, "n_bfp_dense": 41, "n_bfp_sparse": 7},
        "solver": {
            "particle_material": 2.48,
            "medium_material": 1.40,
            "diameter_nm": 270.0,
            "eps": 0.08,
            "beta_deg": 25.0,
            "incident_mode": "linear_x",
            "detection_mode": "co_pol",
        },
    },
    {
        "name": "high_contrast_lower_tilt_transition",
        "description": "High contrast with lower tilt than the failure-domain case to probe whether shared coefficient maps stabilize in the odd-path transition region.",
        "source": {"lambda0_nm": 855.0, "fwhm_nm": 56.0, "n_lambda": 181},
        "grid": {"z_span_um": 20.0, "n_z": 601, "x_span_um": 6.0, "n_x": 61, "na": 0.08, "n_bfp_dense": 41, "n_bfp_sparse": 7},
        "solver": {
            "particle_material": 2.48,
            "medium_material": 1.40,
            "diameter_nm": 300.0,
            "eps": 0.18,
            "beta_deg": 35.0,
            "incident_mode": "linear_x",
            "detection_mode": "co_pol",
        },
    },
]


def load_legacy_module():
    if LEGACY_MILESTONE1 is None or not LEGACY_MILESTONE1.exists():
        return None
    spec = importlib.util.spec_from_file_location("legacy_tmatrix_m1", LEGACY_MILESTONE1)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def aligned_complex_residual(reference, candidate):
    reference = np.asarray(reference, dtype=np.complex128)
    candidate = np.asarray(candidate, dtype=np.complex128)
    scale = np.vdot(reference, candidate) / (np.vdot(reference, reference) + 1e-30)
    residual = np.linalg.norm(candidate - scale * reference) / (np.linalg.norm(candidate) + 1e-30)
    return {
        "scale_abs": float(np.abs(scale)),
        "scale_phase_rad": float(np.angle(scale)),
        "relative_residual": float(residual),
    }


def image_difference_diagnostics(label, sample_a, sample_b):
    image_a = sample_a["image"]
    image_b = sample_b["image"]
    delta = np.abs(image_a - image_b)
    peak_index = np.unravel_index(int(np.argmax(delta)), delta.shape)
    diagnostics = {
        "label": label,
        "fwhm_delta_um": abs(sample_a["fwhm_opd_um"] - sample_b["fwhm_opd_um"]),
        "psr_delta_db": abs(sample_a["psr_db"] - sample_b["psr_db"]) if np.isfinite(sample_a["psr_db"]) and np.isfinite(sample_b["psr_db"]) else 0.0,
        "peakline_x_delta_um": abs(sample_a["peakline_x_um"] - sample_b["peakline_x_um"]),
        "centroid_opd_delta_um": abs(sample_a["centroid_opd_um"] - sample_b["centroid_opd_um"]),
        "image_relative_l2": float(np.linalg.norm(image_a - image_b) / (np.linalg.norm(image_b) + 1e-30)),
        "max_abs_delta": float(delta[peak_index]),
        "max_delta_index": [int(peak_index[0]), int(peak_index[1])],
        "max_delta_x_um": float(sample_b["x_um"][peak_index[0]]),
        "max_delta_opd_um": float(sample_b["opd_um"][peak_index[1]]),
    }
    raw_image_a = sample_a.get("raw_image")
    raw_image_b = sample_b.get("raw_image")
    if raw_image_a is not None and raw_image_b is not None:
        raw_delta = np.abs(raw_image_a - raw_image_b)
        raw_peak_index = np.unravel_index(int(np.argmax(raw_delta)), raw_delta.shape)
        raw_peak_a = float(np.max(raw_image_a))
        raw_peak_b = float(np.max(raw_image_b))
        diagnostics.update(
            {
                "raw_image_relative_l2": float(np.linalg.norm(raw_image_a - raw_image_b) / (np.linalg.norm(raw_image_b) + 1e-30)),
                "raw_peak_relative_delta": float(abs(raw_peak_a - raw_peak_b) / (abs(raw_peak_b) + 1e-30)),
                "raw_max_abs_delta": float(raw_delta[raw_peak_index]),
                "raw_max_delta_index": [int(raw_peak_index[0]), int(raw_peak_index[1])],
                "raw_max_delta_x_um": float(sample_b["x_um"][raw_peak_index[0]]),
                "raw_max_delta_opd_um": float(sample_b["opd_um"][raw_peak_index[1]]),
            }
        )
    return diagnostics


def snapshot_for_comparison(result):
    return {
        "peakline_x_um": float(result["peakline_x_um"]),
        "fwhm_opd_um": float(result["axial_intensity_metrics"]["fwhm_opd_um"]),
        "psr_db": float(result["axial_intensity_metrics"]["psr_db"]),
        "centroid_opd_um": float(result["axial_intensity_metrics"]["centroid_opd_um"]),
        "x_um": result["x_um"],
        "opd_um": result["opd_um"],
        "image": result["intensity_xz"],
        "raw_image": result["raw_intensity_xz"],
    }


def run_round6p1_case(case_definition, *, mode, **solver_overrides):
    source = SourceConfig(**case_definition["source"])
    grid = GridConfig(**case_definition["grid"])
    solver_kwargs = dict(case_definition["solver"])
    solver_kwargs.update(solver_overrides)
    solver = SolverConfig(mode=mode, **solver_kwargs)
    return solve_oct_particle_response(source, grid, solver)


def apply_complex_field_match_scale(candidate_result, reference_result):
    candidate_field = np.asarray(candidate_result["field_xz"], dtype=np.complex128)
    reference_field = np.asarray(reference_result["field_xz"], dtype=np.complex128)
    scale = np.vdot(candidate_field, reference_field) / (np.vdot(candidate_field, candidate_field) + 1e-30)
    scaled_field = scale * candidate_field
    raw_envelope_xz = np.abs(scaled_field)
    raw_intensity_xz = raw_envelope_xz ** 2
    envelope_xz, envelope_scale = normalize_intensity(raw_envelope_xz, return_scale=True)
    intensity_xz, intensity_scale = normalize_intensity(raw_intensity_xz, return_scale=True)
    axial_views = build_full_na_axial_views(
        np.asarray(candidate_result["x_um"], dtype=float),
        np.asarray(candidate_result["opd_um"], dtype=float),
        raw_intensity_xz,
        raw_envelope_xz,
    )
    scaled_result = dict(candidate_result)
    scaled_result.update(
        {
            "field_xz": scaled_field,
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
            "experimental_post_scale_factor_complex": complex(scale),
            "experimental_post_scale_factor_abs": float(np.abs(scale)),
            "experimental_post_scale_factor_phase_rad": float(np.angle(scale)),
            "experimental_post_scale_kind": "least_squares_complex_field_match_to_reference",
        }
    )
    normalization = dict(candidate_result.get("normalization", {}))
    scales = dict(normalization.get("scales", {}))
    scales.update(
        {
            "envelope_xz_peak": float(envelope_scale),
            "intensity_xz_peak": float(intensity_scale),
            "centerline_axial_envelope_peak": float(np.max(axial_views["centerline_raw_axial_envelope"])),
            "centerline_axial_intensity_peak": float(np.max(axial_views["centerline_raw_axial_intensity"])),
            "peakline_axial_envelope_peak": float(np.max(axial_views["peakline_raw_axial_envelope"])),
            "peakline_axial_intensity_peak": float(np.max(axial_views["peakline_raw_axial_intensity"])),
        }
    )
    normalization["scales"] = scales
    scaled_result["normalization"] = normalization
    return scaled_result


def summarize_directional_first_order_ablation(case_payloads):
    successful_cases = []
    for payload in case_payloads:
        tensor = payload["tensor_closure"]
        directional = payload["directional_field_expansion_scaled"]
        directional_first = payload["directional_field_expansion_first_order_scaled"]
        peakline_improved = (
            directional_first["peakline_x_delta_um"] < tensor["peakline_x_delta_um"]
            and directional_first["peakline_x_delta_um"] <= directional["peakline_x_delta_um"]
        )
        image_not_worse = directional_first["image_relative_l2"] <= min(
            tensor["image_relative_l2"],
            directional["image_relative_l2"],
        ) + 0.02
        raw_stable = directional_first.get("raw_peak_relative_delta", np.inf) <= (
            max(
                tensor.get("raw_peak_relative_delta", 0.0),
                directional.get("raw_peak_relative_delta", 0.0),
            )
            + 0.10
        )
        if peakline_improved and image_not_worse and raw_stable:
            successful_cases.append(payload["case_name"])
    return {
        "directional_first_order_is_promising": len(successful_cases) >= 2,
        "directional_first_order_successful_cases": successful_cases,
        "directional_first_order_success_count": len(successful_cases),
        "directional_first_order_total_cases": len(case_payloads),
    }


def relative_axial_l2(result_a, result_b):
    profile_a = np.asarray(result_a["peakline_axial_intensity"], dtype=float)
    profile_b = np.asarray(result_b["peakline_axial_intensity"], dtype=float)
    return float(np.linalg.norm(profile_a - profile_b) / (np.linalg.norm(profile_b) + 1e-30))


def schema_regression_diagnostics(result):
    forbidden_present = sorted(FORBIDDEN_SCHEMA_KEYS.intersection(result.keys()))
    required_missing = sorted(key for key in REQUIRED_SCHEMA_KEYS if key not in result)
    return {
        "mode": result["mode"],
        "forbidden_present": forbidden_present,
        "required_missing": required_missing,
        "schema_version": result.get("schema_version"),
        "paper_safe": bool(result.get("paper_safe")),
    }


def paper_facing_contract_diagnostics(result):
    required_common = [
        "approximation_label",
        "axial_axis_kind",
        "depth_convention_helper",
        "material_support",
        "material_range_notes",
        "normalization",
        "peakline_raw_axial_intensity",
        "raw_intensity_xz",
        "raw_peak_intensity",
        "schema_version",
        "paper_safe",
    ]
    missing = [key for key in required_common if key not in result]
    normalization = result.get("normalization", {})
    for key in ("normalization_scope", "absolute_amplitude_supported"):
        if key not in normalization:
            missing.append(f"normalization.{key}")
    if result["mode"] in {VECTOR_BRIDGE_MODE, LOW_NA_ASYMPTOTIC_MODE}:
        for key in ("channel_projection_kind", "channel_definition", "projection_semantics_note", "polarization_model_kind", "supported_polarization_modes"):
            if key not in result:
                missing.append(key)
    if result["mode"] == LOW_NA_ASYMPTOTIC_MODE:
        for key in (
            "mu2_profile_kind",
            "mu2_profile_semantics_note",
            "mu2_profile_complexity_note",
            "mu2_profile_phase_span_rad",
            "mu2_profile_real_imag_ratio",
            "mu2_profile_complexity_summary",
            "mu2_reference_wavelength_nm",
            "mu2_wavelength_model",
            "mu2_wavelength_model_note",
            "mu2_wavelength_samples_nm",
            "mu2_dispersion_sensitivity",
            "mu2_tensor_reference",
            "mu2_tensor_profile",
            "C2_abs_std_over_azimuth",
            "C2_tensor_k",
            "C2_tensor_kind",
            "C2_slice_k",
            "C2_slice_projection_note",
            "second_order_model",
            "per_azimuth_B_k",
            "per_azimuth_C2_k",
            "C2_azimuth_variation_summary",
            "C2_scalar_validity_indicator",
            "second_order_closure_note",
        ):
            if key not in result:
                missing.append(key)
    helper = result.get("depth_convention_helper", {})
    return {
        "mode": result["mode"],
        "missing": missing,
        "depth_axis_status": helper.get("depth_axis_status"),
        "paper_safe": bool(result.get("paper_safe")),
        "schema_version": result.get("schema_version"),
    }


def annotate_check_statuses(report):
    informational_checks = {
        "asymptotic_mu2_wavelength_freeze_diagnostic",
        "low_na_asymptotic_second_order_model_ablation",
        "low_na_asymptotic_directional_first_order_ablation",
        "low_na_asymptotic_slice_projected_stability_gate",
        "low_na_asymptotic_slice_projected_fidelity_gate",
        "low_na_asymptotic_mu2_wavelength_model_ablation",
        "low_na_asymptotic_lateral_shift_model_ablation",
    }
    for check in report.get("checks", []):
        name = check.get("name", "")
        if check.get("skipped"):
            check["status"] = "informational"
            check["status_category"] = "diagnostic"
            check["status_reason"] = "Check was skipped because a required dependency or backend was unavailable."
            continue
        if name in informational_checks:
            check["status"] = "informational"
            check["status_category"] = "diagnostic"
            check["status_reason"] = "Diagnostic check recorded for machine-readable tracking; interpret its payload rather than the boolean alone."
            continue
        if name == "low_na_asymptotic_failure_domain_lateral_shift":
            if check.get("passed"):
                check["status"] = "expected_fail"
                check["status_category"] = "model_limit"
                check["status_reason"] = "Failure-domain benchmark confirmed the expected lateral divergence of the current asymptotic model."
            else:
                check["status"] = "fail"
                check["status_category"] = "hard_gate"
                check["status_reason"] = "Failure-domain benchmark did not show the expected model-limit divergence."
            continue
        if name == "low_na_asymptotic_absolute_alignment_gate":
            if check.get("passed"):
                check["status"] = "pass"
                check["status_category"] = "model_limit"
                check["status_reason"] = "Current asymptotic model satisfied the present low-NA absolute-alignment threshold."
            else:
                check["status"] = "fail"
                check["status_category"] = "model_limit"
                check["status_reason"] = "Current asymptotic model remains insufficiently laterally faithful to pass the absolute alignment gate."
            continue
        if name == "mu2_dispersion_current_case_gate":
            check["status"] = "pass" if check.get("passed") else "fail"
            check["status_category"] = "model_limit"
            check["status_reason"] = (
                "The current frozen-at-lambda0 mu2 approximation stayed inside the present dispersion-sensitivity tolerance for the active validation case."
                if check.get("passed")
                else "The current frozen-at-lambda0 mu2 approximation exceeded the present dispersion-sensitivity tolerance for the active validation case."
            )
            continue
        if name == "mu2_dispersion_benchmark_design":
            check["status"] = "pass" if check.get("passed") else "informational"
            check["status_category"] = "diagnostic"
            check["status_reason"] = (
                "The control/stress benchmark design is behaving as expected and can be used to interpret frozen-mu2 sensitivity safely."
                if check.get("passed")
                else "The control/stress benchmark design did not cleanly separate a trivial control from a nontrivial stress case."
            )
            continue
        if name == "low_na_asymptotic_first_order_not_prioritized":
            check["status"] = "informational"
            check["status_category"] = "model_direction"
            check["status_reason"] = "Current evidence does not support prioritizing the first_order lateral shift branch."
            continue
        if name == "low_na_asymptotic_endpoint_refit_not_prioritized":
            check["status"] = "informational"
            check["status_category"] = "model_direction"
            check["status_reason"] = "Current evidence does not support prioritizing the endpoint_refit mu2 branch."
            continue
        check["status"] = "pass" if check.get("passed") else "fail"
        check["status_category"] = "hard_gate"
        check["status_reason"] = "Hard validation gate under the current validator thresholds."


DOMINANT_ERROR_THRESHOLDS = {
    "lateral_shift": ("peakline_x_delta_um", 0.5),
    "axial_centroid": ("centroid_opd_delta_um", 0.25),
    "axial_width": ("fwhm_delta_um", 0.25),
    "sidelobe_structure": ("psr_delta_db", 1.5),
    "raw_amplitude": ("raw_peak_relative_delta", 0.75),
}


def _dominant_error_severity(bucket, value, threshold):
    value = abs(float(value))
    threshold = max(float(threshold), 1e-30)
    if bucket == "raw_amplitude":
        # Use a logarithmic scale so large raw-return ratios do not drown out
        # slice-shift diagnostics that are the main modeling target here.
        return float(np.log10(1.0 + value) / threshold)
    return value / threshold


def classify_dominant_error_bucket(diagnostics):
    diagnostics = diagnostics or {}
    best_bucket = "unavailable"
    best_metric = None
    best_value = None
    best_severity = -1.0
    for bucket, (metric, threshold) in DOMINANT_ERROR_THRESHOLDS.items():
        if metric not in diagnostics:
            continue
        value = float(diagnostics[metric])
        severity = _dominant_error_severity(bucket, value, threshold)
        if severity > best_severity:
            best_bucket = bucket
            best_metric = metric
            best_value = value
            best_severity = severity
    return {
        "dominant_error_bucket": best_bucket,
        "dominant_error_metric": best_metric,
        "dominant_error_value": best_value,
        "dominant_error_severity": float(best_severity if best_severity >= 0.0 else 0.0),
    }


MODEL_LIMIT_PRIORITY = [
    "low_na_asymptotic_absolute_alignment_gate",
    "mu2_dispersion_current_case_gate",
]


def _find_check(report, name):
    for check in report.get("checks", []):
        if check.get("name") == name:
            return check
    return None


def summarize_open_model_limits(report):
    failed_model_limits = [
        check
        for check in report.get("checks", [])
        if check.get("status") == "fail" and check.get("status_category") == "model_limit"
    ]
    if not failed_model_limits:
        return {
            "most_critical_open_model_limit": "none",
            "recommended_next_action": "no_open_model_limit",
        }
    priority_index = {name: idx for idx, name in enumerate(MODEL_LIMIT_PRIORITY)}
    most_critical = min(
        failed_model_limits,
        key=lambda check: (priority_index.get(check.get("name"), len(priority_index)), check.get("name", "")),
    )
    most_critical_name = most_critical.get("name", "unknown_model_limit")
    dominant = most_critical.get("dominant_error_summary") or {}
    dominant_bucket = dominant.get("dominant_error_bucket")
    first_order_check = _find_check(report, "low_na_asymptotic_first_order_not_prioritized")
    slice_fidelity_check = _find_check(report, "low_na_asymptotic_slice_projected_fidelity_gate")
    directional_first_order_is_promising = bool(report.get("directional_first_order_is_promising"))
    if most_critical_name == "low_na_asymptotic_absolute_alignment_gate" and dominant_bucket == "lateral_shift":
        if directional_first_order_is_promising:
            return {
                "most_critical_open_model_limit": most_critical_name,
                "recommended_next_action": "investigate_directional_first_order_field_basis",
            }
        if first_order_check is not None and slice_fidelity_check is not None and not bool(slice_fidelity_check.get("passed")):
            return {
                "most_critical_open_model_limit": most_critical_name,
                "recommended_next_action": "promote_directional_model_freedom",
            }
        if first_order_check is not None:
            return {
                "most_critical_open_model_limit": most_critical_name,
                "recommended_next_action": "do_not_prioritize_first_order_shift_branch",
            }
    if dominant_bucket == "axial_width":
        return {
            "most_critical_open_model_limit": most_critical_name,
            "recommended_next_action": "revisit_mu2_or_second_order_closure",
        }
    if dominant_bucket == "raw_amplitude":
        return {
            "most_critical_open_model_limit": most_critical_name,
            "recommended_next_action": "revisit_scaling_and_raw_amplitude_consistency",
        }
    if most_critical_name == "mu2_dispersion_current_case_gate":
        return {
            "most_critical_open_model_limit": most_critical_name,
            "recommended_next_action": "revisit_mu2_or_second_order_closure",
        }
    return {
        "most_critical_open_model_limit": most_critical_name,
        "recommended_next_action": "inspect_open_model_limit_manually",
    }


def load_basis_projection_summary(report_path=DEFAULT_BASIS_PROJECTION_REPORT_PATH):
    report_path = Path(report_path)
    if not report_path.exists():
        return None
    try:
        payload = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    action = payload.get("recommended_next_action") or payload.get("basis_projection_recommended_next_action")
    if not action:
        return None
    return {
        "basis_projection_recommended_next_action": action,
        "basis_projection_case_names": payload.get(
            "basis_projection_case_names",
            [case.get("case_name") for case in payload.get("basis_projection_cases", [])],
        ),
    }


def load_coefficient_recovery_summary(report_path=DEFAULT_COEFFICIENT_RECOVERY_REPORT_PATH):
    report_path = Path(report_path)
    if not report_path.exists():
        return None
    try:
        payload = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    action = payload.get("recommended_next_action") or payload.get("coefficient_recovery_recommended_next_action")
    if not action:
        return None
    return {
        "coefficient_recovery_recommended_next_action": action,
        "coefficient_recovery_case_names": payload.get(
            "coefficient_recovery_case_names",
            [case.get("case_name") for case in payload.get("coefficient_recovery_cases", [])],
        ),
        "basis_conditioning_status": payload.get("basis_conditioning_status", "unknown"),
        "basis_conditioning_note": payload.get("basis_conditioning_note"),
        "coefficient_interpretability_status": payload.get("coefficient_interpretability_status", "unknown"),
        "coefficient_interpretability_note": payload.get("coefficient_interpretability_note"),
        "shared_scale_consistency_status": payload.get("shared_scale_consistency_status", "unknown"),
        "shared_scale_consistency_note": payload.get("shared_scale_consistency_note"),
    }


def load_fit_sensitivity_summary(report_path=DEFAULT_FIT_SENSITIVITY_REPORT_PATH):
    report_path = Path(report_path)
    if not report_path.exists():
        return None
    try:
        payload = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    action = payload.get("recommended_next_action") or payload.get("fit_sensitivity_recommended_next_action")
    if not action:
        return None
    return {
        "fit_sensitivity_recommended_next_action": action,
        "fit_sensitivity_case_names": payload.get(
            "fit_sensitivity_case_names",
            [case.get("case_name") for case in payload.get("fit_sensitivity_cases", [])],
        ),
        "fit_window_sensitivity_status": payload.get("fit_window_sensitivity_status", "unknown"),
    }


def load_coefficient_injection_summary(report_path=DEFAULT_COEFFICIENT_INJECTION_REPORT_PATH):
    report_path = Path(report_path)
    if not report_path.exists():
        return None
    try:
        payload = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    action = payload.get("recommended_next_action") or payload.get("coefficient_injection_recommended_next_action")
    if not action:
        return None
    return {
        "coefficient_injection_recommended_next_action": action,
        "coefficient_injection_case_names": payload.get(
            "coefficient_injection_case_names",
            [case.get("case_name") for case in payload.get("coefficient_injection_cases", [])],
        ),
    }


def load_coefficient_map_audit_summary(report_path=DEFAULT_COEFFICIENT_MAP_AUDIT_REPORT_PATH):
    report_path = Path(report_path)
    if not report_path.exists():
        return None
    try:
        payload = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    action = payload.get("recommended_next_action") or payload.get("coefficient_map_audit_recommended_next_action")
    if not action:
        return None
    return {
        "coefficient_map_audit_recommended_next_action": action,
        "coefficient_map_audit_case_names": payload.get(
            "coefficient_map_audit_case_names",
            [case.get("case_name") for case in payload.get("coefficient_map_audit_cases", [])],
        ),
        "coefficient_map_models": payload.get("coefficient_map_models", []),
    }


def load_coefficient_map_ablation_summary(report_path=DEFAULT_COEFFICIENT_MAP_ABLATION_REPORT_PATH):
    report_path = Path(report_path)
    if not report_path.exists():
        return None
    try:
        payload = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    action = payload.get("recommended_next_action") or payload.get("coefficient_map_ablation_recommended_next_action")
    if not action:
        return None
    return {
        "coefficient_map_ablation_recommended_next_action": action,
        "coefficient_map_ablation_case_names": payload.get(
            "coefficient_map_ablation_case_names",
            [case.get("case_name") for case in payload.get("coefficient_map_ablation_cases", [])],
        ),
        "coefficient_map_ablation_models": payload.get("coefficient_map_ablation_models", []),
        "best_ablated_coefficient_map_model_id": payload.get("best_ablated_coefficient_map_model_id"),
    }


def load_coefficient_map_stability_summary(report_path=DEFAULT_COEFFICIENT_MAP_STABILITY_REPORT_PATH):
    report_path = Path(report_path)
    if not report_path.exists():
        return None
    try:
        payload = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    action = payload.get("recommended_next_action") or payload.get("coefficient_map_stability_recommended_next_action")
    if not action:
        return None
    return {
        "coefficient_map_stability_recommended_next_action": action,
        "coefficient_map_stability_case_names": payload.get("coefficient_map_stability_case_names", []),
        "coefficient_map_models": payload.get("coefficient_map_models", []),
        "best_generalizing_model_id": payload.get("best_generalizing_model_id"),
        "promoted_shared_map_model_id": payload.get("promoted_shared_map_model_id"),
        "promoted_shared_map_runtime_scope": payload.get("promoted_shared_map_runtime_scope"),
        "promoted_shared_map_runtime_contract_status": payload.get("promoted_shared_map_runtime_contract_status"),
        "promoted_shared_map_runtime_supported_lateral_shift_models": payload.get(
            "promoted_shared_map_runtime_supported_lateral_shift_models",
            [],
        ),
        "promoted_shared_map_runtime_lateral_shift_constraint": payload.get(
            "promoted_shared_map_runtime_lateral_shift_constraint",
            "unknown",
        ),
        "promoted_shared_map_runtime_shift_target": payload.get(
            "promoted_shared_map_runtime_shift_target",
            "none",
        ),
    }


def load_fit_strategy_ablation_summary(report_path=DEFAULT_FIT_STRATEGY_ABLATION_REPORT_PATH):
    report_path = Path(report_path)
    if not report_path.exists():
        return None
    try:
        payload = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    action = payload.get("recommended_next_action") or payload.get("effective_channel_fit_strategy_recommended_next_action")
    if not action:
        return None
    return {
        "effective_channel_fit_strategy_recommended_next_action": action,
        "effective_channel_fit_strategy_case_names": payload.get(
            "effective_channel_fit_strategy_case_names",
            [case.get("case_name") for case in payload.get("effective_channel_fit_strategy_cases", [])],
        ),
        "effective_channel_fit_strategy_status": payload.get("effective_channel_fit_strategy_status", "unknown"),
    }


def load_slice_axis_crosscheck_summary(report_path=DEFAULT_SLICE_AXIS_CROSSCHECK_REPORT_PATH):
    report_path = Path(report_path)
    if not report_path.exists():
        return None
    try:
        payload = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    action = payload.get("recommended_next_action") or payload.get("slice_axis_crosscheck_recommended_next_action")
    if not action:
        return None
    return {
        "slice_axis_crosscheck_recommended_next_action": action,
        "slice_axis_crosscheck_status": payload.get("slice_axis_crosscheck_status", "unknown"),
        "slice_axis_crosscheck_case_names": payload.get(
            "slice_axis_crosscheck_case_names",
            [case.get("case_name") for case in payload.get("slice_axis_crosscheck_cases", [])],
        ),
        "slice_axis_crosscheck_note": payload.get("slice_axis_crosscheck_note"),
    }


def load_measurement_protocol_summary(report_path=DEFAULT_MEASUREMENT_PROTOCOL_REPORT_PATH):
    report_path = Path(report_path)
    if not report_path.exists():
        return None
    try:
        payload = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if payload.get("status") == "skipped" or payload.get("skipped"):
        return {
            "measurement_pipeline_guidance_status": "skipped",
            "measurement_pipeline_evidence_status": "skipped",
            "measurement_pipeline_skip_reason": payload.get("reason") or payload.get("skip_reason"),
            "measurement_pipeline_modes": payload.get("measurement_pipeline_modes", []),
            "measurement_case_names": [],
            "measurement_default_pipeline_modes": [],
            "measurement_pipeline_default_mode": "unknown",
            "measurement_report_schema_versions": [],
            "measurement_pipeline_failures": {},
            "fd_oct_measurement_wrapper_status": "skipped",
            "measurement_reference_arm_policy": "unknown",
            "measurement_reference_arm_policy_status": "unknown",
            "measurement_reference_arm_policy_note": "Measurement report was skipped before reference-arm policy could be evaluated.",
            "measurement_fd_oct_depth_conventions": [],
            "measurement_fd_oct_k_axis_kinds": [],
            "measurement_fd_oct_medium_index_policies": [],
            "measurement_fd_oct_reference_arm_policies": [],
            "measurement_fd_oct_depth_policy_status": "skipped",
        }
    cases = payload.get("cases", [])
    pipeline_modes = list(payload.get("measurement_pipeline_modes", []))
    if not pipeline_modes:
        pipeline_modes = sorted(
            {
                mode
                for case in cases
                for mode in case.get("measurement_pipeline_modes", [])
            }
        )
    case_names = [case.get("name") for case in cases if case.get("name")]
    default_modes = sorted(
        {
            case.get("default_measurement_pipeline_mode")
            for case in cases
            if case.get("default_measurement_pipeline_mode")
        }
    )
    if len(default_modes) == 1:
        default_pipeline_mode = default_modes[0]
    elif default_modes:
        default_pipeline_mode = "mixed"
    else:
        default_pipeline_mode = "unknown"
    schema_versions = sorted(
        {
            case.get("measurement_report_schema_version")
            for case in cases
            if case.get("measurement_report_schema_version")
        }
    )
    pipeline_failures = {
        case.get("name", f"case_{idx}"): case.get("pipeline_failures", {})
        for idx, case in enumerate(cases)
        if case.get("pipeline_failures")
    }
    measurement_rows = []
    for case in cases:
        pipeline_comparison_modes = case.get("pipeline_comparison_modes", {})
        if not isinstance(pipeline_comparison_modes, dict):
            continue
        for extraction_rows_by_mode in pipeline_comparison_modes.values():
            if not isinstance(extraction_rows_by_mode, dict):
                continue
            for rows in extraction_rows_by_mode.values():
                if isinstance(rows, list):
                    measurement_rows.extend(row for row in rows if isinstance(row, dict))
    fd_oct_depth_conventions = sorted(
        {
            row.get("fd_oct_depth_convention")
            for row in measurement_rows
            if row.get("fd_oct_depth_convention")
        }
    )
    fd_oct_k_axis_kinds = sorted(
        {
            row.get("fd_oct_k_axis_kind")
            for row in measurement_rows
            if row.get("fd_oct_k_axis_kind")
        }
    )
    fd_oct_medium_index_policies = sorted(
        {
            row.get("fd_oct_medium_index_policy")
            for row in measurement_rows
            if row.get("fd_oct_medium_index_policy")
        }
    )
    fd_oct_reference_arm_policies = sorted(
        {
            row.get("fd_oct_reference_arm_policy")
            for row in measurement_rows
            if row.get("fd_oct_reference_arm_policy")
        }
    )
    fd_oct_in_chain = "fd_oct_reconstruction" in pipeline_modes or "fd_oct_reconstruction" in default_modes
    return {
        "measurement_pipeline_guidance_status": "explicit_report_used",
        "measurement_pipeline_evidence_status": (
            "fd_oct_reconstruction_in_evidence_chain"
            if fd_oct_in_chain
            else "solver_output_adapter_only"
        ),
        "measurement_pipeline_modes": pipeline_modes,
        "measurement_case_names": case_names,
        "measurement_default_pipeline_modes": default_modes,
        "measurement_pipeline_default_mode": default_pipeline_mode,
        "measurement_report_schema_versions": schema_versions,
        "measurement_pipeline_failures": pipeline_failures,
        "fd_oct_measurement_wrapper_status": (
            "integrated_in_measurement_evidence_chain"
            if fd_oct_in_chain
            else "not_integrated"
        ),
        "measurement_reference_arm_policy": "flat_synthetic_reference_when_measurement_reference_arm_field_absent",
        "measurement_reference_arm_policy_status": "scaffold_not_calibrated",
        "measurement_reference_arm_policy_note": (
            "The FD-OCT reconstruction path uses measurement_reference_arm_field when supplied; current solver "
            "outputs normally omit a calibrated reference arm, so the wrapper uses a flat synthetic reference. "
            "Absolute-amplitude and PSR conclusions remain measurement-scaffold diagnostics until this policy is calibrated."
        ),
        "measurement_fd_oct_depth_conventions": fd_oct_depth_conventions,
        "measurement_fd_oct_k_axis_kinds": fd_oct_k_axis_kinds,
        "measurement_fd_oct_medium_index_policies": fd_oct_medium_index_policies,
        "measurement_fd_oct_reference_arm_policies": fd_oct_reference_arm_policies,
        "measurement_fd_oct_depth_policy_status": (
            "medium_effective_k_geometric_depth_axis_declared"
            if any("medium_effective" in value for value in fd_oct_k_axis_kinds)
            and any("geometric_roundtrip" in value for value in fd_oct_depth_conventions)
            else (
                "medium_effective_k_axis_declared_depth_axis_unverified"
                if any("medium_effective" in value for value in fd_oct_k_axis_kinds)
                else "vacuum_or_not_reported"
            )
        ),
    }


def load_particle_size_sweep_summary_from_payload(payload: dict | None):
    if not payload:
        return None
    if payload.get("status") == "skipped" or payload.get("skipped"):
        return {
            "particle_size_sweep_guidance_status": "skipped",
            "particle_size_sweep_status": "skipped",
            "particle_size_sweep_skip_reason": payload.get("reason") or payload.get("skip_reason"),
            "particle_size_sweep_case_count": 0,
            "particle_size_sweep_ok_count": 0,
            "particle_size_sweep_failed_count": 0,
            "particle_size_sweep_diameter_range_nm": None,
            "particle_size_sweep_mode": payload.get("mode_requested", "unknown"),
            "particle_size_sweep_recommended_next_action": "particle_size_sweep_skipped",
            "particle_size_sweep_scope_note": "Particle-size sweep report was skipped.",
        }
    return {
        "particle_size_sweep_guidance_status": payload.get(
            "particle_size_sweep_guidance_status",
            "explicit_report_used",
        ),
        "particle_size_sweep_status": payload.get("sweep_status", "unknown"),
        "particle_size_sweep_case_count": payload.get("sweep_case_count", len(payload.get("rows", []))),
        "particle_size_sweep_ok_count": payload.get("ok_count"),
        "particle_size_sweep_failed_count": payload.get("failed_count"),
        "particle_size_sweep_diameter_range_nm": payload.get("diameter_range_nm"),
        "particle_size_sweep_mode": payload.get("mode_requested", "unknown"),
        "particle_size_sweep_metric_ranges": payload.get("metric_ranges", {}),
        "particle_size_sweep_recommended_next_action": payload.get(
            "recommended_next_action",
            "inspect_particle_size_sweep_report",
        ),
        "particle_size_sweep_scope_note": payload.get(
            "particle_lateral_scattering_scope_note",
            "Particle-size sweep scope note was not provided.",
        ),
        "particle_size_sweep_schema_version": payload.get("sweep_schema_version"),
        "particle_size_sweep_skip_reason": None,
    }


def load_particle_size_sweep_summary(report_path=DEFAULT_PARTICLE_SIZE_SWEEP_REPORT_PATH):
    report_path = Path(report_path)
    if not report_path.exists():
        return None
    try:
        payload = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return load_particle_size_sweep_summary_from_payload(payload)


def load_cp310_evidence_readiness_summary(report_path=DEFAULT_CP310_EVIDENCE_READINESS_REPORT_PATH):
    report_path = Path(report_path)
    if not report_path.exists():
        return None
    try:
        payload = json.loads(report_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    selected = payload.get("selected_probe") or {}
    classification = selected.get("classification") or {}
    return {
        "cp310_evidence_rebuild_readiness_status": payload.get(
            "readiness_status",
            classification.get("readiness_status", "unknown"),
        ),
        "cp310_evidence_rebuild_ready": bool(payload.get("ready_to_rebuild")),
        "cp310_evidence_rebuild_reason": classification.get("reason"),
        "cp310_evidence_rebuild_selected_python_command": selected.get("python_command"),
        "cp310_evidence_rebuild_selected_python_version": selected.get("python_version"),
        "cp310_evidence_rebuild_status": payload.get("rebuild_status", "not_requested"),
        "cp310_evidence_rebuild_execute_requested": bool(payload.get("execute_requested")),
    }


def apply_basis_projection_summary(report: dict, basis_projection_summary=None) -> dict:
    open_model_limit_action = report.get("recommended_next_action", "inspect_open_model_limit_manually")
    final_action = open_model_limit_action
    final_source = "open_model_limit"
    report.pop("basis_projection_recommended_next_action", None)
    if basis_projection_summary:
        report["basis_projection_case_names"] = basis_projection_summary.get("basis_projection_case_names", [])
        basis_action = basis_projection_summary.get("basis_projection_recommended_next_action")
        if basis_action:
            final_action = basis_action
            final_source = "basis_projection"
        report["basis_projection_guidance_status"] = "explicit_report_used"
    else:
        report.setdefault("basis_projection_case_names", [])
        report["basis_projection_guidance_status"] = "not_supplied"
    report["recommended_next_action"] = final_action
    report["final_recommended_next_action"] = final_action
    report["final_recommended_next_action_source"] = final_source
    return summarize_evidence_dependency_status(report)


def apply_coefficient_recovery_summary(report: dict, coefficient_recovery_summary=None) -> dict:
    final_action = report.get("final_recommended_next_action", report.get("recommended_next_action", "inspect_open_model_limit_manually"))
    final_source = report.get("final_recommended_next_action_source", "open_model_limit")
    report.pop("coefficient_recovery_recommended_next_action", None)
    if coefficient_recovery_summary:
        report["coefficient_recovery_case_names"] = coefficient_recovery_summary.get("coefficient_recovery_case_names", [])
        report["basis_conditioning_status"] = coefficient_recovery_summary.get("basis_conditioning_status", "unknown")
        report["basis_conditioning_note"] = coefficient_recovery_summary.get("basis_conditioning_note")
        report["coefficient_interpretability_status"] = coefficient_recovery_summary.get("coefficient_interpretability_status", "unknown")
        report["coefficient_interpretability_note"] = coefficient_recovery_summary.get("coefficient_interpretability_note")
        report["shared_scale_consistency_status"] = coefficient_recovery_summary.get("shared_scale_consistency_status", "unknown")
        report["shared_scale_consistency_note"] = coefficient_recovery_summary.get("shared_scale_consistency_note")
        coefficient_action = coefficient_recovery_summary.get("coefficient_recovery_recommended_next_action")
        if coefficient_action:
            final_action = coefficient_action
            final_source = "coefficient_recovery"
        report["coefficient_recovery_guidance_status"] = "explicit_report_used"
    else:
        report.setdefault("coefficient_recovery_case_names", [])
        report.setdefault("basis_conditioning_status", "unknown")
        report.setdefault("basis_conditioning_note", "Coefficient-recovery report not supplied.")
        report.setdefault("coefficient_interpretability_status", "unknown")
        report.setdefault("coefficient_interpretability_note", "Coefficient-recovery report not supplied.")
        report.setdefault("shared_scale_consistency_status", "unknown")
        report.setdefault("shared_scale_consistency_note", "Coefficient-recovery report not supplied.")
        report["coefficient_recovery_guidance_status"] = "not_supplied"
    report["recommended_next_action"] = final_action
    report["final_recommended_next_action"] = final_action
    report["final_recommended_next_action_source"] = final_source
    return summarize_evidence_dependency_status(report)


def apply_fit_sensitivity_summary(report: dict, fit_sensitivity_summary=None) -> dict:
    final_action = report.get("final_recommended_next_action", report.get("recommended_next_action", "inspect_open_model_limit_manually"))
    final_source = report.get("final_recommended_next_action_source", "open_model_limit")
    if fit_sensitivity_summary:
        report["fit_sensitivity_case_names"] = fit_sensitivity_summary.get("fit_sensitivity_case_names", [])
        report["fit_sensitivity_recommended_next_action"] = fit_sensitivity_summary.get(
            "fit_sensitivity_recommended_next_action",
            "fit_sensitivity_not_supplied",
        )
        if report["fit_sensitivity_recommended_next_action"] == "debug_effective_channel_fit_window_before_usage_mapping":
            final_action = report["fit_sensitivity_recommended_next_action"]
            final_source = "fit_sensitivity"
        report["fit_window_sensitivity_status"] = fit_sensitivity_summary.get(
            "fit_window_sensitivity_status",
            "dominant"
            if report["fit_sensitivity_recommended_next_action"] == "debug_effective_channel_fit_window_before_usage_mapping"
            else "not_dominant",
        )
        report["fit_sensitivity_guidance_status"] = "explicit_report_used"
    else:
        report.setdefault("fit_sensitivity_case_names", [])
        report.setdefault("fit_sensitivity_recommended_next_action", "fit_sensitivity_not_supplied")
        report.setdefault("fit_window_sensitivity_status", "unknown")
        report["fit_sensitivity_guidance_status"] = "not_supplied"
    report["recommended_next_action"] = final_action
    report["final_recommended_next_action"] = final_action
    report["final_recommended_next_action_source"] = final_source
    return report


def apply_coefficient_injection_summary(report: dict, coefficient_injection_summary=None) -> dict:
    final_action = report.get("final_recommended_next_action", report.get("recommended_next_action", "inspect_open_model_limit_manually"))
    final_source = report.get("final_recommended_next_action_source", "open_model_limit")
    report.pop("coefficient_injection_recommended_next_action", None)
    if coefficient_injection_summary:
        report["coefficient_injection_case_names"] = coefficient_injection_summary.get("coefficient_injection_case_names", [])
        injection_action = coefficient_injection_summary.get("coefficient_injection_recommended_next_action")
        if injection_action:
            final_action = injection_action
            final_source = "coefficient_injection"
        report["coefficient_injection_guidance_status"] = "explicit_report_used"
    else:
        report.setdefault("coefficient_injection_case_names", [])
        report["coefficient_injection_guidance_status"] = "not_supplied"
    report["recommended_next_action"] = final_action
    report["final_recommended_next_action"] = final_action
    report["final_recommended_next_action_source"] = final_source
    report = summarize_evidence_dependency_status(report)
    return summarize_guidance_confidence(report)


def apply_coefficient_map_audit_summary(report: dict, coefficient_map_audit_summary=None) -> dict:
    final_action = report.get("final_recommended_next_action", report.get("recommended_next_action", "inspect_open_model_limit_manually"))
    final_source = report.get("final_recommended_next_action_source", "open_model_limit")
    if coefficient_map_audit_summary:
        report["coefficient_map_audit_case_names"] = coefficient_map_audit_summary.get("coefficient_map_audit_case_names", [])
        report["coefficient_map_models"] = coefficient_map_audit_summary.get("coefficient_map_models", [])
        report["coefficient_map_audit_recommended_next_action"] = coefficient_map_audit_summary.get(
            "coefficient_map_audit_recommended_next_action",
            "coefficient_map_audit_not_supplied",
        )
        audit_action = report["coefficient_map_audit_recommended_next_action"]
        if audit_action:
            final_action = audit_action
            final_source = "coefficient_map_audit"
        report["coefficient_map_audit_guidance_status"] = "explicit_report_used"
    else:
        report.setdefault("coefficient_map_audit_case_names", [])
        report.setdefault("coefficient_map_models", [])
        report.setdefault("coefficient_map_audit_recommended_next_action", "coefficient_map_audit_not_supplied")
        report["coefficient_map_audit_guidance_status"] = "not_supplied"
    report["recommended_next_action"] = final_action
    report["final_recommended_next_action"] = final_action
    report["final_recommended_next_action_source"] = final_source
    report = summarize_evidence_dependency_status(report)
    return summarize_guidance_confidence(report)


def apply_coefficient_map_stability_summary(report: dict, coefficient_map_stability_summary=None) -> dict:
    final_action = report.get("final_recommended_next_action", report.get("recommended_next_action", "inspect_open_model_limit_manually"))
    final_source = report.get("final_recommended_next_action_source", "open_model_limit")
    if coefficient_map_stability_summary:
        report["coefficient_map_stability_case_names"] = coefficient_map_stability_summary.get(
            "coefficient_map_stability_case_names",
            [],
        )
        report["coefficient_map_stability_recommended_next_action"] = coefficient_map_stability_summary.get(
            "coefficient_map_stability_recommended_next_action",
            "coefficient_map_stability_not_supplied",
        )
        report["best_generalizing_coefficient_map_model_id"] = coefficient_map_stability_summary.get(
            "best_generalizing_model_id",
        )
        report["promoted_shared_map_model_id"] = coefficient_map_stability_summary.get(
            "promoted_shared_map_model_id",
        )
        report["promoted_shared_map_runtime_scope"] = coefficient_map_stability_summary.get(
            "promoted_shared_map_runtime_scope",
            "unknown",
        )
        report["promoted_shared_map_runtime_contract_status"] = coefficient_map_stability_summary.get(
            "promoted_shared_map_runtime_contract_status",
            "unknown",
        )
        report["promoted_shared_map_runtime_supported_lateral_shift_models"] = coefficient_map_stability_summary.get(
            "promoted_shared_map_runtime_supported_lateral_shift_models",
            [],
        )
        report["promoted_shared_map_runtime_lateral_shift_constraint"] = coefficient_map_stability_summary.get(
            "promoted_shared_map_runtime_lateral_shift_constraint",
            "unknown",
        )
        report["promoted_shared_map_runtime_shift_target"] = coefficient_map_stability_summary.get(
            "promoted_shared_map_runtime_shift_target",
            "none",
        )
        if coefficient_map_stability_summary.get("coefficient_map_models"):
            report["coefficient_map_models"] = coefficient_map_stability_summary.get("coefficient_map_models", [])
        stability_action = report["coefficient_map_stability_recommended_next_action"]
        if stability_action:
            final_action = stability_action
            final_source = "coefficient_map_stability"
        report["coefficient_map_stability_guidance_status"] = "explicit_report_used"
    else:
        report.setdefault("coefficient_map_stability_case_names", [])
        report.setdefault("coefficient_map_stability_recommended_next_action", "coefficient_map_stability_not_supplied")
        report.setdefault("best_generalizing_coefficient_map_model_id", None)
        report.setdefault("promoted_shared_map_model_id", None)
        report.setdefault("promoted_shared_map_runtime_scope", "unknown")
        report.setdefault("promoted_shared_map_runtime_contract_status", "unknown")
        report.setdefault("promoted_shared_map_runtime_supported_lateral_shift_models", [])
        report.setdefault("promoted_shared_map_runtime_lateral_shift_constraint", "unknown")
        report.setdefault("promoted_shared_map_runtime_shift_target", "none")
        report["coefficient_map_stability_guidance_status"] = "not_supplied"
    report["recommended_next_action"] = final_action
    report["final_recommended_next_action"] = final_action
    report["final_recommended_next_action_source"] = final_source
    report = summarize_evidence_dependency_status(report)
    return summarize_guidance_confidence(report)


def apply_coefficient_map_ablation_summary(report: dict, coefficient_map_ablation_summary=None) -> dict:
    final_action = report.get("final_recommended_next_action", report.get("recommended_next_action", "inspect_open_model_limit_manually"))
    final_source = report.get("final_recommended_next_action_source", "open_model_limit")
    if coefficient_map_ablation_summary:
        report["coefficient_map_ablation_case_names"] = coefficient_map_ablation_summary.get(
            "coefficient_map_ablation_case_names",
            [],
        )
        report["coefficient_map_ablation_models"] = coefficient_map_ablation_summary.get(
            "coefficient_map_ablation_models",
            [],
        )
        report["best_ablated_coefficient_map_model_id"] = coefficient_map_ablation_summary.get(
            "best_ablated_coefficient_map_model_id",
        )
        report["coefficient_map_ablation_recommended_next_action"] = coefficient_map_ablation_summary.get(
            "coefficient_map_ablation_recommended_next_action",
            "coefficient_map_ablation_not_supplied",
        )
        ablation_action = report["coefficient_map_ablation_recommended_next_action"]
        if ablation_action:
            final_action = ablation_action
            final_source = "coefficient_map_ablation"
        report["coefficient_map_ablation_guidance_status"] = "explicit_report_used"
    else:
        report.setdefault("coefficient_map_ablation_case_names", [])
        report.setdefault("coefficient_map_ablation_models", [])
        report.setdefault("best_ablated_coefficient_map_model_id", None)
        report.setdefault("coefficient_map_ablation_recommended_next_action", "coefficient_map_ablation_not_supplied")
        report["coefficient_map_ablation_guidance_status"] = "not_supplied"
    report["recommended_next_action"] = final_action
    report["final_recommended_next_action"] = final_action
    report["final_recommended_next_action_source"] = final_source
    report = summarize_evidence_dependency_status(report)
    return summarize_guidance_confidence(report)


def apply_fit_strategy_ablation_summary(report: dict, fit_strategy_ablation_summary=None) -> dict:
    final_action = report.get("final_recommended_next_action", report.get("recommended_next_action", "inspect_open_model_limit_manually"))
    final_source = report.get("final_recommended_next_action_source", "open_model_limit")
    if fit_strategy_ablation_summary:
        report["effective_channel_fit_strategy_case_names"] = fit_strategy_ablation_summary.get(
            "effective_channel_fit_strategy_case_names",
            [],
        )
        report["effective_channel_fit_strategy_recommended_next_action"] = fit_strategy_ablation_summary.get(
            "effective_channel_fit_strategy_recommended_next_action",
            "fit_strategy_ablation_not_supplied",
        )
        if report["effective_channel_fit_strategy_recommended_next_action"] == "promote_joint_low_order_fit_strategy":
            final_action = report["effective_channel_fit_strategy_recommended_next_action"]
            final_source = "fit_strategy_ablation"
        report["effective_channel_fit_strategy_status"] = fit_strategy_ablation_summary.get(
            "effective_channel_fit_strategy_status",
            "joint_promising"
            if report["effective_channel_fit_strategy_recommended_next_action"] == "promote_joint_low_order_fit_strategy"
            else "not_yet_decisive",
        )
        report["effective_channel_fit_strategy_guidance_status"] = "explicit_report_used"
    else:
        report.setdefault("effective_channel_fit_strategy_case_names", [])
        report.setdefault("effective_channel_fit_strategy_recommended_next_action", "fit_strategy_ablation_not_supplied")
        report.setdefault("effective_channel_fit_strategy_status", "unknown")
        report["effective_channel_fit_strategy_guidance_status"] = "not_supplied"
    report["recommended_next_action"] = final_action
    report["final_recommended_next_action"] = final_action
    report["final_recommended_next_action_source"] = final_source
    return report


def apply_slice_axis_crosscheck_summary(report: dict, slice_axis_crosscheck_summary=None) -> dict:
    final_action = report.get("final_recommended_next_action", report.get("recommended_next_action", "inspect_open_model_limit_manually"))
    final_source = report.get("final_recommended_next_action_source", "open_model_limit")
    if slice_axis_crosscheck_summary:
        report["slice_axis_crosscheck_case_names"] = slice_axis_crosscheck_summary.get("slice_axis_crosscheck_case_names", [])
        report["slice_axis_crosscheck_recommended_next_action"] = slice_axis_crosscheck_summary.get(
            "slice_axis_crosscheck_recommended_next_action",
            "slice_axis_crosscheck_not_supplied",
        )
        report["slice_axis_crosscheck_status"] = slice_axis_crosscheck_summary.get("slice_axis_crosscheck_status", "unknown")
        report["slice_axis_crosscheck_note"] = slice_axis_crosscheck_summary.get("slice_axis_crosscheck_note")
        if report["slice_axis_crosscheck_recommended_next_action"] == "verify_slice_direction_dependence_before_usage_mapping":
            final_action = report["slice_axis_crosscheck_recommended_next_action"]
            final_source = "slice_axis_crosscheck"
        report["slice_axis_crosscheck_guidance_status"] = "explicit_report_used"
    else:
        report.setdefault("slice_axis_crosscheck_case_names", [])
        report.setdefault("slice_axis_crosscheck_recommended_next_action", "slice_axis_crosscheck_not_supplied")
        report.setdefault("slice_axis_crosscheck_status", "unknown")
        report.setdefault("slice_axis_crosscheck_note", "Slice-axis cross-check report not supplied.")
        report["slice_axis_crosscheck_guidance_status"] = "not_supplied"
    report["recommended_next_action"] = final_action
    report["final_recommended_next_action"] = final_action
    report["final_recommended_next_action_source"] = final_source
    return report


def apply_measurement_protocol_summary(report: dict, measurement_protocol_summary=None) -> dict:
    if measurement_protocol_summary:
        report["measurement_pipeline_case_names"] = measurement_protocol_summary.get("measurement_case_names", [])
        report["measurement_pipeline_modes"] = measurement_protocol_summary.get("measurement_pipeline_modes", [])
        report["measurement_default_pipeline_modes"] = measurement_protocol_summary.get(
            "measurement_default_pipeline_modes",
            [],
        )
        report["measurement_pipeline_default_mode"] = measurement_protocol_summary.get(
            "measurement_pipeline_default_mode",
            "unknown",
        )
        report["measurement_pipeline_evidence_status"] = measurement_protocol_summary.get(
            "measurement_pipeline_evidence_status",
            "unknown",
        )
        report["fd_oct_measurement_wrapper_status"] = measurement_protocol_summary.get(
            "fd_oct_measurement_wrapper_status",
            "unknown",
        )
        report["measurement_report_schema_versions"] = measurement_protocol_summary.get(
            "measurement_report_schema_versions",
            [],
        )
        report["measurement_pipeline_failures"] = measurement_protocol_summary.get("measurement_pipeline_failures", {})
        report["measurement_reference_arm_policy"] = measurement_protocol_summary.get(
            "measurement_reference_arm_policy",
            "unknown",
        )
        report["measurement_reference_arm_policy_status"] = measurement_protocol_summary.get(
            "measurement_reference_arm_policy_status",
            "unknown",
        )
        report["measurement_reference_arm_policy_note"] = measurement_protocol_summary.get(
            "measurement_reference_arm_policy_note",
            "Measurement report did not include a reference-arm policy note.",
        )
        report["measurement_fd_oct_depth_conventions"] = measurement_protocol_summary.get(
            "measurement_fd_oct_depth_conventions",
            [],
        )
        report["measurement_fd_oct_k_axis_kinds"] = measurement_protocol_summary.get(
            "measurement_fd_oct_k_axis_kinds",
            [],
        )
        report["measurement_fd_oct_medium_index_policies"] = measurement_protocol_summary.get(
            "measurement_fd_oct_medium_index_policies",
            [],
        )
        report["measurement_fd_oct_reference_arm_policies"] = measurement_protocol_summary.get(
            "measurement_fd_oct_reference_arm_policies",
            [],
        )
        report["measurement_fd_oct_depth_policy_status"] = measurement_protocol_summary.get(
            "measurement_fd_oct_depth_policy_status",
            "unknown",
        )
        report["measurement_pipeline_skip_reason"] = measurement_protocol_summary.get("measurement_pipeline_skip_reason")
        report["measurement_pipeline_guidance_status"] = measurement_protocol_summary.get(
            "measurement_pipeline_guidance_status",
            "explicit_report_used",
        )
    else:
        report.setdefault("measurement_pipeline_case_names", [])
        report.setdefault("measurement_pipeline_modes", [])
        report.setdefault("measurement_default_pipeline_modes", [])
        report.setdefault("measurement_pipeline_default_mode", "not_supplied")
        report.setdefault("measurement_pipeline_evidence_status", "not_supplied")
        report.setdefault("fd_oct_measurement_wrapper_status", "unknown")
        report.setdefault("measurement_report_schema_versions", [])
        report.setdefault("measurement_pipeline_failures", {})
        report.setdefault("measurement_reference_arm_policy", "not_supplied")
        report.setdefault("measurement_reference_arm_policy_status", "unknown")
        report.setdefault("measurement_reference_arm_policy_note", "Measurement protocol report not supplied.")
        report.setdefault("measurement_fd_oct_depth_conventions", [])
        report.setdefault("measurement_fd_oct_k_axis_kinds", [])
        report.setdefault("measurement_fd_oct_medium_index_policies", [])
        report.setdefault("measurement_fd_oct_reference_arm_policies", [])
        report.setdefault("measurement_fd_oct_depth_policy_status", "not_supplied")
        report.setdefault("measurement_pipeline_skip_reason", None)
        report["measurement_pipeline_guidance_status"] = "not_supplied"
    return report


def apply_particle_size_sweep_summary(report: dict, particle_size_sweep_summary=None) -> dict:
    if particle_size_sweep_summary:
        report["particle_size_sweep_guidance_status"] = particle_size_sweep_summary.get(
            "particle_size_sweep_guidance_status",
            "explicit_report_used",
        )
        report["particle_size_sweep_status"] = particle_size_sweep_summary.get("particle_size_sweep_status", "unknown")
        report["particle_size_sweep_case_count"] = particle_size_sweep_summary.get("particle_size_sweep_case_count", 0)
        report["particle_size_sweep_ok_count"] = particle_size_sweep_summary.get("particle_size_sweep_ok_count")
        report["particle_size_sweep_failed_count"] = particle_size_sweep_summary.get("particle_size_sweep_failed_count")
        report["particle_size_sweep_diameter_range_nm"] = particle_size_sweep_summary.get(
            "particle_size_sweep_diameter_range_nm"
        )
        report["particle_size_sweep_mode"] = particle_size_sweep_summary.get("particle_size_sweep_mode", "unknown")
        report["particle_size_sweep_metric_ranges"] = particle_size_sweep_summary.get(
            "particle_size_sweep_metric_ranges",
            {},
        )
        report["particle_size_sweep_recommended_next_action"] = particle_size_sweep_summary.get(
            "particle_size_sweep_recommended_next_action",
            "inspect_particle_size_sweep_report",
        )
        report["particle_size_sweep_scope_note"] = particle_size_sweep_summary.get(
            "particle_size_sweep_scope_note",
            "Particle-size sweep scope note was not provided.",
        )
        report["particle_size_sweep_schema_version"] = particle_size_sweep_summary.get(
            "particle_size_sweep_schema_version"
        )
        report["particle_size_sweep_skip_reason"] = particle_size_sweep_summary.get("particle_size_sweep_skip_reason")
        if report["particle_size_sweep_status"] in {"all_failed", "partial_failures"}:
            report["particle_size_sweep_failure_action"] = "inspect_particle_size_sweep_failures"
    else:
        report.setdefault("particle_size_sweep_guidance_status", "not_supplied")
        report.setdefault("particle_size_sweep_status", "not_supplied")
        report.setdefault("particle_size_sweep_case_count", 0)
        report.setdefault("particle_size_sweep_ok_count", None)
        report.setdefault("particle_size_sweep_failed_count", None)
        report.setdefault("particle_size_sweep_diameter_range_nm", None)
        report.setdefault("particle_size_sweep_mode", "not_supplied")
        report.setdefault("particle_size_sweep_metric_ranges", {})
        report.setdefault("particle_size_sweep_recommended_next_action", "not_supplied")
        report.setdefault("particle_size_sweep_scope_note", "Particle-size sweep report not supplied.")
        report.setdefault("particle_size_sweep_schema_version", None)
        report.setdefault("particle_size_sweep_skip_reason", None)
    return report


def apply_cp310_evidence_readiness_summary(report: dict, cp310_evidence_readiness_summary=None) -> dict:
    if cp310_evidence_readiness_summary:
        report.update(cp310_evidence_readiness_summary)
        if cp310_evidence_readiness_summary.get("cp310_evidence_rebuild_ready"):
            action = "run_controlled_cp310_evidence_rebuild_with_execute"
            guidance_status = "ready_for_controlled_rebuild"
        else:
            action = "install_or_select_cp310_runtime_or_portable_tmatrix_backend"
            guidance_status = "fresh_evidence_rebuild_blocked_by_runtime"
        report["cp310_evidence_rebuild_recommended_next_action"] = action
        report["cp310_evidence_rebuild_guidance_status"] = guidance_status
    else:
        report.setdefault("cp310_evidence_rebuild_readiness_status", "not_supplied")
        report.setdefault("cp310_evidence_rebuild_ready", False)
        report.setdefault("cp310_evidence_rebuild_reason", None)
        report.setdefault("cp310_evidence_rebuild_selected_python_command", None)
        report.setdefault("cp310_evidence_rebuild_selected_python_version", None)
        report.setdefault("cp310_evidence_rebuild_status", "not_supplied")
        report.setdefault("cp310_evidence_rebuild_execute_requested", False)
        report.setdefault("cp310_evidence_rebuild_recommended_next_action", "cp310_readiness_not_supplied")
        report.setdefault("cp310_evidence_rebuild_guidance_status", "not_supplied")
    return report


def summarize_evidence_dependency_status(report: dict) -> dict:
    basis_status = report.get("basis_projection_guidance_status", "not_supplied")
    coefficient_status = report.get("coefficient_recovery_guidance_status", "not_supplied")
    if basis_status == "explicit_report_used" and coefficient_status == "explicit_report_used":
        report["evidence_dependency_status"] = "complete"
    elif basis_status == "explicit_report_used":
        report["evidence_dependency_status"] = "coefficient_missing"
    elif coefficient_status == "explicit_report_used":
        report["evidence_dependency_status"] = "basis_missing"
    else:
        report["evidence_dependency_status"] = "both_missing"
    return report


def summarize_guidance_confidence(report: dict) -> dict:
    statuses = {
        "basis": report.get("basis_projection_guidance_status", "not_supplied"),
        "coefficient": report.get("coefficient_recovery_guidance_status", "not_supplied"),
        "injection": report.get("coefficient_injection_guidance_status", "not_supplied"),
        "coefficient_map_audit": report.get("coefficient_map_audit_guidance_status", "not_supplied"),
        "coefficient_map_stability": report.get("coefficient_map_stability_guidance_status", "not_supplied"),
        "coefficient_map_ablation": report.get("coefficient_map_ablation_guidance_status", "not_supplied"),
        "fit_sensitivity": report.get("fit_sensitivity_guidance_status", "not_supplied"),
        "fit_strategy": report.get("effective_channel_fit_strategy_guidance_status", "not_supplied"),
        "slice_axis_crosscheck": report.get("slice_axis_crosscheck_guidance_status", "not_supplied"),
        "measurement_protocol": report.get("measurement_pipeline_guidance_status", "not_supplied"),
        "particle_size_sweep": report.get("particle_size_sweep_guidance_status", "not_supplied"),
    }
    explicit_count = sum(status == "explicit_report_used" for status in statuses.values())
    if explicit_count == len(statuses):
        report["guidance_confidence"] = "full_evidence"
    elif explicit_count > 0:
        report["guidance_confidence"] = "partial_evidence"
    else:
        report["guidance_confidence"] = "fallback_only"
    return report


def compact_first_order_validity_summary(result: dict) -> dict:
    return {
        "first_order_invalid_fraction": float(result.get("first_order_invalid_fraction", 0.0)),
        "first_order_finite_fraction": float(result.get("first_order_finite_fraction", 1.0)),
        "first_order_B_k_small_fraction": float(result.get("first_order_B_k_small_fraction", 0.0)),
        "first_order_B_k_small_threshold": float(result.get("first_order_B_k_small_threshold", 0.0)),
        "note": result.get("first_order_shift_validity_summary", {}).get("first_order_validity_note")
        or result.get("first_order_validity_note"),
    }


def _strict_gate_mode_enabled(strict_gates=False):
    if strict_gates:
        return True
    env_value = os.environ.get("OCT_VALIDATE_STRICT", "")
    return env_value.strip().lower() in {"1", "true", "yes", "on"}


def _synthetic_dispersive_medium_factory(lambda0_um: float, slope_per_um: float):
    return lambda l_um, lambda0_um=lambda0_um, slope_per_um=slope_per_um: 1.40 + slope_per_um * (float(l_um) - lambda0_um)


def build_mu2_dispersion_benchmark_cases():
    low_na_module = load_round6_extension("11_low_na_asymptotic.py", "round6_low_na_asymptotic_validator")
    control_case = low_na_module.summarize_mu2_wavelength_freeze_sensitivity(
        lambda0_nm=855.0,
        fwhm_nm=180.0,
        medium_material=1.40,
        na=0.08,
        obliquity_kind="sqrt_cos",
        n_pupil=49,
    )
    stress_case = low_na_module.summarize_mu2_wavelength_freeze_sensitivity(
        lambda0_nm=855.0,
        fwhm_nm=180.0,
        medium_material=_synthetic_dispersive_medium_factory(0.855, 0.6),
        na=0.08,
        obliquity_kind="sqrt_cos",
        n_pupil=49,
    )
    return {
        "constant_material_control_case": {
            "medium_material": "1.40 (constant)",
            **control_case,
        },
        "dispersive_material_stress_case": {
            "medium_material": "synthetic_linear_dispersion(n = 1.40 + 0.6*(lambda_um-0.855))",
            **stress_case,
        },
    }


def exit_code_from_report(report, *, strict_gates=False):
    strict_mode = _strict_gate_mode_enabled(strict_gates)
    for check in report.get("checks", []):
        if check.get("status") != "fail":
            continue
        category = check.get("status_category")
        if category == "hard_gate":
            return 1
        if strict_mode and category == "model_limit":
            return 1
    return 0


SUMMARY_METRIC_THRESHOLDS = {
    "image_relative_l2": 0.25,
    "peakline_x_delta_um": 0.5,
    "centroid_opd_delta_um": 0.25,
    "fwhm_delta_um": 0.25,
    "psr_delta_db": 1.5,
}


def _collect_comparison_records(value, path="report"):
    records = []
    if isinstance(value, dict):
        metric_subset = {key: float(value[key]) for key in SUMMARY_METRIC_THRESHOLDS if key in value}
        if metric_subset:
            records.append(
                {
                    "label": value.get("label", path),
                    **metric_subset,
                }
            )
        for key, item in value.items():
            records.extend(_collect_comparison_records(item, f"{path}.{key}"))
    elif isinstance(value, list):
        for idx, item in enumerate(value):
            records.extend(_collect_comparison_records(item, f"{path}[{idx}]"))
    return records


def _select_worst_metric(record):
    best_key = None
    best_value = None
    best_severity = -1.0
    for key, threshold in SUMMARY_METRIC_THRESHOLDS.items():
        if key not in record:
            continue
        severity = abs(float(record[key])) / max(float(threshold), 1e-30)
        if severity > best_severity:
            best_key = key
            best_value = float(record[key])
            best_severity = severity
    return best_key, best_value, best_severity


def summarize_worst_case_metrics(report):
    records = _collect_comparison_records(report)
    if not records:
        return {
            "worst_case_name": "unavailable",
            "worst_metric_name": "unavailable",
            "worst_metric_value": None,
            "worst_case_summary": {},
            "dominant_error_bucket": "unavailable",
            "dominant_error_metric": "unavailable",
            "dominant_error_value": None,
            "dominant_error_severity": 0.0,
        }
    worst_record = max(records, key=lambda item: _select_worst_metric(item)[2])
    worst_metric, worst_value, _ = _select_worst_metric(worst_record)
    summary = dict(worst_record)
    dominant = classify_dominant_error_bucket(worst_record)
    return {
        "worst_case_name": worst_record.get("label", "unavailable"),
        "worst_metric_name": worst_metric or "unavailable",
        "worst_metric_value": None if worst_metric is None else float(worst_value),
        "worst_case_summary": summary,
        **dominant,
    }


def render_failure_summary(report):
    hard_failures = [check["name"] for check in report.get("checks", []) if check.get("status") == "fail" and check.get("status_category") == "hard_gate"]
    model_limit_failures = [check["name"] for check in report.get("checks", []) if check.get("status") == "fail" and check.get("status_category") == "model_limit"]
    expected_failures = [check["name"] for check in report.get("checks", []) if check.get("status") == "expected_fail"]
    worst_summary = summarize_worst_case_metrics(report)
    worst_case_line = f"Worst case: {worst_summary['worst_case_name']}"
    worst_metric_line = "Worst metric: unavailable"
    if worst_summary["worst_metric_name"] != "unavailable" and worst_summary["worst_metric_value"] is not None:
        worst_metric_line = f"Worst metric: {worst_summary['worst_metric_name']} = {worst_summary['worst_metric_value']:.6g}"
    dominant_bucket_line = "Dominant error bucket: unavailable"
    dominant_candidates = []
    for check in report.get("checks", []):
        dominant = check.get("dominant_error_summary")
        if isinstance(dominant, dict) and dominant.get("dominant_error_metric"):
            dominant_candidates.append(
                {
                    "check": check.get("name"),
                    **dominant,
                }
            )
    if dominant_candidates:
        dominant = max(dominant_candidates, key=lambda item: item.get("dominant_error_severity", 0.0))
        dominant_bucket_line = (
            f"Dominant error bucket: {dominant['dominant_error_bucket']} "
            f"({dominant['dominant_error_metric']} = {dominant['dominant_error_value']:.6g})"
        )
    guidance = {
        "most_critical_open_model_limit": report.get("most_critical_open_model_limit", "none"),
        "recommended_next_action": report.get("recommended_next_action", "inspect_open_model_limit_manually"),
        "final_recommended_next_action_source": report.get("final_recommended_next_action_source", "open_model_limit"),
        "evidence_dependency_status": report.get("evidence_dependency_status", "both_missing"),
        "guidance_confidence": report.get("guidance_confidence", "fallback_only"),
        "coefficient_map_audit_recommended_next_action": report.get(
            "coefficient_map_audit_recommended_next_action",
            "coefficient_map_audit_not_supplied",
        ),
        "coefficient_map_stability_recommended_next_action": report.get(
            "coefficient_map_stability_recommended_next_action",
            "coefficient_map_stability_not_supplied",
        ),
        "best_generalizing_coefficient_map_model_id": report.get("best_generalizing_coefficient_map_model_id"),
        "promoted_shared_map_model_id": report.get("promoted_shared_map_model_id"),
        "promoted_shared_map_runtime_scope": report.get("promoted_shared_map_runtime_scope", "unknown"),
        "promoted_shared_map_runtime_contract_status": report.get(
            "promoted_shared_map_runtime_contract_status",
            "unknown",
        ),
        "promoted_shared_map_runtime_supported_lateral_shift_models": report.get(
            "promoted_shared_map_runtime_supported_lateral_shift_models",
            [],
        ),
        "promoted_shared_map_runtime_lateral_shift_constraint": report.get(
            "promoted_shared_map_runtime_lateral_shift_constraint",
            "unknown",
        ),
        "promoted_shared_map_runtime_shift_target": report.get(
            "promoted_shared_map_runtime_shift_target",
            "none",
        ),
        "coefficient_map_ablation_recommended_next_action": report.get(
            "coefficient_map_ablation_recommended_next_action",
            "coefficient_map_ablation_not_supplied",
        ),
        "best_ablated_coefficient_map_model_id": report.get("best_ablated_coefficient_map_model_id"),
        "fit_sensitivity_recommended_next_action": report.get("fit_sensitivity_recommended_next_action", "fit_sensitivity_not_supplied"),
        "fit_window_sensitivity_status": report.get("fit_window_sensitivity_status", "unknown"),
        "effective_channel_fit_strategy_recommended_next_action": report.get(
            "effective_channel_fit_strategy_recommended_next_action",
            "fit_strategy_ablation_not_supplied",
        ),
        "effective_channel_fit_strategy_status": report.get("effective_channel_fit_strategy_status", "unknown"),
        "slice_axis_crosscheck_recommended_next_action": report.get(
            "slice_axis_crosscheck_recommended_next_action",
            "slice_axis_crosscheck_not_supplied",
        ),
        "slice_axis_crosscheck_status": report.get("slice_axis_crosscheck_status", "unknown"),
        "measurement_pipeline_evidence_status": report.get("measurement_pipeline_evidence_status", "not_supplied"),
        "measurement_pipeline_default_mode": report.get("measurement_pipeline_default_mode", "not_supplied"),
        "measurement_pipeline_modes": report.get("measurement_pipeline_modes", []),
        "fd_oct_measurement_wrapper_status": report.get("fd_oct_measurement_wrapper_status", "unknown"),
        "measurement_reference_arm_policy": report.get("measurement_reference_arm_policy", "not_supplied"),
        "measurement_reference_arm_policy_status": report.get("measurement_reference_arm_policy_status", "unknown"),
        "measurement_fd_oct_depth_policy_status": report.get("measurement_fd_oct_depth_policy_status", "not_supplied"),
        "measurement_fd_oct_k_axis_kinds": report.get("measurement_fd_oct_k_axis_kinds", []),
        "measurement_fd_oct_medium_index_policies": report.get("measurement_fd_oct_medium_index_policies", []),
        "measurement_fd_oct_depth_conventions": report.get("measurement_fd_oct_depth_conventions", []),
        "measurement_artifact_freshness_status": report.get(
            "measurement_artifact_freshness_status",
            "not_supplied",
        ),
        "measurement_contract_refreshed_row_count": report.get(
            "measurement_contract_refreshed_row_count",
            0,
        ),
        "cp310_evidence_rebuild_readiness_status": report.get(
            "cp310_evidence_rebuild_readiness_status",
            "not_supplied",
        ),
        "cp310_evidence_rebuild_ready": report.get("cp310_evidence_rebuild_ready", False),
        "cp310_evidence_rebuild_selected_python_version": report.get(
            "cp310_evidence_rebuild_selected_python_version"
        ),
        "cp310_evidence_rebuild_status": report.get("cp310_evidence_rebuild_status", "not_supplied"),
        "cp310_evidence_rebuild_recommended_next_action": report.get(
            "cp310_evidence_rebuild_recommended_next_action",
            "cp310_readiness_not_supplied",
        ),
        "particle_size_sweep_status": report.get("particle_size_sweep_status", "not_supplied"),
        "particle_size_sweep_mode": report.get("particle_size_sweep_mode", "not_supplied"),
        "particle_size_sweep_diameter_range_nm": report.get("particle_size_sweep_diameter_range_nm"),
        "particle_size_sweep_case_count": report.get("particle_size_sweep_case_count", 0),
        "particle_size_sweep_ok_count": report.get("particle_size_sweep_ok_count"),
        "particle_size_sweep_failed_count": report.get("particle_size_sweep_failed_count"),
        "particle_size_sweep_recommended_next_action": report.get(
            "particle_size_sweep_recommended_next_action",
            "not_supplied",
        ),
        "particle_size_sweep_scope_note": report.get("particle_size_sweep_scope_note", "not_supplied"),
        "basis_conditioning_status": report.get("basis_conditioning_status", "unknown"),
        "coefficient_interpretability_status": report.get("coefficient_interpretability_status", "unknown"),
        "shared_scale_consistency_status": report.get("shared_scale_consistency_status", "unknown"),
    }
    report_version_tag = report.get("report_version_tag", DEFAULT_REPORT_VERSION_TAG)
    lines = [
        f"{report_version_tag} validation failure summary",
        f"Hard gate failures: {', '.join(hard_failures) if hard_failures else 'none'}",
        f"Model-limit failures: {', '.join(model_limit_failures) if model_limit_failures else 'none'}",
        f"Expected-fail checks: {', '.join(expected_failures) if expected_failures else 'none'}",
        worst_case_line,
        worst_metric_line,
        dominant_bucket_line,
        f"Directional first-order is promising: {bool(report.get('directional_first_order_is_promising'))}",
        f"Most critical open model limit: {guidance['most_critical_open_model_limit']}",
        f"Recommended next action: {guidance['recommended_next_action']}",
        f"Recommended action source: {guidance['final_recommended_next_action_source']}",
        f"Evidence dependency status: {guidance['evidence_dependency_status']}",
        f"Guidance confidence: {guidance['guidance_confidence']}",
        f"Coefficient-map audit recommended next action: {guidance['coefficient_map_audit_recommended_next_action']}",
        f"Coefficient-map stability recommended next action: {guidance['coefficient_map_stability_recommended_next_action']}",
        f"Best generalizing coefficient-map model: {guidance['best_generalizing_coefficient_map_model_id']}",
        f"Promoted shared coefficient-map model: {guidance['promoted_shared_map_model_id']}",
        f"Promoted shared coefficient-map runtime scope: {guidance['promoted_shared_map_runtime_scope']}",
        f"Promoted shared coefficient-map contract status: {guidance['promoted_shared_map_runtime_contract_status']}",
        "Promoted shared coefficient-map supported lateral-shift models: "
        + (
            ", ".join(guidance["promoted_shared_map_runtime_supported_lateral_shift_models"])
            if guidance["promoted_shared_map_runtime_supported_lateral_shift_models"]
            else "none declared"
        ),
        "Promoted shared coefficient-map lateral-shift constraint: "
        f"{guidance['promoted_shared_map_runtime_lateral_shift_constraint']}",
        f"Promoted shared coefficient-map shift target: {guidance['promoted_shared_map_runtime_shift_target']}",
        f"Coefficient-map ablation recommended next action: {guidance['coefficient_map_ablation_recommended_next_action']}",
        f"Best ablated coefficient-map model: {guidance['best_ablated_coefficient_map_model_id']}",
        f"Fit sensitivity recommended next action: {guidance['fit_sensitivity_recommended_next_action']}",
        f"Fit-window sensitivity status: {guidance['fit_window_sensitivity_status']}",
        f"Effective-channel fit strategy recommended next action: {guidance['effective_channel_fit_strategy_recommended_next_action']}",
        f"Effective-channel fit strategy status: {guidance['effective_channel_fit_strategy_status']}",
        f"Slice-axis crosscheck recommended next action: {guidance['slice_axis_crosscheck_recommended_next_action']}",
        f"Slice-axis crosscheck status: {guidance['slice_axis_crosscheck_status']}",
        f"Measurement pipeline evidence status: {guidance['measurement_pipeline_evidence_status']}",
        f"Measurement pipeline default mode: {guidance['measurement_pipeline_default_mode']}",
        "Measurement pipeline modes: "
        + (
            ", ".join(guidance["measurement_pipeline_modes"])
            if guidance["measurement_pipeline_modes"]
            else "none declared"
        ),
        f"FD-OCT measurement wrapper status: {guidance['fd_oct_measurement_wrapper_status']}",
        f"Measurement reference-arm policy: {guidance['measurement_reference_arm_policy']}",
        f"Measurement reference-arm policy status: {guidance['measurement_reference_arm_policy_status']}",
        f"Measurement FD-OCT depth policy status: {guidance['measurement_fd_oct_depth_policy_status']}",
        "Measurement FD-OCT k-axis kinds: "
        + (
            ", ".join(guidance["measurement_fd_oct_k_axis_kinds"])
            if guidance["measurement_fd_oct_k_axis_kinds"]
            else "none declared"
        ),
        "Measurement FD-OCT medium-index policies: "
        + (
            ", ".join(guidance["measurement_fd_oct_medium_index_policies"])
            if guidance["measurement_fd_oct_medium_index_policies"]
            else "none declared"
        ),
        "Measurement FD-OCT depth conventions: "
        + (
            ", ".join(guidance["measurement_fd_oct_depth_conventions"])
            if guidance["measurement_fd_oct_depth_conventions"]
            else "none declared"
        ),
        f"Measurement artifact freshness status: {guidance['measurement_artifact_freshness_status']}",
        f"Measurement contract refreshed row count: {guidance['measurement_contract_refreshed_row_count']}",
        f"CPython 3.10 evidence rebuild readiness status: {guidance['cp310_evidence_rebuild_readiness_status']}",
        f"CPython 3.10 evidence rebuild ready: {guidance['cp310_evidence_rebuild_ready']}",
        f"CPython 3.10 evidence rebuild selected Python version: {guidance['cp310_evidence_rebuild_selected_python_version']}",
        f"CPython 3.10 evidence rebuild status: {guidance['cp310_evidence_rebuild_status']}",
        f"CPython 3.10 evidence rebuild recommended next action: {guidance['cp310_evidence_rebuild_recommended_next_action']}",
        f"Particle-size sweep status: {guidance['particle_size_sweep_status']}",
        f"Particle-size sweep mode: {guidance['particle_size_sweep_mode']}",
        f"Particle-size sweep diameter range nm: {guidance['particle_size_sweep_diameter_range_nm']}",
        "Particle-size sweep cases: "
        f"{guidance['particle_size_sweep_ok_count']} ok / {guidance['particle_size_sweep_failed_count']} failed "
        f"({guidance['particle_size_sweep_case_count']} total)",
        f"Particle-size sweep recommended next action: {guidance['particle_size_sweep_recommended_next_action']}",
        f"Particle-size sweep scope note: {guidance['particle_size_sweep_scope_note']}",
        f"Basis conditioning status: {guidance['basis_conditioning_status']}",
        f"Coefficient interpretability status: {guidance['coefficient_interpretability_status']}",
        f"Shared-scale consistency status: {guidance['shared_scale_consistency_status']}",
    ]
    return "\n".join(lines) + "\n"


def write_text_with_runtime_sidecar(path, text, *, encoding="utf-8"):
    """Write a report, falling back to a sidecar when a locked canonical artifact blocks refresh."""

    path = Path(path)
    try:
        path.write_text(text, encoding=encoding)
        return {"path": str(path), "status": "canonical_artifact_updated"}
    except PermissionError as exc:
        sidecar = path.with_name(f"{path.stem}.runtime{path.suffix}")
        sidecar.write_text(text, encoding=encoding)
        return {
            "path": str(path),
            "status": "canonical_artifact_permission_denied_runtime_sidecar_written",
            "sidecar_path": str(sidecar),
            "error": str(exc),
        }


def validate(
    lib_path=None,
    *,
    basis_projection_summary=None,
    coefficient_recovery_summary=None,
    fit_sensitivity_summary=None,
    coefficient_injection_summary=None,
    coefficient_map_audit_summary=None,
    coefficient_map_stability_summary=None,
    coefficient_map_ablation_summary=None,
    fit_strategy_ablation_summary=None,
    slice_axis_crosscheck_summary=None,
    measurement_protocol_summary=None,
    particle_size_sweep_summary=None,
    cp310_evidence_readiness_summary=None,
):
    report = {
        "checks": [],
        "report_version_tag": DEFAULT_REPORT_VERSION_TAG,
    }

    lambda_probe = np.array([855.0], dtype=float)
    na_probe = 0.05
    geometry_14 = derive_na_geometry_series(lambda_probe, 1.40, na_probe)
    geometry_17 = derive_na_geometry_series(lambda_probe, 1.70, na_probe)
    report["checks"].append(
        {
            "name": "na_geometry_convention",
            "passed": bool(
                abs(geometry_14["n_medium"][0] * geometry_14["sin_theta_max"][0] - na_probe) < 1e-12
                and abs(geometry_17["n_medium"][0] * geometry_17["sin_theta_max"][0] - na_probe) < 1e-12
                and abs(geometry_14["n_medium"][0] * geometry_14["sin_theta_max"][0] - geometry_17["n_medium"][0] * geometry_17["sin_theta_max"][0]) < 1e-12
            ),
            "k0_na_equivalence_error": float(abs(geometry_14["n_medium"][0] * geometry_14["sin_theta_max"][0] - geometry_17["n_medium"][0] * geometry_17["sin_theta_max"][0])),
            "sin_theta_max_1p40": float(geometry_14["sin_theta_max"][0]),
            "sin_theta_max_1p70": float(geometry_17["sin_theta_max"][0]),
        }
    )

    ideal = solve_oct_particle_response(
        SourceConfig(n_lambda=121),
        GridConfig(z_span_um=20.0, n_z=801, x_span_um=4.0, n_x=41),
        SolverConfig(mode="low_na", medium_material=1.40, ideal=True),
    )
    center_idx = int(np.argmin(np.abs(ideal["x_um"])))
    report["checks"].append(
        {
            "name": "low_na_ideal",
            "passed": bool(
                ideal["mode"] == LOW_NA_BASELINE_MODE
                and np.max(ideal["intensity_xz"]) > 0.999
                and abs(ideal["axial_intensity_metrics"]["peak_opd_um"]) < 0.15
                and ideal["axial_intensity_metrics"]["quantity_kind"] == "intensity"
                and ideal["axial_envelope_metrics"]["quantity_kind"] == "envelope"
                and ideal["axial_axis_kind"] == "opd"
                and ideal["schema_version"] == SCHEMA_VERSION
                and ideal["intensity_xz"][center_idx, ideal["intensity_xz"].shape[1] // 2] >= ideal["intensity_xz"][0, ideal["intensity_xz"].shape[1] // 2]
            ),
            "metrics": ideal["axial_intensity_metrics"],
        }
    )

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        sphere = solve_oct_particle_response(
            SourceConfig(n_lambda=121),
            GridConfig(z_span_um=20.0, n_z=801, x_span_um=4.0, n_x=41),
            SolverConfig(mode=LOW_NA_BASELINE_MODE, particle_material="TiO2-anatase", medium_material="PDMS", diameter_nm=150.0),
        )
    report["checks"].append(
        {
            "name": "low_na_mie_smoke",
            "passed": bool(
                np.isfinite(sphere["intensity_xz"]).all()
                and sphere["mode"] == LOW_NA_BASELINE_MODE
                and sphere["display_mode_label"] == LOW_NA_DISPLAY_LABEL
                and sphere["axial_intensity_metrics"]["fwhm_opd_um"] > 0
                and sphere["axial_intensity_metrics"]["psr_reference"] == "intensity"
                and not sphere["tmatrix_used"]
                and "axial_intensity" not in sphere
                and "axial_envelope" not in sphere
            ),
            "metrics": sphere["axial_intensity_metrics"],
        }
    )

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        full_na_sphere = solve_oct_particle_response(
            SourceConfig(n_lambda=21),
            GridConfig(z_span_um=12.0, n_z=241, x_span_um=4.0, n_x=41, na=0.05, n_bfp_dense=31, n_bfp_sparse=7),
            SolverConfig(
                mode=FULL_NA_BASELINE_MODE,
                particle_material="TiO2-anatase",
                medium_material="PDMS",
                diameter_nm=300.0,
                eps=0.0,
                beta_deg=0.0,
                amp_component="S22",
                ideal=False,
                force_tmatrix=False,
            ),
        )
    sphere_mie_branch_passed = bool(
        full_na_sphere.get("sphere_mie_used")
        and not full_na_sphere.get("tmatrix_used")
        and not full_na_sphere.get("tmatrix_backend_required")
        and full_na_sphere.get("scattering_branch") == "sphere_mie_full_na"
        and full_na_sphere.get("lateral_response_model") == "sphere_mie_angle_resolved_pupil_field"
        and full_na_sphere.get("particle_lateral_scattering_enters_profile")
        and np.isfinite(full_na_sphere["raw_intensity_xz"]).all()
        and full_na_sphere["raw_peak_intensity"] > 0
    )
    report["sphere_mie_branch_status"] = "available" if sphere_mie_branch_passed else "contract_failed"
    report["sphere_mie_branch_scope"] = "full_na_exact_sphere_eps0_force_tmatrix_false"
    report["sphere_full_na_without_tmatrix_backend"] = bool(full_na_sphere.get("sphere_mie_used") and not full_na_sphere.get("tmatrix_used"))
    report["sphere_lateral_scattering_enters_profile"] = bool(full_na_sphere.get("particle_lateral_scattering_enters_profile"))
    report["sphere_mie_reference_validation_status"] = (
        "s22_backscatter_convention_covered_by_unit_test"
        if sphere_mie_branch_passed
        else "inspect_sphere_branch_contract"
    )
    report["checks"].append(
        {
            "name": "full_na_sphere_mie_branch_without_tmatrix",
            "passed": sphere_mie_branch_passed,
            "sphere_mie_used": bool(full_na_sphere.get("sphere_mie_used")),
            "tmatrix_used": bool(full_na_sphere.get("tmatrix_used")),
            "tmatrix_backend_required": bool(full_na_sphere.get("tmatrix_backend_required")),
            "scattering_branch": full_na_sphere.get("scattering_branch"),
            "lateral_response_model": full_na_sphere.get("lateral_response_model"),
            "particle_lateral_scattering_enters_profile": bool(
                full_na_sphere.get("particle_lateral_scattering_enters_profile")
            ),
            "raw_peak_intensity": float(full_na_sphere.get("raw_peak_intensity", 0.0)),
        }
    )

    def _unranged_debug_particle_material(_l_um):
        return 2.48

    def _unranged_debug_medium_material(_l_um):
        return 1.40

    strict_range_triggered = False
    strict_error = None
    try:
        solve_oct_particle_response(
            SourceConfig(lambda0_nm=855.0, fwhm_nm=56.0, n_lambda=31),
            GridConfig(z_span_um=6.0, n_z=101, x_span_um=2.0, n_x=11),
            SolverConfig(mode=LOW_NA_BASELINE_MODE, particle_material=_unranged_debug_particle_material, medium_material=1.40, diameter_nm=150.0, strict_material_range=True),
        )
    except ValueError as error:
        strict_range_triggered = "explicit encoded wavelength support range" in str(error)
        strict_error = str(error)
    report["checks"].append(
        {
            "name": "strict_material_range_requires_explicit_support",
            "passed": strict_range_triggered,
            "error": strict_error,
            "note": "Built-in project materials now carry encoded support ranges; this gate uses an intentionally unranged debug callable to keep strict-mode protection active.",
        }
    )

    reset_material_support_warning_cache()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        solve_oct_particle_response(
            SourceConfig(lambda0_nm=855.0, fwhm_nm=56.0, n_lambda=31),
            GridConfig(z_span_um=6.0, n_z=101, x_span_um=2.0, n_x=11),
            SolverConfig(mode=LOW_NA_BASELINE_MODE, particle_material=_unranged_debug_particle_material, medium_material=_unranged_debug_medium_material, diameter_nm=150.0),
        )
        solve_oct_particle_response(
            SourceConfig(lambda0_nm=855.0, fwhm_nm=56.0, n_lambda=31),
            GridConfig(z_span_um=6.0, n_z=101, x_span_um=2.0, n_x=11),
            SolverConfig(mode=LOW_NA_BASELINE_MODE, particle_material=_unranged_debug_particle_material, medium_material=_unranged_debug_medium_material, diameter_nm=150.0),
        )
    range_warning_messages = [
        str(item.message)
        for item in caught
        if "without an explicit encoded wavelength support range" in str(item.message)
    ]
    report["checks"].append(
        {
            "name": "analytic_material_range_warning_dedup",
            "passed": len(range_warning_messages) == 2,
            "warning_count": len(range_warning_messages),
            "messages": range_warning_messages,
            "note": "Built-in project materials now validate against encoded support ranges; this warning-dedup gate uses intentionally unranged debug callables.",
        }
    )

    try:
        tmatrix_path = ensure_tmatrix_loaded(lib_path)
    except FileNotFoundError as error:
        report["tmatrix_backend_status"] = probe_tmatrix_backend(lib_path)
        report["checks"].append({"name": "tmatrix_available", "passed": False, "skipped": True, "reason": str(error)})
        return report

    lambda_cmp = np.linspace(830.0, 880.0, 11)
    mie = mie_backscatter_spectrum(200.0, 2.48, 1.40, lambda_cmp)
    s11 = tmatrix_backscatter_spectrum(200.0, 0.0, 0.0, 2.48, 1.40, lambda_cmp, amp_component="S11", library_path=tmatrix_path)
    s22 = tmatrix_backscatter_spectrum(200.0, 0.0, 0.0, 2.48, 1.40, lambda_cmp, amp_component="S22", library_path=tmatrix_path)
    s12 = tmatrix_backscatter_spectrum(200.0, 0.0, 0.0, 2.48, 1.40, lambda_cmp, amp_component="S12", library_path=tmatrix_path)
    s21 = tmatrix_backscatter_spectrum(200.0, 0.0, 0.0, 2.48, 1.40, lambda_cmp, amp_component="S21", library_path=tmatrix_path)
    mie_vs_s22 = aligned_complex_residual(mie, s22)
    s11_vs_neg_s22 = aligned_complex_residual(s11, -s22)
    offdiag_sphere = {
        "s12_over_s22": float(np.linalg.norm(s12) / (np.linalg.norm(s22) + 1e-30)),
        "s21_over_s22": float(np.linalg.norm(s21) / (np.linalg.norm(s22) + 1e-30)),
    }
    report["checks"].append(
        {
            "name": "sphere_complex_spectrum_mie_tmatrix",
            "passed": bool(
                mie_vs_s22["relative_residual"] < 0.05
                and s11_vs_neg_s22["relative_residual"] < 1e-6
                and offdiag_sphere["s12_over_s22"] < 1e-6
                and offdiag_sphere["s21_over_s22"] < 1e-6
            ),
            "mie_vs_s22": mie_vs_s22,
            "s11_vs_neg_s22": s11_vs_neg_s22,
            "offdiag_sphere": offdiag_sphere,
        }
    )

    n_medium = resolve_material_model(1.40)(0.855)
    sin_theta_max = derive_na_geometry_series(np.array([855.0]), 1.40, 0.05)["sin_theta_max"][0]
    angle_map = build_bfp_angle_map(sin_theta_max=sin_theta_max, n_bfp=9)
    sphere_offdiag = []
    nonspherical_offdiag = []
    for row in range(angle_map["theta_deg"].shape[0]):
        for col in range(angle_map["theta_deg"].shape[1]):
            if not angle_map["valid_mask"][row, col]:
                continue
            theta_deg = angle_map["theta_deg"][row, col]
            phi_deg = angle_map["phi_deg"][row, col]
            sphere_s, _ = calc_sz(0.1, 0.855 / float(np.real(n_medium)), 2.48 / n_medium, 1.0, thet=theta_deg, phi=phi_deg, beta=0.0, library_path=tmatrix_path)
            nonspherical_s, _ = calc_sz(0.1, 0.855 / float(np.real(n_medium)), 2.48 / n_medium, 1.1, thet=theta_deg, phi=phi_deg, beta=45.0, library_path=tmatrix_path)
            sphere_diag = np.linalg.norm([sphere_s[0, 0], sphere_s[1, 1]]) + 1e-30
            nonspherical_diag = np.linalg.norm([nonspherical_s[0, 0], nonspherical_s[1, 1]]) + 1e-30
            sphere_offdiag.append(float(np.linalg.norm([sphere_s[0, 1], sphere_s[1, 0]]) / sphere_diag))
            nonspherical_offdiag.append(float(np.linalg.norm([nonspherical_s[0, 1], nonspherical_s[1, 0]]) / nonspherical_diag))
    report["checks"].append(
        {
            "name": "amp_component_fixed_basis_sensitivity",
            "passed": bool(max(nonspherical_offdiag) > 1.5 * max(sphere_offdiag)),
            "sphere_max_offdiag_ratio": float(max(sphere_offdiag)),
            "nonspherical_max_offdiag_ratio": float(max(nonspherical_offdiag)),
            "note": "This confirms the current baseline basis/channel choice is geometry-dependent and should be interpreted as a fixed-basis approximation rather than a measured OCT channel.",
        }
    )

    legacy = load_legacy_module()
    if legacy is None:
        report["checks"].append(
            {
                "name": "legacy_milestone1_available",
                "passed": False,
                "skipped": True,
                "reason": "Legacy milestone1 script not available; set OCT_LEGACY_MILESTONE1 to enable this comparison.",
            }
        )
    elif str(tmatrix_path).startswith("python:"):
        report["checks"].append(
            {
                "name": "low_na_vs_legacy_milestone1",
                "passed": False,
                "skipped": True,
                "reason": "Legacy milestone1 only supports ctypes/libpytmatrix paths; current backend is the vendored Python extension.",
                "backend": tmatrix_path,
            }
        )
    else:
        low_na_exact = solve_oct_particle_response(
            SourceConfig(lambda0_nm=855.0, fwhm_nm=56.0, n_lambda=801),
            GridConfig(z_span_um=20.0, n_z=8001, x_span_um=4.0, n_x=41),
            SolverConfig(mode=LOW_NA_BASELINE_MODE, particle_material=2.48, medium_material=1.40, diameter_nm=300.0, force_tmatrix=True, library_path=tmatrix_path),
        )
        legacy_metrics, _, _ = legacy.run_case(300.0, 0.0, 0.0, library_path=tmatrix_path)
        compare = {
            "peak_delta_um": abs(low_na_exact["axial_intensity_metrics"]["peak_opd_um"] - legacy_metrics["peak_opd_um"]),
            "centroid_delta_um": abs(low_na_exact["axial_intensity_metrics"]["centroid_opd_um"] - legacy_metrics["centroid_opd_um"]),
            "fwhm_delta_um": abs(low_na_exact["axial_intensity_metrics"]["fwhm_opd_um"] - legacy_metrics["fwhm_opd_um"]),
            "psr_delta_db": abs(low_na_exact["axial_intensity_metrics"]["psr_db"] - legacy_metrics["psr_db"]),
        }
        report["checks"].append(
            {
                "name": "low_na_vs_legacy_milestone1",
                "passed": bool(
                    compare["peak_delta_um"] < 0.05
                    and compare["centroid_delta_um"] < 0.05
                    and compare["fwhm_delta_um"] < 0.05
                    and compare["psr_delta_db"] < 0.5
                ),
                "deltas": compare,
                "metrics": low_na_exact["axial_intensity_metrics"],
            }
        )

    full_na = solve_oct_particle_response(
        SourceConfig(n_lambda=41),
        GridConfig(z_span_um=8.0, n_z=301, x_span_um=3.0, n_x=41, na=0.05, n_bfp_dense=49, n_bfp_sparse=7),
        SolverConfig(mode=FULL_NA_BASELINE_MODE, particle_material=2.48, medium_material=1.40, diameter_nm=200.0, eps=0.10, beta_deg=45.0, library_path=tmatrix_path),
    )
    peak_index = np.unravel_index(np.argmax(full_na["intensity_xz"]), full_na["intensity_xz"].shape)
    report["checks"].append(
        {
            "name": "full_na_tmatrix_smoke",
            "passed": bool(
                full_na["mode"] == FULL_NA_BASELINE_MODE
                and np.isfinite(full_na["intensity_xz"]).all()
                and abs(full_na["x_um"][peak_index[0]]) <= 0.25
                and full_na["axial_intensity_metrics"]["fwhm_opd_um"] > 0
                and full_na["display_mode_label"] == FULL_NA_DISPLAY_LABEL
                and full_na["solver_output_kind"] == "xz_slice"
                and full_na["lateral_slice_axis"] == "x"
                and full_na["primary_axial_metrics_line"] == "peakline"
                and "axial_intensity" not in full_na
                and "axial_envelope" not in full_na
                and full_na["normalization"]["absolute_amplitude_supported"] is False
            ),
            "metrics": full_na["axial_intensity_metrics"],
            "peak_x_um": float(full_na["x_um"][peak_index[0]]),
            "centerline_x_um": float(full_na["centerline_x_um"]),
            "peakline_x_um": float(full_na["peakline_x_um"]),
            "pupil_shape": full_na.get("pupil_shape"),
        }
    )

    bridge = solve_oct_particle_response(
        SourceConfig(n_lambda=41),
        GridConfig(z_span_um=8.0, n_z=301, x_span_um=3.0, n_x=41, na=0.05, n_bfp_dense=49, n_bfp_sparse=7),
        SolverConfig(mode=VECTOR_BRIDGE_MODE, particle_material=2.48, medium_material=1.40, diameter_nm=200.0, eps=0.10, beta_deg=45.0, incident_mode="linear_x", detection_mode="co_pol", library_path=tmatrix_path),
    )
    bridge_diag = image_difference_diagnostics("scalar_vs_bridge", snapshot_for_comparison(full_na), snapshot_for_comparison(bridge))
    report["checks"].append(
        {
            "name": "bridge_vs_scalar_difference_gate",
            "passed": bool(
                bridge["mode"] == VECTOR_BRIDGE_MODE
                and bridge["display_mode_label"] == VECTOR_BRIDGE_DISPLAY_LABEL
                and bridge["channel_projection_kind"] == "local_jones_projection"
                and bridge_diag["image_relative_l2"] > 1e-4
            ),
            "diagnostics": bridge_diag,
            "bridge_peakline_metrics": bridge["axial_intensity_metrics"],
        }
    )

    bridge_sphere_ref = solve_oct_particle_response(
        SourceConfig(n_lambda=41),
        GridConfig(z_span_um=8.0, n_z=301, x_span_um=3.0, n_x=41, na=0.05, n_bfp_dense=49, n_bfp_sparse=7),
        SolverConfig(mode=VECTOR_BRIDGE_MODE, particle_material=2.48, medium_material=1.40, diameter_nm=200.0, eps=0.0, beta_deg=0.0, incident_mode="linear_x", detection_mode="co_pol", library_path=tmatrix_path),
    )
    bridge_sphere_rotated = solve_oct_particle_response(
        SourceConfig(n_lambda=41),
        GridConfig(z_span_um=8.0, n_z=301, x_span_um=3.0, n_x=41, na=0.05, n_bfp_dense=49, n_bfp_sparse=7),
        SolverConfig(mode=VECTOR_BRIDGE_MODE, particle_material=2.48, medium_material=1.40, diameter_nm=200.0, eps=0.0, beta_deg=60.0, incident_mode="linear_x", detection_mode="co_pol", library_path=tmatrix_path),
    )
    bridge_consistency_diag = image_difference_diagnostics(
        "bridge_sphere_orientation_invariance",
        snapshot_for_comparison(bridge_sphere_rotated),
        snapshot_for_comparison(bridge_sphere_ref),
    )
    bridge_supported_modes = bridge["supported_polarization_modes"]
    report["checks"].append(
        {
            "name": "bridge_consistency_gate",
            "passed": bool(
                bridge_sphere_ref["channel_projection_kind"] == "local_jones_projection"
                and bridge_sphere_ref["polarization_model_kind"] == "lab_to_local_jones_surrogate"
                and bridge_sphere_ref["supported_polarization_modes"] == bridge_supported_modes
                and bridge_sphere_ref["polarization_projection_level"] == "lab_to_local_jones_surrogate"
                and bridge_consistency_diag["image_relative_l2"] < 1e-6
                and bridge_consistency_diag["raw_image_relative_l2"] < 1e-6
            ),
            "diagnostics": bridge_consistency_diag,
            "reference_metrics": bridge_sphere_ref["axial_intensity_metrics"],
            "rotated_metrics": bridge_sphere_rotated["axial_intensity_metrics"],
        }
    )

    asymptotic = solve_oct_particle_response(
        SourceConfig(n_lambda=241),
        GridConfig(z_span_um=20.0, n_z=801, x_span_um=4.0, n_x=41, na=0.10),
        SolverConfig(mode=LOW_NA_ASYMPTOTIC_MODE, particle_material=2.48, medium_material=1.40, diameter_nm=400.0, eps=0.15, beta_deg=35.0, incident_mode="linear_x", detection_mode="co_pol", library_path=tmatrix_path),
    )
    baseline_low_na = solve_oct_particle_response(
        SourceConfig(n_lambda=241),
        GridConfig(z_span_um=20.0, n_z=801, x_span_um=4.0, n_x=41, na=0.10),
        SolverConfig(mode=LOW_NA_BASELINE_MODE, particle_material=2.48, medium_material=1.40, diameter_nm=400.0, eps=0.15, beta_deg=35.0, force_tmatrix=True, library_path=tmatrix_path),
    )
    asymptotic_axial_l2 = relative_axial_l2(asymptotic, baseline_low_na)
    asymptotic_lambda0_nm = float(asymptotic["source"]["lambda0_nm"])
    asymptotic_supported_modes = bridge["supported_polarization_modes"]
    report["checks"].append(
        {
            "name": "low_na_asymptotic_vs_separable_baseline",
            "passed": bool(
                asymptotic["mode"] == LOW_NA_ASYMPTOTIC_MODE
                and asymptotic["channel_projection_kind"] == "local_jones_projection"
                and asymptotic["channel_definition"] == "effective_jones_projected_channel"
                and asymptotic["polarization_model_kind"] == "lab_to_local_jones_surrogate"
                and asymptotic["supported_polarization_modes"] == asymptotic_supported_modes
                and "share the same effective channel definition" in asymptotic["channel_alignment_note"]
                and asymptotic["c2_estimation_method"] == "local quadratic tensor fit around backscatter direction on the Jones-projected effective channel"
                and asymptotic["C2_tensor_kind"] == "local_backscatter_quadratic_tensor"
                and asymptotic["C2_scalar_weighting_kind"] == "effective_channel_energy_weighted_over_theta"
                and np.asarray(asymptotic["C2_tensor_k"]).shape[1:] == (2, 2)
                and np.asarray(asymptotic["mu2_tensor_profile"]).shape[1:] == (2, 2)
                and np.isclose(asymptotic["mu2_reference_wavelength_nm"], asymptotic_lambda0_nm)
                and asymptotic["mu2_wavelength_model"] == "frozen_at_lambda0"
                and asymptotic["mu2_wavelength_samples_nm"] == [asymptotic_lambda0_nm]
                and "wavelength_samples_nm" in asymptotic["mu2_dispersion_sensitivity"]
                and "C2_slice_k" in asymptotic
                and np.isfinite(asymptotic["mu2_profile_phase_span_rad"])
                and np.isfinite(asymptotic["mu2_profile_real_imag_ratio"])
                and "Tr[C2_tensor_k * mu2_tensor_profile(x)]" in asymptotic["second_order_closure_note"]
                and np.isfinite(asymptotic["intensity_xz"]).all()
                and asymptotic_axial_l2 > 1e-4
            ),
            "axial_relative_l2": asymptotic_axial_l2,
            "mu2_profile_phase_span_rad": float(asymptotic["mu2_profile_phase_span_rad"]),
            "mu2_profile_real_imag_ratio": float(asymptotic["mu2_profile_real_imag_ratio"]),
            "mu2_wavelength_model": asymptotic["mu2_wavelength_model"],
            "mu2_wavelength_samples_nm": asymptotic["mu2_wavelength_samples_nm"],
            "baseline_metrics": baseline_low_na["axial_intensity_metrics"],
            "asymptotic_metrics": asymptotic["axial_intensity_metrics"],
        }
    )
    report["checks"].append(
        {
            "name": "asymptotic_mu2_wavelength_freeze_diagnostic",
            "passed": bool(
                asymptotic["mu2_wavelength_model"] == "frozen_at_lambda0"
                and np.isfinite(asymptotic["mu2_reference_wavelength_nm"])
                and np.isfinite(asymptotic["mu2_dispersion_sensitivity"]["max_relative_reference_tensor_delta"])
                and np.isfinite(asymptotic["mu2_dispersion_sensitivity"]["max_relative_reference_trace_delta"])
            ),
            "mu2_reference_wavelength_nm": float(asymptotic["mu2_reference_wavelength_nm"]),
            "mu2_wavelength_model": asymptotic["mu2_wavelength_model"],
            "mu2_wavelength_samples_nm": asymptotic["mu2_wavelength_samples_nm"],
            "mu2_dispersion_sensitivity": asymptotic["mu2_dispersion_sensitivity"],
        }
    )
    mu2_benchmark_cases = build_mu2_dispersion_benchmark_cases()
    mu2_control_case = mu2_benchmark_cases["constant_material_control_case"]
    mu2_stress_case = mu2_benchmark_cases["dispersive_material_stress_case"]
    report["checks"].append(
        {
            "name": "mu2_dispersion_benchmark_design",
            "passed": bool(
                mu2_control_case["max_relative_reference_tensor_delta"] < 1e-6
                and mu2_control_case["max_relative_reference_trace_delta"] < 1e-6
                and mu2_stress_case["max_relative_reference_tensor_delta"] > 0.05
            ),
            "control_case": mu2_control_case,
            "stress_case": mu2_stress_case,
            "control_case_is_near_zero": bool(
                mu2_control_case["max_relative_reference_tensor_delta"] < 1e-6
                and mu2_control_case["max_relative_reference_trace_delta"] < 1e-6
            ),
            "stress_case_is_nontrivial": bool(mu2_stress_case["max_relative_reference_tensor_delta"] > 0.05),
            "control_threshold": 1e-6,
            "stress_floor": 0.05,
            "note": "The control case keeps constant materials so frozen_at_lambda0 should produce negligible tensor drift; the stress case injects synthetic dispersion so the same diagnostic must respond measurably.",
        }
    )
    report["checks"].append(
        {
            "name": "mu2_dispersion_current_case_gate",
            "passed": bool(
                asymptotic["mu2_dispersion_sensitivity"]["max_relative_reference_tensor_delta"] < 0.05
                and asymptotic["mu2_dispersion_sensitivity"]["max_relative_reference_trace_delta"] < 0.05
            ),
            "max_relative_reference_tensor_delta": float(asymptotic["mu2_dispersion_sensitivity"]["max_relative_reference_tensor_delta"]),
            "max_relative_reference_trace_delta": float(asymptotic["mu2_dispersion_sensitivity"]["max_relative_reference_trace_delta"]),
            "threshold": 0.05,
            "mu2_wavelength_model": asymptotic["mu2_wavelength_model"],
            "current_case_note": "This gate only describes the active validation case; stress-benchmark behavior is tracked separately in mu2_dispersion_benchmark_design.",
        }
    )

    bridge_low_na_small = solve_oct_particle_response(
        SourceConfig(n_lambda=181),
        GridConfig(z_span_um=18.0, n_z=601, x_span_um=4.0, n_x=41, na=0.03, n_bfp_dense=41, n_bfp_sparse=7),
        SolverConfig(mode=VECTOR_BRIDGE_MODE, particle_material=2.48, medium_material=1.40, diameter_nm=250.0, eps=0.08, beta_deg=20.0, incident_mode="linear_x", detection_mode="co_pol", library_path=tmatrix_path),
    )
    asymptotic_low_na_small = solve_oct_particle_response(
        SourceConfig(n_lambda=181),
        GridConfig(z_span_um=18.0, n_z=601, x_span_um=4.0, n_x=41, na=0.03, n_bfp_dense=41, n_bfp_sparse=7),
        SolverConfig(mode=LOW_NA_ASYMPTOTIC_MODE, particle_material=2.48, medium_material=1.40, diameter_nm=250.0, eps=0.08, beta_deg=20.0, incident_mode="linear_x", detection_mode="co_pol", library_path=tmatrix_path),
    )
    bridge_low_na_large = solve_oct_particle_response(
        SourceConfig(n_lambda=181),
        GridConfig(z_span_um=18.0, n_z=601, x_span_um=4.0, n_x=41, na=0.09, n_bfp_dense=41, n_bfp_sparse=7),
        SolverConfig(mode=VECTOR_BRIDGE_MODE, particle_material=2.48, medium_material=1.40, diameter_nm=250.0, eps=0.08, beta_deg=20.0, incident_mode="linear_x", detection_mode="co_pol", library_path=tmatrix_path),
    )
    asymptotic_low_na_large = solve_oct_particle_response(
        SourceConfig(n_lambda=181),
        GridConfig(z_span_um=18.0, n_z=601, x_span_um=4.0, n_x=41, na=0.09, n_bfp_dense=41, n_bfp_sparse=7),
        SolverConfig(mode=LOW_NA_ASYMPTOTIC_MODE, particle_material=2.48, medium_material=1.40, diameter_nm=250.0, eps=0.08, beta_deg=20.0, incident_mode="linear_x", detection_mode="co_pol", library_path=tmatrix_path),
    )
    alignment_small = image_difference_diagnostics(
        "bridge_vs_asymptotic_na0p03",
        snapshot_for_comparison(asymptotic_low_na_small),
        snapshot_for_comparison(bridge_low_na_small),
    )
    alignment_large = image_difference_diagnostics(
        "bridge_vs_asymptotic_na0p09",
        snapshot_for_comparison(asymptotic_low_na_large),
        snapshot_for_comparison(bridge_low_na_large),
    )
    report["checks"].append(
        {
            "name": "low_na_asymptotic_channel_alignment_trend",
            "passed": bool(alignment_small["image_relative_l2"] < alignment_large["image_relative_l2"]),
            "na0p03": alignment_small,
            "na0p09": alignment_large,
            "dominant_error_summary_na0p03": classify_dominant_error_bucket(alignment_small),
            "dominant_error_summary_na0p09": classify_dominant_error_bucket(alignment_large),
        }
    )

    bridge_low_na_abs = solve_oct_particle_response(
        SourceConfig(n_lambda=181),
        GridConfig(z_span_um=18.0, n_z=601, x_span_um=4.0, n_x=41, na=0.015, n_bfp_dense=41, n_bfp_sparse=7),
        SolverConfig(mode=VECTOR_BRIDGE_MODE, particle_material=2.48, medium_material=1.40, diameter_nm=250.0, eps=0.08, beta_deg=20.0, incident_mode="linear_x", detection_mode="co_pol", library_path=tmatrix_path),
    )
    asymptotic_low_na_abs = solve_oct_particle_response(
        SourceConfig(n_lambda=181),
        GridConfig(z_span_um=18.0, n_z=601, x_span_um=4.0, n_x=41, na=0.015, n_bfp_dense=41, n_bfp_sparse=7),
        SolverConfig(mode=LOW_NA_ASYMPTOTIC_MODE, particle_material=2.48, medium_material=1.40, diameter_nm=250.0, eps=0.08, beta_deg=20.0, incident_mode="linear_x", detection_mode="co_pol", library_path=tmatrix_path),
    )
    asymptotic_low_na_abs_slice_projected = solve_oct_particle_response(
        SourceConfig(n_lambda=181),
        GridConfig(z_span_um=18.0, n_z=601, x_span_um=4.0, n_x=41, na=0.015, n_bfp_dense=41, n_bfp_sparse=7),
        SolverConfig(
            mode=LOW_NA_ASYMPTOTIC_MODE,
            particle_material=2.48,
            medium_material=1.40,
            diameter_nm=250.0,
            eps=0.08,
            beta_deg=20.0,
            incident_mode="linear_x",
            detection_mode="co_pol",
            library_path=tmatrix_path,
            second_order_model="slice_projected",
        ),
    )
    asymptotic_low_na_abs_directional_field = solve_oct_particle_response(
        SourceConfig(n_lambda=181),
        GridConfig(z_span_um=18.0, n_z=601, x_span_um=4.0, n_x=41, na=0.015, n_bfp_dense=41, n_bfp_sparse=7),
        SolverConfig(
            mode=LOW_NA_ASYMPTOTIC_MODE,
            particle_material=2.48,
            medium_material=1.40,
            diameter_nm=250.0,
            eps=0.08,
            beta_deg=20.0,
            incident_mode="linear_x",
            detection_mode="co_pol",
            library_path=tmatrix_path,
            second_order_model="directional_field_expansion",
        ),
    )
    asymptotic_low_na_abs_directional_field_first_order = solve_oct_particle_response(
        SourceConfig(n_lambda=181),
        GridConfig(z_span_um=18.0, n_z=601, x_span_um=4.0, n_x=41, na=0.015, n_bfp_dense=41, n_bfp_sparse=7),
        SolverConfig(
            mode=LOW_NA_ASYMPTOTIC_MODE,
            particle_material=2.48,
            medium_material=1.40,
            diameter_nm=250.0,
            eps=0.08,
            beta_deg=20.0,
            incident_mode="linear_x",
            detection_mode="co_pol",
            library_path=tmatrix_path,
            second_order_model="directional_field_expansion_first_order",
        ),
    )
    asymptotic_low_na_abs_endpoint_refit = solve_oct_particle_response(
        SourceConfig(n_lambda=181),
        GridConfig(z_span_um=18.0, n_z=601, x_span_um=4.0, n_x=41, na=0.015, n_bfp_dense=41, n_bfp_sparse=7),
        SolverConfig(
            mode=LOW_NA_ASYMPTOTIC_MODE,
            particle_material=2.48,
            medium_material=1.40,
            diameter_nm=250.0,
            eps=0.08,
            beta_deg=20.0,
            incident_mode="linear_x",
            detection_mode="co_pol",
            library_path=tmatrix_path,
            mu2_wavelength_model="endpoint_refit",
        ),
    )
    asymptotic_low_na_abs_first_order = solve_oct_particle_response(
        SourceConfig(n_lambda=181),
        GridConfig(z_span_um=18.0, n_z=601, x_span_um=4.0, n_x=41, na=0.015, n_bfp_dense=41, n_bfp_sparse=7),
        SolverConfig(
            mode=LOW_NA_ASYMPTOTIC_MODE,
            particle_material=2.48,
            medium_material=1.40,
            diameter_nm=250.0,
            eps=0.08,
            beta_deg=20.0,
            incident_mode="linear_x",
            detection_mode="co_pol",
            library_path=tmatrix_path,
            lateral_shift_model="first_order",
        ),
    )
    asymptotic_low_na_abs_first_order_coupled = solve_oct_particle_response(
        SourceConfig(n_lambda=181),
        GridConfig(z_span_um=18.0, n_z=601, x_span_um=4.0, n_x=41, na=0.015, n_bfp_dense=41, n_bfp_sparse=7),
        SolverConfig(
            mode=LOW_NA_ASYMPTOTIC_MODE,
            particle_material=2.48,
            medium_material=1.40,
            diameter_nm=250.0,
            eps=0.08,
            beta_deg=20.0,
            incident_mode="linear_x",
            detection_mode="co_pol",
            library_path=tmatrix_path,
            lateral_shift_model="first_order",
            lateral_shift_coupling="shift_envelope_and_mu2",
        ),
    )
    asymptotic_low_na_abs_first_order_coupled_analytic = solve_oct_particle_response(
        SourceConfig(n_lambda=181),
        GridConfig(z_span_um=18.0, n_z=601, x_span_um=4.0, n_x=41, na=0.015, n_bfp_dense=41, n_bfp_sparse=7),
        SolverConfig(
            mode=LOW_NA_ASYMPTOTIC_MODE,
            particle_material=2.48,
            medium_material=1.40,
            diameter_nm=250.0,
            eps=0.08,
            beta_deg=20.0,
            incident_mode="linear_x",
            detection_mode="co_pol",
            library_path=tmatrix_path,
            lateral_shift_model="first_order",
            lateral_shift_coupling="shift_envelope_and_mu2",
            lateral_shift_impl="analytic_gaussian",
        ),
    )
    asymptotic_low_na_abs_first_order_coupled_edge_hold = solve_oct_particle_response(
        SourceConfig(n_lambda=181),
        GridConfig(z_span_um=18.0, n_z=601, x_span_um=4.0, n_x=41, na=0.015, n_bfp_dense=41, n_bfp_sparse=7),
        SolverConfig(
            mode=LOW_NA_ASYMPTOTIC_MODE,
            particle_material=2.48,
            medium_material=1.40,
            diameter_nm=250.0,
            eps=0.08,
            beta_deg=20.0,
            incident_mode="linear_x",
            detection_mode="co_pol",
            library_path=tmatrix_path,
            lateral_shift_model="first_order",
            lateral_shift_coupling="shift_envelope_and_mu2",
            lateral_shift_impl="interp_edge_hold",
        ),
    )
    alignment_abs = image_difference_diagnostics(
        "bridge_vs_asymptotic_na0p015",
        snapshot_for_comparison(asymptotic_low_na_abs),
        snapshot_for_comparison(bridge_low_na_abs),
    )
    alignment_abs_slice_projected = image_difference_diagnostics(
        "bridge_vs_asymptotic_na0p015_slice_projected",
        snapshot_for_comparison(asymptotic_low_na_abs_slice_projected),
        snapshot_for_comparison(bridge_low_na_abs),
    )
    alignment_abs_directional_field = image_difference_diagnostics(
        "bridge_vs_asymptotic_na0p015_directional_field_expansion",
        snapshot_for_comparison(asymptotic_low_na_abs_directional_field),
        snapshot_for_comparison(bridge_low_na_abs),
    )
    alignment_abs_directional_field_first_order = image_difference_diagnostics(
        "bridge_vs_asymptotic_na0p015_directional_field_expansion_first_order",
        snapshot_for_comparison(asymptotic_low_na_abs_directional_field_first_order),
        snapshot_for_comparison(bridge_low_na_abs),
    )
    alignment_abs_endpoint_refit = image_difference_diagnostics(
        "bridge_vs_asymptotic_na0p015_endpoint_refit",
        snapshot_for_comparison(asymptotic_low_na_abs_endpoint_refit),
        snapshot_for_comparison(bridge_low_na_abs),
    )
    asymptotic_low_na_abs_slice_projected_scaled = apply_complex_field_match_scale(
        asymptotic_low_na_abs_slice_projected,
        bridge_low_na_abs,
    )
    alignment_abs_slice_projected_scaled = image_difference_diagnostics(
        "bridge_vs_asymptotic_na0p015_slice_projected_scaled",
        snapshot_for_comparison(asymptotic_low_na_abs_slice_projected_scaled),
        snapshot_for_comparison(bridge_low_na_abs),
    )
    asymptotic_low_na_abs_directional_field_scaled = apply_complex_field_match_scale(
        asymptotic_low_na_abs_directional_field,
        bridge_low_na_abs,
    )
    alignment_abs_directional_field_scaled = image_difference_diagnostics(
        "bridge_vs_asymptotic_na0p015_directional_field_expansion_scaled",
        snapshot_for_comparison(asymptotic_low_na_abs_directional_field_scaled),
        snapshot_for_comparison(bridge_low_na_abs),
    )
    asymptotic_low_na_abs_directional_field_first_order_scaled = apply_complex_field_match_scale(
        asymptotic_low_na_abs_directional_field_first_order,
        bridge_low_na_abs,
    )
    alignment_abs_directional_field_first_order_scaled = image_difference_diagnostics(
        "bridge_vs_asymptotic_na0p015_directional_field_expansion_first_order_scaled",
        snapshot_for_comparison(asymptotic_low_na_abs_directional_field_first_order_scaled),
        snapshot_for_comparison(bridge_low_na_abs),
    )
    alignment_abs_first_order = image_difference_diagnostics(
        "bridge_vs_asymptotic_na0p015_first_order_shift",
        snapshot_for_comparison(asymptotic_low_na_abs_first_order),
        snapshot_for_comparison(bridge_low_na_abs),
    )
    alignment_abs_first_order_coupled = image_difference_diagnostics(
        "bridge_vs_asymptotic_na0p015_first_order_shift_coupled",
        snapshot_for_comparison(asymptotic_low_na_abs_first_order_coupled),
        snapshot_for_comparison(bridge_low_na_abs),
    )
    alignment_abs_first_order_coupled_analytic = image_difference_diagnostics(
        "bridge_vs_asymptotic_na0p015_first_order_shift_coupled_analytic",
        snapshot_for_comparison(asymptotic_low_na_abs_first_order_coupled_analytic),
        snapshot_for_comparison(bridge_low_na_abs),
    )
    alignment_abs_first_order_coupled_edge_hold = image_difference_diagnostics(
        "bridge_vs_asymptotic_na0p015_first_order_shift_coupled_interp_edge_hold",
        snapshot_for_comparison(asymptotic_low_na_abs_first_order_coupled_edge_hold),
        snapshot_for_comparison(bridge_low_na_abs),
    )
    report["checks"].append(
        {
            "name": "low_na_asymptotic_absolute_alignment_gate",
            "passed": bool(
                alignment_abs["image_relative_l2"] < 0.25
                and alignment_abs["fwhm_delta_um"] < 0.25
                and alignment_abs["psr_delta_db"] < 1.5
                and alignment_abs["centroid_opd_delta_um"] < 0.25
                and alignment_abs["peakline_x_delta_um"] < 0.5
            ),
            "na0p015": alignment_abs,
            "dominant_error_summary": classify_dominant_error_bucket(alignment_abs),
        }
    )
    report["checks"].append(
        {
            "name": "low_na_asymptotic_second_order_model_ablation",
            "passed": bool(
                alignment_abs_slice_projected_scaled["peakline_x_delta_um"] < alignment_abs["peakline_x_delta_um"]
                or alignment_abs_slice_projected_scaled["image_relative_l2"] < alignment_abs["image_relative_l2"]
                or alignment_abs_directional_field_scaled["peakline_x_delta_um"] < alignment_abs["peakline_x_delta_um"]
                or alignment_abs_directional_field_scaled["image_relative_l2"] < alignment_abs["image_relative_l2"]
                or alignment_abs_directional_field_first_order_scaled["peakline_x_delta_um"] < alignment_abs["peakline_x_delta_um"]
                or alignment_abs_directional_field_first_order_scaled["image_relative_l2"] < alignment_abs["image_relative_l2"]
            ),
            "tensor_closure": alignment_abs,
            "slice_projected_raw": alignment_abs_slice_projected,
            "slice_projected_scaled": alignment_abs_slice_projected_scaled,
            "directional_field_expansion_raw": alignment_abs_directional_field,
            "directional_field_expansion_scaled": alignment_abs_directional_field_scaled,
            "directional_field_expansion_first_order_raw": alignment_abs_directional_field_first_order,
            "directional_field_expansion_first_order_scaled": alignment_abs_directional_field_first_order_scaled,
            "slice_projected_scale_factor_abs": float(asymptotic_low_na_abs_slice_projected_scaled["experimental_post_scale_factor_abs"]),
            "slice_projected_scale_factor_phase_rad": float(asymptotic_low_na_abs_slice_projected_scaled["experimental_post_scale_factor_phase_rad"]),
            "directional_field_expansion_scale_factor_abs": float(asymptotic_low_na_abs_directional_field_scaled["experimental_post_scale_factor_abs"]),
            "directional_field_expansion_scale_factor_phase_rad": float(asymptotic_low_na_abs_directional_field_scaled["experimental_post_scale_factor_phase_rad"]),
            "directional_field_expansion_first_order_scale_factor_abs": float(asymptotic_low_na_abs_directional_field_first_order_scaled["experimental_post_scale_factor_abs"]),
            "directional_field_expansion_first_order_scale_factor_phase_rad": float(asymptotic_low_na_abs_directional_field_first_order_scaled["experimental_post_scale_factor_phase_rad"]),
            "peakline_x_delta_improvement_um": float(alignment_abs["peakline_x_delta_um"] - alignment_abs_slice_projected_scaled["peakline_x_delta_um"]),
            "image_relative_l2_improvement": float(alignment_abs["image_relative_l2"] - alignment_abs_slice_projected_scaled["image_relative_l2"]),
            "raw_peak_relative_delta_improvement": float(
                alignment_abs_slice_projected.get("raw_peak_relative_delta", 0.0)
                - alignment_abs_slice_projected_scaled.get("raw_peak_relative_delta", 0.0)
            ),
            "raw_image_relative_l2_improvement": float(
                alignment_abs_slice_projected.get("raw_image_relative_l2", 0.0)
                - alignment_abs_slice_projected_scaled.get("raw_image_relative_l2", 0.0)
            ),
            "directional_field_peakline_x_delta_improvement_um": float(
                alignment_abs["peakline_x_delta_um"] - alignment_abs_directional_field_scaled["peakline_x_delta_um"]
            ),
            "directional_field_image_relative_l2_improvement": float(
                alignment_abs["image_relative_l2"] - alignment_abs_directional_field_scaled["image_relative_l2"]
            ),
            "directional_field_raw_peak_relative_delta_improvement": float(
                alignment_abs_directional_field.get("raw_peak_relative_delta", 0.0)
                - alignment_abs_directional_field_scaled.get("raw_peak_relative_delta", 0.0)
            ),
            "directional_field_raw_image_relative_l2_improvement": float(
                alignment_abs_directional_field.get("raw_image_relative_l2", 0.0)
                - alignment_abs_directional_field_scaled.get("raw_image_relative_l2", 0.0)
            ),
            "directional_field_first_order_peakline_x_delta_improvement_um": float(
                alignment_abs["peakline_x_delta_um"] - alignment_abs_directional_field_first_order_scaled["peakline_x_delta_um"]
            ),
            "directional_field_first_order_image_relative_l2_improvement": float(
                alignment_abs["image_relative_l2"] - alignment_abs_directional_field_first_order_scaled["image_relative_l2"]
            ),
            "directional_field_first_order_raw_peak_relative_delta_improvement": float(
                alignment_abs_directional_field_first_order.get("raw_peak_relative_delta", 0.0)
                - alignment_abs_directional_field_first_order_scaled.get("raw_peak_relative_delta", 0.0)
            ),
            "directional_field_first_order_raw_image_relative_l2_improvement": float(
                alignment_abs_directional_field_first_order.get("raw_image_relative_l2", 0.0)
                - alignment_abs_directional_field_first_order_scaled.get("raw_image_relative_l2", 0.0)
            ),
            "note": "A/B experiment comparing the default tensor_closure asymptotic model against the experimental slice_projected, directional_field_expansion, and directional_field_expansion_first_order variants on the same bridge-matching case, with post-hoc complex amplitude matches used to separate raw-amplitude instability from shape mismatch.",
            "dominant_error_summary_tensor_closure": classify_dominant_error_bucket(alignment_abs),
            "dominant_error_summary_slice_projected_raw": classify_dominant_error_bucket(alignment_abs_slice_projected),
            "dominant_error_summary_slice_projected_scaled": classify_dominant_error_bucket(alignment_abs_slice_projected_scaled),
            "dominant_error_summary_directional_field_expansion_raw": classify_dominant_error_bucket(alignment_abs_directional_field),
            "dominant_error_summary_directional_field_expansion_scaled": classify_dominant_error_bucket(alignment_abs_directional_field_scaled),
            "dominant_error_summary_directional_field_expansion_first_order_raw": classify_dominant_error_bucket(alignment_abs_directional_field_first_order),
            "dominant_error_summary_directional_field_expansion_first_order_scaled": classify_dominant_error_bucket(alignment_abs_directional_field_first_order_scaled),
        }
    )
    report["checks"].append(
        {
            "name": "low_na_asymptotic_slice_projected_stability_gate",
            "passed": bool(
                alignment_abs_slice_projected_scaled.get("raw_peak_relative_delta", np.inf)
                < alignment_abs_slice_projected.get("raw_peak_relative_delta", np.inf)
                and alignment_abs_slice_projected_scaled.get("raw_image_relative_l2", np.inf)
                < alignment_abs_slice_projected.get("raw_image_relative_l2", np.inf)
            ),
            "slice_projected_raw": alignment_abs_slice_projected,
            "slice_projected_scaled": alignment_abs_slice_projected_scaled,
            "raw_peak_relative_delta_improvement": float(
                alignment_abs_slice_projected.get("raw_peak_relative_delta", 0.0)
                - alignment_abs_slice_projected_scaled.get("raw_peak_relative_delta", 0.0)
            ),
            "raw_image_relative_l2_improvement": float(
                alignment_abs_slice_projected.get("raw_image_relative_l2", 0.0)
                - alignment_abs_slice_projected_scaled.get("raw_image_relative_l2", 0.0)
            ),
            "note": "Stability gate for the experimental slice_projected branch: post-hoc amplitude matching should substantially reduce the raw-return blow-up before any fidelity comparison is interpreted.",
        }
    )
    report["checks"].append(
        {
            "name": "low_na_asymptotic_slice_projected_fidelity_gate",
            "passed": bool(
                alignment_abs_slice_projected_scaled["peakline_x_delta_um"] < alignment_abs["peakline_x_delta_um"]
                or alignment_abs_slice_projected_scaled["image_relative_l2"] < alignment_abs["image_relative_l2"]
            ),
            "tensor_closure": alignment_abs,
            "slice_projected_scaled": alignment_abs_slice_projected_scaled,
            "peakline_x_delta_improvement_um": float(
                alignment_abs["peakline_x_delta_um"] - alignment_abs_slice_projected_scaled["peakline_x_delta_um"]
            ),
            "image_relative_l2_improvement": float(
                alignment_abs["image_relative_l2"] - alignment_abs_slice_projected_scaled["image_relative_l2"]
            ),
            "note": "Fidelity gate for the experimental slice_projected branch after raw-amplitude stabilization.",
        }
    )
    report["checks"].append(
        {
            "name": "low_na_asymptotic_mu2_wavelength_model_ablation",
            "passed": bool(
                alignment_abs_endpoint_refit["peakline_x_delta_um"] < alignment_abs["peakline_x_delta_um"]
                or alignment_abs_endpoint_refit["image_relative_l2"] < alignment_abs["image_relative_l2"]
            ),
            "frozen_at_lambda0": alignment_abs,
            "endpoint_refit": alignment_abs_endpoint_refit,
            "peakline_x_delta_improvement_um": float(alignment_abs["peakline_x_delta_um"] - alignment_abs_endpoint_refit["peakline_x_delta_um"]),
            "image_relative_l2_improvement": float(alignment_abs["image_relative_l2"] - alignment_abs_endpoint_refit["image_relative_l2"]),
            "note": "A/B experiment comparing the default frozen-at-lambda0 mu2 closure against the cheap endpoint_refit surrogate on the same bridge-matching case.",
            "dominant_error_summary_frozen_at_lambda0": classify_dominant_error_bucket(alignment_abs),
            "dominant_error_summary_endpoint_refit": classify_dominant_error_bucket(alignment_abs_endpoint_refit),
        }
    )
    report["checks"].append(
        {
            "name": "low_na_asymptotic_endpoint_refit_not_prioritized",
            "passed": bool(
                alignment_abs_endpoint_refit["peakline_x_delta_um"] >= alignment_abs["peakline_x_delta_um"]
                and alignment_abs_endpoint_refit["image_relative_l2"] >= alignment_abs["image_relative_l2"]
            ),
            "frozen_at_lambda0": alignment_abs,
            "endpoint_refit": alignment_abs_endpoint_refit,
            "note": "Current evidence does not support prioritizing the endpoint_refit mu2 branch.",
        }
    )
    report["checks"].append(
        {
            "name": "low_na_asymptotic_lateral_shift_model_ablation",
            "passed": bool(
                alignment_abs_first_order["peakline_x_delta_um"] < alignment_abs["peakline_x_delta_um"]
                or alignment_abs_first_order["image_relative_l2"] < alignment_abs["image_relative_l2"]
                or alignment_abs_first_order_coupled["peakline_x_delta_um"] < alignment_abs["peakline_x_delta_um"]
                or alignment_abs_first_order_coupled["image_relative_l2"] < alignment_abs["image_relative_l2"]
                or alignment_abs_first_order_coupled_analytic["peakline_x_delta_um"] < alignment_abs["peakline_x_delta_um"]
                or alignment_abs_first_order_coupled_analytic["image_relative_l2"] < alignment_abs["image_relative_l2"]
                or alignment_abs_first_order_coupled_edge_hold["peakline_x_delta_um"] < alignment_abs["peakline_x_delta_um"]
                or alignment_abs_first_order_coupled_edge_hold["image_relative_l2"] < alignment_abs["image_relative_l2"]
            ),
            "none": alignment_abs,
            "first_order_envelope_only_interp": alignment_abs_first_order,
            "first_order_shift_envelope_and_mu2_interp": alignment_abs_first_order_coupled,
            "first_order_shift_envelope_and_mu2_analytic_gaussian": alignment_abs_first_order_coupled_analytic,
            "first_order_shift_envelope_and_mu2_interp_edge_hold": alignment_abs_first_order_coupled_edge_hold,
            "peakline_x_delta_improvement_um": {
                "first_order_envelope_only_interp": float(
                    alignment_abs["peakline_x_delta_um"] - alignment_abs_first_order["peakline_x_delta_um"]
                ),
                "first_order_shift_envelope_and_mu2_interp": float(
                    alignment_abs["peakline_x_delta_um"] - alignment_abs_first_order_coupled["peakline_x_delta_um"]
                ),
                "first_order_shift_envelope_and_mu2_analytic_gaussian": float(
                    alignment_abs["peakline_x_delta_um"] - alignment_abs_first_order_coupled_analytic["peakline_x_delta_um"]
                ),
                "first_order_shift_envelope_and_mu2_interp_edge_hold": float(
                    alignment_abs["peakline_x_delta_um"] - alignment_abs_first_order_coupled_edge_hold["peakline_x_delta_um"]
                ),
            },
            "image_relative_l2_improvement": {
                "first_order_envelope_only_interp": float(
                    alignment_abs["image_relative_l2"] - alignment_abs_first_order["image_relative_l2"]
                ),
                "first_order_shift_envelope_and_mu2_interp": float(
                    alignment_abs["image_relative_l2"] - alignment_abs_first_order_coupled["image_relative_l2"]
                ),
                "first_order_shift_envelope_and_mu2_analytic_gaussian": float(
                    alignment_abs["image_relative_l2"] - alignment_abs_first_order_coupled_analytic["image_relative_l2"]
                ),
                "first_order_shift_envelope_and_mu2_interp_edge_hold": float(
                    alignment_abs["image_relative_l2"] - alignment_abs_first_order_coupled_edge_hold["image_relative_l2"]
                ),
            },
            "centroid_opd_delta_improvement_um": {
                "first_order_envelope_only_interp": float(
                    alignment_abs["centroid_opd_delta_um"] - alignment_abs_first_order["centroid_opd_delta_um"]
                ),
                "first_order_shift_envelope_and_mu2_interp": float(
                    alignment_abs["centroid_opd_delta_um"] - alignment_abs_first_order_coupled["centroid_opd_delta_um"]
                ),
                "first_order_shift_envelope_and_mu2_analytic_gaussian": float(
                    alignment_abs["centroid_opd_delta_um"] - alignment_abs_first_order_coupled_analytic["centroid_opd_delta_um"]
                ),
                "first_order_shift_envelope_and_mu2_interp_edge_hold": float(
                    alignment_abs["centroid_opd_delta_um"] - alignment_abs_first_order_coupled_edge_hold["centroid_opd_delta_um"]
                ),
            },
            "lateral_shift_delta_x_k_um_summary": {
                "first_order_envelope_only_interp": asymptotic_low_na_abs_first_order["lateral_shift_delta_summary"],
                "first_order_shift_envelope_and_mu2_interp": asymptotic_low_na_abs_first_order_coupled["lateral_shift_delta_summary"],
                "first_order_shift_envelope_and_mu2_analytic_gaussian": asymptotic_low_na_abs_first_order_coupled_analytic["lateral_shift_delta_summary"],
                "first_order_shift_envelope_and_mu2_interp_edge_hold": asymptotic_low_na_abs_first_order_coupled_edge_hold["lateral_shift_delta_summary"],
            },
            "first_order_validity_summary": {
                "first_order_envelope_only_interp": compact_first_order_validity_summary(asymptotic_low_na_abs_first_order),
                "first_order_shift_envelope_and_mu2_interp": compact_first_order_validity_summary(asymptotic_low_na_abs_first_order_coupled),
                "first_order_shift_envelope_and_mu2_analytic_gaussian": compact_first_order_validity_summary(asymptotic_low_na_abs_first_order_coupled_analytic),
                "first_order_shift_envelope_and_mu2_interp_edge_hold": compact_first_order_validity_summary(asymptotic_low_na_abs_first_order_coupled_edge_hold),
            },
            "note": "Experimental A/B that keeps the tensor_closure second-order correction but adds a first-order wavelength-dependent lateral envelope shift derived from D1_slice_k, comparing envelope-only coupling against correction-shifted variants plus analytic-Gaussian and edge-hold shift implementations.",
            "dominant_error_summary_none": classify_dominant_error_bucket(alignment_abs),
            "dominant_error_summary_first_order_envelope_only_interp": classify_dominant_error_bucket(alignment_abs_first_order),
            "dominant_error_summary_first_order_shift_envelope_and_mu2_interp": classify_dominant_error_bucket(alignment_abs_first_order_coupled),
            "dominant_error_summary_first_order_shift_envelope_and_mu2_analytic_gaussian": classify_dominant_error_bucket(alignment_abs_first_order_coupled_analytic),
            "dominant_error_summary_first_order_shift_envelope_and_mu2_interp_edge_hold": classify_dominant_error_bucket(alignment_abs_first_order_coupled_edge_hold),
        }
    )
    report["checks"].append(
        {
            "name": "low_na_asymptotic_first_order_not_prioritized",
            "passed": bool(
                alignment_abs_first_order["peakline_x_delta_um"] >= alignment_abs["peakline_x_delta_um"]
                and alignment_abs_first_order["image_relative_l2"] >= alignment_abs["image_relative_l2"]
                and alignment_abs_first_order_coupled["peakline_x_delta_um"] >= alignment_abs["peakline_x_delta_um"]
                and alignment_abs_first_order_coupled["image_relative_l2"] >= alignment_abs["image_relative_l2"]
                and alignment_abs_first_order_coupled_analytic["peakline_x_delta_um"] >= alignment_abs["peakline_x_delta_um"]
                and alignment_abs_first_order_coupled_analytic["image_relative_l2"] >= alignment_abs["image_relative_l2"]
                and alignment_abs_first_order_coupled_edge_hold["peakline_x_delta_um"] >= alignment_abs["peakline_x_delta_um"]
                and alignment_abs_first_order_coupled_edge_hold["image_relative_l2"] >= alignment_abs["image_relative_l2"]
            ),
            "none": alignment_abs,
            "first_order_envelope_only_interp": alignment_abs_first_order,
            "first_order_shift_envelope_and_mu2_interp": alignment_abs_first_order_coupled,
            "first_order_shift_envelope_and_mu2_analytic_gaussian": alignment_abs_first_order_coupled_analytic,
            "first_order_shift_envelope_and_mu2_interp_edge_hold": alignment_abs_first_order_coupled_edge_hold,
            "note": "Current evidence does not support prioritizing the first_order lateral shift branch.",
        }
    )
    directional_first_order_case_payloads = []
    for case_definition in ROUND6P1_REPRESENTATIVE_CASES:
        bridge_case = run_round6p1_case(case_definition, mode=VECTOR_BRIDGE_MODE, library_path=tmatrix_path)
        tensor_case = run_round6p1_case(case_definition, mode=LOW_NA_ASYMPTOTIC_MODE, library_path=tmatrix_path)
        directional_case = run_round6p1_case(
            case_definition,
            mode=LOW_NA_ASYMPTOTIC_MODE,
            library_path=tmatrix_path,
            second_order_model="directional_field_expansion",
        )
        directional_first_case = run_round6p1_case(
            case_definition,
            mode=LOW_NA_ASYMPTOTIC_MODE,
            library_path=tmatrix_path,
            second_order_model="directional_field_expansion_first_order",
        )
        directional_case_scaled = apply_complex_field_match_scale(directional_case, bridge_case)
        directional_first_case_scaled = apply_complex_field_match_scale(directional_first_case, bridge_case)
        directional_first_order_case_payloads.append(
            {
                "case_name": case_definition["name"],
                "description": case_definition["description"],
                "tensor_closure": image_difference_diagnostics(
                    f"{case_definition['name']}_tensor_closure_vs_bridge",
                    snapshot_for_comparison(tensor_case),
                    snapshot_for_comparison(bridge_case),
                ),
                "directional_field_expansion_raw": image_difference_diagnostics(
                    f"{case_definition['name']}_directional_field_expansion_vs_bridge",
                    snapshot_for_comparison(directional_case),
                    snapshot_for_comparison(bridge_case),
                ),
                "directional_field_expansion_scaled": image_difference_diagnostics(
                    f"{case_definition['name']}_directional_field_expansion_scaled_vs_bridge",
                    snapshot_for_comparison(directional_case_scaled),
                    snapshot_for_comparison(bridge_case),
                ),
                "directional_field_expansion_first_order_raw": image_difference_diagnostics(
                    f"{case_definition['name']}_directional_field_expansion_first_order_vs_bridge",
                    snapshot_for_comparison(directional_first_case),
                    snapshot_for_comparison(bridge_case),
                ),
                "directional_field_expansion_first_order_scaled": image_difference_diagnostics(
                    f"{case_definition['name']}_directional_field_expansion_first_order_scaled_vs_bridge",
                    snapshot_for_comparison(directional_first_case_scaled),
                    snapshot_for_comparison(bridge_case),
                ),
                "directional_field_expansion_scale_factor_abs": float(directional_case_scaled["experimental_post_scale_factor_abs"]),
                "directional_field_expansion_scale_factor_phase_rad": float(directional_case_scaled["experimental_post_scale_factor_phase_rad"]),
                "directional_field_expansion_first_order_scale_factor_abs": float(directional_first_case_scaled["experimental_post_scale_factor_abs"]),
                "directional_field_expansion_first_order_scale_factor_phase_rad": float(directional_first_case_scaled["experimental_post_scale_factor_phase_rad"]),
            }
        )
    directional_first_order_summary = summarize_directional_first_order_ablation(directional_first_order_case_payloads)
    report["checks"].append(
        {
            "name": "low_na_asymptotic_directional_first_order_ablation",
            "passed": bool(directional_first_order_summary["directional_first_order_is_promising"]),
            "cases": directional_first_order_case_payloads,
            **directional_first_order_summary,
            "note": "Representative 3-case ablation comparing tensor_closure, directional_field_expansion, and directional_field_expansion_first_order, with post-hoc complex field matching retained for the directional branches so lateral-shift improvements can be judged without raw-amplitude scale confounds.",
        }
    )

    bridge_low_na_failure = solve_oct_particle_response(
        SourceConfig(n_lambda=181),
        GridConfig(z_span_um=20.0, n_z=601, x_span_um=6.0, n_x=61, na=0.08, n_bfp_dense=41, n_bfp_sparse=7),
        SolverConfig(mode=VECTOR_BRIDGE_MODE, particle_material=2.48, medium_material=1.40, diameter_nm=300.0, eps=0.18, beta_deg=50.0, incident_mode="linear_x", detection_mode="co_pol", library_path=tmatrix_path),
    )
    asymptotic_low_na_failure = solve_oct_particle_response(
        SourceConfig(n_lambda=181),
        GridConfig(z_span_um=20.0, n_z=601, x_span_um=6.0, n_x=61, na=0.08, n_bfp_dense=41, n_bfp_sparse=7),
        SolverConfig(mode=LOW_NA_ASYMPTOTIC_MODE, particle_material=2.48, medium_material=1.40, diameter_nm=300.0, eps=0.18, beta_deg=50.0, incident_mode="linear_x", detection_mode="co_pol", library_path=tmatrix_path),
    )
    alignment_failure = image_difference_diagnostics(
        "bridge_vs_asymptotic_failure_domain",
        snapshot_for_comparison(asymptotic_low_na_failure),
        snapshot_for_comparison(bridge_low_na_failure),
    )
    report["checks"].append(
        {
            "name": "low_na_asymptotic_failure_domain_lateral_shift",
            "passed": bool(
                alignment_failure["peakline_x_delta_um"] > 0.75
                and alignment_failure["image_relative_l2"] > 0.20
            ),
            "failure_case": alignment_failure,
            "dominant_error_summary": classify_dominant_error_bucket(alignment_failure),
            "note": "This benchmark is expected to diverge and marks a regime where low_na_asymptotic should not be treated as laterally faithful to the bridge model.",
        }
    )

    convergence_results = []
    convergence_grids = [(33, 7), (49, 9), (65, 11)]
    for dense, sparse in convergence_grids:
        sample = solve_oct_particle_response(
            SourceConfig(n_lambda=17),
            GridConfig(z_span_um=8.0, n_z=241, x_span_um=3.0, n_x=41, na=0.05, n_bfp_dense=dense, n_bfp_sparse=sparse),
            SolverConfig(mode=FULL_NA_BASELINE_MODE, particle_material=2.48, medium_material=1.40, diameter_nm=200.0, eps=0.10, beta_deg=45.0, library_path=tmatrix_path),
        )
        convergence_results.append(
            {
                "n_bfp_dense": dense,
                "n_bfp_sparse": sparse,
                **snapshot_for_comparison(sample),
            }
        )
    coarse_medium = image_difference_diagnostics("coarse_vs_medium", convergence_results[0], convergence_results[1])
    medium_fine = image_difference_diagnostics("medium_vs_fine", convergence_results[1], convergence_results[2])
    for item in convergence_results:
        del item["x_um"]
        del item["opd_um"]
        del item["image"]
        del item["raw_image"]
    report["checks"].append(
        {
            "name": "full_na_sampling_convergence",
            "passed": bool(
                coarse_medium["fwhm_delta_um"] < 0.2
                and coarse_medium["psr_delta_db"] < 1.0
                and coarse_medium["peakline_x_delta_um"] < 0.1
                and coarse_medium["image_relative_l2"] < 0.08
                and coarse_medium["raw_image_relative_l2"] < 0.12
                and coarse_medium["raw_peak_relative_delta"] < 0.15
                and medium_fine["fwhm_delta_um"] < 0.2
                and medium_fine["psr_delta_db"] < 1.0
                and medium_fine["peakline_x_delta_um"] < 0.1
                and medium_fine["image_relative_l2"] < 0.08
                and medium_fine["raw_image_relative_l2"] < 0.08
                and medium_fine["raw_peak_relative_delta"] < 0.10
            ),
            "grids": convergence_results,
            "coarse_vs_medium": coarse_medium,
            "medium_vs_fine": medium_fine,
        }
    )

    spectral_results = []
    spectral_samples = [61, 121, 241]
    for n_lambda in spectral_samples:
        sample = solve_oct_particle_response(
            SourceConfig(n_lambda=n_lambda),
            GridConfig(z_span_um=8.0, n_z=241, x_span_um=3.0, n_x=41, na=0.05, n_bfp_dense=49, n_bfp_sparse=9),
            SolverConfig(mode=VECTOR_BRIDGE_MODE, particle_material=2.48, medium_material=1.40, diameter_nm=200.0, eps=0.10, beta_deg=45.0, incident_mode="linear_x", detection_mode="co_pol", library_path=tmatrix_path),
        )
        spectral_results.append(
            {
                "n_lambda": n_lambda,
                **snapshot_for_comparison(sample),
            }
        )
    spectral_coarse_medium = image_difference_diagnostics("n_lambda_61_vs_121", spectral_results[0], spectral_results[1])
    spectral_medium_fine = image_difference_diagnostics("n_lambda_121_vs_241", spectral_results[1], spectral_results[2])
    for item in spectral_results:
        del item["x_um"]
        del item["opd_um"]
        del item["image"]
        del item["raw_image"]
    report["checks"].append(
        {
            "name": "bridge_spectral_sampling_convergence",
            "passed": bool(
                spectral_coarse_medium["fwhm_delta_um"] < 0.25
                and spectral_coarse_medium["psr_delta_db"] < 1.5
                and spectral_coarse_medium["peakline_x_delta_um"] < 0.1
                and spectral_coarse_medium["image_relative_l2"] < 0.12
                and spectral_medium_fine["fwhm_delta_um"] < 0.15
                and spectral_medium_fine["psr_delta_db"] < 1.0
                and spectral_medium_fine["peakline_x_delta_um"] < 0.1
                and spectral_medium_fine["image_relative_l2"] < 0.08
            ),
            "samples": spectral_results,
            "coarse_vs_medium": spectral_coarse_medium,
            "medium_vs_fine": spectral_medium_fine,
        }
    )

    asymptotic_spectral_results = []
    for n_lambda in spectral_samples:
        sample = solve_oct_particle_response(
            SourceConfig(n_lambda=n_lambda),
            GridConfig(z_span_um=8.0, n_z=241, x_span_um=3.0, n_x=41, na=0.05, n_bfp_dense=49, n_bfp_sparse=9),
            SolverConfig(mode=LOW_NA_ASYMPTOTIC_MODE, particle_material=2.48, medium_material=1.40, diameter_nm=200.0, eps=0.10, beta_deg=45.0, incident_mode="linear_x", detection_mode="co_pol", library_path=tmatrix_path),
        )
        asymptotic_spectral_results.append(
            {
                "n_lambda": n_lambda,
                **snapshot_for_comparison(sample),
            }
        )
    asymptotic_spectral_coarse_medium = image_difference_diagnostics(
        "asymptotic_n_lambda_61_vs_121", asymptotic_spectral_results[0], asymptotic_spectral_results[1]
    )
    asymptotic_spectral_medium_fine = image_difference_diagnostics(
        "asymptotic_n_lambda_121_vs_241", asymptotic_spectral_results[1], asymptotic_spectral_results[2]
    )
    for item in asymptotic_spectral_results:
        del item["x_um"]
        del item["opd_um"]
        del item["image"]
        del item["raw_image"]
    report["checks"].append(
        {
            "name": "asymptotic_spectral_sampling_convergence",
            "passed": bool(
                asymptotic_spectral_coarse_medium["fwhm_delta_um"] < 0.25
                and asymptotic_spectral_coarse_medium["psr_delta_db"] < 1.5
                and asymptotic_spectral_coarse_medium["centroid_opd_delta_um"] < 0.15
                and asymptotic_spectral_coarse_medium["image_relative_l2"] < 0.12
                and asymptotic_spectral_medium_fine["fwhm_delta_um"] < 0.15
                and asymptotic_spectral_medium_fine["psr_delta_db"] < 1.0
                and asymptotic_spectral_medium_fine["centroid_opd_delta_um"] < 0.10
                and asymptotic_spectral_medium_fine["image_relative_l2"] < 0.08
            ),
            "samples": asymptotic_spectral_results,
            "coarse_vs_medium": asymptotic_spectral_coarse_medium,
            "medium_vs_fine": asymptotic_spectral_medium_fine,
        }
    )

    paper_safe_cases = [
        solve_oct_particle_response(
            SourceConfig(lambda0_nm=855.0, fwhm_nm=56.0, n_lambda=31),
            GridConfig(z_span_um=6.0, n_z=101, x_span_um=2.0, n_x=11, na=0.04, n_bfp_dense=25, n_bfp_sparse=5),
            SolverConfig(mode=LOW_NA_BASELINE_MODE, particle_material=2.48, medium_material=1.40, diameter_nm=180.0, strict_material_range=True, library_path=tmatrix_path),
        ),
        solve_oct_particle_response(
            SourceConfig(lambda0_nm=855.0, fwhm_nm=56.0, n_lambda=31),
            GridConfig(z_span_um=6.0, n_z=101, x_span_um=2.0, n_x=11, na=0.04, n_bfp_dense=25, n_bfp_sparse=5),
            SolverConfig(mode=FULL_NA_BASELINE_MODE, particle_material=2.48, medium_material=1.40, diameter_nm=180.0, strict_material_range=True, library_path=tmatrix_path),
        ),
        solve_oct_particle_response(
            SourceConfig(lambda0_nm=855.0, fwhm_nm=56.0, n_lambda=31),
            GridConfig(z_span_um=6.0, n_z=101, x_span_um=2.0, n_x=11, na=0.04, n_bfp_dense=25, n_bfp_sparse=5),
            SolverConfig(mode=VECTOR_BRIDGE_MODE, particle_material=2.48, medium_material=1.40, diameter_nm=180.0, incident_mode="linear_x", detection_mode="co_pol", strict_material_range=True, library_path=tmatrix_path),
        ),
        solve_oct_particle_response(
            SourceConfig(lambda0_nm=855.0, fwhm_nm=56.0, n_lambda=31),
            GridConfig(z_span_um=6.0, n_z=101, x_span_um=2.0, n_x=11, na=0.04, n_bfp_dense=25, n_bfp_sparse=5),
            SolverConfig(mode=LOW_NA_ASYMPTOTIC_MODE, particle_material=2.48, medium_material=1.40, diameter_nm=180.0, incident_mode="linear_x", detection_mode="co_pol", strict_material_range=True, library_path=tmatrix_path),
        ),
    ]
    report["checks"].append(
        {
            "name": "paper_safe_regression",
            "passed": all(
                case["paper_safe"]
                and "peakline_raw_axial_intensity" in case
                and "raw_intensity_xz" in case
                and "raw_peak_intensity" in case
                and "normalization" in case
                and "normalization_scope" in case["normalization"]
                and "absolute_amplitude_supported" in case["normalization"]
                for case in paper_safe_cases
            ),
            "modes": [case["mode"] for case in paper_safe_cases],
            "paper_safe_flags": [bool(case["paper_safe"]) for case in paper_safe_cases],
            "peakline_raw_axial_intensity_present": ["peakline_raw_axial_intensity" in case for case in paper_safe_cases],
            "raw_peak_intensity_present": ["raw_peak_intensity" in case for case in paper_safe_cases],
            "normalization_scope_present": [
                "normalization" in case and "normalization_scope" in case["normalization"] for case in paper_safe_cases
            ],
            "absolute_amplitude_supported_flags": [
                case.get("normalization", {}).get("absolute_amplitude_supported") for case in paper_safe_cases
            ],
        }
    )

    paper_contract_cases = [
        paper_facing_contract_diagnostics(case)
        for case in paper_safe_cases
    ]
    report["checks"].append(
        {
            "name": "paper_facing_result_contract",
            "passed": all(
                (not case["missing"])
                and case["depth_axis_status"] == "helper_only_not_frozen_for_paper"
                and case["paper_safe"]
                and case["schema_version"] == SCHEMA_VERSION
                for case in paper_contract_cases
            ),
            "results": paper_contract_cases,
        }
    )

    schema_cases = {
        "low_na_separable_baseline": baseline_low_na,
        "full_na_scalar_fixed_basis": full_na,
        "vector_pupil_overlap_bridge": bridge,
        "low_na_asymptotic": asymptotic,
    }
    schema_results = [schema_regression_diagnostics(sample) for sample in schema_cases.values()]
    report["checks"].append(
        {
            "name": "schema_regression_round6",
            "passed": all((not item["forbidden_present"]) and (not item["required_missing"]) and item["schema_version"] == SCHEMA_VERSION for item in schema_results),
            "results": schema_results,
        }
    )

    report.update(directional_first_order_summary)
    annotate_check_statuses(report)
    report.update(summarize_worst_case_metrics(report))
    report.update(summarize_open_model_limits(report))
    report = apply_basis_projection_summary(report, basis_projection_summary)
    report = apply_coefficient_recovery_summary(report, coefficient_recovery_summary)
    report = apply_fit_sensitivity_summary(report, fit_sensitivity_summary)
    report = apply_coefficient_injection_summary(report, coefficient_injection_summary)
    report = apply_coefficient_map_audit_summary(report, coefficient_map_audit_summary)
    report = apply_coefficient_map_stability_summary(report, coefficient_map_stability_summary)
    report = apply_fit_strategy_ablation_summary(report, fit_strategy_ablation_summary)
    report = apply_coefficient_map_ablation_summary(report, coefficient_map_ablation_summary)
    report = apply_slice_axis_crosscheck_summary(report, slice_axis_crosscheck_summary)
    report = apply_measurement_protocol_summary(report, measurement_protocol_summary)
    report = apply_particle_size_sweep_summary(report, particle_size_sweep_summary)
    report = apply_cp310_evidence_readiness_summary(report, cp310_evidence_readiness_summary)
    return summarize_guidance_confidence(report)


def build_arg_parser():
    parser = argparse.ArgumentParser(description="Validate round6 OCT non-spherical PSF solver contracts and model-limit benchmarks.")
    parser.add_argument("--output-prefix", default=DEFAULT_REPORT_VERSION_TAG)
    parser.add_argument("--output-json", default=None)
    parser.add_argument("--failure-summary-txt", default=None)
    parser.add_argument(
        "--basis-projection-report",
        default=None,
        help="Optional explicit round6p1 basis projection diagnostics JSON to merge into the top-level summary. Omit to keep validator results independent from prior artifacts.",
    )
    parser.add_argument(
        "--coefficient-recovery-report",
        default=None,
        help="Optional explicit round6p1 coefficient recovery diagnostics JSON to merge into the top-level summary. Omit to keep validator results independent from prior artifacts.",
    )
    parser.add_argument(
        "--fit-sensitivity-report",
        default=None,
        help="Optional explicit round6p1 fit sensitivity diagnostics JSON to merge into the top-level summary.",
    )
    parser.add_argument(
        "--coefficient-injection-report",
        default=None,
        help="Optional explicit round6p1 coefficient injection diagnostics JSON to merge into the top-level summary. Omit to keep validator results independent from prior artifacts.",
    )
    parser.add_argument(
        "--coefficient-map-audit-report",
        default=None,
        help="Optional explicit round6p1 coefficient-map audit diagnostics JSON to merge into the top-level summary.",
    )
    parser.add_argument(
        "--coefficient-map-stability-report",
        default=None,
        help="Optional explicit round6p1 coefficient-map stability diagnostics JSON to merge into the top-level summary.",
    )
    parser.add_argument(
        "--coefficient-map-ablation-report",
        default=None,
        help="Optional explicit round6p1 coefficient-map ablation diagnostics JSON to merge into the top-level summary.",
    )
    parser.add_argument(
        "--fit-strategy-ablation-report",
        default=None,
        help="Optional explicit round6p1 fit-strategy ablation diagnostics JSON to merge into the top-level summary.",
    )
    parser.add_argument(
        "--slice-axis-crosscheck-report",
        default=None,
        help="Optional explicit round6p1 x/y lateral-slice cross-check diagnostics JSON to merge into the top-level summary.",
    )
    parser.add_argument(
        "--measurement-protocol-report",
        default=None,
        help="Optional explicit round6p1 measurement protocol bias JSON to merge into the top-level summary.",
    )
    parser.add_argument(
        "--particle-size-sweep-report",
        default=None,
        help="Optional explicit round6p1 particle-size sweep JSON to merge into the top-level summary.",
    )
    parser.add_argument(
        "--cp310-evidence-readiness-report",
        default=None,
        help="Optional explicit CPython 3.10 evidence-rebuild readiness JSON to merge into the top-level summary.",
    )
    parser.add_argument(
        "--strict-gates",
        action="store_true",
        help="Treat model-limit failures as blocking for process exit. Equivalent to OCT_VALIDATE_STRICT=1.",
    )
    parser.add_argument("--no-write", action="store_true", help="Print the JSON report but skip writing report artifacts to disk.")
    return parser


if __name__ == "__main__":
    args = build_arg_parser().parse_args()
    basis_projection_summary = load_basis_projection_summary(args.basis_projection_report) if args.basis_projection_report else None
    coefficient_recovery_summary = (
        load_coefficient_recovery_summary(args.coefficient_recovery_report)
        if args.coefficient_recovery_report
        else None
    )
    fit_sensitivity_summary = load_fit_sensitivity_summary(args.fit_sensitivity_report) if args.fit_sensitivity_report else None
    coefficient_injection_summary = (
        load_coefficient_injection_summary(args.coefficient_injection_report)
        if args.coefficient_injection_report
        else None
    )
    coefficient_map_audit_summary = (
        load_coefficient_map_audit_summary(args.coefficient_map_audit_report)
        if args.coefficient_map_audit_report
        else None
    )
    coefficient_map_stability_summary = (
        load_coefficient_map_stability_summary(args.coefficient_map_stability_report)
        if args.coefficient_map_stability_report
        else None
    )
    coefficient_map_ablation_summary = (
        load_coefficient_map_ablation_summary(args.coefficient_map_ablation_report)
        if args.coefficient_map_ablation_report
        else None
    )
    fit_strategy_ablation_summary = (
        load_fit_strategy_ablation_summary(args.fit_strategy_ablation_report)
        if args.fit_strategy_ablation_report
        else None
    )
    slice_axis_crosscheck_summary = (
        load_slice_axis_crosscheck_summary(args.slice_axis_crosscheck_report)
        if args.slice_axis_crosscheck_report
        else None
    )
    measurement_protocol_summary = (
        load_measurement_protocol_summary(args.measurement_protocol_report)
        if args.measurement_protocol_report
        else None
    )
    particle_size_sweep_summary = (
        load_particle_size_sweep_summary(args.particle_size_sweep_report)
        if args.particle_size_sweep_report
        else None
    )
    cp310_evidence_readiness_summary = (
        load_cp310_evidence_readiness_summary(args.cp310_evidence_readiness_report)
        if args.cp310_evidence_readiness_report
        else None
    )
    report = validate(
        basis_projection_summary=basis_projection_summary,
        coefficient_recovery_summary=coefficient_recovery_summary,
        fit_sensitivity_summary=fit_sensitivity_summary,
        coefficient_injection_summary=coefficient_injection_summary,
        coefficient_map_audit_summary=coefficient_map_audit_summary,
        coefficient_map_stability_summary=coefficient_map_stability_summary,
        coefficient_map_ablation_summary=coefficient_map_ablation_summary,
        fit_strategy_ablation_summary=fit_strategy_ablation_summary,
        slice_axis_crosscheck_summary=slice_axis_crosscheck_summary,
        measurement_protocol_summary=measurement_protocol_summary,
        particle_size_sweep_summary=particle_size_sweep_summary,
        cp310_evidence_readiness_summary=cp310_evidence_readiness_summary,
    )
    payload = json.dumps(report, indent=2)
    print(payload)
    output_json = Path(args.output_json) if args.output_json else build_report_path(args.output_prefix, "validation_summary", "json")
    failure_summary_txt = (
        Path(args.failure_summary_txt)
        if args.failure_summary_txt
        else build_report_path(args.output_prefix, "validation_failure_summary", "txt")
    )
    if not args.no_write:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        failure_summary_txt.parent.mkdir(parents=True, exist_ok=True)
        write_results = {
            "validation_summary": write_text_with_runtime_sidecar(output_json, payload + "\n"),
            "failure_summary": write_text_with_runtime_sidecar(
                failure_summary_txt,
                render_failure_summary(report),
            ),
        }
        if any(result["status"] != "canonical_artifact_updated" for result in write_results.values()):
            print(json.dumps({"validation_artifact_write_results": write_results}, indent=2), file=sys.stderr)
    raise SystemExit(exit_code_from_report(report, strict_gates=args.strict_gates))
