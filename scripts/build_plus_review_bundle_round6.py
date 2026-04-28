from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
REPORTS_DIR = PROJECT_ROOT / "reports"


SCRIPT_FILE_MAP = {
    "oct_nonspherical_psf_solver.py": "01_oct_nonspherical_psf_solver.py",
    "10_vector_pupil_overlap_bridge.py": "02_vector_pupil_overlap_bridge.py",
    "11_low_na_asymptotic.py": "03_low_na_asymptotic.py",
    "validate_oct_nonspherical_psf_solver.py": "04_validate_oct_nonspherical_psf_solver.py",
    "build_round6p1_evidence_package.py": "05_build_round6p1_evidence_package.py",
    "14_bridge_basis_projection_diagnostics.py": "06_bridge_basis_projection_diagnostics.py",
    "15_bridge_basis_coefficient_recovery.py": "07_bridge_basis_coefficient_recovery.py",
    "16_effective_channel_fit_sensitivity.py": "08_effective_channel_fit_sensitivity.py",
    "17_bridge_coefficient_injection_diagnostics.py": "09_bridge_coefficient_injection_diagnostics.py",
    "18_effective_channel_fit_strategy_ablation.py": "10_effective_channel_fit_strategy_ablation.py",
    "19_lateral_slice_axis_crosscheck.py": "11_lateral_slice_axis_crosscheck.py",
    "20_coefficient_map_audit.py": "20_coefficient_map_audit.py",
    "21_coefficient_map_stability.py": "21_coefficient_map_stability.py",
    "22_coefficient_map_ablation.py": "22_coefficient_map_ablation.py",
    "particle_size_sweep_runner.py": "28_particle_size_sweep_runner.py",
    "refresh_round6p1_measurement_contract_artifacts.py": "30_refresh_round6p1_measurement_contract_artifacts.py",
    "controlled_cp310_evidence_rebuild.py": "31_controlled_cp310_evidence_rebuild.py",
}

ROOT_FILE_MAP = {
    "test_low_na_asymptotic_helpers.py": "12_test_low_na_asymptotic_helpers.py",
}

SCRIPTS_COMPAT_FILE_MAP = {
    "oct_nonspherical_psf_solver.py": ("oct_nonspherical_psf_solver.py",),
    "10_vector_pupil_overlap_bridge.py": ("10_vector_pupil_overlap_bridge.py", "vector_pupil_overlap_bridge.py"),
    "11_low_na_asymptotic.py": ("11_low_na_asymptotic.py", "low_na_asymptotic.py"),
    "validate_oct_nonspherical_psf_solver.py": ("validate_oct_nonspherical_psf_solver.py",),
    "build_round6p1_evidence_package.py": ("build_round6p1_evidence_package.py",),
    "particle_size_sweep_runner.py": ("particle_size_sweep_runner.py",),
    "refresh_round6p1_measurement_contract_artifacts.py": ("refresh_round6p1_measurement_contract_artifacts.py",),
    "controlled_cp310_evidence_rebuild.py": ("controlled_cp310_evidence_rebuild.py",),
}

TEST_COMPAT_FILE_MAP = {
    "tests/test_low_na_asymptotic_helpers.py": "tests/test_low_na_asymptotic_helpers.py",
}

REPORT_FILE_MAP = {
    "round6p1_update.md": "13_round6p1_update.md",
    "round6p1_validation_summary.json": "14_round6p1_validation_summary.json",
    "round6p1_validation_failure_summary.txt": "14a_round6p1_validation_failure_summary.txt",
    "round6p1_error_attribution.json": "15_round6p1_error_attribution.json",
    "round6p1_error_attribution.md": "15a_round6p1_error_attribution.md",
    "round6p1_ablation_results.json": "16_round6p1_ablation_results.json",
    "round6p1_ablation_results.md": "16a_round6p1_ablation_results.md",
    "round6p1_basis_projection_diagnostics.json": "17_round6p1_basis_projection_diagnostics.json",
    "round6p1_basis_projection_diagnostics.md": "17a_round6p1_basis_projection_diagnostics.md",
    "round6p1_basis_coefficient_recovery.json": "18_round6p1_basis_coefficient_recovery.json",
    "round6p1_basis_coefficient_recovery.md": "18a_round6p1_basis_coefficient_recovery.md",
    "round6p1_effective_channel_fit_sensitivity.json": "19_round6p1_effective_channel_fit_sensitivity.json",
    "round6p1_effective_channel_fit_sensitivity.md": "19a_round6p1_effective_channel_fit_sensitivity.md",
    "round6p1_coefficient_injection_diagnostics.json": "20_round6p1_coefficient_injection_diagnostics.json",
    "round6p1_coefficient_injection_diagnostics.md": "20a_round6p1_coefficient_injection_diagnostics.md",
    "round6p1_effective_channel_fit_strategy_ablation.json": "21_round6p1_effective_channel_fit_strategy_ablation.json",
    "round6p1_effective_channel_fit_strategy_ablation.md": "21a_round6p1_effective_channel_fit_strategy_ablation.md",
    "round6p1_lateral_slice_axis_crosscheck.json": "22_round6p1_lateral_slice_axis_crosscheck.json",
    "round6p1_lateral_slice_axis_crosscheck.md": "22a_round6p1_lateral_slice_axis_crosscheck.md",
    "round6p1_coefficient_map_audit.json": "22b_round6p1_coefficient_map_audit.json",
    "round6p1_coefficient_map_audit.md": "22c_round6p1_coefficient_map_audit.md",
    "round6p1_coefficient_map_stability.json": "22d_round6p1_coefficient_map_stability.json",
    "round6p1_coefficient_map_stability.md": "22e_round6p1_coefficient_map_stability.md",
    "round6p1_coefficient_map_ablation.json": "22f_round6p1_coefficient_map_ablation.json",
    "round6p1_coefficient_map_ablation.md": "22g_round6p1_coefficient_map_ablation.md",
    "result_schema_round6p1.md": "23_result_schema_round6p1.md",
    "benchmark_gates_round6p1.md": "24_benchmark_gates_round6p1.md",
    "known_limits_round6p1.md": "25_known_limits_round6p1.md",
    "round6p1_new_thread_handoff.md": "26_round6p1_new_thread_handoff.md",
    "round6p1_measurement_protocol_bias.json": "27_round6p1_measurement_protocol_bias.json",
    "round6p1_measurement_protocol_bias.md": "27a_round6p1_measurement_protocol_bias.md",
    "round6p1_particle_size_sweep.json": "29_round6p1_particle_size_sweep.json",
    "round6p1_particle_size_sweep.md": "29a_round6p1_particle_size_sweep.md",
}

