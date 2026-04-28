import importlib.util
import json
import os
import shutil
import sys
import types
import unittest
import warnings
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from apps.report_paths import build_report_path as build_report_path_core
from apps.report_paths import resolve_reports_dir as resolve_reports_dir_core
from apps.report_paths import resolve_runtime_root as resolve_runtime_root_core
from diagnostics import _runtime as DIAGNOSTIC_RUNTIME_CORE
from diagnostics import basis_coefficient_recovery as COEFF_RECOVERY_CORE
from diagnostics import bridge_basis_projection as BASIS_PROJECTION_CORE
from diagnostics import coefficient_map_ablation as COEFF_MAP_ABLATION_CORE
from diagnostics import coefficient_map_audit as COEFF_MAP_AUDIT_CORE
from diagnostics import coefficient_map_stability as COEFF_MAP_STABILITY_CORE
from diagnostics import coefficient_injection as COEFF_INJECTION_CORE
from diagnostics import fit_sensitivity as FIT_SENSITIVITY_CORE
from diagnostics import fit_strategy_ablation as FIT_STRATEGY_CORE
from diagnostics import slice_axis_crosscheck as SLICE_AXIS_CROSSCHECK_CORE
from measurement_protocol.bias_experiment import build_measurement_protocol_package
from oct_forward import (
    build_fd_oct_interference_spectrum,
    extract_solver_result_contract,
    reconstruct_fd_oct_a_scan,
)
from physics import tmatrix_backend_registry as TMATRIX_REGISTRY_CORE
from solvers import coefficient_path_bundle as COEFF_BUNDLE_CORE
from solvers import effective_channel_coefficients as COEFF_CORE
from solvers import low_na_effective_channel as LOW_NA_COEFF_CORE


def resolve_test_module_path(*names: str) -> Path:
    roots = [ROOT / "scripts", ROOT]
    for base in roots:
        for name in names:
            candidate = base / name
            if candidate.exists():
                if str(base) not in sys.path:
                    sys.path.insert(0, str(base))
                return candidate
    raise FileNotFoundError(f"Unable to resolve any of: {', '.join(names)}")


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def workspace_tempdir(prefix: str) -> Path:
    if (ROOT / "scripts").exists():
        root = ROOT / "reports" / "_unit_test_tmp"
    else:
        root = ROOT / "_unit_test_tmp"
    root.mkdir(parents=True, exist_ok=True)
    safe_prefix = prefix.rstrip("-")
    path = root / f"{safe_prefix}-{os.getpid()}"
    shutil.rmtree(path, ignore_errors=True)
    path.mkdir(parents=True, exist_ok=True)
    return path


SOLVER = load_module(
    "oct_nonspherical_psf_solver",
    resolve_test_module_path("oct_nonspherical_psf_solver.py", "01_oct_nonspherical_psf_solver.py"),
)
LOW_NA = load_module(
    "round6_low_na_asymptotic_test",
    resolve_test_module_path("11_low_na_asymptotic.py", "03_low_na_asymptotic.py"),
)
VALIDATOR = load_module(
    "round6_validate_oct_solver_test",
    resolve_test_module_path("validate_oct_nonspherical_psf_solver.py", "04_validate_oct_nonspherical_psf_solver.py"),
)
EVIDENCE_BUILDER = load_module(
    "round6_evidence_builder_test",
    resolve_test_module_path("build_round6p1_evidence_package.py", "05_build_round6p1_evidence_package.py"),
)
MEASUREMENT_CONTRACT_REFRESH = load_module(
    "round6_measurement_contract_refresh_test",
    resolve_test_module_path(
        "refresh_round6p1_measurement_contract_artifacts.py",
        "30_refresh_round6p1_measurement_contract_artifacts.py",
    ),
)
CP310_EVIDENCE_REBUILD = load_module(
    "round6_cp310_evidence_rebuild_test",
    resolve_test_module_path(
        "controlled_cp310_evidence_rebuild.py",
        "31_controlled_cp310_evidence_rebuild.py",
    ),
)
PARTICLE_SWEEP = load_module(
    "round6_particle_size_sweep_test",
    resolve_test_module_path("particle_size_sweep_runner.py", "06_particle_size_sweep_runner.py", "28_particle_size_sweep_runner.py"),
)
COEFF_RECOVERY = load_module(
    "round6_bridge_basis_coefficient_recovery_test",
    resolve_test_module_path("15_bridge_basis_coefficient_recovery.py", "07_bridge_basis_coefficient_recovery.py"),
)
FIT_SENSITIVITY = load_module(
    "round6_fit_sensitivity_test",
    resolve_test_module_path("16_effective_channel_fit_sensitivity.py", "08_effective_channel_fit_sensitivity.py"),
)
SLICE_AXIS_CROSSCHECK = load_module(
    "round6_slice_axis_crosscheck_test",
    resolve_test_module_path("19_lateral_slice_axis_crosscheck.py", "11_lateral_slice_axis_crosscheck.py"),
)
from measurement_protocol import compare_measurement_snapshots, extract_measurement_snapshot
from measurement_protocol import psf_bias_protocol as PSF_PROTOCOL_CORE


