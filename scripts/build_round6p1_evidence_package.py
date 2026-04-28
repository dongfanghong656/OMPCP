from __future__ import annotations

import argparse
import datetime as _dt
import gc
import importlib.util
import json
import platform
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from apps.report_paths import resolve_reports_dir
from diagnostics import (
    _runtime as diagnostics_runtime,
    basis_coefficient_recovery as coefficient_recovery_diagnostics,
    coefficient_map_audit as coefficient_map_audit_diagnostics,
    coefficient_map_ablation as coefficient_map_ablation_diagnostics,
    coefficient_map_stability as coefficient_map_stability_diagnostics,
    bridge_basis_projection as basis_projection_diagnostics,
    coefficient_injection as coefficient_injection_diagnostics,
    fit_sensitivity as fit_sensitivity_diagnostics,
    fit_strategy_ablation as fit_strategy_ablation_diagnostics,
    slice_axis_crosscheck as slice_axis_crosscheck_diagnostics,
)
from physics.tmatrix_backend import probe_tmatrix_backend


def _load_module_with_alias(module_name: str, *candidate_names: str):
    module = sys.modules.get(module_name)
    if module is not None:
        return module
    try:
        return __import__(module_name)
    except ModuleNotFoundError:
        for candidate_name in candidate_names:
            candidate_path = SCRIPT_DIR / candidate_name
            if candidate_path.exists():
                spec = importlib.util.spec_from_file_location(module_name, candidate_path)
                if spec is None or spec.loader is None:
                    continue
                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module
                spec.loader.exec_module(module)
                return module
        raise


_SOLVER = _load_module_with_alias("oct_nonspherical_psf_solver", "oct_nonspherical_psf_solver.py", "01_oct_nonspherical_psf_solver.py")
_VALIDATOR = _load_module_with_alias(
    "validate_oct_nonspherical_psf_solver",
    "validate_oct_nonspherical_psf_solver.py",
    "04_validate_oct_nonspherical_psf_solver.py",
)
_PARTICLE_SWEEP = _load_module_with_alias(
    "particle_size_sweep_runner",
    "particle_size_sweep_runner.py",
    "28_particle_size_sweep_runner.py",
)
from measurement_protocol import build_measurement_protocol_package as build_measurement_protocol_package_core
from measurement_protocol import compare_measurement_snapshots

FULL_NA_BASELINE_MODE = _SOLVER.FULL_NA_BASELINE_MODE
LOW_NA_BASELINE_MODE = _SOLVER.LOW_NA_BASELINE_MODE
LOW_NA_ASYMPTOTIC_MODE = _SOLVER.LOW_NA_ASYMPTOTIC_MODE
GridConfig = _SOLVER.GridConfig
SolverConfig = _SOLVER.SolverConfig
SourceConfig = _SOLVER.SourceConfig
VECTOR_BRIDGE_MODE = _SOLVER.VECTOR_BRIDGE_MODE
solve_oct_particle_response = _SOLVER.solve_oct_particle_response

DEFAULT_FAILURE_SUMMARY_PATH = _VALIDATOR.DEFAULT_FAILURE_SUMMARY_PATH
DEFAULT_JSON_REPORT_PATH = _VALIDATOR.DEFAULT_JSON_REPORT_PATH
DEFAULT_BASIS_PROJECTION_REPORT_PATH = _VALIDATOR.DEFAULT_BASIS_PROJECTION_REPORT_PATH
DEFAULT_COEFFICIENT_RECOVERY_REPORT_PATH = _VALIDATOR.DEFAULT_COEFFICIENT_RECOVERY_REPORT_PATH
ROUND6P1_REPRESENTATIVE_CASES = _VALIDATOR.ROUND6P1_REPRESENTATIVE_CASES
apply_complex_field_match_scale = _VALIDATOR.apply_complex_field_match_scale
classify_dominant_error_bucket = _VALIDATOR.classify_dominant_error_bucket
image_difference_diagnostics = _VALIDATOR.image_difference_diagnostics
render_failure_summary = _VALIDATOR.render_failure_summary
snapshot_for_comparison = _VALIDATOR.snapshot_for_comparison
validate = _VALIDATOR.validate