OPTIONAL_REPORT_FILE_MAP = {
    "round6p1_cp310_evidence_rebuild_readiness.json": "31_round6p1_cp310_evidence_rebuild_readiness.json",
    "round6p1_cp310_evidence_rebuild_readiness.md": "31a_round6p1_cp310_evidence_rebuild_readiness.md",
}

REPORT_GLOB_PATTERNS = (
    "round6p1_*_native_identity_coefficient_bundle.npz",
    "round6p1_*_shared_map_promoted_*_coefficient_bundle.npz",
    "round6p1_*_case_specific_fitted_map_diagnostic_bundle.npz",
    "round6p1_shared_coefficient_map_candidate_*.npz",
)

TREE_COPY_MAP = {
    "vendor": "vendor",
    "measurement_protocol": "measurement_protocol",
    "oct_forward": "oct_forward",
    "apps": "apps",
    "diagnostics": "diagnostics",
    "physics": "physics",
    "solvers": "solvers",
}

IGNORE_NAMES = shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo", ".pytest_cache", "_cache", "tmp")


def read_summary() -> dict:
    summary_path = _resolve_report_source("round6p1_validation_summary.json")
    return json.loads(summary_path.read_text(encoding="utf-8"))


def _resolve_report_source(source_name: str) -> Path:
    source_path = REPORTS_DIR / source_name
    if source_name == "round6p1_validation_summary.json":
        refreshed_path = REPORTS_DIR / "round6p1_validation_summary.refreshed.json"
        if refreshed_path.exists():
            return refreshed_path
    if source_name == "round6p1_validation_failure_summary.txt":
        refreshed_path = REPORTS_DIR / "round6p1_validation_failure_summary.refreshed.txt"
        if refreshed_path.exists():
            return refreshed_path
    return source_path


def ensure_clean_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def copy_mapped_file(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def copy_tree(source: Path, destination: Path) -> None:
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination, ignore=IGNORE_NAMES)