class LowNaAsymptoticHelperTests(unittest.TestCase):
    def test_builtin_material_support_has_project_window_metadata(self):
        lambda_nm = np.array([845.0, 880.0, 915.0])
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            particle = SOLVER.validate_material_support(
                "TiO2-anatase",
                lambda_nm,
                strict_material_range=True,
                role="particle_material",
            )
            medium = SOLVER.validate_material_support(
                "PDMS",
                lambda_nm,
                strict_material_range=True,
                role="medium_material",
            )
        self.assertEqual(len(caught), 0)
        self.assertEqual(particle["status"], "validated_range")
        self.assertEqual(medium["status"], "validated_range")
        self.assertEqual(particle["range_um"], SOLVER.PROJECT_OCT_MATERIAL_SUPPORT_RANGE_UM)
        self.assertEqual(medium["range_basis"], "project OCT operating window guard")
        self.assertEqual(medium["extrapolation_policy"], "error_outside_encoded_range")
        with self.assertRaises(ValueError):
            SOLVER.validate_material_support("PDMS", np.array([650.0]), strict_material_range=True, role="medium_material")

        def _unranged_debug_material(_l_um):
            return 1.40

        with self.assertRaises(ValueError):
            SOLVER.validate_material_support(_unranged_debug_material, lambda_nm, strict_material_range=True, role="debug_material")

    def test_runtime_report_resolution_supports_repo_and_flat_bundle_layouts(self):
        validator_anchor = resolve_test_module_path("validate_oct_nonspherical_psf_solver.py", "04_validate_oct_nonspherical_psf_solver.py")
        repo_reports = SOLVER.resolve_reports_dir(validator_anchor)
        if validator_anchor.parent.name == "scripts":
            self.assertEqual(repo_reports, ROOT / "reports")
        else:
            self.assertEqual(repo_reports, ROOT)

        bundle_root = workspace_tempdir("runtime-layout-")
        try:
            (bundle_root / "00_README.txt").write_text("bundle", encoding="utf-8")
            (bundle_root / "01_oct_nonspherical_psf_solver.py").write_text("# bundle solver", encoding="utf-8")
            bundle_anchor = bundle_root / "04_validate_oct_nonspherical_psf_solver.py"
            self.assertEqual(SOLVER.resolve_runtime_root(bundle_anchor), bundle_root)
            self.assertEqual(SOLVER.resolve_reports_dir(bundle_anchor), bundle_root)
            self.assertEqual(resolve_runtime_root_core(bundle_anchor), bundle_root)
            self.assertEqual(resolve_reports_dir_core(bundle_anchor), bundle_root)
        finally:
            shutil.rmtree(bundle_root, ignore_errors=True)

    def test_oct_forward_result_contract_requires_expected_solver_keys(self):
        with self.assertRaises(KeyError):
            extract_solver_result_contract({"mode": "partial"})

    def test_oct_forward_result_contract_coerces_core_arrays(self):
        result = {
            "mode": "demo",
            "lateral_slice_axis": "x",
            "x_um": [-1.0, 0.0, 1.0],
            "opd_um": [-2.0, 0.0, 2.0],
            "raw_intensity_xz": [[0.0, 1.0, 0.0], [0.2, 2.0, 0.1], [0.0, 0.5, 0.0]],
            "global_peak_index": [1, 1],
            "peakline_x_um": 0.0,
            "axial_intensity_metrics": {"peak_opd_um": 0.0, "centroid_opd_um": 0.1, "fwhm_opd_um": 1.0, "psr_db": 5.0, "sidelobe_energy_fraction": 0.2},
            "raw_peak_intensity": 2.0,
        }
        contract = extract_solver_result_contract(result)
        self.assertEqual(contract["global_peak_index"], (1, 1))
        self.assertEqual(contract["x_um"].shape, (3,))
        self.assertEqual(contract["raw_intensity_xz"].shape, (3, 3))

    def test_oct_forward_result_contract_rejects_mismatched_image_shape(self):
        result = {
            "mode": "demo",
            "lateral_slice_axis": "x",
            "x_um": [-1.0, 0.0, 1.0],
            "opd_um": [-2.0, 0.0, 2.0],
            "raw_intensity_xz": [[0.0, 1.0], [0.2, 2.0], [0.0, 0.5]],
            "global_peak_index": [1, 1],
            "peakline_x_um": 0.0,
            "axial_intensity_metrics": {"peak_opd_um": 0.0, "centroid_opd_um": 0.1, "fwhm_opd_um": 1.0, "psr_db": 5.0, "sidelobe_energy_fraction": 0.2},
            "raw_peak_intensity": 2.0,
        }
        with self.assertRaises(ValueError):
            extract_solver_result_contract(result)

    def test_oct_forward_result_contract_requires_complete_axial_metrics(self):
        result = {
            "mode": "demo",
            "lateral_slice_axis": "x",
            "x_um": [-1.0, 0.0, 1.0],
            "opd_um": [-2.0, 0.0, 2.0],
            "raw_intensity_xz": [[0.0, 1.0, 0.0], [0.2, 2.0, 0.1], [0.0, 0.5, 0.0]],
            "global_peak_index": [1, 1],
            "peakline_x_um": 0.0,
            "axial_intensity_metrics": {"peak_opd_um": 0.0, "centroid_opd_um": 0.1, "fwhm_opd_um": 1.0, "psr_db": 5.0},
            "raw_peak_intensity": 2.0,
        }
        with self.assertRaises(KeyError):
            extract_solver_result_contract(result)

    def test_oct_forward_result_contract_rejects_out_of_bounds_peak_index(self):
        result = {
            "mode": "demo",
            "lateral_slice_axis": "x",
            "x_um": [-1.0, 0.0, 1.0],
            "opd_um": [-2.0, 0.0, 2.0],
            "raw_intensity_xz": [[0.0, 1.0, 0.0], [0.2, 2.0, 0.1], [0.0, 0.5, 0.0]],
            "global_peak_index": [5, 1],
            "peakline_x_um": 0.0,
            "axial_intensity_metrics": {"peak_opd_um": 0.0, "centroid_opd_um": 0.1, "fwhm_opd_um": 1.0, "psr_db": 5.0, "sidelobe_energy_fraction": 0.2},
            "raw_peak_intensity": 2.0,
        }
        with self.assertRaises(ValueError):
            extract_solver_result_contract(result)

    def test_oct_forward_result_contract_requires_lateral_slice_axis(self):
        result = {
            "mode": "demo",
            "x_um": [-1.0, 0.0, 1.0],
            "opd_um": [-2.0, 0.0, 2.0],
            "raw_intensity_xz": [[0.0, 1.0, 0.0], [0.2, 2.0, 0.1], [0.0, 0.5, 0.0]],
            "global_peak_index": [1, 1],
            "peakline_x_um": 0.0,
            "axial_intensity_metrics": {"peak_opd_um": 0.0, "centroid_opd_um": 0.1, "fwhm_opd_um": 1.0, "psr_db": 5.0, "sidelobe_energy_fraction": 0.2},
            "raw_peak_intensity": 2.0,
        }
        with self.assertRaises(KeyError):
            extract_solver_result_contract(result)

    def test_report_path_module_builds_round_tagged_output_paths(self):
        validator_anchor = resolve_test_module_path("validate_oct_nonspherical_psf_solver.py", "04_validate_oct_nonspherical_psf_solver.py")
        path = build_report_path_core("round6p1", "validation_summary", "json", anchor_path=validator_anchor)
        self.assertEqual(path.name, "round6p1_validation_summary.json")
        self.assertEqual(path.parent, resolve_reports_dir_core(validator_anchor))

    def test_low_na_effective_channel_api_is_reexported_from_solver_module(self):
        self.assertIs(LOW_NA.estimate_effective_channel_B_C2, LOW_NA_COEFF_CORE.estimate_effective_channel_B_C2)
        self.assertIs(LOW_NA.resolve_effective_channel_fit_config, LOW_NA_COEFF_CORE.resolve_effective_channel_fit_config)
        self.assertIs(LOW_NA.build_directional_field_expansion_profiles, LOW_NA_COEFF_CORE.build_directional_field_expansion_profiles)
        self.assertIs(LOW_NA.build_first_order_field_profile, LOW_NA_COEFF_CORE.build_first_order_field_profile)

    def test_diagnostics_scripts_are_wrappers_over_package_modules(self):
        basis_projection_script = load_module(
            "round6_basis_projection_wrapper_test",
            resolve_test_module_path("14_bridge_basis_projection_diagnostics.py", "06_bridge_basis_projection_diagnostics.py"),
        )
        self.assertIs(COEFF_RECOVERY.build_coefficient_recovery_report, COEFF_RECOVERY_CORE.build_coefficient_recovery_report)
        self.assertIs(COEFF_RECOVERY._fit_coefficients, COEFF_RECOVERY_CORE._fit_coefficients)
        self.assertIs(
            basis_projection_script.build_basis_projection_report,
            BASIS_PROJECTION_CORE.build_basis_projection_report,
        )
        coefficient_injection_script = load_module(
            "round6_coefficient_injection_wrapper_test",
            resolve_test_module_path("17_bridge_coefficient_injection_diagnostics.py", "09_bridge_coefficient_injection_diagnostics.py"),
        )
        fit_sensitivity_script = load_module(
            "round6_fit_sensitivity_wrapper_test",
            resolve_test_module_path("16_effective_channel_fit_sensitivity.py", "08_effective_channel_fit_sensitivity.py"),
        )
        fit_strategy_script = load_module(
            "round6_fit_strategy_wrapper_test",
            resolve_test_module_path("18_effective_channel_fit_strategy_ablation.py", "10_effective_channel_fit_strategy_ablation.py"),
        )
        slice_axis_crosscheck_script = load_module(
            "round6_slice_axis_crosscheck_wrapper_test",
            resolve_test_module_path("19_lateral_slice_axis_crosscheck.py", "11_lateral_slice_axis_crosscheck.py"),
        )
        coefficient_map_audit_script = load_module(
            "round6_coefficient_map_audit_wrapper_test",
            resolve_test_module_path("20_coefficient_map_audit.py"),
        )
        coefficient_map_stability_script = load_module(
            "round6_coefficient_map_stability_wrapper_test",
            resolve_test_module_path("21_coefficient_map_stability.py"),
        )
        coefficient_map_ablation_script = load_module(
            "round6_coefficient_map_ablation_wrapper_test",
            resolve_test_module_path("22_coefficient_map_ablation.py"),
        )
        self.assertIs(
            coefficient_injection_script.build_coefficient_injection_report,
            COEFF_INJECTION_CORE.build_coefficient_injection_report,
        )
        self.assertIs(fit_sensitivity_script.build_fit_sensitivity_report, FIT_SENSITIVITY_CORE.build_fit_sensitivity_report)
        self.assertIs(fit_strategy_script.build_fit_strategy_ablation_report, FIT_STRATEGY_CORE.build_fit_strategy_ablation_report)
        self.assertIs(
            slice_axis_crosscheck_script.build_slice_axis_crosscheck_report,
            SLICE_AXIS_CROSSCHECK_CORE.build_slice_axis_crosscheck_report,
        )
        self.assertIs(
            coefficient_map_audit_script.build_coefficient_map_audit_report,
            COEFF_MAP_AUDIT_CORE.build_coefficient_map_audit_report,
        )
        self.assertIs(
            coefficient_map_stability_script.build_coefficient_map_stability_report,
            COEFF_MAP_STABILITY_CORE.build_coefficient_map_stability_report,
        )
        self.assertIs(
            coefficient_map_ablation_script.build_coefficient_map_ablation_report,
            COEFF_MAP_ABLATION_CORE.build_coefficient_map_ablation_report,
        )

    def test_coefficient_map_audit_prefers_non_identity_when_it_improves_bridge_alignment(self):
        case_reports = [
            {
                "best_model_id": "shared_complex_scale_map",
                "map_models": [],
                "native_asymptotic_vs_bridge": {},
            },
            {
                "best_model_id": "componentwise_complex_scale_map",
                "map_models": [],
                "native_asymptotic_vs_bridge": {},
            },
            {
                "best_model_id": "identity_slice_projected_rendered_basis",
                "map_models": [],
                "native_asymptotic_vs_bridge": {},
            },
        ]
        self.assertEqual(
            COEFF_MAP_AUDIT_CORE._recommend_next_action(case_reports),
            "audit_coefficient_map_stage_before_basis_expansion",
        )

    def test_coefficient_map_stability_promotes_shared_candidate_when_leave_one_out_is_consistent(self):
        aggregate = {
            "cases_improving_peakline": 3,
            "cases_improving_image_l2": 3,
            "total_cases": 3,
            "mean_peakline_x_delta_um": 0.0,
            "mean_image_relative_l2": 0.02,
        }
        identity_aggregate = {
            "mean_image_relative_l2": 0.5,
        }
        pairwise = [
            {"normalized_frobenius_distance": 0.2},
            {"normalized_frobenius_distance": 0.3},
            {"normalized_frobenius_distance": 0.4},
        ]
        self.assertEqual(
            COEFF_MAP_STABILITY_CORE._recommend_next_action(
                best_model_id="fitted_linear_map_3x3",
                best_aggregate=aggregate,
                identity_aggregate=identity_aggregate,
                pairwise_case_map_distances=pairwise,
            ),
            "prototype_shared_coefficient_map_candidate_before_measurement_wrapper",
        )

    def test_coefficient_map_generalization_panel_extends_representative_cases(self):
        representative = [case["name"] for case in VALIDATOR.ROUND6P1_REPRESENTATIVE_CASES]
        generalization = [case["name"] for case in VALIDATOR.ROUND6P1_COEFFICIENT_MAP_GENERALIZATION_CASES]
        self.assertGreater(len(generalization), len(representative))
        self.assertEqual(generalization[: len(representative)], representative)

    def test_shared_candidate_artifact_roundtrip_uses_public_contract(self):
        tmp_dir = workspace_tempdir("shared-map-artifact-")
        try:
            fitted_map = COEFF_BUNDLE_CORE.FittedCoefficientMap(
                coefficient_map_model_id="componentwise_complex_scale_map",
                map_matrix=np.diag(
                    np.asarray([1.1 + 0.0j, 0.9 + 0.1j, 1.05 - 0.02j], dtype=np.complex128)
                ),
                coefficient_map_note="unit-test componentwise map",
                coefficient_map_parameters={"unit_test": True},
            )
            artifact_path = COEFF_BUNDLE_CORE.shared_coefficient_map_candidate_report_path(
                tmp_dir,
                "componentwise_complex_scale_map",
            )
            written = COEFF_BUNDLE_CORE.write_shared_coefficient_map_candidate_npz(
                artifact_path,
                fitted_map,
                panel_case_names=["case_a", "case_b"],
            )
            self.assertEqual(
                written.name,
                "round6p1_shared_coefficient_map_candidate_componentwise_complex_scale_map.npz",
            )
            loaded = COEFF_BUNDLE_CORE.read_shared_coefficient_map_candidate_npz(written)
            self.assertEqual(
                loaded["validated"]["coefficient_map_model_id"],
                "componentwise_complex_scale_map",
            )
            self.assertEqual(loaded["validated"]["panel_case_count"], 2)
            np.testing.assert_allclose(
                loaded["validated"]["map_matrix"],
                fitted_map.map_matrix,
                rtol=1e-10,
                atol=1e-12,
            )
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_resolve_runtime_fitted_coefficient_map_requires_artifact_for_non_identity(self):
        with self.assertRaises(ValueError):
            COEFF_BUNDLE_CORE.resolve_runtime_fitted_coefficient_map(
                coefficient_map_model_id="shared_complex_scale_map",
            )

    def test_resolve_runtime_fitted_coefficient_map_reads_shared_candidate_artifact(self):
        tmp_dir = workspace_tempdir("runtime-map-artifact-")
        try:
            fitted_map = COEFF_BUNDLE_CORE.FittedCoefficientMap(
                coefficient_map_model_id="shared_complex_scale_map",
                map_matrix=np.eye(3, dtype=np.complex128) * (1.2 + 0.0j),
                coefficient_map_note="unit-test shared scale",
                coefficient_map_parameters={"unit_test": True},
            )
            artifact_path = COEFF_BUNDLE_CORE.write_shared_coefficient_map_candidate_npz(
                COEFF_BUNDLE_CORE.shared_coefficient_map_candidate_report_path(
                    tmp_dir,
                    "shared_complex_scale_map",
                ),
                fitted_map,
                panel_case_names=["case_a", "case_b", "case_c"],
            )
            resolved = COEFF_BUNDLE_CORE.resolve_runtime_fitted_coefficient_map(
                coefficient_map_model_id="shared_complex_scale_map",
                artifact_path=artifact_path,
            )
            self.assertEqual(resolved.coefficient_map_model_id, "shared_complex_scale_map")
            self.assertEqual(resolved.coefficient_map_parameters["runtime_source"], "shared_candidate_artifact")
            np.testing.assert_allclose(resolved.map_matrix, fitted_map.map_matrix, rtol=1e-10, atol=1e-12)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_runtime_low_na_asymptotic_promotes_artifact_backed_coefficient_map(self):
        tmp_dir = workspace_tempdir("runtime-map-promote-")
        try:
            fitted_map = COEFF_BUNDLE_CORE.FittedCoefficientMap(
                coefficient_map_model_id="shared_complex_scale_map",
                map_matrix=np.eye(3, dtype=np.complex128) * (1.15 + 0.0j),
                coefficient_map_note="unit-test runtime promoted map",
                coefficient_map_parameters={"unit_test": True},
            )
            artifact_path = COEFF_BUNDLE_CORE.write_shared_coefficient_map_candidate_npz(
                COEFF_BUNDLE_CORE.shared_coefficient_map_candidate_report_path(
                    tmp_dir,
                    "shared_complex_scale_map",
                ),
                fitted_map,
                panel_case_names=["case_a", "case_b", "case_c"],
            )
            result = SOLVER.solve_oct_particle_response(
                SOLVER.SourceConfig(lambda0_nm=855.0, fwhm_nm=56.0, n_lambda=21),
                SOLVER.GridConfig(
                    z_span_um=12.0,
                    n_z=201,
                    x_span_um=4.0,
                    n_x=21,
                    na=0.05,
                    n_bfp_dense=21,
                    n_bfp_sparse=7,
                ),
                SOLVER.SolverConfig(
                    mode=SOLVER.LOW_NA_ASYMPTOTIC_MODE,
                    ideal=True,
                    second_order_model="directional_field_expansion_first_order",
                    coefficient_map_model_id="shared_complex_scale_map",
                    coefficient_map_artifact_path=str(artifact_path),
                ),
            )
            self.assertEqual(result["coefficient_map_requested_model_id"], "shared_complex_scale_map")
            self.assertEqual(result["coefficient_map_model_id"], "shared_complex_scale_map")
            self.assertEqual(result["coefficient_map_runtime_status"], "artifact_promoted")
            self.assertEqual(result["coefficient_map_artifact_path"], str(artifact_path))
            self.assertIsNotNone(result["coefficient_map_matrix_condition_number"])
            self.assertEqual(np.asarray(result["projected_coefficients_raw"]).shape[1], 3)
            self.assertEqual(np.asarray(result["rendered_coefficients_raw"]).shape[1], 3)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_runtime_low_na_asymptotic_supports_rendered_basis_override_contract(self):
        tmp_dir = workspace_tempdir("runtime-map-override-")
        try:
            fitted_map = COEFF_BUNDLE_CORE.FittedCoefficientMap(
                coefficient_map_model_id="shared_complex_scale_map",
                map_matrix=np.eye(3, dtype=np.complex128) * (1.05 + 0.0j),
                coefficient_map_note="unit-test runtime override map",
                coefficient_map_parameters={"unit_test": True},
            )
            artifact_path = COEFF_BUNDLE_CORE.write_shared_coefficient_map_candidate_npz(
                COEFF_BUNDLE_CORE.shared_coefficient_map_candidate_report_path(
                    tmp_dir,
                    "shared_complex_scale_map",
                ),
                fitted_map,
                panel_case_names=["case_a", "case_b", "case_c"],
            )
            result = SOLVER.solve_oct_particle_response(
                SOLVER.SourceConfig(lambda0_nm=855.0, fwhm_nm=56.0, n_lambda=21),
                SOLVER.GridConfig(
                    z_span_um=12.0,
                    n_z=201,
                    x_span_um=4.0,
                    n_x=21,
                    na=0.05,
                    n_bfp_dense=21,
                    n_bfp_sparse=7,
                ),
                SOLVER.SolverConfig(
                    mode=SOLVER.LOW_NA_ASYMPTOTIC_MODE,
                    ideal=True,
                    second_order_model="tensor_closure",
                    coefficient_map_model_id="shared_complex_scale_map",
                    coefficient_map_runtime_mode="rendered_basis_override",
                    coefficient_map_artifact_path=str(artifact_path),
                ),
            )
            self.assertEqual(result["requested_second_order_model"], "tensor_closure")
            self.assertEqual(result["second_order_model"], "tensor_closure")
            self.assertEqual(result["runtime_field_assembly_contract"], "rendered_basis_override")
            self.assertEqual(result["coefficient_map_requested_model_id"], "shared_complex_scale_map")
            self.assertEqual(result["coefficient_map_runtime_mode"], "rendered_basis_override")
            self.assertEqual(result["coefficient_map_model_id"], "shared_complex_scale_map")
            self.assertEqual(result["coefficient_map_runtime_status"], "artifact_promoted_override")
            self.assertEqual(
                result["coefficient_map_runtime_contract_status"],
                "explicit_rendered_basis_override_contract",
            )
            self.assertEqual(
                result["runtime_field_assembly_supported_lateral_shift_models"],
                ["none", "first_order"],
            )
            self.assertEqual(
                result["runtime_field_assembly_lateral_shift_constraint"],
                "rendered_basis_override_supports_first_order_only_with_envelope_only_analytic_gaussian_or_rendered_interp",
            )
            self.assertEqual(result["coefficient_map_artifact_path"], str(artifact_path))
            self.assertEqual(np.asarray(result["projected_coefficients_raw"]).shape[1], 3)
            self.assertEqual(np.asarray(result["rendered_coefficients_raw"]).shape[1], 3)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_runtime_low_na_asymptotic_supports_rendered_basis_override_first_order_shift(self):
        tmp_dir = workspace_tempdir("runtime-map-override-shift-")
        try:
            fitted_map = COEFF_BUNDLE_CORE.FittedCoefficientMap(
                coefficient_map_model_id="shared_complex_scale_map",
                map_matrix=np.eye(3, dtype=np.complex128) * (1.02 + 0.0j),
                coefficient_map_note="unit-test runtime override shifted map",
                coefficient_map_parameters={"unit_test": True},
            )
            artifact_path = COEFF_BUNDLE_CORE.write_shared_coefficient_map_candidate_npz(
                COEFF_BUNDLE_CORE.shared_coefficient_map_candidate_report_path(
                    tmp_dir,
                    "shared_complex_scale_map",
                ),
                fitted_map,
                panel_case_names=["case_a", "case_b"],
            )
            result = SOLVER.solve_oct_particle_response(
                SOLVER.SourceConfig(lambda0_nm=855.0, fwhm_nm=56.0, n_lambda=21),
                SOLVER.GridConfig(
                    z_span_um=12.0,
                    n_z=201,
                    x_span_um=4.0,
                    n_x=21,
                    na=0.05,
                    n_bfp_dense=21,
                    n_bfp_sparse=7,
                ),
                SOLVER.SolverConfig(
                    mode=SOLVER.LOW_NA_ASYMPTOTIC_MODE,
                    ideal=True,
                    second_order_model="tensor_closure",
                    lateral_shift_model="first_order",
                    lateral_shift_coupling="envelope_only",
                    lateral_shift_impl="analytic_gaussian",
                    coefficient_map_model_id="shared_complex_scale_map",
                    coefficient_map_runtime_mode="rendered_basis_override",
                    coefficient_map_artifact_path=str(artifact_path),
                    rendered_basis_shift_target="baseline_envelope_ratio",
                ),
            )
            self.assertEqual(result["runtime_field_assembly_contract"], "rendered_basis_override")
            self.assertEqual(result["rendered_basis_shift_target"], "baseline_envelope_ratio")
            self.assertEqual(result["runtime_field_assembly_shift_target"], "baseline_envelope_ratio")
            self.assertEqual(
                result["runtime_field_assembly_lateral_shift_constraint"],
                "rendered_basis_override_supports_first_order_only_with_envelope_only_analytic_gaussian_or_rendered_interp",
            )
            self.assertEqual(result["lateral_shift_model"], "first_order")
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_vendored_backend_note_flags_incompatible_binary_inventory(self):
        old_roots = SOLVER.LOCAL_PYTMATRIX_SOURCE_ROOTS
        try:
            vendor_root = workspace_tempdir("vendor-note-")
            fortran_dir = vendor_root / "pytmatrix" / "fortran_tm"
            fortran_dir.mkdir(parents=True, exist_ok=True)
            (fortran_dir / "pytmatrix.cp999-win_amd64.pyd").write_text("", encoding="utf-8")
            SOLVER.LOCAL_PYTMATRIX_SOURCE_ROOTS = [vendor_root]
            note = SOLVER._vendored_python_backend_note()
            self.assertIsNotNone(note)
            self.assertIn("incompatible", note)
        finally:
            SOLVER.LOCAL_PYTMATRIX_SOURCE_ROOTS = old_roots
            if "vendor_root" in locals():
                shutil.rmtree(vendor_root, ignore_errors=True)

    def test_reset_tmatrix_backend_state_clears_cached_backend(self):
        class _DummyHandle:
            def __init__(self):
                self.closed = False

            def close(self):
                self.closed = True

        handle = _DummyHandle()
        SOLVER._TMATRIX_LIB = object()
        SOLVER._CALCTMAT = object()
        SOLVER._CALCAMPL = object()
        SOLVER._TMATRIX_LIB_PATH = "dummy"
        SOLVER._TMATRIX_BACKEND = "python"
        SOLVER._PYTMATRIX_MODULE = object()
        SOLVER._DLL_DIRECTORY_HANDLES.append(handle)
        try:
            SOLVER.reset_tmatrix_backend_state()
            self.assertIsNone(SOLVER._TMATRIX_LIB)
            self.assertIsNone(SOLVER._CALCTMAT)
            self.assertIsNone(SOLVER._CALCAMPL)
            self.assertIsNone(SOLVER._TMATRIX_LIB_PATH)
            self.assertIsNone(SOLVER._TMATRIX_BACKEND)
            self.assertIsNone(SOLVER._PYTMATRIX_MODULE)
            self.assertEqual(SOLVER._DLL_DIRECTORY_HANDLES, [])
            self.assertTrue(handle.closed)
        finally:
            SOLVER.reset_tmatrix_backend_state(drop_python_modules=True)

    def test_measurement_protocol_reports_peak_and_width_bias(self):
        x_um = np.array([-1.0, 0.0, 1.0], dtype=float)
        opd_um = np.array([-0.5, 0.0, 0.5], dtype=float)
        bridge = {
            "mode": "bridge",
            "lateral_slice_axis": "x",
            "x_um": x_um,
            "opd_um": opd_um,
            "raw_intensity_xz": np.array(
                [
                    [0.1, 0.2, 0.1],
                    [0.2, 1.0, 0.2],
                    [0.1, 0.4, 0.1],
                ],
                dtype=float,
            ),
            "global_peak_index": [1, 1],
            "peakline_x_um": 0.0,
            "raw_peak_intensity": 1.0,
            "axial_intensity_metrics": {
                "peak_opd_um": 0.0,
                "centroid_opd_um": 0.0,
                "fwhm_opd_um": 0.8,
                "psr_db": -20.0,
                "sidelobe_energy_fraction": 0.05,
            },
        }
        candidate = {
            **bridge,
            "mode": "candidate",
            "raw_intensity_xz": np.array(
                [
                    [0.1, 0.1, 0.1],
                    [0.2, 0.4, 0.2],
                    [0.1, 1.0, 0.1],
                ],
                dtype=float,
            ),
            "global_peak_index": [2, 1],
            "peakline_x_um": 1.0,
            "raw_peak_intensity": 1.0,
            "axial_intensity_metrics": {
                "peak_opd_um": 0.0,
                "centroid_opd_um": 0.1,
                "fwhm_opd_um": 1.0,
                "psr_db": -18.0,
                "sidelobe_energy_fraction": 0.08,
            },
        }
        bridge_snapshot = extract_measurement_snapshot(bridge)
        candidate_snapshot = extract_measurement_snapshot(candidate)
        comparison = compare_measurement_snapshots(candidate, bridge)
        self.assertEqual(bridge_snapshot["measured_lateral_peak_x_um"], 0.0)
        self.assertEqual(candidate_snapshot["measured_lateral_peak_x_um"], 1.0)
        self.assertEqual(comparison["measured_peak_shift_um"], 1.0)
        self.assertAlmostEqual(comparison["measured_axial_width_bias_um"], 0.2)
        self.assertGreater(comparison["measured_sidelobe_distortion"], 0.0)

    def test_solver_axial_psr_exports_explicit_sign_conventions(self):
        opd_um = np.arange(-5.0, 6.0, dtype=float)
        profile = np.array([0.0, 0.0, 0.12, 0.0, 0.5, 1.0, 0.5, 0.0, 0.12, 0.0, 0.0], dtype=float)
        metrics = SOLVER.axial_profile_metrics(opd_um, profile, quantity_kind="intensity")
        self.assertEqual(metrics["psr_definition"], "sidelobe_to_main_db")
        self.assertLess(metrics["sidelobe_to_main_db"], 0.0)
        self.assertAlmostEqual(metrics["main_to_sidelobe_rejection_db"], -metrics["sidelobe_to_main_db"])
        self.assertEqual(metrics["psr_db"], metrics["sidelobe_to_main_db"])

    def test_measurement_sideband_metrics_exports_both_psr_conventions(self):
        opd_um = np.arange(-5.0, 6.0, dtype=float)
        profile = np.array([0.0, 0.0, 0.1, 0.0, 0.5, 1.0, 0.5, 0.0, 0.1, 0.0, 0.0], dtype=float)
        metrics = PSF_PROTOCOL_CORE._profile_sideband_metrics(opd_um, profile)
        self.assertEqual(metrics["psr_definition"], "main_to_sidelobe_rejection_db")
        self.assertGreater(metrics["main_to_sidelobe_rejection_db"], 0.0)
        self.assertLess(metrics["sidelobe_to_main_db"], 0.0)
        self.assertAlmostEqual(metrics["main_to_sidelobe_rejection_db"], -metrics["sidelobe_to_main_db"])
        self.assertEqual(metrics["psr_db"], metrics["main_to_sidelobe_rejection_db"])

    def test_measurement_protocol_reference_peak_plane_reuses_reference_plane(self):
        x_um = np.array([-1.0, 0.0, 1.0], dtype=float)
        opd_um = np.array([-1.0, 0.0, 1.0], dtype=float)
        bridge = {
            "mode": "bridge",
            "lateral_slice_axis": "x",
            "x_um": x_um,
            "opd_um": opd_um,
            "raw_intensity_xz": np.array(
                [
                    [0.2, 0.1, 0.1],
                    [1.0, 0.2, 0.2],
                    [0.2, 0.1, 0.1],
                ],
                dtype=float,
            ),
            "global_peak_index": [1, 0],
            "peakline_x_um": 0.0,
            "raw_peak_intensity": 1.0,
            "axial_intensity_metrics": {
                "peak_opd_um": -1.0,
                "centroid_opd_um": -0.8,
                "fwhm_opd_um": 1.0,
                "psr_db": 6.0,
                "sidelobe_energy_fraction": 0.03,
            },
        }
        candidate = {
            **bridge,
            "mode": "candidate",
            "raw_intensity_xz": np.array(
                [
                    [0.1, 0.1, 0.1],
                    [0.2, 0.2, 0.3],
                    [0.9, 1.0, 0.4],
                ],
                dtype=float,
            ),
            "global_peak_index": [2, 1],
            "peakline_x_um": 1.0,
            "raw_peak_intensity": 1.0,
            "axial_intensity_metrics": {
                "peak_opd_um": 0.0,
                "centroid_opd_um": 0.1,
                "fwhm_opd_um": 1.2,
                "psr_db": 5.5,
                "sidelobe_energy_fraction": 0.05,
            },
        }
        self_peak = compare_measurement_snapshots(candidate, bridge, extraction_mode="self_peak")
        reference_peak = compare_measurement_snapshots(candidate, bridge, extraction_mode="reference_peak_plane")
        self.assertEqual(self_peak["measurement_extraction_mode"], "self_peak")
        self.assertEqual(reference_peak["measurement_extraction_mode"], "reference_peak_plane")
        self.assertEqual(reference_peak["reference_snapshot"]["extraction_plane_index"], 0)
        self.assertEqual(reference_peak["candidate_snapshot"]["extraction_plane_index"], 0)
        self.assertNotEqual(
            self_peak["candidate_snapshot"]["extraction_plane_index"],
            reference_peak["candidate_snapshot"]["extraction_plane_index"],
        )

    def test_measurement_protocol_package_uses_comparison_modes_schema(self):
        representative_cases = [{"name": "synthetic", "description": "demo"}]

        def _run_case(_case, *, mode):
            return {"mode": mode}

        def _compare(candidate, _bridge, *, extraction_mode="self_peak", pipeline_mode="solver_output_peak_slice_adapter"):
            return {
                "candidate_snapshot": {
                    "measured_lateral_peak_x_um": 0.0,
                    "measured_lateral_fwhm_um": 1.0,
                    "measured_axial_fwhm_opd_um": 2.0,
                    "measured_psr_db": 3.0,
                    "raw_peak_intensity": 4.0,
                    "extraction_plane_opd_um": 5.0 if extraction_mode == "self_peak" else 6.0,
                },
                "measured_peak_shift_um": 0.1,
                "measured_lateral_width_bias_um": 0.2,
                "measured_axial_width_bias_um": 0.3,
                "measured_sidelobe_distortion": 0.4,
            }

        package, _markdown = build_measurement_protocol_package(
            representative_cases=representative_cases,
            run_case=_run_case,
            compare_measurement_snapshots=_compare,
            full_na_mode="full_na",
            low_na_mode="low_na",
            asymptotic_mode="asymptotic",
            bridge_mode="bridge",
        )
        case = package["cases"][0]
        self.assertNotIn("rows", case)
        self.assertEqual(case["default_comparison_mode"], "self_peak")
        self.assertIn("reference_peak_plane", case["comparison_modes"])
        self.assertIn("pipeline_comparison_modes", case)
        self.assertEqual(case["default_measurement_pipeline_mode"], "fd_oct_reconstruction")
        self.assertIn("fd_oct_reconstruction", case["pipeline_comparison_modes"])
        self.assertIn("solver_output_peak_slice_adapter", case["pipeline_comparison_modes"])
        self.assertEqual(
            case["comparison_modes"],
            case["pipeline_comparison_modes"][case["default_measurement_pipeline_mode"]],
        )

    def test_validator_loads_measurement_protocol_summary(self):
        tempdir = workspace_tempdir("measurement-summary-")
        try:
            report_path = tempdir / "measurement.json"
            payload = {
                "measurement_pipeline_modes": [
                    "fd_oct_reconstruction",
                    "solver_output_peak_slice_adapter",
                ],
                "cases": [
                    {
                        "name": "case_a",
                        "measurement_pipeline_modes": [
                            "fd_oct_reconstruction",
                            "solver_output_peak_slice_adapter",
                        ],
                        "default_measurement_pipeline_mode": "fd_oct_reconstruction",
                        "measurement_report_schema_version": "pipeline_and_comparison_modes",
                        "pipeline_failures": {},
                    }
                ],
            }
            report_path.write_text(json.dumps(payload), encoding="utf-8")
            summary = VALIDATOR.load_measurement_protocol_summary(report_path)
            self.assertEqual(summary["measurement_pipeline_guidance_status"], "explicit_report_used")
            self.assertEqual(summary["measurement_pipeline_evidence_status"], "fd_oct_reconstruction_in_evidence_chain")
            self.assertEqual(summary["measurement_pipeline_default_mode"], "fd_oct_reconstruction")
            self.assertEqual(summary["fd_oct_measurement_wrapper_status"], "integrated_in_measurement_evidence_chain")
            self.assertEqual(summary["measurement_reference_arm_policy_status"], "scaffold_not_calibrated")
        finally:
            shutil.rmtree(tempdir, ignore_errors=True)

    def test_apply_measurement_protocol_summary_exposes_failure_summary_fields(self):
        report = VALIDATOR.apply_measurement_protocol_summary(
            {
                "checks": [],
                "recommended_next_action": "debug_coefficient_extraction_or_usage_mapping",
                "final_recommended_next_action_source": "coefficient_map_stability",
            },
            {
                "measurement_pipeline_guidance_status": "explicit_report_used",
                "measurement_pipeline_evidence_status": "fd_oct_reconstruction_in_evidence_chain",
                "measurement_pipeline_modes": [
                    "fd_oct_reconstruction",
                    "solver_output_peak_slice_adapter",
                ],
                "measurement_case_names": ["case_a"],
                "measurement_default_pipeline_modes": ["fd_oct_reconstruction"],
                "measurement_pipeline_default_mode": "fd_oct_reconstruction",
                "measurement_report_schema_versions": ["pipeline_and_comparison_modes"],
                "measurement_pipeline_failures": {},
                "fd_oct_measurement_wrapper_status": "integrated_in_measurement_evidence_chain",
                "measurement_reference_arm_policy": "flat_synthetic_reference_when_measurement_reference_arm_field_absent",
                "measurement_reference_arm_policy_status": "scaffold_not_calibrated",
                "measurement_reference_arm_policy_note": "synthetic note",
            },
        )
        self.assertEqual(report["measurement_pipeline_default_mode"], "fd_oct_reconstruction")
        self.assertEqual(report["fd_oct_measurement_wrapper_status"], "integrated_in_measurement_evidence_chain")
        summary = VALIDATOR.render_failure_summary(report)
        self.assertIn("Measurement pipeline evidence status: fd_oct_reconstruction_in_evidence_chain", summary)
        self.assertIn("Measurement pipeline default mode: fd_oct_reconstruction", summary)
        self.assertIn("FD-OCT measurement wrapper status: integrated_in_measurement_evidence_chain", summary)
        self.assertIn(
            "Measurement reference-arm policy: flat_synthetic_reference_when_measurement_reference_arm_field_absent",
            summary,
        )

    def test_measurement_contract_refresh_updates_legacy_fd_oct_depth_labels(self):
        payload = {
            "cases": [
                {
                    "name": "case_a",
                    "pipeline_comparison_modes": {
                        "fd_oct_reconstruction": {
                            "self_peak": [
                                {
                                    "fd_oct_depth_convention": "opd_conjugate_to_medium_effective_wavenumber",
                                    "extraction_plane_opd_um": 0.0,
                                }
                            ]
                        }
                    },
                }
            ]
        }
        refreshed, count = MEASUREMENT_CONTRACT_REFRESH.refresh_measurement_payload(payload)
        row = refreshed["cases"][0]["pipeline_comparison_modes"]["fd_oct_reconstruction"]["self_peak"][0]
        self.assertEqual(count, 1)
        self.assertEqual(
            row["fd_oct_depth_convention"],
            "geometric_roundtrip_conjugate_to_medium_effective_wavenumber",
        )
        self.assertEqual(row["extraction_plane_geometric_roundtrip_um"], 0.0)
        self.assertEqual(
            refreshed["measurement_contract_refresh_status"],
            "depth_contract_label_refreshed_from_existing_numerical_evidence",
        )

    def test_measurement_contract_refresh_updates_validation_summary_fields(self):
        tmp_dir = workspace_tempdir("measurement-refresh")
        try:
            measurement_payload = {
                "measurement_pipeline_modes": [
                    "fd_oct_reconstruction",
                    "solver_output_peak_slice_adapter",
                ],
                "cases": [
                    {
                        "name": "case_a",
                        "measurement_pipeline_modes": [
                            "fd_oct_reconstruction",
                            "solver_output_peak_slice_adapter",
                        ],
                        "default_measurement_pipeline_mode": "fd_oct_reconstruction",
                        "measurement_report_schema_version": "pipeline_and_comparison_modes",
                        "pipeline_failures": {},
                        "pipeline_comparison_modes": {
                            "fd_oct_reconstruction": {
                                "self_peak": [
                                    {
                                        "fd_oct_depth_convention": "opd_conjugate_to_medium_effective_wavenumber",
                                        "fd_oct_k_axis_kind": "constant_medium_effective_wavenumber_rad_per_um",
                                        "fd_oct_medium_index_policy": "derived_geometry_series_n_medium",
                                        "fd_oct_reference_arm_policy": "synthetic_flat_amplitude_reference_with_optional_delay",
                                        "extraction_plane_opd_um": 0.0,
                                    }
                                ]
                            }
                        },
                    }
                ],
            }
            (tmp_dir / "round6p1_measurement_protocol_bias.json").write_text(
                json.dumps(measurement_payload) + "\n",
                encoding="utf-8",
            )
            (tmp_dir / "round6p1_measurement_protocol_bias.md").write_text(
                "legacy opd_conjugate_to_medium_effective_wavenumber\n",
                encoding="utf-8",
            )
            (tmp_dir / "round6p1_validation_summary.json").write_text(
                json.dumps({"checks": [], "report_version_tag": "round6p1"}) + "\n",
                encoding="utf-8",
            )
            exit_code = MEASUREMENT_CONTRACT_REFRESH.main(["--reports-dir", str(tmp_dir)])
            self.assertEqual(exit_code, 0)
            measurement = json.loads((tmp_dir / "round6p1_measurement_protocol_bias.json").read_text(encoding="utf-8"))
            row = measurement["cases"][0]["pipeline_comparison_modes"]["fd_oct_reconstruction"]["self_peak"][0]
            self.assertEqual(
                row["fd_oct_depth_convention"],
                "geometric_roundtrip_conjugate_to_medium_effective_wavenumber",
            )
            summary = json.loads((tmp_dir / "round6p1_validation_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(
                summary["measurement_fd_oct_depth_policy_status"],
                "medium_effective_k_geometric_depth_axis_declared",
            )
            self.assertEqual(
                summary["measurement_artifact_freshness_status"],
                "source_contract_refreshed_existing_numerical_evidence",
            )
            failure_summary = (tmp_dir / "round6p1_validation_failure_summary.txt").read_text(encoding="utf-8")
            self.assertIn("Measurement FD-OCT depth policy status: medium_effective_k_geometric_depth_axis_declared", failure_summary)
            self.assertIn(
                "Measurement artifact freshness status: source_contract_refreshed_existing_numerical_evidence",
                failure_summary,
            )
            self.assertIn("Measurement contract refreshed row count: 1", failure_summary)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_cp310_rebuild_candidate_commands_prefer_explicit_then_env_then_launcher(self):
        commands = CP310_EVIDENCE_REBUILD.build_candidate_python_commands(
            explicit_python="C:/Python310/python.exe",
            env={"ROUND6P1_CP310_PYTHON": "py -3.10", "OCT_CP310_PYTHON": "py -3.10"},
        )
        self.assertEqual(commands[0], ["C:/Python310/python.exe"])
        self.assertIn(["py", "-3.10"], commands)
        self.assertEqual(commands.count(["py", "-3.10"]), 1)

    def test_cp310_rebuild_readiness_classifier_requires_cp310_and_backend(self):
        wrong_runtime = {
            "probe_status": "runtime_probe_ok",
            "python_version": "3.13.2",
            "is_cp310": False,
            "tmatrix_backend_status": {"available": True},
        }
        self.assertEqual(
            CP310_EVIDENCE_REBUILD.classify_probe_payload(wrong_runtime)["readiness_status"],
            "wrong_python_runtime",
        )
        missing_backend = {
            "probe_status": "runtime_probe_ok",
            "python_version": "3.10.11",
            "is_cp310": True,
            "tmatrix_backend_status": {"available": False, "reason": "synthetic missing backend"},
        }
        self.assertEqual(
            CP310_EVIDENCE_REBUILD.classify_probe_payload(missing_backend)["readiness_status"],
            "backend_unavailable_in_cp310_runtime",
        )
        ready = {
            "probe_status": "runtime_probe_ok",
            "python_version": "3.10.11",
            "is_cp310": True,
            "tmatrix_backend_status": {"available": True, "backend": "python"},
        }
        self.assertTrue(CP310_EVIDENCE_REBUILD.classify_probe_payload(ready)["ready_to_rebuild"])

    def test_cp310_rebuild_readiness_script_writes_structured_not_ready_report(self):
        tmp_dir = workspace_tempdir("cp310-readiness")
        old_candidates = CP310_EVIDENCE_REBUILD.build_candidate_python_commands
        try:
            CP310_EVIDENCE_REBUILD.build_candidate_python_commands = lambda **_kwargs: [
                ["__definitely_missing_round6p1_cp310_python__"]
            ]
            exit_code = CP310_EVIDENCE_REBUILD.main(["--reports-dir", str(tmp_dir)])
            self.assertEqual(exit_code, 0)
            report_path = tmp_dir / "round6p1_cp310_evidence_rebuild_readiness.json"
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(report["report_kind"], "round6p1_cp310_evidence_rebuild_readiness")
            self.assertEqual(report["readiness_status"], "cp310_runtime_unavailable")
            self.assertFalse(report["ready_to_rebuild"])
            self.assertEqual(report["rebuild_status"], "not_requested")
            self.assertTrue((tmp_dir / "round6p1_cp310_evidence_rebuild_readiness.md").exists())
        finally:
            CP310_EVIDENCE_REBUILD.build_candidate_python_commands = old_candidates
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_cp310_readiness_summary_marks_runtime_blocked_guidance(self):
        updated = VALIDATOR.apply_cp310_evidence_readiness_summary(
            {},
            {
                "cp310_evidence_rebuild_readiness_status": "cp310_runtime_unavailable",
                "cp310_evidence_rebuild_ready": False,
                "cp310_evidence_rebuild_status": "not_requested",
            },
        )
        self.assertEqual(
            updated["cp310_evidence_rebuild_guidance_status"],
            "fresh_evidence_rebuild_blocked_by_runtime",
        )
        self.assertEqual(
            updated["cp310_evidence_rebuild_recommended_next_action"],
            "install_or_select_cp310_runtime_or_portable_tmatrix_backend",
        )

    def test_runtime_build_backend_skipped_report_is_structured(self):
        payload = DIAGNOSTIC_RUNTIME_CORE.build_backend_skipped_report(
            title="Synthetic Diagnostic",
            backend_status={"available": False, "reason": "synthetic-unavailable"},
        )
        self.assertEqual(payload["status"], "skipped")
        self.assertEqual(payload["skip_reason"], "tmatrix_backend_unavailable")
        self.assertEqual(payload["tmatrix_backend_status"]["reason"], "synthetic-unavailable")

    def test_fit_sensitivity_report_returns_skipped_payload_without_traceback(self):
        old_probe = FIT_SENSITIVITY_CORE.probe_backend_or_write_skip
        FIT_SENSITIVITY_CORE.probe_backend_or_write_skip = lambda **kwargs: (
            {"available": False, "reason": "synthetic"},
            {"status": "skipped", "skip_reason": "tmatrix_backend_unavailable"},
        )
        try:
            report = FIT_SENSITIVITY_CORE.build_fit_sensitivity_report(write_reports=False)
        finally:
            FIT_SENSITIVITY_CORE.probe_backend_or_write_skip = old_probe
        self.assertEqual(report["status"], "skipped")
        self.assertEqual(report["skip_reason"], "tmatrix_backend_unavailable")

    def test_evidence_builder_argparse_help_has_no_report_side_effects(self):
        tmp_dir = workspace_tempdir("evidence-help")
        sentinel = tmp_dir / "round6p1_validation_summary.json"
        sentinel.write_text('{"sentinel": true}\n', encoding="utf-8")
        try:
            with self.assertRaises(SystemExit) as raised:
                EVIDENCE_BUILDER.build_arg_parser().parse_args(["--help"])
            self.assertEqual(raised.exception.code, 0)
            self.assertEqual(json.loads(sentinel.read_text(encoding="utf-8")), {"sentinel": True})
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_evidence_builder_backend_unavailable_does_not_overwrite_without_force(self):
        tmp_dir = workspace_tempdir("evidence-backend-skip")
        sentinel = tmp_dir / "round6p1_validation_summary.json"
        sentinel_payload = {"sentinel": True}
        sentinel.write_text(json.dumps(sentinel_payload) + "\n", encoding="utf-8")
        old_probe = EVIDENCE_BUILDER.probe_tmatrix_backend
        try:
            EVIDENCE_BUILDER.probe_tmatrix_backend = lambda library_path=None: {
                "available": False,
                "reason": "synthetic backend unavailable",
            }
            exit_code = EVIDENCE_BUILDER.main(["--reports-dir", str(tmp_dir)])
            self.assertEqual(exit_code, 0)
            self.assertEqual(json.loads(sentinel.read_text(encoding="utf-8")), sentinel_payload)
            self.assertFalse((tmp_dir / "round6p1_basis_projection_diagnostics.json").exists())
        finally:
            EVIDENCE_BUILDER.probe_tmatrix_backend = old_probe
            EVIDENCE_BUILDER.configure_report_paths(EVIDENCE_BUILDER.DEFAULT_REPORTS_DIR)
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_evidence_builder_dry_run_does_not_create_report_dir(self):
        tmp_dir = workspace_tempdir("evidence-dry-run-parent")
        dry_run_dir = tmp_dir / "would-be-reports"
        old_probe = EVIDENCE_BUILDER.probe_tmatrix_backend
        try:
            EVIDENCE_BUILDER.probe_tmatrix_backend = lambda library_path=None: {
                "available": True,
                "backend": "synthetic",
            }
            exit_code = EVIDENCE_BUILDER.main(["--reports-dir", str(dry_run_dir), "--dry-run"])
            self.assertEqual(exit_code, 0)
            self.assertFalse(dry_run_dir.exists())
        finally:
            EVIDENCE_BUILDER.probe_tmatrix_backend = old_probe
            EVIDENCE_BUILDER.configure_report_paths(EVIDENCE_BUILDER.DEFAULT_REPORTS_DIR)
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_particle_size_sweep_parses_comma_and_range_diameters(self):
        self.assertEqual(PARTICLE_SWEEP.parse_diameters("200,300;500"), [200.0, 300.0, 500.0])
        self.assertEqual(PARTICLE_SWEEP.parse_diameters("200:200:1000"), [200.0, 400.0, 600.0, 800.0, 1000.0])
        with self.assertRaises(ValueError):
            PARTICLE_SWEEP.parse_diameters("200:0:1000")

    def test_particle_size_sweep_resolves_repo_solver_path(self):
        solver_path = PARTICLE_SWEEP.resolve_solver_path(ROOT)
        self.assertIn(solver_path.name, {"oct_nonspherical_psf_solver.py", "01_oct_nonspherical_psf_solver.py"})
        self.assertTrue(solver_path.exists())

    def test_particle_size_sweep_default_project_root_supports_repo_and_flat_bundle(self):
        self.assertEqual(PARTICLE_SWEEP.default_project_root_for(ROOT / "scripts"), ROOT)
        self.assertEqual(PARTICLE_SWEEP.default_project_root_for(ROOT / "flat_bundle"), ROOT / "flat_bundle")

    def test_particle_size_sweep_package_summarizes_low_na_scope(self):
        args = PARTICLE_SWEEP.build_arg_parser().parse_args(
            [
                "--diameters",
                "200,300",
                "--mode",
                "low_na",
                "--na",
                "0.05",
                "--particle-material",
                "TiO2-anatase",
                "--medium-material",
                "PDMS",
            ]
        )
        rows = [
            {
                "diameter_nm": 200.0,
                "status": "ok",
                "fwhm_opd_um": 3.0,
                "peak_opd_um": 0.0,
                "centroid_opd_um": 0.1,
                "main_to_sidelobe_rejection_db": 5.0,
                "raw_peak_intensity": 1.0,
                "peakline_x_um": 0.0,
            },
            {
                "diameter_nm": 300.0,
                "status": "ok",
                "fwhm_opd_um": 3.5,
                "peak_opd_um": 0.0,
                "centroid_opd_um": 0.2,
                "main_to_sidelobe_rejection_db": 6.0,
                "raw_peak_intensity": 2.0,
                "peakline_x_um": 0.0,
            },
        ]
        package = PARTICLE_SWEEP.build_particle_size_sweep_package(args, rows)
        self.assertEqual(package["sweep_status"], "complete")
        self.assertEqual(package["diameter_range_nm"], [200.0, 300.0])
        self.assertEqual(package["recommended_next_action"], "use_sweep_as_axial_spectral_smoke_not_lateral_truth")
        self.assertIn("Gaussian system surrogate", package["particle_lateral_scattering_scope_note"])
        self.assertEqual(package["metric_ranges"]["fwhm_opd_um"], [3.0, 3.5])

    def test_particle_size_sweep_failed_cases_drive_cli_exit_code(self):
        package = {"failed_count": 1}
        self.assertEqual(PARTICLE_SWEEP.exit_code_for_sweep_package(package), 2)
        self.assertEqual(PARTICLE_SWEEP.exit_code_for_sweep_package(package, allow_failed_cases=True), 0)
        self.assertEqual(PARTICLE_SWEEP.exit_code_for_sweep_package({"failed_count": 0}), 0)

    def test_tmatrix_backend_registry_reports_portable_backend_as_unimplemented(self):
        provenance = TMATRIX_REGISTRY_CORE.build_backend_provenance("portable_isoc")
        self.assertFalse(provenance["backend_available"])
        self.assertEqual(provenance["requested_backend_id"], "portable_isoc")
        self.assertIn("not implemented", provenance["reason"])
        with self.assertRaises(RuntimeError):
            TMATRIX_REGISTRY_CORE.require_backend_available(provenance)

    def test_particle_size_sweep_require_backend_preflight_is_structured(self):
        tmp_dir = workspace_tempdir("particle-sweep-backend-preflight")
        try:
            args = PARTICLE_SWEEP.build_arg_parser().parse_args(
                [
                    "--diameters",
                    "200,300",
                    "--mode",
                    "vector_pupil_overlap_bridge",
                    "--tmatrix-backend",
                    "portable_isoc",
                    "--require-tmatrix-backend",
                    "--output-dir",
                    str(tmp_dir),
                    "--no-plots",
                ]
            )
            package, _markdown = PARTICLE_SWEEP.run_particle_size_sweep(
                args,
                solver=SOLVER,
                write_artifacts=True,
                make_plots=False,
            )
            self.assertEqual(package["sweep_status"], "all_failed")
            self.assertEqual(package["failed_count"], 2)
            self.assertEqual(package["tmatrix_backend_requested_id"], "portable_isoc")
            self.assertFalse(package["tmatrix_backend_available"])
            self.assertEqual(package["rows"][0]["failure_stage"], "tmatrix_backend_preflight")
            self.assertTrue((tmp_dir / "backend_provenance.json").exists())
            self.assertEqual(PARTICLE_SWEEP.exit_code_for_sweep_package(package), 2)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_validator_loads_particle_size_sweep_summary(self):
        tempdir = workspace_tempdir("particle-sweep-summary-")
        try:
            report_path = tempdir / "particle_sweep.json"
            report_path.write_text(
                json.dumps(
                    {
                        "sweep_schema_version": "particle_size_sweep_v1",
                        "sweep_status": "complete",
                        "recommended_next_action": "use_sweep_as_axial_spectral_smoke_not_lateral_truth",
                        "mode_requested": "low_na",
                        "diameter_range_nm": [200.0, 1000.0],
                        "sweep_case_count": 9,
                        "ok_count": 9,
                        "failed_count": 0,
                        "metric_ranges": {"fwhm_opd_um": [3.0, 4.0]},
                        "particle_lateral_scattering_scope_note": "low_na scope note",
                        "rows": [],
                    }
                ),
                encoding="utf-8",
            )
            summary = VALIDATOR.load_particle_size_sweep_summary(report_path)
            self.assertEqual(summary["particle_size_sweep_guidance_status"], "explicit_report_used")
            self.assertEqual(summary["particle_size_sweep_status"], "complete")
            self.assertEqual(summary["particle_size_sweep_diameter_range_nm"], [200.0, 1000.0])
            report = VALIDATOR.apply_particle_size_sweep_summary({"checks": []}, summary)
            self.assertEqual(report["particle_size_sweep_mode"], "low_na")
            self.assertEqual(report["particle_size_sweep_metric_ranges"]["fwhm_opd_um"], [3.0, 4.0])
        finally:
            shutil.rmtree(tempdir, ignore_errors=True)

    def test_estimate_effective_channel_recovers_tensor_fit(self):
        backscatter = np.array([0.0, 0.0, -1.0], dtype=float)
        tangent_u = np.array([1.0, 0.0, 0.0], dtype=float)
        tangent_v = np.array([0.0, 1.0, 0.0], dtype=float)
        fake_api = types.SimpleNamespace(
            _backscatter_basis=lambda: (backscatter.copy(), tangent_u.copy(), tangent_v.copy()),
            trapezoid_weights=lambda axis: np.ones_like(np.asarray(axis, dtype=float)),
        )
        B_true = np.array([1.0 + 0.2j, 0.7 - 0.1j], dtype=np.complex128)
        D1_x_true = np.array([0.08 - 0.01j, -0.03 + 0.02j], dtype=np.complex128)
        D1_y_true = np.array([-0.04 + 0.03j, 0.06 - 0.01j], dtype=np.complex128)
        C_xx_true = np.array([0.3 - 0.02j, -0.1 + 0.04j], dtype=np.complex128)
        C_xy_true = np.array([0.05 + 0.01j, 0.02 - 0.03j], dtype=np.complex128)
        C_yy_true = np.array([-0.2 + 0.07j, 0.4 + 0.02j], dtype=np.complex128)

        def sample_effective_channel(**kwargs):
            theta = np.deg2rad(np.asarray(kwargs["theta_deg"], dtype=float))
            phi = np.deg2rad(np.asarray(kwargs["phi_deg"], dtype=float))
            directions = np.stack(
                [
                    np.sin(theta) * np.cos(phi),
                    np.sin(theta) * np.sin(phi),
                    np.cos(theta),
                ],
                axis=-1,
            )
            cos_vartheta = np.clip(np.tensordot(directions, backscatter, axes=([-1], [0])), -1.0, 1.0)
            vartheta = np.arccos(cos_vartheta)
            sin_vartheta = np.sqrt(np.clip(1.0 - cos_vartheta**2, 0.0, None))
            alpha = np.zeros_like(vartheta)
            beta = np.zeros_like(vartheta)
            valid = sin_vartheta > 1e-12
            alpha[valid] = vartheta[valid] * (
                np.tensordot(directions[valid], tangent_u, axes=([-1], [0])) / sin_vartheta[valid]
            )
            beta[valid] = vartheta[valid] * (
                np.tensordot(directions[valid], tangent_v, axes=([-1], [0])) / sin_vartheta[valid]
            )
            amplitudes = np.zeros((len(kwargs["wavelengths_um"]),) + alpha.shape, dtype=np.complex128)
            for idx in range(len(kwargs["wavelengths_um"])):
                amplitudes[idx] = (
                    B_true[idx]
                    + D1_x_true[idx] * alpha
                    + D1_y_true[idx] * beta
                    + C_xx_true[idx] * alpha**2
                    + 2.0 * C_xy_true[idx] * alpha * beta
                    + C_yy_true[idx] * beta**2
                )
            return amplitudes

        fake_bridge = types.SimpleNamespace(sample_effective_channel=sample_effective_channel)
        old_solver_api = LOW_NA._solver_api
        old_load_bridge_module = LOW_NA._load_bridge_module
        old_coeff_core_solver_api = LOW_NA_COEFF_CORE._solver_api
        old_coeff_core_load_bridge_module = LOW_NA_COEFF_CORE._load_bridge_module
        LOW_NA._solver_api = lambda: fake_api
        LOW_NA._load_bridge_module = lambda: fake_bridge
        LOW_NA_COEFF_CORE._solver_api = lambda: fake_api
        LOW_NA_COEFF_CORE._load_bridge_module = lambda: fake_bridge
        try:
            estimate = LOW_NA.estimate_effective_channel_B_C2(
                np.array([0.84, 0.86], dtype=float),
                material_particle=2.48,
                material_medium=1.40,
                particle_geometry={"diameter_nm": 250.0},
                incident_mode="linear_x",
                detection_mode="co_pol",
                theta_fit_max_rad=0.08,
                n_theta_fit=7,
                n_azimuth_fit=8,
                fit_strategy="split_even_odd",
            )
            joint_estimate = LOW_NA.estimate_effective_channel_B_C2(
                np.array([0.84, 0.86], dtype=float),
                material_particle=2.48,
                material_medium=1.40,
                particle_geometry={"diameter_nm": 250.0},
                incident_mode="linear_x",
                detection_mode="co_pol",
                theta_fit_max_rad=0.08,
                n_theta_fit=7,
                n_azimuth_fit=8,
                fit_strategy="joint_low_order",
            )
        finally:
            LOW_NA._solver_api = old_solver_api
            LOW_NA._load_bridge_module = old_load_bridge_module
            LOW_NA_COEFF_CORE._solver_api = old_coeff_core_solver_api
            LOW_NA_COEFF_CORE._load_bridge_module = old_coeff_core_load_bridge_module

        diagnostics = estimate["fit_diagnostics"]
        joint_diagnostics = joint_estimate["fit_diagnostics"]
        recovered_tensor = np.asarray(diagnostics["C2_tensor_k"])
        joint_recovered_tensor = np.asarray(joint_diagnostics["C2_tensor_k"])
        np.testing.assert_allclose(estimate["B_k"], B_true, rtol=1e-8, atol=1e-10)
        np.testing.assert_allclose(joint_estimate["B_k"], B_true, rtol=1e-8, atol=1e-10)
        np.testing.assert_allclose(recovered_tensor[:, 0, 0], C_xx_true, rtol=1e-8, atol=1e-10)
        np.testing.assert_allclose(recovered_tensor[:, 0, 1], C_xy_true, rtol=1e-8, atol=1e-10)
        np.testing.assert_allclose(recovered_tensor[:, 1, 1], C_yy_true, rtol=1e-8, atol=1e-10)
        np.testing.assert_allclose(joint_recovered_tensor[:, 0, 0], C_xx_true, rtol=1e-8, atol=1e-10)
        np.testing.assert_allclose(joint_recovered_tensor[:, 0, 1], C_xy_true, rtol=1e-8, atol=1e-10)
        np.testing.assert_allclose(joint_recovered_tensor[:, 1, 1], C_yy_true, rtol=1e-8, atol=1e-10)
        np.testing.assert_allclose(diagnostics["D1_vector_k"][:, 0], D1_x_true, rtol=1e-8, atol=1e-10)
        np.testing.assert_allclose(diagnostics["D1_vector_k"][:, 1], D1_y_true, rtol=1e-8, atol=1e-10)
        np.testing.assert_allclose(joint_diagnostics["D1_vector_k"][:, 0], D1_x_true, rtol=1e-8, atol=1e-10)
        np.testing.assert_allclose(joint_diagnostics["D1_vector_k"][:, 1], D1_y_true, rtol=1e-8, atol=1e-10)
        self.assertEqual(diagnostics["fit_strategy"], "split_even_odd")
        self.assertEqual(joint_diagnostics["fit_strategy"], "joint_low_order")
        self.assertEqual(diagnostics["relative_fit_residual_model"], "even")
        self.assertEqual(joint_diagnostics["relative_fit_residual_model"], "low_order")
        self.assertGreater(float(np.max(np.asarray(diagnostics["relative_fit_residual_even"], dtype=float))), 1e-6)
        self.assertGreater(float(np.max(np.asarray(joint_diagnostics["relative_fit_residual_even"], dtype=float))), 1e-6)
        self.assertLess(float(np.max(np.asarray(diagnostics["relative_fit_residual_low_order"], dtype=float))), 1e-10)
        self.assertLess(float(np.max(np.asarray(joint_diagnostics["relative_fit_residual_low_order"], dtype=float))), 1e-10)
        self.assertGreater(float(np.max(np.asarray(diagnostics["relative_fit_residual"], dtype=float))), 1e-6)
        self.assertLess(float(np.max(np.asarray(joint_diagnostics["relative_fit_residual"], dtype=float))), 1e-10)
        self.assertGreater(
            float(np.max(np.asarray(diagnostics["per_azimuth_relative_fit_residual_even"], dtype=float))),
            1e-6,
        )
        self.assertLess(
            float(np.max(np.asarray(diagnostics["per_azimuth_relative_fit_residual_low_order"], dtype=float))),
            1e-10,
        )
        self.assertGreater(
            float(np.max(np.asarray(joint_diagnostics["per_azimuth_relative_fit_residual_even"], dtype=float))),
            1e-6,
        )
        self.assertLess(
            float(np.max(np.asarray(joint_diagnostics["per_azimuth_relative_fit_residual_low_order"], dtype=float))),
            1e-10,
        )
        azimuth = np.asarray(diagnostics["azimuth_samples_rad"], dtype=float)
        expected_per_azimuth = (
            C_xx_true[:, None] * np.cos(azimuth)[None, :] ** 2
            + 2.0 * C_xy_true[:, None] * np.cos(azimuth)[None, :] * np.sin(azimuth)[None, :]
            + C_yy_true[:, None] * np.sin(azimuth)[None, :] ** 2
        )
        np.testing.assert_allclose(
            diagnostics["per_azimuth_C2_k"],
            expected_per_azimuth,
            rtol=1e-8,
            atol=1e-10,
        )
        theta_weights = np.ones(7, dtype=float)
        local_alpha = np.asarray(diagnostics["local_alpha_samples_rad"], dtype=float)
        local_beta = np.asarray(diagnostics["local_beta_samples_rad"], dtype=float)
        amplitudes = np.zeros((2,) + local_alpha.shape, dtype=np.complex128)
        for idx in range(2):
            amplitudes[idx] = (
                B_true[idx]
                + D1_x_true[idx] * local_alpha
                + D1_y_true[idx] * local_beta
                + C_xx_true[idx] * local_alpha**2
                + 2.0 * C_xy_true[idx] * local_alpha * local_beta
                + C_yy_true[idx] * local_beta**2
            )
        expected_weights = np.sum(theta_weights[None, :, None] * np.abs(amplitudes) ** 2, axis=1)
        expected_weights /= np.sum(expected_weights, axis=1, keepdims=True)
        np.testing.assert_allclose(diagnostics["C2_azimuth_weights_k"], expected_weights, rtol=1e-8, atol=1e-10)
        np.testing.assert_allclose(
            estimate["C2_k"],
            np.sum(expected_weights * expected_per_azimuth, axis=1),
            rtol=1e-8,
            atol=1e-10,
        )
        np.testing.assert_allclose(
            diagnostics["C2_trace_summary_k"],
            0.5 * (C_xx_true + C_yy_true),
            rtol=1e-8,
            atol=1e-10,
        )
        np.testing.assert_allclose(
            LOW_NA._project_quadratic_tensor_to_direction(recovered_tensor, np.array([1.0, 0.0])),
            C_xx_true,
            rtol=1e-8,
            atol=1e-10,
        )
        mu2_tensor_profile = np.zeros((3, 2, 2), dtype=np.complex128)
        mu2_tensor_profile[:, 0, 0] = np.array([1.0, 2.0, 3.0], dtype=np.complex128)
        mu2_tensor_profile[:, 1, 1] = np.array([0.5, 0.25, 0.75], dtype=np.complex128)
        mu2_profile = mu2_tensor_profile[:, 0, 0] + mu2_tensor_profile[:, 1, 1]
        tensor_correction = LOW_NA.compute_second_order_correction(
            second_order_model="tensor_closure",
            C2_tensor_k=recovered_tensor[:1],
            mu2_tensor_profile=mu2_tensor_profile,
            C2_slice_k=np.array([C_xx_true[0]], dtype=np.complex128),
            mu2_profile=mu2_profile,
        )
        slice_correction = LOW_NA.compute_second_order_correction(
            second_order_model="slice_projected",
            C2_tensor_k=recovered_tensor[:1],
            mu2_tensor_profile=mu2_tensor_profile,
            C2_slice_k=np.array([C_xx_true[0]], dtype=np.complex128),
            mu2_profile=mu2_profile,
        )
        np.testing.assert_allclose(
            tensor_correction[0],
            recovered_tensor[0, 0, 0] * mu2_tensor_profile[:, 0, 0]
            + recovered_tensor[0, 0, 1] * mu2_tensor_profile[:, 0, 1]
            + recovered_tensor[0, 1, 0] * mu2_tensor_profile[:, 1, 0]
            + recovered_tensor[0, 1, 1] * mu2_tensor_profile[:, 1, 1],
            rtol=1e-8,
            atol=1e-10,
        )
        np.testing.assert_allclose(slice_correction[0], C_xx_true[0] * mu2_profile, rtol=1e-8, atol=1e-10)

    def test_mu2_tensor_profile_returns_trace_consistent_components(self):
        def build_unit_pupil_grid(n_bfp):
            axis = np.linspace(-1.0, 1.0, n_bfp)
            u, v = np.meshgrid(axis, axis)
            valid_mask = (u**2 + v**2) <= 1.0
            return {"pupil_axis": axis, "u_pupil": u, "v_pupil": v, "valid_mask": valid_mask}

        fake_api = types.SimpleNamespace(
            _build_unit_pupil_grid=build_unit_pupil_grid,
            trapezoid_weights=lambda axis: np.ones_like(np.asarray(axis, dtype=float)),
            resolve_material_model=lambda _material: (lambda _lam_um: 1.40),
            derive_na_geometry=lambda na, n_medium: {"sin_theta_max": float(na) / float(np.real(n_medium))},
        )
        old_solver_api = LOW_NA._solver_api
        LOW_NA._solver_api = lambda: fake_api
        try:
            diagnostics = LOW_NA.compute_mu2_profile_from_pupil_weight(
                np.array([-0.5, 0.0, 0.5], dtype=float),
                850.0,
                1.40,
                0.12,
                obliquity_kind="sqrt_cos",
                n_pupil=9,
            )
        finally:
            LOW_NA._solver_api = old_solver_api

        mu2_tensor_profile = np.asarray(diagnostics["mu2_tensor_profile"])
        mu2_reference_tensor = np.asarray(diagnostics["mu2_reference_tensor"])
        mu2_profile = np.asarray(diagnostics["mu2_profile"])
        self.assertEqual(mu2_tensor_profile.shape, (3, 2, 2))
        self.assertEqual(mu2_reference_tensor.shape, (2, 2))
        self.assertEqual(np.asarray(diagnostics["reference_pupil_field_profile"]).shape, (3,))
        self.assertEqual(np.asarray(diagnostics["reference_first_order_field_vector"]).shape, (3, 2))
        self.assertEqual(np.asarray(diagnostics["reference_second_order_field_tensor"]).shape, (3, 2, 2))
        np.testing.assert_allclose(
            mu2_profile,
            mu2_tensor_profile[:, 0, 0] + mu2_tensor_profile[:, 1, 1],
            rtol=1e-10,
            atol=1e-12,
        )
        np.testing.assert_allclose(
            diagnostics["mu2_reference_trace"],
            np.trace(mu2_reference_tensor),
            rtol=1e-10,
            atol=1e-12,
        )
        np.testing.assert_allclose(mu2_tensor_profile[:, 0, 1], 0.0, atol=1e-12)
        np.testing.assert_allclose(mu2_tensor_profile[:, 1, 0], 0.0, atol=1e-12)
        self.assertTrue(np.isfinite(diagnostics["mu2_profile_phase_span_rad"]))
        self.assertGreaterEqual(diagnostics["mu2_profile_phase_span_rad"], 0.0)
        self.assertTrue(np.isfinite(diagnostics["mu2_profile_real_imag_ratio"]))
        self.assertGreaterEqual(diagnostics["mu2_profile_valid_fraction"], 0.0)
        self.assertLessEqual(diagnostics["mu2_profile_valid_fraction"], 1.0)
        self.assertIn("note", diagnostics["mu2_profile_complexity_summary"])
        self.assertIn("phase_span_rad", diagnostics["mu2_profile_complexity_summary"])
        self.assertIn("real_imag_ratio", diagnostics["mu2_profile_complexity_summary"])
        freeze_summary = LOW_NA.summarize_mu2_wavelength_freeze_sensitivity(
            lambda0_nm=850.0,
            fwhm_nm=40.0,
            medium_material=1.40,
            na=0.12,
            obliquity_kind="sqrt_cos",
            n_pupil=9,
        )
        self.assertEqual(freeze_summary["wavelength_samples_nm"][1], 850.0)
        self.assertGreaterEqual(freeze_summary["max_relative_reference_tensor_delta"], 0.0)
        self.assertGreaterEqual(freeze_summary["max_relative_reference_trace_delta"], 0.0)
        self.assertIn("note", freeze_summary)
        frozen_payload, frozen_sensitivity = LOW_NA.build_mu2_profile_wavelength_model(
            np.array([-0.5, 0.0, 0.5], dtype=float),
            types.SimpleNamespace(lambda0_nm=850.0, fwhm_nm=40.0),
            1.40,
            0.12,
            mu2_wavelength_model="frozen_at_lambda0",
            obliquity_kind="sqrt_cos",
            n_pupil=9,
        )
        endpoint_payload, endpoint_sensitivity = LOW_NA.build_mu2_profile_wavelength_model(
            np.array([-0.5, 0.0, 0.5], dtype=float),
            types.SimpleNamespace(lambda0_nm=850.0, fwhm_nm=40.0),
            1.40,
            0.12,
            mu2_wavelength_model="endpoint_refit",
            obliquity_kind="sqrt_cos",
            n_pupil=9,
        )
        self.assertEqual(frozen_payload["mu2_wavelength_samples_nm"], [850.0])
        self.assertEqual(endpoint_payload["mu2_wavelength_samples_nm"], [830.0, 870.0])
        self.assertIn("lambda0", frozen_payload["mu2_wavelength_model_note"])
        self.assertIn("band-edge", endpoint_payload["mu2_wavelength_model_note"])
        self.assertEqual(frozen_sensitivity["wavelength_samples_nm"][1], 850.0)
        self.assertEqual(endpoint_sensitivity["wavelength_samples_nm"][1], 850.0)
        self.assertEqual(endpoint_payload["mu2_tensor_profile"].shape, (3, 2, 2))
        directional_profiles = LOW_NA.build_directional_field_expansion_profiles(diagnostics)
        self.assertEqual(directional_profiles["reference_field_profile"].shape, (3,))
        self.assertEqual(directional_profiles["second_order_field_tensor"].shape, (3, 2, 2))
        self.assertGreater(directional_profiles["normalization_scale"], 0.0)
        self.assertIn("basis functions", directional_profiles["note"])
        first_order_profiles = LOW_NA.build_first_order_field_profile(diagnostics, np.array([1.0, 0.0], dtype=float))
        self.assertEqual(first_order_profiles["first_order_field_profile"].shape, (3,))
        self.assertGreater(first_order_profiles["normalization_scale"], 0.0)
        self.assertIn("odd x-dependent basis", first_order_profiles["note"])
        self.assertAlmostEqual(float(np.abs(first_order_profiles["first_order_field_profile"][1])), 0.0, places=10)
        direction_y, axis_y = LOW_NA.resolve_lateral_slice_direction(types.SimpleNamespace(lateral_slice_axis="y"))
        np.testing.assert_allclose(direction_y, np.array([0.0, 1.0], dtype=float))
        self.assertEqual(axis_y, "y")
        fit_config = LOW_NA.resolve_effective_channel_fit_config(
            source=types.SimpleNamespace(lambda0_nm=850.0),
            grid=types.SimpleNamespace(na=0.12),
            solver=types.SimpleNamespace(
                medium_material=1.40,
                effective_channel_theta_fit_max_rad=None,
                effective_channel_theta_fit_fraction=0.25,
                effective_channel_theta_fit_cap_rad=0.05,
                effective_channel_n_theta_fit=11,
                effective_channel_n_azimuth_fit=6,
            ),
        )
        self.assertEqual(fit_config["fit_window_kind"], "heuristic_fraction_cap")
        self.assertEqual(fit_config["n_theta_fit"], 11)
        self.assertEqual(fit_config["n_azimuth_fit"], 6)

    def test_validator_exit_code_uses_status_not_boolean_only(self):
        report = {
            "checks": [
                {"name": "expected_limit", "status": "expected_fail", "status_category": "model_limit"},
                {"name": "diagnostic", "status": "informational", "status_category": "diagnostic"},
                {"name": "model_limit_fail", "status": "fail", "status_category": "model_limit"},
            ]
        }
        self.assertEqual(VALIDATOR.exit_code_from_report(report), 0)
        self.assertEqual(VALIDATOR.exit_code_from_report(report, strict_gates=True), 1)
        report["checks"].append({"name": "hard_fail", "status": "fail", "status_category": "hard_gate"})
        self.assertEqual(VALIDATOR.exit_code_from_report(report), 1)
        dominant = VALIDATOR.classify_dominant_error_bucket(
            {
                "peakline_x_delta_um": 2.0,
                "centroid_opd_delta_um": 0.1,
                "fwhm_delta_um": 0.05,
                "psr_delta_db": 0.2,
                "raw_peak_relative_delta": 158.62232515290077,
            }
        )
        self.assertEqual(dominant["dominant_error_bucket"], "lateral_shift")
        self.assertEqual(dominant["dominant_error_metric"], "peakline_x_delta_um")
        summary = VALIDATOR.render_failure_summary(
            {
                "checks": report["checks"],
                "diagnostics": {
                    "case": {
                        "label": "bridge_vs_asymptotic",
                        "image_relative_l2": 0.31,
                        "peakline_x_delta_um": 0.42,
                    }
                },
            }
        )
        self.assertIn("Hard gate failures: hard_fail", summary)
        self.assertIn("Model-limit failures: model_limit_fail", summary)
        self.assertIn("Expected-fail checks: expected_limit", summary)
        self.assertIn("Worst case: bridge_vs_asymptotic", summary)
        self.assertIn("Worst metric: image_relative_l2", summary)

    def test_recommendation_precedence_prefers_explicit_recovery_evidence(self):
        dominant = {
            "dominant_error_bucket": "lateral_shift",
            "dominant_error_metric": "peakline_x_delta_um",
            "dominant_error_value": 2.0,
            "dominant_error_severity": 1.0,
        }
        report = {
            "recommended_next_action": "promote_directional_model_freedom",
            "checks": [
                {
                    "name": "low_na_asymptotic_absolute_alignment_gate",
                    "status": "fail",
                    "status_category": "model_limit",
                    "dominant_error_summary": dominant,
                },
                {
                    "name": "low_na_asymptotic_first_order_not_prioritized",
                    "status": "informational",
                    "status_category": "model_direction",
                },
                {
                    "name": "low_na_asymptotic_slice_projected_fidelity_gate",
                    "passed": False,
                },
            ],
        }
        report = VALIDATOR.apply_basis_projection_summary(
            report,
            {
                "basis_projection_recommended_next_action": "debug_coefficient_extraction_or_promote_directional_basis",
                "basis_projection_case_names": ["case_a"],
            },
        )
        self.assertEqual(report["evidence_dependency_status"], "coefficient_missing")
        self.assertEqual(report["final_recommended_next_action"], "debug_coefficient_extraction_or_promote_directional_basis")
        self.assertEqual(report["final_recommended_next_action_source"], "basis_projection")
        report = VALIDATOR.apply_coefficient_recovery_summary(
            report,
            {
                "coefficient_recovery_recommended_next_action": "debug_coefficient_extraction_or_usage_mapping",
                "coefficient_recovery_case_names": ["case_a"],
                "basis_conditioning_status": "poor",
                "basis_conditioning_note": "synthetic poor conditioning",
                "coefficient_interpretability_status": "ill_conditioned",
                "coefficient_interpretability_note": "synthetic ill conditioning",
                "shared_scale_consistency_status": "d1_primary_with_bc2_caution",
                "shared_scale_consistency_note": "synthetic shared-scale caution",
            },
        )
        self.assertEqual(report["evidence_dependency_status"], "complete")
        self.assertEqual(report["recommended_next_action"], "debug_coefficient_extraction_or_usage_mapping")
        self.assertEqual(report["final_recommended_next_action"], "debug_coefficient_extraction_or_usage_mapping")
        self.assertEqual(report["final_recommended_next_action_source"], "coefficient_recovery")
        self.assertEqual(report["basis_conditioning_status"], "poor")
        self.assertEqual(report["coefficient_interpretability_status"], "ill_conditioned")
        self.assertEqual(report["shared_scale_consistency_status"], "d1_primary_with_bc2_caution")
        report = VALIDATOR.apply_fit_sensitivity_summary(
            report,
            {
                "fit_sensitivity_recommended_next_action": "fit_window_sensitivity_not_dominant",
                "fit_sensitivity_case_names": ["case_a"],
                "fit_window_sensitivity_status": "not_dominant",
            },
        )
        self.assertEqual(report["fit_sensitivity_recommended_next_action"], "fit_window_sensitivity_not_dominant")
        self.assertEqual(report["fit_window_sensitivity_status"], "not_dominant")
        report = VALIDATOR.apply_coefficient_injection_summary(
            report,
            {
                "coefficient_injection_recommended_next_action": "debug_coefficient_extraction_or_usage_mapping",
                "coefficient_injection_case_names": ["case_a"],
            },
        )
        self.assertEqual(report["guidance_confidence"], "partial_evidence")
        self.assertEqual(report["final_recommended_next_action_source"], "coefficient_injection")
        report = VALIDATOR.apply_coefficient_map_audit_summary(
            report,
            {
                "coefficient_map_audit_recommended_next_action": "audit_coefficient_map_stage_before_basis_expansion",
                "coefficient_map_audit_case_names": ["case_a"],
                "coefficient_map_models": [
                    "identity_slice_projected_rendered_basis",
                    "fitted_linear_map_3x3",
                ],
            },
        )
        self.assertEqual(report["final_recommended_next_action"], "audit_coefficient_map_stage_before_basis_expansion")
        self.assertEqual(report["final_recommended_next_action_source"], "coefficient_map_audit")
        self.assertIn("fitted_linear_map_3x3", report["coefficient_map_models"])
        report = VALIDATOR.apply_coefficient_map_stability_summary(
            report,
            {
                "coefficient_map_stability_recommended_next_action": "prototype_shared_coefficient_map_candidate_before_measurement_wrapper",
                "coefficient_map_stability_case_names": ["case_a"],
                "coefficient_map_models": [
                    "identity_slice_projected_rendered_basis",
                    "fitted_linear_map_3x3",
                ],
                "best_generalizing_model_id": "fitted_linear_map_3x3",
                "promoted_shared_map_model_id": "low_order_coupled_odd_even_map",
                "promoted_shared_map_runtime_scope": "general_asymptotic_rendered_basis_override",
                "promoted_shared_map_runtime_contract_status": "explicit_rendered_basis_override_contract",
                "promoted_shared_map_runtime_supported_lateral_shift_models": ["none", "first_order"],
                "promoted_shared_map_runtime_lateral_shift_constraint": "rendered_basis_override_supports_first_order_only_with_envelope_only_analytic_gaussian_or_rendered_interp",
                "promoted_shared_map_runtime_shift_target": "baseline_envelope_ratio",
            },
        )
        self.assertEqual(
            report["final_recommended_next_action"],
            "prototype_shared_coefficient_map_candidate_before_measurement_wrapper",
        )
        self.assertEqual(report["final_recommended_next_action_source"], "coefficient_map_stability")
        self.assertEqual(report["best_generalizing_coefficient_map_model_id"], "fitted_linear_map_3x3")
        self.assertEqual(report["promoted_shared_map_model_id"], "low_order_coupled_odd_even_map")
        self.assertEqual(report["promoted_shared_map_runtime_scope"], "general_asymptotic_rendered_basis_override")
        self.assertEqual(report["promoted_shared_map_runtime_contract_status"], "explicit_rendered_basis_override_contract")
        self.assertEqual(report["promoted_shared_map_runtime_supported_lateral_shift_models"], ["none", "first_order"])
        self.assertEqual(
            report["promoted_shared_map_runtime_lateral_shift_constraint"],
            "rendered_basis_override_supports_first_order_only_with_envelope_only_analytic_gaussian_or_rendered_interp",
        )
        self.assertEqual(report["promoted_shared_map_runtime_shift_target"], "baseline_envelope_ratio")
        report = VALIDATOR.apply_fit_strategy_ablation_summary(
            report,
            {
                "effective_channel_fit_strategy_recommended_next_action": "promote_joint_low_order_fit_strategy",
                "effective_channel_fit_strategy_case_names": ["case_a"],
                "effective_channel_fit_strategy_status": "joint_promising",
            },
        )
        self.assertEqual(report["effective_channel_fit_strategy_recommended_next_action"], "promote_joint_low_order_fit_strategy")
        self.assertEqual(report["effective_channel_fit_strategy_status"], "joint_promising")
        summary = VALIDATOR.render_failure_summary(report)
        self.assertIn("Dominant error bucket: lateral_shift", summary)
        self.assertIn("Promoted shared coefficient-map model: low_order_coupled_odd_even_map", summary)
        self.assertIn(
            "Promoted shared coefficient-map runtime scope: general_asymptotic_rendered_basis_override",
            summary,
        )
        self.assertIn(
            "Promoted shared coefficient-map contract status: explicit_rendered_basis_override_contract",
            summary,
        )
        self.assertIn(
            "Promoted shared coefficient-map supported lateral-shift models: none, first_order",
            summary,
        )
        self.assertIn(
            "Promoted shared coefficient-map lateral-shift constraint: rendered_basis_override_supports_first_order_only_with_envelope_only_analytic_gaussian_or_rendered_interp",
            summary,
        )
        self.assertIn(
            "Promoted shared coefficient-map shift target: baseline_envelope_ratio",
            summary,
        )
        guidance = VALIDATOR.summarize_open_model_limits(
            {
                "directional_first_order_is_promising": False,
                "checks": [
                    {
                        "name": "low_na_asymptotic_absolute_alignment_gate",
                        "status": "fail",
                        "status_category": "model_limit",
                        "dominant_error_summary": dominant,
                    },
                    {
                        "name": "low_na_asymptotic_first_order_not_prioritized",
                        "status": "informational",
                        "status_category": "model_direction",
                    },
                    {
                        "name": "low_na_asymptotic_slice_projected_fidelity_gate",
                        "passed": False,
                    },
                ]
            }
        )
        self.assertEqual(guidance["most_critical_open_model_limit"], "low_na_asymptotic_absolute_alignment_gate")
        self.assertEqual(guidance["recommended_next_action"], "promote_directional_model_freedom")
        guidance = VALIDATOR.summarize_open_model_limits(
            {
                "directional_first_order_is_promising": True,
                "checks": [
                    {
                        "name": "low_na_asymptotic_absolute_alignment_gate",
                        "status": "fail",
                        "status_category": "model_limit",
                        "dominant_error_summary": dominant,
                    }
                ],
            }
        )
        self.assertEqual(guidance["recommended_next_action"], "investigate_directional_first_order_field_basis")

    def test_slice_axis_crosscheck_ignores_axes_that_do_not_need_odd_basis(self):
        status, action = SLICE_AXIS_CROSSCHECK._recommend_next_action(
            [
                {
                    "axis": "x",
                    "axis_requires_odd_basis": True,
                    "odd_basis_resolves_axis": True,
                },
                {
                    "axis": "y",
                    "axis_requires_odd_basis": False,
                    "odd_basis_resolves_axis": False,
                },
            ]
        )
        self.assertEqual(status, "consistent")
        self.assertEqual(action, "coefficient_debug_generalizes_across_slice_axes")

    def test_summarize_worst_case_metrics_exposes_dominant_error_bucket(self):
        summary = VALIDATOR.summarize_worst_case_metrics(
            {
                "diagnostics": {
                    "case": {
                        "label": "synthetic_bridge_vs_asymptotic",
                        "image_relative_l2": 0.31,
                        "peakline_x_delta_um": 2.0,
                        "centroid_opd_delta_um": 0.1,
                        "fwhm_delta_um": 0.05,
                        "psr_delta_db": 0.2,
                        "raw_peak_relative_delta": 1.5,
                    }
                }
            }
        )
        self.assertEqual(summary["worst_case_name"], "synthetic_bridge_vs_asymptotic")
        self.assertEqual(summary["dominant_error_bucket"], "lateral_shift")
        self.assertEqual(summary["dominant_error_metric"], "peakline_x_delta_um")

    def test_apply_complex_field_match_scale_recovers_reference_amplitude(self):
        x_um = np.array([-0.5, 0.0, 0.5], dtype=float)
        opd_um = np.array([-1.0, 0.0], dtype=float)
        reference_field = np.array(
            [
                [1.0 + 0.5j, 0.2 - 0.1j],
                [0.3 + 0.0j, 0.8 - 0.4j],
                [0.1 - 0.2j, 0.4 + 0.6j],
            ],
            dtype=np.complex128,
        )
        scale = 3.0 * np.exp(1j * 0.4)
        candidate_result = {
            "field_xz": scale * reference_field,
            "x_um": x_um,
            "opd_um": opd_um,
            "normalization": {},
        }
        reference_result = {"field_xz": reference_field}
        scaled = VALIDATOR.apply_complex_field_match_scale(candidate_result, reference_result)
        np.testing.assert_allclose(scaled["field_xz"], reference_field, rtol=1e-10, atol=1e-12)
        self.assertAlmostEqual(scaled["experimental_post_scale_factor_abs"], 1.0 / 3.0, places=10)
        self.assertAlmostEqual(
            scaled["raw_peak_intensity"],
            float(np.max(np.abs(reference_field) ** 2)),
            places=10,
        )

    def test_mu2_dispersion_benchmark_cases_include_control_and_stress(self):
        cases = VALIDATOR.build_mu2_dispersion_benchmark_cases()
        control = cases["constant_material_control_case"]
        stress = cases["dispersive_material_stress_case"]
        self.assertLess(control["max_relative_reference_tensor_delta"], 1e-12)
        self.assertLess(control["max_relative_reference_trace_delta"], 1e-12)
        self.assertGreater(stress["max_relative_reference_tensor_delta"], 0.05)
        self.assertGreater(stress["max_relative_reference_trace_delta"], 0.01)

    def test_first_order_lateral_shift_helpers_move_envelope(self):
        shift = LOW_NA.estimate_first_order_lateral_shift_um(
            D1_slice_k=np.array([1j, -2j], dtype=np.complex128),
            B_k=np.array([1.0 + 0.0j, 2.0 + 0.0j], dtype=np.complex128),
            k_medium_rad_per_um=np.array([10.0, 10.0], dtype=float),
        )
        np.testing.assert_allclose(shift, np.array([-0.1, 0.1], dtype=float), rtol=1e-10, atol=1e-12)

        x_um = np.linspace(-1.0, 1.0, 5)
        lateral_envelope = np.exp(-(x_um**2))
        shifted = LOW_NA.build_shifted_lateral_envelope(
            x_um,
            lateral_envelope,
            np.array([0.0, 0.5], dtype=float),
            shift_impl="interp",
        )
        self.assertEqual(int(np.argmax(np.abs(shifted[0]))), 2)
        self.assertGreater(float(x_um[int(np.argmax(np.abs(shifted[1])))]), 0.0)
        shifted_analytic = LOW_NA.build_shifted_lateral_envelope(
            x_um,
            lateral_envelope,
            np.array([0.0, 0.5], dtype=float),
            shift_impl="analytic_gaussian",
            lambda0_nm=850.0,
            na=0.2,
        )
        self.assertEqual(shifted_analytic.shape, (2, 5))
        self.assertAlmostEqual(float(np.max(np.abs(shifted_analytic[0]))), 1.0, places=10)
        coupled = LOW_NA.shift_second_order_correction(
            x_um,
            np.array([lateral_envelope, lateral_envelope], dtype=np.complex128),
            np.array([0.0, 0.5], dtype=float),
            lateral_shift_coupling="shift_envelope_and_mu2",
        )
        self.assertEqual(coupled.shape, (2, 5))
        self.assertGreater(float(x_um[int(np.argmax(np.abs(coupled[1])))]), 0.0)
        uncoupled = LOW_NA.shift_second_order_correction(
            x_um,
            np.array([lateral_envelope, lateral_envelope], dtype=np.complex128),
            np.array([0.0, 0.5], dtype=float),
            lateral_shift_coupling="envelope_only",
        )
        np.testing.assert_allclose(uncoupled[1], lateral_envelope, rtol=1e-10, atol=1e-12)
        shifted_edge_hold = LOW_NA.build_shifted_lateral_envelope(
            x_um,
            lateral_envelope,
            np.array([0.5], dtype=float),
            shift_impl="interp_edge_hold",
        )
        self.assertEqual(shifted_edge_hold.shape, (1, 5))
        self.assertGreaterEqual(float(np.real(shifted_edge_hold[0, 0])), float(np.real(shifted[1, 0])))

    def test_first_order_validity_summary_exposes_small_Bk_and_nonfinite_cases(self):
        summary = LOW_NA.summarize_first_order_shift_validity(
            D1_slice_k=np.array([1j, 1j, 1j], dtype=np.complex128),
            B_k=np.array([1.0 + 0.0j, 1e-18 + 0.0j, 0.0 + 0.0j], dtype=np.complex128),
            k_medium_rad_per_um=np.array([10.0, 10.0, 10.0], dtype=float),
            relative_b_floor=1e-6,
        )
        self.assertEqual(summary["first_order_validity_mask"].shape, (3,))
        self.assertGreater(summary["first_order_invalid_fraction"], 0.0)
        self.assertGreater(summary["first_order_B_k_small_fraction"], 0.0)
        self.assertLess(summary["first_order_finite_fraction"], 1.0)
        self.assertIn("ill-conditioned", summary["first_order_validity_note"])

    def test_validate_requires_explicit_basis_projection_summary(self):
        report_without_basis = VALIDATOR.apply_basis_projection_summary(
            {"recommended_next_action": "promote_directional_model_freedom"},
            basis_projection_summary=None,
        )
        self.assertEqual(report_without_basis["evidence_dependency_status"], "both_missing")
        self.assertEqual(
            report_without_basis["final_recommended_next_action"],
            "promote_directional_model_freedom",
        )
        self.assertEqual(report_without_basis["final_recommended_next_action_source"], "open_model_limit")
        self.assertEqual(report_without_basis["basis_projection_guidance_status"], "not_supplied")
        report_with_basis = VALIDATOR.apply_basis_projection_summary(
            {"recommended_next_action": "promote_directional_model_freedom"},
            basis_projection_summary={
                "basis_projection_recommended_next_action": "debug_coefficient_extraction_or_promote_directional_basis",
                "basis_projection_case_names": ["synthetic_case"],
            },
        )
        self.assertEqual(
            report_with_basis["recommended_next_action"],
            "debug_coefficient_extraction_or_promote_directional_basis",
        )
        self.assertEqual(
            report_with_basis["final_recommended_next_action"],
            "debug_coefficient_extraction_or_promote_directional_basis",
        )
        self.assertEqual(report_with_basis["final_recommended_next_action_source"], "basis_projection")
        self.assertEqual(report_with_basis["basis_projection_case_names"], ["synthetic_case"])
        self.assertEqual(report_with_basis["evidence_dependency_status"], "coefficient_missing")

    def test_coefficient_recovery_joint_scale_diagnostics_highlight_component_mismatch(self):
        asym = np.array(
            [
                [1.0 + 0.0j, 0.2 + 0.0j, 3.0 + 0.0j],
                [0.5 + 0.0j, 0.1 + 0.0j, 1.5 + 0.0j],
            ],
            dtype=np.complex128,
        )
        recovered = 2.0 * asym
        recovered[:, 1] *= 100.0
        summary = COEFF_RECOVERY._shared_scale_component_diagnostics(
            asym,
            recovered,
            ("a0_vs_B_k", "a1_vs_D1_slice_k", "a2_vs_C2_slice_k"),
        )
        self.assertGreater(
            summary["component_relative_residuals"]["a1_vs_D1_slice_k"],
            summary["component_relative_residuals"]["a0_vs_B_k"],
        )
        self.assertGreater(
            summary["component_relative_residuals"]["a1_vs_D1_slice_k"],
            summary["component_relative_residuals"]["a2_vs_C2_slice_k"],
        )

    def test_coefficient_recovery_basis_normalization_diagnostics_expose_conditioning(self):
        basis_matrix = np.array(
            [
                [1.0 + 0.0j, 1.0e3 + 0.0j, 0.0 + 0.0j],
                [0.0 + 0.0j, 1.0e3 + 0.0j, 1.0 + 0.0j],
                [1.0 + 0.0j, 0.0 + 0.0j, 1.0 + 0.0j],
            ],
            dtype=np.complex128,
        )
        diagnostics = COEFF_RECOVERY._basis_gram_diagnostics(basis_matrix)
        self.assertGreater(diagnostics["gram_condition_number"], 1.0)
        target = np.array([[1.0 + 0.0j, 2.0 + 0.0j, 3.0 + 0.0j]], dtype=np.complex128)
        orth = COEFF_RECOVERY._orthonormalized_coefficients(target, basis_matrix)
        self.assertIn("abs_q1_over_abs_q0", orth["coefficient_energy_ratio"])
        self.assertGreater(orth["r_condition_number"], 1.0)

    def test_coefficient_recovery_shared_scale_status_is_more_cautious_than_d1_only(self):
        case_reports = [
            {
                "shared_scale_consistency": {
                    "component_relative_residuals": {
                        "a0_vs_B_k": 0.82,
                        "a1_vs_D1_slice_k": 1.0,
                        "a2_vs_C2_slice_k": 0.14,
                    }
                }
            }
        ]
        status, note = COEFF_RECOVERY._shared_scale_consistency_status(case_reports)
        self.assertEqual(status, "mixed_bc2_caution")
        self.assertIn("B/C2", note)
        core_status, core_note = COEFF_CORE.shared_scale_consistency_status(case_reports)
        self.assertEqual(core_status, status)
        self.assertEqual(core_note, note)

    def test_coefficient_core_joint_diagnostics_capture_component_mismatch(self):
        asym = np.array(
            [
                [1.0 + 0.0j, 0.2 + 0.0j, 3.0 + 0.0j],
                [0.5 + 0.0j, 0.1 + 0.0j, 1.5 + 0.0j],
            ],
            dtype=np.complex128,
        )
        recovered = 2.0 * asym
        recovered[:, 1] *= 100.0
        shared = COEFF_CORE.shared_scale_component_diagnostics(
            asym,
            recovered,
            ("a0_vs_B_k", "a1_vs_D1_slice_k", "a2_vs_C2_slice_k"),
        )
        self.assertGreater(shared["component_relative_residuals"]["a1_vs_D1_slice_k"], 0.5)
        self.assertLess(shared["component_relative_residuals"]["a2_vs_C2_slice_k"], 0.5)

    def test_effective_coefficient_contract_accepts_valid_result(self):
        result = {
            "lambda_nm": np.array([840.0, 860.0], dtype=float),
            "B_k": np.array([1.0 + 0.0j, 0.8 + 0.1j], dtype=np.complex128),
            "D1_vector_k": np.array([[0.1 + 0.0j, 0.01 + 0.0j], [0.05 + 0.02j, 0.02 + 0.01j]], dtype=np.complex128),
            "D1_slice_k": np.array([0.1 + 0.0j, 0.05 + 0.02j], dtype=np.complex128),
            "C2_tensor_k": np.array(
                [
                    [[0.2 - 0.01j, 0.01 + 0.0j], [0.01 + 0.0j, 0.15 + 0.01j]],
                    [[0.1 + 0.03j, 0.02 + 0.0j], [0.02 + 0.0j, 0.08 + 0.02j]],
                ],
                dtype=np.complex128,
            ),
            "C2_slice_k": np.array([0.2 - 0.01j, 0.1 + 0.03j], dtype=np.complex128),
            "lateral_slice_axis": "x",
            "fit_diagnostics": {
                "fit_strategy": "joint_low_order",
                "relative_fit_residual_model": "low_order",
                "C2_tensor_basis": "local_backscatter_angle_components_alpha_beta",
                "D1_tensor_basis": "local_backscatter_angle_components_alpha_beta",
                "theta_samples_rad": np.array([0.0, 0.05, 0.1], dtype=float),
                "theta_quadrature_weights": np.array([0.5, 1.0, 0.5], dtype=float),
                "azimuth_samples_rad": np.array([0.0, np.pi], dtype=float),
                "relative_fit_residual": np.array([0.1, 0.2], dtype=float),
            },
        }
        contract = COEFF_CORE.extract_effective_coefficient_contract(result)
        self.assertEqual(contract["slice_direction_label"], "x")
        self.assertEqual(contract["fit_strategy"], "joint_low_order")
        self.assertEqual(contract["lambda_nm"].shape, (2,))

    def test_effective_coefficient_contract_rejects_shape_mismatch(self):
        result = {
            "lambda_nm": np.array([840.0, 860.0], dtype=float),
            "B_k": np.array([1.0 + 0.0j], dtype=np.complex128),
            "D1_vector_k": np.array([[0.1 + 0.0j, 0.01 + 0.0j], [0.05 + 0.02j, 0.02 + 0.01j]], dtype=np.complex128),
            "D1_slice_k": np.array([0.1 + 0.0j, 0.05 + 0.02j], dtype=np.complex128),
            "C2_tensor_k": np.array(
                [
                    [[0.2 - 0.01j, 0.01 + 0.0j], [0.01 + 0.0j, 0.15 + 0.01j]],
                    [[0.1 + 0.03j, 0.02 + 0.0j], [0.02 + 0.0j, 0.08 + 0.02j]],
                ],
                dtype=np.complex128,
            ),
            "C2_slice_k": np.array([0.2 - 0.01j, 0.1 + 0.03j], dtype=np.complex128),
            "lateral_slice_axis": "x",
            "fit_diagnostics": {
                "fit_strategy": "joint_low_order",
                "relative_fit_residual_model": "low_order",
                "C2_tensor_basis": "local_alpha_beta",
                "D1_tensor_basis": "local_alpha_beta",
            },
        }
        with self.assertRaises(ValueError):
            COEFF_CORE.extract_effective_coefficient_contract(result)

    def test_effective_coefficient_contract_requires_monotonic_lambda_and_supported_enums(self):
        result = {
            "lambda_nm": np.array([860.0, 840.0], dtype=float),
            "B_k": np.array([1.0 + 0.0j, 0.8 + 0.1j], dtype=np.complex128),
            "D1_vector_k": np.array([[0.1 + 0.0j, 0.01 + 0.0j], [0.05 + 0.02j, 0.02 + 0.01j]], dtype=np.complex128),
            "D1_slice_k": np.array([0.1 + 0.0j, 0.05 + 0.02j], dtype=np.complex128),
            "C2_tensor_k": np.array(
                [
                    [[0.2 - 0.01j, 0.01 + 0.0j], [0.01 + 0.0j, 0.15 + 0.01j]],
                    [[0.1 + 0.03j, 0.02 + 0.0j], [0.02 + 0.0j, 0.08 + 0.02j]],
                ],
                dtype=np.complex128,
            ),
            "C2_slice_k": np.array([0.2 - 0.01j, 0.1 + 0.03j], dtype=np.complex128),
            "lateral_slice_axis": "x",
            "fit_diagnostics": {
                "fit_strategy": "unsupported_fit",
                "relative_fit_residual_model": "low_order",
                "C2_tensor_basis": "local_backscatter_angle_components_alpha_beta",
                "D1_tensor_basis": "local_backscatter_angle_components_alpha_beta",
            },
        }
        with self.assertRaises(ValueError):
            COEFF_CORE.extract_effective_coefficient_contract(result)

    def test_coefficient_path_bundle_builds_canonical_rendered_space(self):
        result = {
            "lambda_nm": np.array([840.0, 860.0], dtype=float),
            "x_um": np.array([-1.0, 0.0, 1.0], dtype=float),
            "B_k": np.array([1.0 + 0.0j, 0.8 + 0.1j], dtype=np.complex128),
            "D1_vector_k": np.array([[0.1 + 0.0j, 0.01 + 0.0j], [0.05 + 0.02j, 0.02 + 0.01j]], dtype=np.complex128),
            "D1_slice_k": np.array([0.1 + 0.0j, 0.05 + 0.02j], dtype=np.complex128),
            "C2_tensor_k": np.array(
                [
                    [[0.2 - 0.01j, 0.01 + 0.0j], [0.01 + 0.0j, 0.15 + 0.01j]],
                    [[0.1 + 0.03j, 0.02 + 0.0j], [0.02 + 0.0j, 0.08 + 0.02j]],
                ],
                dtype=np.complex128,
            ),
            "C2_slice_k": np.array([0.2 - 0.01j, 0.1 + 0.03j], dtype=np.complex128),
            "lateral_slice_axis": "x",
            "C2_slice_local_direction": np.array([1.0, 0.0], dtype=float),
            "reference_pupil_field_profile": np.array([1.0 + 0.0j, 0.5 + 0.1j, 0.2 + 0.0j], dtype=np.complex128),
            "directional_first_order_field_profile": np.array([0.0 + 0.1j, 0.2 + 0.0j, 0.0 - 0.1j], dtype=np.complex128),
            "directional_second_order_slice_field_profile": np.array([0.1 + 0.0j, -0.1 + 0.02j, 0.1 + 0.0j], dtype=np.complex128),
            "directional_field_expansion_scale": 2.5,
            "second_order_model": "directional_field_expansion_first_order",
            "fit_diagnostics": {
                "fit_strategy": "joint_low_order",
                "relative_fit_residual_model": "low_order",
                "C2_tensor_basis": "local_backscatter_angle_components_alpha_beta",
                "D1_tensor_basis": "local_backscatter_angle_components_alpha_beta",
                "theta_samples_rad": np.array([0.0, 0.05, 0.1], dtype=float),
                "theta_quadrature_weights": np.array([0.5, 1.0, 0.5], dtype=float),
                "azimuth_samples_rad": np.array([0.0, np.pi], dtype=float),
                "relative_fit_residual": np.array([0.1, 0.2], dtype=float),
            },
        }
        bundle = COEFF_BUNDLE_CORE.build_coefficient_path_bundle(result)
        self.assertEqual(bundle.slice_projected_state.slice_direction_label, "x")
        self.assertEqual(bundle.field_basis_state.field_assembly_model_id, "directional_field_expansion_first_order")
        self.assertEqual(bundle.field_basis_state.basis_matrix.shape, (3, 3))
        self.assertEqual(bundle.rendered_coefficient_state.coefficient_map_model_id, "identity_slice_projected_rendered_basis")
        np.testing.assert_allclose(
            bundle.rendered_coefficient_state.projected_coefficients_raw[:, 1],
            result["D1_slice_k"],
            rtol=1e-10,
            atol=1e-12,
        )
        np.testing.assert_allclose(
            bundle.comparison_state.rendered_coefficients_raw[:, 1],
            result["D1_slice_k"],
            rtol=1e-10,
            atol=1e-12,
        )
        self.assertEqual(bundle.comparison_state.rendered_coefficients_orthonormalized.shape, (2, 3))

    def test_coefficient_path_map_models_are_executable_and_swappable(self):
        projected = np.array(
            [
                [1.0 + 0.0j, 0.2 + 0.1j, 0.5 - 0.1j],
                [0.8 + 0.1j, 0.1 + 0.05j, 0.3 + 0.0j],
            ],
            dtype=np.complex128,
        )
        shared_scale = 2.0 * np.exp(1j * 0.3)
        shared = COEFF_BUNDLE_CORE.map_projected_to_rendered_coefficients(
            projected,
            model_id="shared_complex_scale_map",
            reference_rendered_coefficients_raw=shared_scale * projected,
        )
        np.testing.assert_allclose(shared.rendered_coefficients_raw, shared_scale * projected, rtol=1e-10, atol=1e-12)
        component_scales = np.array([2.0 + 0.0j, 3.0j, 0.5 - 0.2j], dtype=np.complex128)
        component_reference = projected * component_scales[None, :]
        componentwise = COEFF_BUNDLE_CORE.map_projected_to_rendered_coefficients(
            projected,
            model_id="componentwise_complex_scale_map",
            reference_rendered_coefficients_raw=component_reference,
        )
        np.testing.assert_allclose(componentwise.rendered_coefficients_raw, component_reference, rtol=1e-10, atol=1e-12)
        coupled_map = np.array(
            [
                [1.2 + 0.0j, 0.0 + 0.0j, 0.1 + 0.0j],
                [0.0 + 0.0j, 0.5 + 0.2j, 0.0 + 0.0j],
                [0.2 - 0.1j, 0.0 + 0.0j, 0.8 + 0.0j],
            ],
            dtype=np.complex128,
        )
        coupled_reference = projected @ coupled_map
        coupled = COEFF_BUNDLE_CORE.map_projected_to_rendered_coefficients(
            projected,
            model_id="low_order_coupled_odd_even_map",
            reference_rendered_coefficients_raw=coupled_reference,
        )
        np.testing.assert_allclose(coupled.rendered_coefficients_raw, coupled_reference, rtol=1e-10, atol=1e-12)
        linear_map = np.array(
            [
                [1.0 + 0.0j, 0.2 + 0.1j, 0.0 + 0.0j],
                [0.1 + 0.0j, 0.8 + 0.0j, 0.05 + 0.0j],
                [0.0 + 0.0j, -0.1j, 1.1 + 0.0j],
            ],
            dtype=np.complex128,
        )
        linear_reference = projected @ linear_map
        linear = COEFF_BUNDLE_CORE.map_projected_to_rendered_coefficients(
            projected,
            model_id="fitted_linear_map_3x3",
            reference_rendered_coefficients_raw=linear_reference,
        )
        np.testing.assert_allclose(linear.rendered_coefficients_raw, linear_reference, rtol=1e-10, atol=1e-12)

    def test_runtime_field_assembly_plan_supports_rendered_override_first_order_contract(self):
        plan = COEFF_BUNDLE_CORE.plan_runtime_field_assembly_contract(
            requested_second_order_model="tensor_closure",
            coefficient_map_runtime_mode="rendered_basis_override",
            coefficient_map_model_id="low_order_coupled_odd_even_map",
            coefficient_map_artifact_path="shared_map_candidate.npz",
            lateral_shift_model="first_order",
            lateral_shift_coupling="envelope_only",
            lateral_shift_impl="analytic_gaussian",
            rendered_basis_shift_target="baseline_envelope_ratio",
        )
        self.assertEqual(plan.runtime_field_assembly_contract, "rendered_basis_override")
        self.assertEqual(plan.runtime_field_assembly_supported_lateral_shift_models, ("none", "first_order"))
        self.assertEqual(plan.rendered_basis_shift_target, "baseline_envelope_ratio")

    def test_runtime_field_assembly_plan_rejects_invalid_rendered_override_shift_combo(self):
        with self.assertRaises(ValueError):
            COEFF_BUNDLE_CORE.plan_runtime_field_assembly_contract(
                requested_second_order_model="tensor_closure",
                coefficient_map_runtime_mode="rendered_basis_override",
                coefficient_map_model_id="low_order_coupled_odd_even_map",
                coefficient_map_artifact_path="shared_map_candidate.npz",
                lateral_shift_model="first_order",
                lateral_shift_coupling="shift_envelope_and_mu2",
                lateral_shift_impl="interp",
                rendered_basis_shift_target="baseline_envelope_ratio",
            )

    def test_fd_oct_measurement_wrapper_builds_and_reconstructs_spectrum(self):
        lambda_nm = np.linspace(840.0, 860.0, 17)
        sample_arm = np.exp(1j * np.linspace(0.0, np.pi, lambda_nm.size))
        spectrum = build_fd_oct_interference_spectrum(
            lambda_nm,
            sample_arm,
            reference_amplitude=0.8,
            reference_phase_rad=0.2,
        )
        self.assertTrue(spectrum["dc_removed"])
        reconstruction = reconstruct_fd_oct_a_scan(
            lambda_nm,
            spectrum["interference_spectrum"],
            window="hann",
        )
        self.assertEqual(reconstruction["reconstruction_complex"].shape, lambda_nm.shape)
        self.assertEqual(reconstruction["reconstruction_intensity"].shape, lambda_nm.shape)
        self.assertEqual(reconstruction["opd_um"].shape, lambda_nm.shape)

    def test_fd_oct_measurement_wrapper_declares_medium_index_depth_convention(self):
        lambda_nm = np.linspace(840.0, 860.0, 17)
        medium_index = np.full(lambda_nm.shape, 1.4, dtype=float)
        sample_arm = np.exp(1j * np.linspace(0.0, np.pi, lambda_nm.size))
        spectrum = build_fd_oct_interference_spectrum(
            lambda_nm,
            sample_arm,
            medium_index=medium_index,
            reference_delay_opd_um=2.0,
        )
        expected_k = 2.0 * np.pi * medium_index / (lambda_nm / 1000.0)
        np.testing.assert_allclose(spectrum["k_rad_per_um"], expected_k)
        self.assertEqual(spectrum["k_axis_kind"], "constant_medium_effective_wavenumber_rad_per_um")
        self.assertEqual(
            spectrum["fd_oct_depth_convention"],
            "geometric_roundtrip_conjugate_to_medium_effective_wavenumber",
        )
        self.assertEqual(spectrum["reference_delay_opd_um"], 2.0)
        reconstruction = reconstruct_fd_oct_a_scan(
            lambda_nm,
            spectrum["interference_spectrum"],
            medium_index=medium_index,
            window="none",
        )
        self.assertEqual(reconstruction["medium_index_policy"], "constant_reference_n_medium")
        np.testing.assert_allclose(
            reconstruction["single_pass_geometric_depth_um"],
            reconstruction["geometric_roundtrip_um"] / 2.0,
        )
        np.testing.assert_allclose(
            reconstruction["optical_roundtrip_path_um"],
            reconstruction["geometric_roundtrip_um"] * 1.4,
        )
        np.testing.assert_allclose(
            reconstruction["single_pass_depth_from_reference_n_um"],
            reconstruction["single_pass_geometric_depth_um"],
        )

    def test_fd_oct_single_reflector_depth_axis_uses_geometric_roundtrip(self):
        lambda_nm = np.linspace(830.0, 880.0, 257)
        medium_index = np.full(lambda_nm.shape, 1.4, dtype=float)
        k_axis = 2.0 * np.pi * medium_index / (lambda_nm / 1000.0)
        reflector_depth_um = 15.0
        sample_arm = np.exp(1j * 2.0 * k_axis * reflector_depth_um)
        spectrum = build_fd_oct_interference_spectrum(
            lambda_nm,
            sample_arm,
            medium_index=medium_index,
            reference_amplitude=1.0,
        )
        reconstruction = reconstruct_fd_oct_a_scan(
            lambda_nm,
            spectrum["interference_spectrum"],
            medium_index=medium_index,
            window="none",
        )
        axis = np.asarray(reconstruction["geometric_roundtrip_um"], dtype=float)
        intensity = np.asarray(reconstruction["reconstruction_intensity"], dtype=float)
        peak_roundtrip_um = abs(float(axis[int(np.argmax(intensity))]))
        grid_step_um = float(np.median(np.diff(axis)))
        self.assertLessEqual(abs(peak_roundtrip_um - 2.0 * reflector_depth_um), grid_step_um / 2.0 + 1e-9)
        self.assertGreater(abs(peak_roundtrip_um - 2.0 * reflector_depth_um / 1.4), grid_step_um / 4.0)

    def test_measurement_protocol_fd_oct_reconstruction_path_uses_spectral_cube(self):
        lambda_nm = np.linspace(840.0, 860.0, 17)
        x_um = np.array([-1.0, 0.0, 1.0], dtype=float)
        opd_um = np.array([-1.0, 0.0, 1.0], dtype=float)
        center_phase = np.exp(1j * np.linspace(0.0, np.pi, lambda_nm.size))
        off_phase = 0.4 * np.exp(1j * np.linspace(0.0, np.pi / 2.0, lambda_nm.size))
        sample_arm_spectral_cube = np.stack([off_phase, center_phase, off_phase], axis=1)
        result = {
            "mode": "bridge",
            "lateral_slice_axis": "x",
            "x_um": x_um,
            "opd_um": opd_um,
            "lambda_nm": lambda_nm,
            "reference_n_medium": 1.4,
            "derived_geometry_series": {
                "n_medium": np.full(lambda_nm.shape, 1.4, dtype=float),
            },
            "sample_arm_spectral_cube": sample_arm_spectral_cube,
            "raw_intensity_xz": np.ones((x_um.size, opd_um.size), dtype=float),
            "global_peak_index": [1, 1],
            "peakline_x_um": 0.0,
            "raw_peak_intensity": 1.0,
            "axial_intensity_metrics": {
                "peak_opd_um": 0.0,
                "centroid_opd_um": 0.0,
                "fwhm_opd_um": 1.0,
                "psr_db": 3.0,
                "sidelobe_energy_fraction": 0.1,
            },
        }
        snapshot = extract_measurement_snapshot(
            result,
            extraction_mode="self_peak",
            pipeline_mode="fd_oct_reconstruction",
        )
        self.assertEqual(snapshot["measurement_pipeline_mode"], "fd_oct_reconstruction")
        self.assertEqual(snapshot["measurement_protocol_kind"], "fd_oct_reconstruction_peak_slice_protocol")
        self.assertEqual(snapshot["measured_lateral_peak_x_um"], 0.0)
        self.assertEqual(snapshot["fd_oct_k_axis_kind"], "constant_medium_effective_wavenumber_rad_per_um")
        self.assertEqual(
            snapshot["fd_oct_depth_convention"],
            "geometric_roundtrip_conjugate_to_medium_effective_wavenumber",
        )
        self.assertEqual(snapshot["fd_oct_medium_index_policy"], "derived_geometry_series_n_medium")
        self.assertEqual(snapshot["fd_oct_reference_n_medium"], 1.4)

    def test_coefficient_path_bundle_npz_roundtrip_contains_recovered_views(self):
        result = {
            "lambda_nm": np.array([840.0, 860.0], dtype=float),
            "x_um": np.array([-1.0, 0.0, 1.0], dtype=float),
            "B_k": np.array([1.0 + 0.0j, 0.8 + 0.1j], dtype=np.complex128),
            "D1_vector_k": np.array([[0.1 + 0.0j, 0.01 + 0.0j], [0.05 + 0.02j, 0.02 + 0.01j]], dtype=np.complex128),
            "D1_slice_k": np.array([0.1 + 0.0j, 0.05 + 0.02j], dtype=np.complex128),
            "C2_tensor_k": np.array(
                [
                    [[0.2 - 0.01j, 0.01 + 0.0j], [0.01 + 0.0j, 0.15 + 0.01j]],
                    [[0.1 + 0.03j, 0.02 + 0.0j], [0.02 + 0.0j, 0.08 + 0.02j]],
                ],
                dtype=np.complex128,
            ),
            "C2_slice_k": np.array([0.2 - 0.01j, 0.1 + 0.03j], dtype=np.complex128),
            "lateral_slice_axis": "x",
            "C2_slice_local_direction": np.array([1.0, 0.0], dtype=float),
            "reference_pupil_field_profile": np.array([1.0 + 0.0j, 0.5 + 0.1j, 0.2 + 0.0j], dtype=np.complex128),
            "directional_first_order_field_profile": np.array([0.0 + 0.1j, 0.2 + 0.0j, 0.0 - 0.1j], dtype=np.complex128),
            "directional_second_order_slice_field_profile": np.array([0.1 + 0.0j, -0.1 + 0.02j, 0.1 + 0.0j], dtype=np.complex128),
            "directional_field_expansion_scale": 2.5,
            "second_order_model": "directional_field_expansion_first_order",
            "fit_diagnostics": {
                "fit_strategy": "joint_low_order",
                "relative_fit_residual_model": "low_order",
                "C2_tensor_basis": "local_backscatter_angle_components_alpha_beta",
                "D1_tensor_basis": "local_backscatter_angle_components_alpha_beta",
                "theta_samples_rad": np.array([0.0, 0.05, 0.1], dtype=float),
                "theta_quadrature_weights": np.array([0.5, 1.0, 0.5], dtype=float),
                "azimuth_samples_rad": np.array([0.0, np.pi], dtype=float),
                "relative_fit_residual": np.array([0.1, 0.2], dtype=float),
            },
        }
        bundle = COEFF_BUNDLE_CORE.build_coefficient_path_bundle(result)
        tmp_dir = workspace_tempdir("coefficient-bundle-")
        try:
            artifact_path = COEFF_BUNDLE_CORE.write_coefficient_path_bundle_npz(
                COEFF_BUNDLE_CORE.coefficient_bundle_report_path(tmp_dir, "demo_case"),
                bundle,
                case_name="demo_case",
                recovered_coefficients_raw=np.array(
                    [[1.2 + 0.0j, 0.3 + 0.0j, 0.25 + 0.0j], [0.9 + 0.0j, 0.2 + 0.0j, 0.12 + 0.0j]],
                    dtype=np.complex128,
                ),
            )
            loaded = COEFF_BUNDLE_CORE.read_coefficient_path_bundle_npz(artifact_path)
            self.assertIn("rendered_coefficients_raw", loaded)
            self.assertIn("recovered_coefficients_raw", loaded)
            self.assertIn("shared_scale_alignment_json", loaded)
            self.assertIn("fit_diagnostics", loaded)
            self.assertIn("theta_samples_rad", loaded["fit_diagnostics"])
            self.assertIn("fitdiag__theta_samples_rad", loaded)
            self.assertEqual(
                str(np.asarray(loaded["bundle_schema_version"]).item()),
                "round6p1_coefficient_path_bundle_v3",
            )
            self.assertEqual(
                str(np.asarray(loaded["coefficient_bundle_artifact_kind"]).item()),
                "native_identity",
            )
            np.testing.assert_allclose(loaded["slice_direction_local"], np.array([1.0, 0.0], dtype=float))
            np.testing.assert_allclose(
                loaded["validated"]["projected_coefficients_raw"],
                bundle.rendered_coefficient_state.projected_coefficients_raw,
                rtol=1e-10,
                atol=1e-12,
            )
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_coefficient_bundle_report_path_uses_semantic_artifact_kinds(self):
        tmp_dir = workspace_tempdir("coefficient-bundle-path-")
        try:
            native = COEFF_BUNDLE_CORE.coefficient_bundle_report_path(tmp_dir, "demo_case")
            self.assertEqual(
                native.name,
                "round6p1_demo_case_native_identity_coefficient_bundle.npz",
            )
            promoted = COEFF_BUNDLE_CORE.coefficient_bundle_report_path(
                tmp_dir,
                "demo_case",
                artifact_kind="shared_map_promoted",
                coefficient_map_model_id="low_order_coupled_odd_even_map",
            )
            self.assertEqual(
                promoted.name,
                "round6p1_demo_case_shared_map_promoted_low_order_coupled_odd_even_map_coefficient_bundle.npz",
            )
            fitted = COEFF_BUNDLE_CORE.coefficient_bundle_report_path(
                tmp_dir,
                "demo_case",
                artifact_kind="case_specific_fitted_map_diagnostic",
            )
            self.assertEqual(
                fitted.name,
                "round6p1_demo_case_case_specific_fitted_map_diagnostic_bundle.npz",
            )
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_coefficient_path_bundle_validator_rejects_rendered_map_mismatch(self):
        result = {
            "lambda_nm": np.array([840.0, 860.0], dtype=float),
            "x_um": np.array([-1.0, 0.0, 1.0], dtype=float),
            "B_k": np.array([1.0 + 0.0j, 0.8 + 0.1j], dtype=np.complex128),
            "D1_vector_k": np.array([[0.1 + 0.0j, 0.01 + 0.0j], [0.05 + 0.02j, 0.02 + 0.01j]], dtype=np.complex128),
            "D1_slice_k": np.array([0.1 + 0.0j, 0.05 + 0.02j], dtype=np.complex128),
            "C2_tensor_k": np.array(
                [
                    [[0.2 - 0.01j, 0.01 + 0.0j], [0.01 + 0.0j, 0.15 + 0.01j]],
                    [[0.1 + 0.03j, 0.02 + 0.0j], [0.02 + 0.0j, 0.08 + 0.02j]],
                ],
                dtype=np.complex128,
            ),
            "C2_slice_k": np.array([0.2 - 0.01j, 0.1 + 0.03j], dtype=np.complex128),
            "lateral_slice_axis": "x",
            "C2_slice_local_direction": np.array([1.0, 0.0], dtype=float),
            "reference_pupil_field_profile": np.array([1.0 + 0.0j, 0.5 + 0.1j, 0.2 + 0.0j], dtype=np.complex128),
            "directional_first_order_field_profile": np.array([0.0 + 0.1j, 0.2 + 0.0j, 0.0 - 0.1j], dtype=np.complex128),
            "directional_second_order_slice_field_profile": np.array([0.1 + 0.0j, -0.1 + 0.02j, 0.1 + 0.0j], dtype=np.complex128),
            "directional_field_expansion_scale": 2.5,
            "second_order_model": "directional_field_expansion_first_order",
            "fit_diagnostics": {
                "fit_strategy": "joint_low_order",
                "relative_fit_residual_model": "low_order",
                "C2_tensor_basis": "local_backscatter_angle_components_alpha_beta",
                "D1_tensor_basis": "local_backscatter_angle_components_alpha_beta",
                "theta_samples_rad": np.array([0.0, 0.05, 0.1], dtype=float),
                "theta_quadrature_weights": np.array([0.5, 1.0, 0.5], dtype=float),
                "azimuth_samples_rad": np.array([0.0, np.pi], dtype=float),
                "relative_fit_residual": np.array([0.1, 0.2], dtype=float),
            },
        }
        bundle = COEFF_BUNDLE_CORE.build_coefficient_path_bundle(result)
        payload = COEFF_BUNDLE_CORE.coefficient_path_bundle_npz_payload(bundle, case_name="tamper_rendered")
        payload["rendered_coefficients_raw"] = np.asarray(payload["rendered_coefficients_raw"]) + (0.1 + 0.0j)
        with self.assertRaises(ValueError):
            COEFF_BUNDLE_CORE.validate_coefficient_path_bundle_payload(payload)

    def test_coefficient_path_bundle_validator_rejects_orthonormal_mismatch(self):
        result = {
            "lambda_nm": np.array([840.0, 860.0], dtype=float),
            "x_um": np.array([-1.0, 0.0, 1.0], dtype=float),
            "B_k": np.array([1.0 + 0.0j, 0.8 + 0.1j], dtype=np.complex128),
            "D1_vector_k": np.array([[0.1 + 0.0j, 0.01 + 0.0j], [0.05 + 0.02j, 0.02 + 0.01j]], dtype=np.complex128),
            "D1_slice_k": np.array([0.1 + 0.0j, 0.05 + 0.02j], dtype=np.complex128),
            "C2_tensor_k": np.array(
                [
                    [[0.2 - 0.01j, 0.01 + 0.0j], [0.01 + 0.0j, 0.15 + 0.01j]],
                    [[0.1 + 0.03j, 0.02 + 0.0j], [0.02 + 0.0j, 0.08 + 0.02j]],
                ],
                dtype=np.complex128,
            ),
            "C2_slice_k": np.array([0.2 - 0.01j, 0.1 + 0.03j], dtype=np.complex128),
            "lateral_slice_axis": "x",
            "C2_slice_local_direction": np.array([1.0, 0.0], dtype=float),
            "reference_pupil_field_profile": np.array([1.0 + 0.0j, 0.5 + 0.1j, 0.2 + 0.0j], dtype=np.complex128),
            "directional_first_order_field_profile": np.array([0.0 + 0.1j, 0.2 + 0.0j, 0.0 - 0.1j], dtype=np.complex128),
            "directional_second_order_slice_field_profile": np.array([0.1 + 0.0j, -0.1 + 0.02j, 0.1 + 0.0j], dtype=np.complex128),
            "directional_field_expansion_scale": 2.5,
            "second_order_model": "directional_field_expansion_first_order",
            "fit_diagnostics": {
                "fit_strategy": "joint_low_order",
                "relative_fit_residual_model": "low_order",
                "C2_tensor_basis": "local_backscatter_angle_components_alpha_beta",
                "D1_tensor_basis": "local_backscatter_angle_components_alpha_beta",
                "theta_samples_rad": np.array([0.0, 0.05, 0.1], dtype=float),
                "theta_quadrature_weights": np.array([0.5, 1.0, 0.5], dtype=float),
                "azimuth_samples_rad": np.array([0.0, np.pi], dtype=float),
                "relative_fit_residual": np.array([0.1, 0.2], dtype=float),
            },
        }
        bundle = COEFF_BUNDLE_CORE.build_coefficient_path_bundle(result)
        payload = COEFF_BUNDLE_CORE.coefficient_path_bundle_npz_payload(bundle, case_name="tamper_orth")
        payload["rendered_coefficients_orthonormalized"] = np.asarray(payload["rendered_coefficients_orthonormalized"]) + (0.1 + 0.0j)
        with self.assertRaises(ValueError):
            COEFF_BUNDLE_CORE.validate_coefficient_path_bundle_payload(payload)

    def test_apply_coefficient_map_ablation_summary_promotes_ablation_guidance(self):
        report = {
            "recommended_next_action": "debug_coefficient_extraction_or_usage_mapping",
            "final_recommended_next_action": "debug_coefficient_extraction_or_usage_mapping",
            "final_recommended_next_action_source": "coefficient_injection",
        }
        updated = VALIDATOR.apply_coefficient_map_ablation_summary(
            report,
            {
                "coefficient_map_ablation_recommended_next_action": "audit_coefficient_map_generalization_before_production",
                "coefficient_map_ablation_case_names": ["case_a", "case_b"],
                "coefficient_map_ablation_models": ["identity_slice_projected_rendered_basis", "low_order_coupled_odd_even_map"],
                "best_ablated_coefficient_map_model_id": "low_order_coupled_odd_even_map",
            },
        )
        self.assertEqual(updated["final_recommended_next_action"], "audit_coefficient_map_generalization_before_production")
        self.assertEqual(updated["final_recommended_next_action_source"], "coefficient_map_ablation")
        self.assertEqual(updated["best_ablated_coefficient_map_model_id"], "low_order_coupled_odd_even_map")
        self.assertEqual(updated["coefficient_map_ablation_guidance_status"], "explicit_report_used")

    def test_fit_sensitivity_recommendation_flags_large_d1_variation(self):
        action = FIT_SENSITIVITY._recommend_next_action(
            [
                {
                    "sensitivity_summary": {
                        "max_abs_D1_over_abs_B_ratio_vs_default": 3.0,
                        "max_abs_C2_over_abs_B_ratio_vs_default": 1.1,
                        "max_a1_residual_delta_vs_default": 0.12,
                        "max_a2_residual_delta_vs_default": 0.02,
                    }
                },
                {
                    "sensitivity_summary": {
                        "max_abs_D1_over_abs_B_ratio_vs_default": 2.5,
                        "max_abs_C2_over_abs_B_ratio_vs_default": 1.2,
                        "max_a1_residual_delta_vs_default": 0.14,
                        "max_a2_residual_delta_vs_default": 0.01,
                    }
                },
            ]
        )
        self.assertEqual(action, "debug_effective_channel_fit_window_before_usage_mapping")


if __name__ == "__main__":
    unittest.main()