DEFAULT_REPORTS_DIR = resolve_reports_dir(__file__)
REPORTS_DIR = DEFAULT_REPORTS_DIR
SCRIPTS_DIR = Path(__file__).resolve().parent
ERROR_ATTRIBUTION_JSON = REPORTS_DIR / "round6p1_error_attribution.json"
ERROR_ATTRIBUTION_MD = REPORTS_DIR / "round6p1_error_attribution.md"
ABLATION_JSON = REPORTS_DIR / "round6p1_ablation_results.json"
ABLATION_MD = REPORTS_DIR / "round6p1_ablation_results.md"
ROUND6P1_VALIDATION_JSON = REPORTS_DIR / "round6p1_validation_summary.json"
ROUND6P1_FAILURE_SUMMARY = REPORTS_DIR / "round6p1_validation_failure_summary.txt"
FIT_SENSITIVITY_JSON = REPORTS_DIR / "round6p1_effective_channel_fit_sensitivity.json"
FIT_SENSITIVITY_MD = REPORTS_DIR / "round6p1_effective_channel_fit_sensitivity.md"
FIT_STRATEGY_ABLATION_JSON = REPORTS_DIR / "round6p1_effective_channel_fit_strategy_ablation.json"
FIT_STRATEGY_ABLATION_MD = REPORTS_DIR / "round6p1_effective_channel_fit_strategy_ablation.md"
COEFFICIENT_INJECTION_JSON = REPORTS_DIR / "round6p1_coefficient_injection_diagnostics.json"
COEFFICIENT_INJECTION_MD = REPORTS_DIR / "round6p1_coefficient_injection_diagnostics.md"
COEFFICIENT_MAP_AUDIT_JSON = REPORTS_DIR / "round6p1_coefficient_map_audit.json"
COEFFICIENT_MAP_AUDIT_MD = REPORTS_DIR / "round6p1_coefficient_map_audit.md"
COEFFICIENT_MAP_ABLATION_JSON = REPORTS_DIR / "round6p1_coefficient_map_ablation.json"
COEFFICIENT_MAP_ABLATION_MD = REPORTS_DIR / "round6p1_coefficient_map_ablation.md"
COEFFICIENT_MAP_STABILITY_JSON = REPORTS_DIR / "round6p1_coefficient_map_stability.json"
COEFFICIENT_MAP_STABILITY_MD = REPORTS_DIR / "round6p1_coefficient_map_stability.md"
SLICE_AXIS_CROSSCHECK_JSON = REPORTS_DIR / "round6p1_lateral_slice_axis_crosscheck.json"
SLICE_AXIS_CROSSCHECK_MD = REPORTS_DIR / "round6p1_lateral_slice_axis_crosscheck.md"
MEASUREMENT_PROTOCOL_JSON = REPORTS_DIR / "round6p1_measurement_protocol_bias.json"
MEASUREMENT_PROTOCOL_MD = REPORTS_DIR / "round6p1_measurement_protocol_bias.md"
PARTICLE_SIZE_SWEEP_JSON = REPORTS_DIR / "round6p1_particle_size_sweep.json"
PARTICLE_SIZE_SWEEP_MD = REPORTS_DIR / "round6p1_particle_size_sweep.md"