def build_readme(bundle_root: Path, summary: dict) -> None:
    lines = [
        f"Round6 latest Plus review bundle ({bundle_root.name.split('_')[-1]}, self-contained runtime repair)",
        "",
        "This bundle reflects the latest round6p1 source fixes plus a verified flat-bundle rebuild.",
        "It is still a three-layer OCT forward-diagnostic stack, not a measurement-grade raw-domain OCT simulator.",
        "",
        "Key current conclusions:",
        f"- most_critical_open_model_limit = {summary.get('most_critical_open_model_limit')}",
        f"- dominant_error_bucket = {summary.get('dominant_error_bucket')}",
        f"- final_recommended_next_action = {summary.get('final_recommended_next_action')}",
        f"- final_recommended_next_action_source = {summary.get('final_recommended_next_action_source')}",
        f"- evidence_dependency_status = {summary.get('evidence_dependency_status')}",
        f"- guidance_confidence = {summary.get('guidance_confidence')}",
        f"- measurement_pipeline_evidence_status = {summary.get('measurement_pipeline_evidence_status')}",
        f"- measurement_pipeline_default_mode = {summary.get('measurement_pipeline_default_mode')}",
        f"- fd_oct_measurement_wrapper_status = {summary.get('fd_oct_measurement_wrapper_status')}",
        f"- measurement_reference_arm_policy_status = {summary.get('measurement_reference_arm_policy_status')}",
        f"- measurement_artifact_freshness_status = {summary.get('measurement_artifact_freshness_status')}",
        f"- cp310_evidence_rebuild_readiness_status = {summary.get('cp310_evidence_rebuild_readiness_status')}",
        f"- particle_size_sweep_status = {summary.get('particle_size_sweep_status')}",
        f"- particle_size_sweep_diameter_range_nm = {summary.get('particle_size_sweep_diameter_range_nm')}",
        "",
        "Important scope note:",
        "- this bundle is not a full raw-domain OCT measurement simulator",
        "- it is a particle-response solver stack plus bridge/asymptotic diagnostics and a minimal measurement-layer adapter",
        "- the measurement layer now compares both `solver_output_peak_slice_adapter` and `fd_oct_reconstruction` routes when the solver exposes the spectral sample-arm contract",
        "- the FD-OCT route uses `k = 2*pi*n_medium/lambda0`; its FFT axis is `geometric_roundtrip_um`, with `opd_um` retained only as a legacy alias",
        "- `low_na_separable_baseline` must be read as an axial-spectrum baseline with a Gaussian lateral surrogate, not as a particle-aware lateral PSF baseline",
        "- coefficient artifacts are now split semantically into native identity bundles, promoted shared-map runtime bundles, and case-specific fitted-map diagnostic bundles",
        "",
        "Bundle runtime contract:",
        "- 01/02/03 baseline, bridge, and asymptotic modes run directly inside this bundle",
        "- 04_validate... writes reports into the bundle root in flat-bundle mode",
        "- 05_build_round6p1_evidence_package.py is the preferred entrypoint for full-evidence regeneration",
        "- 28_particle_size_sweep_runner.py provides a 200-1000 nm particle-size sweep harness for smoke/coverage runs",
        "- 30_refresh_round6p1_measurement_contract_artifacts.py refreshes measurement-contract labels from existing numerical evidence when the local runtime cannot recompute T-matrix artifacts",
        "- 31_controlled_cp310_evidence_rebuild.py probes a controlled CPython 3.10 runtime and only runs full evidence regeneration when explicitly requested with --execute",
        "- `scripts/` compatibility copies are included so repo-style tests and flat numbered handoff entrypoints both resolve",
        "- 29_round6p1_particle_size_sweep.json/.md is the builder-integrated sweep evidence summary",
        "- unsupported runtimes now degrade gracefully on missing/incompatible T-matrix backends instead of crashing with raw tracebacks",
    ]
    (bundle_root / "00_README.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_zip(bundle_root: Path, zip_path: Path) -> None:
    if zip_path.exists():
        zip_path.unlink()
    with ZipFile(zip_path, "w", compression=ZIP_DEFLATED) as archive:
        for path in sorted(bundle_root.rglob("*")):
            if path.is_dir():
                continue
            archive.write(path, arcname=str(path.relative_to(bundle_root.parent)))


def main() -> None:
    summary = read_summary()
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    bundle_name = f"plus_review_bundle_round6_latest_{timestamp}"
    bundle_root = REPORTS_DIR / bundle_name
    zip_path = REPORTS_DIR / f"{bundle_name}.zip"

    ensure_clean_dir(bundle_root)

    for source_name, dest_name in SCRIPT_FILE_MAP.items():
        copy_mapped_file(SCRIPT_DIR / source_name, bundle_root / dest_name)

    for source_name, dest_name in ROOT_FILE_MAP.items():
        copy_mapped_file(PROJECT_ROOT / source_name, bundle_root / dest_name)

    for source_name, dest_names in SCRIPTS_COMPAT_FILE_MAP.items():
        for dest_name in dest_names:
            copy_mapped_file(SCRIPT_DIR / source_name, bundle_root / "scripts" / dest_name)

    for source_name, dest_name in TEST_COMPAT_FILE_MAP.items():
        copy_mapped_file(PROJECT_ROOT / source_name, bundle_root / dest_name)

    for source_name, dest_name in REPORT_FILE_MAP.items():
        copy_mapped_file(_resolve_report_source(source_name), bundle_root / dest_name)

    for source_name, dest_name in OPTIONAL_REPORT_FILE_MAP.items():
        source_path = _resolve_report_source(source_name)
        if source_path.exists():
            copy_mapped_file(source_path, bundle_root / dest_name)

    for pattern in REPORT_GLOB_PATTERNS:
        for source_path in sorted(REPORTS_DIR.glob(pattern)):
            copy_mapped_file(source_path, bundle_root / source_path.name)

    for source_name, dest_name in TREE_COPY_MAP.items():
        copy_tree(PROJECT_ROOT / source_name, bundle_root / dest_name)

    build_readme(bundle_root, summary)
    write_zip(bundle_root, zip_path)
    (REPORTS_DIR / "_latest_bundle_path.txt").write_text(str(bundle_root) + "\n", encoding="utf-8")

    print(f"BUNDLE_DIR={bundle_root}")
    print(f"BUNDLE_ZIP={zip_path}")


if __name__ == "__main__":
    main()