def configure_report_paths(reports_dir: str | Path) -> Path:
    """Route this builder and imported diagnostics to one explicit report dir."""
    global REPORTS_DIR
    global ERROR_ATTRIBUTION_JSON, ERROR_ATTRIBUTION_MD
    global ABLATION_JSON, ABLATION_MD
    global ROUND6P1_VALIDATION_JSON, ROUND6P1_FAILURE_SUMMARY
    global FIT_SENSITIVITY_JSON, FIT_SENSITIVITY_MD
    global FIT_STRATEGY_ABLATION_JSON, FIT_STRATEGY_ABLATION_MD
    global COEFFICIENT_INJECTION_JSON, COEFFICIENT_INJECTION_MD
    global COEFFICIENT_MAP_AUDIT_JSON, COEFFICIENT_MAP_AUDIT_MD
    global COEFFICIENT_MAP_ABLATION_JSON, COEFFICIENT_MAP_ABLATION_MD
    global COEFFICIENT_MAP_STABILITY_JSON, COEFFICIENT_MAP_STABILITY_MD
    global SLICE_AXIS_CROSSCHECK_JSON, SLICE_AXIS_CROSSCHECK_MD
    global MEASUREMENT_PROTOCOL_JSON, MEASUREMENT_PROTOCOL_MD
    global PARTICLE_SIZE_SWEEP_JSON, PARTICLE_SIZE_SWEEP_MD
    global DEFAULT_FAILURE_SUMMARY_PATH, DEFAULT_JSON_REPORT_PATH
    global DEFAULT_BASIS_PROJECTION_REPORT_PATH, DEFAULT_COEFFICIENT_RECOVERY_REPORT_PATH

    REPORTS_DIR = Path(reports_dir).resolve()
    ERROR_ATTRIBUTION_JSON = REPORTS_DIR / "round6p1_error_attribution.json"
    ERROR_ATTRIBUTION_MD = REPORTS_DIR / "round6p1_error_attribution.md"
    ABLATION_JSON = REPORTS_DIR / "round6p1_ablation_results.json"
    ABLATION_MD = REPORTS_DIR / "round6p1_ablation_results.md"
    ROUND6P1_VALIDATION_JSON = REPORTS_DIR / "round6p1_validation_summary.json"
    ROUND6P1_FAILURE_SUMMARY = REPORTS_DIR / "round6p1_validation_failure_summary.txt"
    FIT_SENSITIVITY_JSON = REPORTS_DIR / "round6p1_effective_channel_fit_sensitivity.json"
    FIT_SENSITIVITY_MD = REPORTS_DIR / "round6p1_effective_channel_fit_sensitivity.md"
    FIT_STRATEGY_ABLATION_JSON = REPORTS_DIR / "round6p1_effective_channel_fit_strategy_ablation.json"
    FIT_STRATEGY_ABLATION_MD = REPORTS_DIR / "round6p1_effective_channel_fit_strategy_ablation.md"
    COEFFICIENT_INJECTION_JSON = REPORTS_DIR / "round6p1_coefficient_injection_diagnostics.json"
    COEFFICIENT_INJECTION_MD = REPORTS_DIR / "round6p1_coefficient_injection_diagnostics.md"
    COEFFICIENT_MAP_AUDIT_JSON = REPORTS_DIR / "round6p1_coefficient_map_audit.json"
    COEFFICIENT_MAP_AUDIT_MD = REPORTS_DIR / "round6p1_coefficient_map_audit.md"
    COEFFICIENT_MAP_ABLATION_JSON = REPORTS_DIR / "round6p1_coefficient_map_ablation.json"
    COEFFICIENT_MAP_ABLATION_MD = REPORTS_DIR / "round6p1_coefficient_map_ablation.md"
    COEFFICIENT_MAP_STABILITY_JSON = REPORTS_DIR / "round6p1_coefficient_map_stability.json"
    COEFFICIENT_MAP_STABILITY_MD = REPORTS_DIR / "round6p1_coefficient_map_stability.md"
    SLICE_AXIS_CROSSCHECK_JSON = REPORTS_DIR / "round6p1_lateral_slice_axis_crosscheck.json"
    SLICE_AXIS_CROSSCHECK_MD = REPORTS_DIR / "round6p1_lateral_slice_axis_crosscheck.md"
    MEASUREMENT_PROTOCOL_JSON = REPORTS_DIR / "round6p1_measurement_protocol_bias.json"
    MEASUREMENT_PROTOCOL_MD = REPORTS_DIR / "round6p1_measurement_protocol_bias.md"
    PARTICLE_SIZE_SWEEP_JSON = REPORTS_DIR / "round6p1_particle_size_sweep.json"
    PARTICLE_SIZE_SWEEP_MD = REPORTS_DIR / "round6p1_particle_size_sweep.md"

    DEFAULT_JSON_REPORT_PATH = ROUND6P1_VALIDATION_JSON
    DEFAULT_FAILURE_SUMMARY_PATH = ROUND6P1_FAILURE_SUMMARY
    DEFAULT_BASIS_PROJECTION_REPORT_PATH = REPORTS_DIR / "round6p1_basis_projection_diagnostics.json"
    DEFAULT_COEFFICIENT_RECOVERY_REPORT_PATH = REPORTS_DIR / "round6p1_basis_coefficient_recovery.json"

    _VALIDATOR.REPORTS_DIR = REPORTS_DIR
    _VALIDATOR.DEFAULT_JSON_REPORT_PATH = DEFAULT_JSON_REPORT_PATH
    _VALIDATOR.DEFAULT_FAILURE_SUMMARY_PATH = DEFAULT_FAILURE_SUMMARY_PATH
    _VALIDATOR.DEFAULT_BASIS_PROJECTION_REPORT_PATH = DEFAULT_BASIS_PROJECTION_REPORT_PATH
    _VALIDATOR.DEFAULT_COEFFICIENT_RECOVERY_REPORT_PATH = DEFAULT_COEFFICIENT_RECOVERY_REPORT_PATH
    _VALIDATOR.DEFAULT_FIT_SENSITIVITY_REPORT_PATH = FIT_SENSITIVITY_JSON
    _VALIDATOR.DEFAULT_COEFFICIENT_INJECTION_REPORT_PATH = COEFFICIENT_INJECTION_JSON
    _VALIDATOR.DEFAULT_COEFFICIENT_MAP_AUDIT_REPORT_PATH = COEFFICIENT_MAP_AUDIT_JSON
    _VALIDATOR.DEFAULT_COEFFICIENT_MAP_ABLATION_REPORT_PATH = COEFFICIENT_MAP_ABLATION_JSON
    _VALIDATOR.DEFAULT_COEFFICIENT_MAP_STABILITY_REPORT_PATH = COEFFICIENT_MAP_STABILITY_JSON
    _VALIDATOR.DEFAULT_FIT_STRATEGY_ABLATION_REPORT_PATH = FIT_STRATEGY_ABLATION_JSON
    _VALIDATOR.DEFAULT_SLICE_AXIS_CROSSCHECK_REPORT_PATH = SLICE_AXIS_CROSSCHECK_JSON
    _VALIDATOR.DEFAULT_MEASUREMENT_PROTOCOL_REPORT_PATH = MEASUREMENT_PROTOCOL_JSON
    _VALIDATOR.DEFAULT_PARTICLE_SIZE_SWEEP_REPORT_PATH = PARTICLE_SIZE_SWEEP_JSON

    for module in (
        diagnostics_runtime,
        basis_projection_diagnostics,
        coefficient_recovery_diagnostics,
        coefficient_injection_diagnostics,
        fit_sensitivity_diagnostics,
        fit_strategy_ablation_diagnostics,
        slice_axis_crosscheck_diagnostics,
        coefficient_map_audit_diagnostics,
        coefficient_map_ablation_diagnostics,
        coefficient_map_stability_diagnostics,
    ):
        if hasattr(module, "REPORTS_DIR"):
            module.REPORTS_DIR = REPORTS_DIR
    return REPORTS_DIR


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build the round6p1 evidence package with explicit no-side-effect controls."
    )
    parser.add_argument(
        "--reports-dir",
        default=str(DEFAULT_REPORTS_DIR),
        help="Directory for generated report artifacts. Defaults to the project reports directory.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Probe configuration and print the planned outputs without running diagnostics or writing files.",
    )
    parser.add_argument(
        "--no-write",
        action="store_true",
        help="Run diagnostics when possible and print the validation summary without writing artifacts.",
    )
    parser.add_argument(
        "--force-overwrite",
        action="store_true",
        help="Allow backend-unavailable skipped reports to overwrite existing evidence artifacts.",
    )
    parser.add_argument("--library-path", default=None, help="Optional explicit T-matrix library path.")
    return parser


def _git_revision() -> str | None:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except Exception:
        return None
    revision = completed.stdout.strip()
    return revision or None


def _planned_output_paths() -> list[str]:
    return [
        str(path)
        for path in (
            ERROR_ATTRIBUTION_JSON,
            ERROR_ATTRIBUTION_MD,
            ABLATION_JSON,
            ABLATION_MD,
            FIT_SENSITIVITY_JSON,
            FIT_SENSITIVITY_MD,
            FIT_STRATEGY_ABLATION_JSON,
            FIT_STRATEGY_ABLATION_MD,
            COEFFICIENT_INJECTION_JSON,
            COEFFICIENT_INJECTION_MD,
            COEFFICIENT_MAP_AUDIT_JSON,
            COEFFICIENT_MAP_AUDIT_MD,
            COEFFICIENT_MAP_ABLATION_JSON,
            COEFFICIENT_MAP_ABLATION_MD,
            COEFFICIENT_MAP_STABILITY_JSON,
            COEFFICIENT_MAP_STABILITY_MD,
            SLICE_AXIS_CROSSCHECK_JSON,
            SLICE_AXIS_CROSSCHECK_MD,
            MEASUREMENT_PROTOCOL_JSON,
            MEASUREMENT_PROTOCOL_MD,
            PARTICLE_SIZE_SWEEP_JSON,
            PARTICLE_SIZE_SWEEP_MD,
            DEFAULT_BASIS_PROJECTION_REPORT_PATH,
            DEFAULT_BASIS_PROJECTION_REPORT_PATH.with_suffix(".md"),
            DEFAULT_COEFFICIENT_RECOVERY_REPORT_PATH,
            DEFAULT_COEFFICIENT_RECOVERY_REPORT_PATH.with_suffix(".md"),
            ROUND6P1_VALIDATION_JSON,
            ROUND6P1_FAILURE_SUMMARY,
        )
    ]


def _runtime_metadata(args: argparse.Namespace, backend_status: dict, argv: list[str]) -> dict:
    return {
        "builder": "build_round6p1_evidence_package",
        "timestamp_utc": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "command_line": [Path(sys.argv[0]).name, *argv],
        "reports_dir": str(REPORTS_DIR),
        "python_executable": sys.executable,
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
        "git_revision": _git_revision(),
        "dry_run": bool(args.dry_run),
        "no_write": bool(args.no_write),
        "force_overwrite": bool(args.force_overwrite),
        "library_path": args.library_path,
        "tmatrix_backend_status": backend_status,
    }


def _print_payload(payload: dict) -> None:
    print(json.dumps(payload, indent=2))


def _remove_legacy_generic_coefficient_bundles():
    legacy_case_names = [case_definition["name"] for case_definition in ROUND6P1_REPRESENTATIVE_CASES]
    for case_name in legacy_case_names:
        legacy_path = REPORTS_DIR / f"round6p1_{case_name}_coefficient_bundle.npz"
        if legacy_path.exists():
            legacy_path.unlink()


def _write_skipped_report(json_path: Path, md_path: Path, *, title: str, reason: str, backend_status: dict):
    payload = {
        "report_version_tag": "round6p1",
        "status": "skipped",
        "title": title,
        "reason": reason,
        "tmatrix_backend_status": backend_status,
    }
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(f"# {title}\n\nStatus: `skipped`\n\nReason: {reason}\n", encoding="utf-8")


def _write_backend_unavailable_package(reason: str, backend_status: dict):
    _write_skipped_report(
        DEFAULT_BASIS_PROJECTION_REPORT_PATH,
        DEFAULT_BASIS_PROJECTION_REPORT_PATH.with_suffix(".md"),
        title="Round 6p1 Basis Projection Diagnostics",
        reason=reason,
        backend_status=backend_status,
    )
    _write_skipped_report(
        DEFAULT_COEFFICIENT_RECOVERY_REPORT_PATH,
        DEFAULT_COEFFICIENT_RECOVERY_REPORT_PATH.with_suffix(".md"),
        title="Round 6p1 Basis Coefficient Recovery",
        reason=reason,
        backend_status=backend_status,
    )
    _write_skipped_report(
        ERROR_ATTRIBUTION_JSON,
        ERROR_ATTRIBUTION_MD,
        title="Round 6p1 Error Attribution",
        reason=reason,
        backend_status=backend_status,
    )
    _write_skipped_report(
        ABLATION_JSON,
        ABLATION_MD,
        title="Round 6p1 Ablation Results",
        reason=reason,
        backend_status=backend_status,
    )
    _write_skipped_report(
        FIT_SENSITIVITY_JSON,
        FIT_SENSITIVITY_MD,
        title="Round 6p1 Effective-Channel Fit Sensitivity",
        reason=reason,
        backend_status=backend_status,
    )
    _write_skipped_report(
        FIT_STRATEGY_ABLATION_JSON,
        FIT_STRATEGY_ABLATION_MD,
        title="Round 6p1 Effective-Channel Fit Strategy Ablation",
        reason=reason,
        backend_status=backend_status,
    )
    _write_skipped_report(
        COEFFICIENT_INJECTION_JSON,
        COEFFICIENT_INJECTION_MD,
        title="Round 6p1 Coefficient Injection Diagnostics",
        reason=reason,
        backend_status=backend_status,
    )
    _write_skipped_report(
        COEFFICIENT_MAP_AUDIT_JSON,
        COEFFICIENT_MAP_AUDIT_MD,
        title="Round 6p1 Coefficient Map Audit",
        reason=reason,
        backend_status=backend_status,
    )
    _write_skipped_report(
        COEFFICIENT_MAP_ABLATION_JSON,
        COEFFICIENT_MAP_ABLATION_MD,
        title="Round 6p1 Coefficient Map Ablation",
        reason=reason,
        backend_status=backend_status,
    )
    _write_skipped_report(
        COEFFICIENT_MAP_STABILITY_JSON,
        COEFFICIENT_MAP_STABILITY_MD,
        title="Round 6p1 Coefficient Map Stability",
        reason=reason,
        backend_status=backend_status,
    )
    _write_skipped_report(
        SLICE_AXIS_CROSSCHECK_JSON,
        SLICE_AXIS_CROSSCHECK_MD,
        title="Round 6p1 Lateral Slice Axis Crosscheck",
        reason=reason,
        backend_status=backend_status,
    )
    _write_skipped_report(
        MEASUREMENT_PROTOCOL_JSON,
        MEASUREMENT_PROTOCOL_MD,
        title="Round 6p1 Measurement Protocol Bias",
        reason=reason,
        backend_status=backend_status,
    )
    _write_skipped_report(
        PARTICLE_SIZE_SWEEP_JSON,
        PARTICLE_SIZE_SWEEP_MD,
        title="Round 6p1 Particle Size Sweep",
        reason=reason,
        backend_status=backend_status,
    )


def _load_script_module(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _resolve_script_path(*names: str) -> Path:
    for name in names:
        candidate = SCRIPTS_DIR / name
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"Unable to resolve any of: {', '.join(names)}")

def _run_case(case_definition: dict, *, mode: str, **solver_overrides):
    gc.collect()
    source = SourceConfig(**case_definition["source"])
    grid = GridConfig(**case_definition["grid"])
    solver_kwargs = dict(case_definition["solver"])
    solver_kwargs.update(solver_overrides)
    solver = SolverConfig(mode=mode, **solver_kwargs)
    return solve_oct_particle_response(source, grid, solver)


def _release_heavy_case_results():
    # The evidence builder intentionally runs many T-matrix-backed cases in a
    # single process. Collect between representative cases so backend/native
    # temporaries do not make later small NumPy allocations fail under tight
    # desktop memory conditions.
    gc.collect()


def _extract_row(result: dict, *, bridge_result: dict | None):
    axial = result["axial_intensity_metrics"]
    row = {
        "mode": result["mode"],
        "display_mode_label": result.get("display_mode_label"),
        "peakline_x_um": float(result["peakline_x_um"]),
        "peak_opd_um": float(axial["peak_opd_um"]),
        "centroid_opd_um": float(axial["centroid_opd_um"]),
        "fwhm_opd_um": float(axial["fwhm_opd_um"]),
        "psr_db": float(axial["psr_db"]),
        "sidelobe_energy_fraction": float(axial["sidelobe_energy_fraction"]),
        "raw_peak_intensity": float(result["raw_peak_intensity"]),
        "raw_peak_intensity_bridge": float(result["raw_peak_intensity"]) if bridge_result is None else float(bridge_result["raw_peak_intensity"]),
        "image_relative_l2_vs_bridge": 0.0,
        "peakline_x_delta_um_vs_bridge": 0.0,
        "centroid_opd_delta_um_vs_bridge": 0.0,
        "fwhm_delta_um_vs_bridge": 0.0,
        "psr_delta_db_vs_bridge": 0.0,
        "raw_image_relative_l2_vs_bridge": 0.0,
        "raw_peak_relative_delta_vs_bridge": 0.0,
    }
    if bridge_result is None:
        return row
    diagnostics = image_difference_diagnostics(
        f"{result['mode']}_vs_bridge",
        snapshot_for_comparison(result),
        snapshot_for_comparison(bridge_result),
    )
    row["image_relative_l2_vs_bridge"] = float(diagnostics["image_relative_l2"])
    row["peakline_x_delta_um_vs_bridge"] = float(diagnostics["peakline_x_delta_um"])
    row["centroid_opd_delta_um_vs_bridge"] = float(diagnostics["centroid_opd_delta_um"])
    row["fwhm_delta_um_vs_bridge"] = float(diagnostics["fwhm_delta_um"])
    row["psr_delta_db_vs_bridge"] = float(diagnostics["psr_delta_db"])
    row["raw_image_relative_l2_vs_bridge"] = float(diagnostics.get("raw_image_relative_l2", 0.0))
    row["raw_peak_relative_delta_vs_bridge"] = float(diagnostics.get("raw_peak_relative_delta", 0.0))
    return row


def _format_float(value: float):
    return f"{float(value):.6g}"


def _markdown_table(rows: list[dict], columns: list[tuple[str, str]]):
    header = "| " + " | ".join(label for _, label in columns) + " |"
    separator = "| " + " | ".join("---" for _ in columns) + " |"
    lines = [header, separator]
    for row in rows:
        values = []
        for key, _label in columns:
            value = row[key]
            if isinstance(value, float):
                values.append(_format_float(value))
            else:
                values.append(str(value))
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def build_error_attribution_package():
    package = {"cases": []}
    md_sections = ["# Round 6p1 Error Attribution", ""]
    columns = [
        ("mode", "mode"),
        ("peakline_x_um", "peakline_x_um"),
        ("peak_opd_um", "peak_opd_um"),
        ("centroid_opd_um", "centroid_opd_um"),
        ("fwhm_opd_um", "fwhm_opd_um"),
        ("psr_db", "psr_db"),
        ("sidelobe_energy_fraction", "sidelobe_energy_fraction"),
        ("raw_peak_intensity", "raw_peak_intensity"),
        ("image_relative_l2_vs_bridge", "image_relative_l2_vs_bridge"),
        ("peakline_x_delta_um_vs_bridge", "peakline_x_delta_um_vs_bridge"),
        ("raw_image_relative_l2_vs_bridge", "raw_image_relative_l2_vs_bridge"),
        ("raw_peak_relative_delta_vs_bridge", "raw_peak_relative_delta_vs_bridge"),
    ]
    for case_definition in ROUND6P1_REPRESENTATIVE_CASES:
        full_na = _run_case(case_definition, mode=FULL_NA_BASELINE_MODE)
        bridge = _run_case(case_definition, mode=VECTOR_BRIDGE_MODE)
        asymptotic = _run_case(case_definition, mode=LOW_NA_ASYMPTOTIC_MODE)
        asymptotic_diagnostics = image_difference_diagnostics(
            f"{LOW_NA_ASYMPTOTIC_MODE}_vs_bridge",
            snapshot_for_comparison(asymptotic),
            snapshot_for_comparison(bridge),
        )
        rows = [
            _extract_row(full_na, bridge_result=bridge),
            _extract_row(bridge, bridge_result=bridge),
            _extract_row(asymptotic, bridge_result=bridge),
        ]
        asymptotic_summary = classify_dominant_error_bucket(asymptotic_diagnostics)
        case_payload = {
            "name": case_definition["name"],
            "description": case_definition["description"],
            "rows": rows,
            "asymptotic_error_summary": asymptotic_summary,
        }
        package["cases"].append(case_payload)
        md_sections.extend(
            [
                f"## {case_definition['name']}",
                case_definition["description"],
                "",
                _markdown_table(rows, columns),
                "",
                f"Asymptotic dominant error bucket: `{asymptotic_summary['dominant_error_bucket']}` (severity {_format_float(asymptotic_summary['dominant_error_severity'])}).",
                "",
            ]
        )
        del full_na, bridge, asymptotic, asymptotic_diagnostics, rows, case_payload
        _release_heavy_case_results()
    return package, "\n".join(md_sections)


def build_ablation_package():
    package = {"cases": []}
    md_sections = ["# Round 6p1 A/B Experiments", ""]
    columns = [
        ("variant", "variant"),
        ("peakline_x_um", "peakline_x_um"),
        ("centroid_opd_um", "centroid_opd_um"),
        ("fwhm_opd_um", "fwhm_opd_um"),
        ("psr_db", "psr_db"),
        ("raw_peak_intensity", "raw_peak_intensity"),
        ("image_relative_l2_vs_bridge", "image_relative_l2_vs_bridge"),
        ("peakline_x_delta_um_vs_bridge", "peakline_x_delta_um_vs_bridge"),
        ("raw_image_relative_l2_vs_bridge", "raw_image_relative_l2_vs_bridge"),
        ("raw_peak_relative_delta_vs_bridge", "raw_peak_relative_delta_vs_bridge"),
    ]
    for case_definition in ROUND6P1_REPRESENTATIVE_CASES:
        bridge = _run_case(case_definition, mode=VECTOR_BRIDGE_MODE)
        tensor_closure = _run_case(case_definition, mode=LOW_NA_ASYMPTOTIC_MODE)
        slice_projected = _run_case(case_definition, mode=LOW_NA_ASYMPTOTIC_MODE, second_order_model="slice_projected")
        slice_projected_scaled = apply_complex_field_match_scale(slice_projected, bridge)
        directional_field_expansion = _run_case(
            case_definition,
            mode=LOW_NA_ASYMPTOTIC_MODE,
            second_order_model="directional_field_expansion",
        )
        directional_field_expansion_scaled = apply_complex_field_match_scale(directional_field_expansion, bridge)
        directional_field_expansion_first_order = _run_case(
            case_definition,
            mode=LOW_NA_ASYMPTOTIC_MODE,
            second_order_model="directional_field_expansion_first_order",
        )
        directional_field_expansion_first_order_scaled = apply_complex_field_match_scale(directional_field_expansion_first_order, bridge)
        endpoint_refit = _run_case(case_definition, mode=LOW_NA_ASYMPTOTIC_MODE, mu2_wavelength_model="endpoint_refit")
        first_order_shift = _run_case(case_definition, mode=LOW_NA_ASYMPTOTIC_MODE, lateral_shift_model="first_order")
        first_order_shift_coupled = _run_case(
            case_definition,
            mode=LOW_NA_ASYMPTOTIC_MODE,
            lateral_shift_model="first_order",
            lateral_shift_coupling="shift_envelope_and_mu2",
        )
        first_order_shift_coupled_analytic = _run_case(
            case_definition,
            mode=LOW_NA_ASYMPTOTIC_MODE,
            lateral_shift_model="first_order",
            lateral_shift_coupling="shift_envelope_and_mu2",
            lateral_shift_impl="analytic_gaussian",
        )
        first_order_shift_coupled_edge_hold = _run_case(
            case_definition,
            mode=LOW_NA_ASYMPTOTIC_MODE,
            lateral_shift_model="first_order",
            lateral_shift_coupling="shift_envelope_and_mu2",
            lateral_shift_impl="interp_edge_hold",
        )
        second_order_rows = []
        for variant_name, result in (
            ("tensor_closure", tensor_closure),
            ("slice_projected_raw", slice_projected),
            ("slice_projected_scaled", slice_projected_scaled),
            ("directional_field_expansion_raw", directional_field_expansion),
            ("directional_field_expansion_scaled", directional_field_expansion_scaled),
            ("directional_field_expansion_first_order_raw", directional_field_expansion_first_order),
            ("directional_field_expansion_first_order_scaled", directional_field_expansion_first_order_scaled),
        ):
            row = _extract_row(result, bridge_result=bridge)
            row["variant"] = variant_name
            second_order_rows.append(row)
        mu2_rows = []
        for variant_name, result in (
            ("frozen_at_lambda0", tensor_closure),
            ("endpoint_refit", endpoint_refit),
        ):
            row = _extract_row(result, bridge_result=bridge)
            row["variant"] = variant_name
            mu2_rows.append(row)
        lateral_shift_rows = []
        for variant_name, result in (
            ("none", tensor_closure),
            ("first_order_envelope_only_interp", first_order_shift),
            ("first_order_shift_envelope_and_mu2_interp", first_order_shift_coupled),
            ("first_order_shift_envelope_and_mu2_analytic_gaussian", first_order_shift_coupled_analytic),
            ("first_order_shift_envelope_and_mu2_interp_edge_hold", first_order_shift_coupled_edge_hold),
        ):
            row = _extract_row(result, bridge_result=bridge)
            row["variant"] = variant_name
            lateral_shift_rows.append(row)
        package["cases"].append(
            {
                "name": case_definition["name"],
                "description": case_definition["description"],
                "second_order_model": second_order_rows,
                "mu2_wavelength_model": mu2_rows,
                "lateral_shift_model": lateral_shift_rows,
            }
        )
        md_sections.extend(
            [
                f"## {case_definition['name']}",
                case_definition["description"],
                "",
                "### second_order_model",
                _markdown_table(second_order_rows, columns),
                "",
                "### mu2_wavelength_model",
                _markdown_table(mu2_rows, columns),
                "",
                "### lateral_shift_model",
                _markdown_table(lateral_shift_rows, columns),
                "",
            ]
        )
        del (
            bridge,
            tensor_closure,
            slice_projected,
            slice_projected_scaled,
            directional_field_expansion,
            directional_field_expansion_scaled,
            directional_field_expansion_first_order,
            directional_field_expansion_first_order_scaled,
            endpoint_refit,
            first_order_shift,
            first_order_shift_coupled,
            first_order_shift_coupled_analytic,
            first_order_shift_coupled_edge_hold,
            second_order_rows,
            mu2_rows,
            lateral_shift_rows,
        )
        _release_heavy_case_results()
    return package, "\n".join(md_sections)


def build_measurement_protocol_package():
    return build_measurement_protocol_package_core(
        representative_cases=ROUND6P1_REPRESENTATIVE_CASES,
        run_case=_run_case,
        compare_measurement_snapshots=compare_measurement_snapshots,
        full_na_mode=FULL_NA_BASELINE_MODE,
        low_na_mode=LOW_NA_BASELINE_MODE,
        asymptotic_mode=LOW_NA_ASYMPTOTIC_MODE,
        bridge_mode=VECTOR_BRIDGE_MODE,
    )


def build_particle_size_sweep_package():
    parser = _PARTICLE_SWEEP.build_arg_parser()
    args = parser.parse_args(
        [
            "--project-root",
            str(PROJECT_ROOT),
            "--output-dir",
            str(REPORTS_DIR / "round6p1_particle_size_sweep_artifacts"),
            "--diameters",
            "200,300,400,500,600,700,800,900,1000",
            "--mode",
            LOW_NA_BASELINE_MODE,
            "--particle-material",
            "TiO2-anatase",
            "--medium-material",
            "PDMS",
            "--n-lambda",
            "121",
            "--z-span-um",
            "20",
            "--n-z",
            "801",
            "--x-span-um",
            "6",
            "--n-x",
            "41",
            "--na",
            "0.05",
            "--no-plots",
        ]
    )
    return _PARTICLE_SWEEP.run_particle_size_sweep(
        args,
        solver=_SOLVER,
        write_artifacts=False,
        make_plots=False,
    )


def _measurement_protocol_summary_from_payload(payload: dict) -> dict:
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
    }


def main(argv: list[str] | None = None) -> int:
    argv_list = list(argv) if argv is not None else sys.argv[1:]
    args = build_arg_parser().parse_args(argv_list)
    configure_report_paths(args.reports_dir)

    backend_status = probe_tmatrix_backend(args.library_path)
    metadata = _runtime_metadata(args, backend_status, argv_list)
    if args.dry_run:
        _print_payload(
            {
                "status": "dry_run",
                "message": "No diagnostics were run and no files were written.",
                "evidence_builder_runtime_metadata": metadata,
                "planned_output_paths": _planned_output_paths(),
            }
        )
        return 0

    if not backend_status["available"]:
        reason = backend_status["reason"] or "T-matrix backend unavailable in the current runtime."
        if not args.force_overwrite:
            _print_payload(
                {
                    "status": "skipped_no_write",
                    "skip_reason": "tmatrix_backend_unavailable",
                    "reason": reason,
                    "message": "Backend unavailable; existing evidence artifacts were left untouched. Use --force-overwrite to write skipped reports.",
                    "evidence_builder_runtime_metadata": metadata,
                }
            )
            return 0
        if args.no_write:
            _print_payload(
                {
                    "status": "skipped_no_write",
                    "skip_reason": "tmatrix_backend_unavailable",
                    "reason": reason,
                    "message": "--no-write was requested, so skipped reports were not written.",
                    "evidence_builder_runtime_metadata": metadata,
                }
            )
            return 0
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        _write_backend_unavailable_package(reason, backend_status)
        report = validate()
        report["tmatrix_backend_status"] = backend_status
        report["evidence_builder_runtime_metadata"] = metadata
        ROUND6P1_VALIDATION_JSON.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        DEFAULT_JSON_REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        failure_summary = render_failure_summary(report)
        ROUND6P1_FAILURE_SUMMARY.write_text(failure_summary, encoding="utf-8")
        DEFAULT_FAILURE_SUMMARY_PATH.write_text(failure_summary, encoding="utf-8")
        return 0

    if not args.no_write:
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        _remove_legacy_generic_coefficient_bundles()
    error_package, error_markdown = build_error_attribution_package()
    if not args.no_write:
        ERROR_ATTRIBUTION_JSON.write_text(json.dumps(error_package, indent=2) + "\n", encoding="utf-8")
        ERROR_ATTRIBUTION_MD.write_text(error_markdown + "\n", encoding="utf-8")
    _release_heavy_case_results()

    ablation_package, ablation_markdown = build_ablation_package()
    if not args.no_write:
        ABLATION_JSON.write_text(json.dumps(ablation_package, indent=2) + "\n", encoding="utf-8")
        ABLATION_MD.write_text(ablation_markdown + "\n", encoding="utf-8")
    _release_heavy_case_results()

    measurement_package, measurement_markdown = build_measurement_protocol_package()
    if not args.no_write:
        MEASUREMENT_PROTOCOL_JSON.write_text(json.dumps(measurement_package, indent=2) + "\n", encoding="utf-8")
        MEASUREMENT_PROTOCOL_MD.write_text(measurement_markdown + "\n", encoding="utf-8")
        measurement_protocol_summary = _VALIDATOR.load_measurement_protocol_summary(MEASUREMENT_PROTOCOL_JSON)
    else:
        measurement_protocol_summary = _measurement_protocol_summary_from_payload(measurement_package)
    _release_heavy_case_results()

    particle_sweep_package, particle_sweep_markdown = build_particle_size_sweep_package()
    if not args.no_write:
        PARTICLE_SIZE_SWEEP_JSON.write_text(json.dumps(particle_sweep_package, indent=2) + "\n", encoding="utf-8")
        PARTICLE_SIZE_SWEEP_MD.write_text(particle_sweep_markdown + "\n", encoding="utf-8")
        particle_size_sweep_summary = _VALIDATOR.load_particle_size_sweep_summary(PARTICLE_SIZE_SWEEP_JSON)
    else:
        particle_size_sweep_summary = _VALIDATOR.load_particle_size_sweep_summary_from_payload(particle_sweep_package)
    _release_heavy_case_results()

    write_reports = not args.no_write
    basis_projection_summary = basis_projection_diagnostics.build_basis_projection_report(write_reports=write_reports, library_path=args.library_path)
    _release_heavy_case_results()
    coefficient_recovery_summary = coefficient_recovery_diagnostics.build_coefficient_recovery_report(write_reports=write_reports, library_path=args.library_path)
    _release_heavy_case_results()
    fit_sensitivity_summary = fit_sensitivity_diagnostics.build_fit_sensitivity_report(write_reports=write_reports, library_path=args.library_path)
    _release_heavy_case_results()
    coefficient_injection_summary = coefficient_injection_diagnostics.build_coefficient_injection_report(write_reports=write_reports, library_path=args.library_path)
    _release_heavy_case_results()
    _coefficient_map_audit_summary = coefficient_map_audit_diagnostics.build_coefficient_map_audit_report(write_reports=write_reports, library_path=args.library_path)
    _release_heavy_case_results()
    coefficient_map_ablation_summary = coefficient_map_ablation_diagnostics.build_coefficient_map_ablation_report(write_reports=write_reports, library_path=args.library_path)
    _release_heavy_case_results()
    coefficient_map_stability_summary = coefficient_map_stability_diagnostics.build_coefficient_map_stability_report(write_reports=write_reports, library_path=args.library_path)
    _release_heavy_case_results()
    fit_strategy_ablation_summary = fit_strategy_ablation_diagnostics.build_fit_strategy_ablation_report(write_reports=write_reports, library_path=args.library_path)
    _release_heavy_case_results()
    slice_axis_crosscheck_summary = slice_axis_crosscheck_diagnostics.build_slice_axis_crosscheck_report(write_reports=write_reports, library_path=args.library_path)
    _release_heavy_case_results()
    report = validate(
        basis_projection_summary=basis_projection_summary,
        coefficient_recovery_summary=coefficient_recovery_summary,
        fit_sensitivity_summary=fit_sensitivity_summary,
        coefficient_injection_summary=coefficient_injection_summary,
        coefficient_map_audit_summary=_coefficient_map_audit_summary,
        coefficient_map_ablation_summary=coefficient_map_ablation_summary,
        coefficient_map_stability_summary=coefficient_map_stability_summary,
        fit_strategy_ablation_summary=fit_strategy_ablation_summary,
        slice_axis_crosscheck_summary=slice_axis_crosscheck_summary,
        measurement_protocol_summary=measurement_protocol_summary,
        particle_size_sweep_summary=particle_size_sweep_summary,
    )
    report["evidence_builder_runtime_metadata"] = metadata
    if args.no_write:
        _print_payload(report)
        return 0
    ROUND6P1_VALIDATION_JSON.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    DEFAULT_JSON_REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    ROUND6P1_FAILURE_SUMMARY.write_text(render_failure_summary(report), encoding="utf-8")
    DEFAULT_FAILURE_SUMMARY_PATH.write_text(render_failure_summary(report), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
