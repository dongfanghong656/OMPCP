from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
REPORTS_DIR = PROJECT_ROOT / "reports"

LEGACY_DEPTH_CONVENTION = "opd_conjugate_to_medium_effective_wavenumber"
CURRENT_DEPTH_CONVENTION = "geometric_roundtrip_conjugate_to_medium_effective_wavenumber"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Refresh round6p1 measurement-contract artifacts from existing numerical reports. "
            "This is an explicit bridge for runtimes that cannot load the vendored CPython 3.10 T-matrix backend."
        )
    )
    parser.add_argument("--reports-dir", default=str(REPORTS_DIR))
    parser.add_argument("--measurement-json", default=None)
    parser.add_argument("--measurement-md", default=None)
    parser.add_argument("--validation-json", default=None)
    parser.add_argument("--failure-summary-txt", default=None)
    parser.add_argument(
        "--no-write",
        action="store_true",
        help="Print the planned refresh result without writing artifacts.",
    )
    return parser


def _walk_and_refresh_depth_contract(obj: Any) -> int:
    refreshed = 0
    if isinstance(obj, dict):
        if obj.get("fd_oct_depth_convention") == LEGACY_DEPTH_CONVENTION:
            obj["fd_oct_depth_convention"] = CURRENT_DEPTH_CONVENTION
            obj["fd_oct_depth_contract_refresh_note"] = (
                "This value was refreshed from the legacy OPD label. Because the k axis is "
                "medium-effective, the numerical axis is geometric roundtrip distance; "
                "a full T-matrix evidence recompute is still required for fresh numerical evidence."
            )
            refreshed += 1
        if "extraction_plane_opd_um" in obj and "extraction_plane_geometric_roundtrip_um" not in obj:
            obj["extraction_plane_geometric_roundtrip_um"] = obj["extraction_plane_opd_um"]
            obj["extraction_plane_axis_note"] = (
                "extraction_plane_opd_um is retained as a legacy compatibility alias; "
                "for medium-effective k-space read extraction_plane_geometric_roundtrip_um."
            )
        for value in obj.values():
            refreshed += _walk_and_refresh_depth_contract(value)
    elif isinstance(obj, list):
        for value in obj:
            refreshed += _walk_and_refresh_depth_contract(value)
    return refreshed


def _count_current_depth_contract_rows(obj: Any) -> int:
    if isinstance(obj, dict):
        count = 1 if obj.get("fd_oct_depth_convention") == CURRENT_DEPTH_CONVENTION else 0
        return count + sum(_count_current_depth_contract_rows(value) for value in obj.values())
    if isinstance(obj, list):
        return sum(_count_current_depth_contract_rows(value) for value in obj)
    return 0


def refresh_measurement_payload(payload: dict[str, Any]) -> tuple[dict[str, Any], int]:
    refreshed = _walk_and_refresh_depth_contract(payload)
    current_count = _count_current_depth_contract_rows(payload)
    previous_status = payload.get("measurement_contract_refresh_status")
    previous_count = int(payload.get("measurement_contract_refreshed_row_count", 0) or 0)
    if refreshed:
        payload["measurement_contract_refresh_status"] = "depth_contract_label_refreshed_from_existing_numerical_evidence"
        payload["measurement_contract_refreshed_row_count"] = int(refreshed)
    elif previous_status == "depth_contract_label_refreshed_from_existing_numerical_evidence":
        payload["measurement_contract_refresh_status"] = previous_status
        payload["measurement_contract_refreshed_row_count"] = previous_count or current_count
    elif current_count:
        payload["measurement_contract_refresh_status"] = "depth_contract_already_current_from_existing_numerical_evidence"
        payload["measurement_contract_refreshed_row_count"] = current_count
    else:
        payload["measurement_contract_refresh_status"] = "already_current_or_no_fd_oct_depth_rows"
        payload["measurement_contract_refreshed_row_count"] = 0
    payload["measurement_contract_refresh_note"] = (
        "This artifact is source-contract synchronized without recomputing T-matrix cases. "
        "Use a compatible CPython 3.10 Windows backend to regenerate all numerical evidence."
    )
    payload["measurement_contract_refresh_requires_full_tmatrix_recompute"] = True
    return payload, int(payload["measurement_contract_refreshed_row_count"])


def refresh_measurement_markdown(text: str, refreshed_count: int) -> str:
    text = text.replace(LEGACY_DEPTH_CONVENTION, CURRENT_DEPTH_CONVENTION)
    note = (
        "\n\n## Measurement Contract Refresh Note\n\n"
        f"- refreshed_fd_oct_depth_rows = {refreshed_count}\n"
        "- status = depth_contract_label_refreshed_from_existing_numerical_evidence\n"
        "- note = Numerical values were not recomputed in this runtime; this synchronizes the "
        "medium-effective k-space depth-axis contract with the current source.\n"
    )
    if "## Measurement Contract Refresh Note" not in text:
        text = text.rstrip() + note
    return text


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    reports_dir = Path(args.reports_dir)
    measurement_json = Path(args.measurement_json) if args.measurement_json else reports_dir / "round6p1_measurement_protocol_bias.json"
    measurement_md = Path(args.measurement_md) if args.measurement_md else reports_dir / "round6p1_measurement_protocol_bias.md"
    validation_json = Path(args.validation_json) if args.validation_json else reports_dir / "round6p1_validation_summary.json"
    failure_summary_txt = (
        Path(args.failure_summary_txt)
        if args.failure_summary_txt
        else reports_dir / "round6p1_validation_failure_summary.txt"
    )

    payload = json.loads(measurement_json.read_text(encoding="utf-8"))
    payload, refreshed = refresh_measurement_payload(payload)

    result = {
        "measurement_json": str(measurement_json),
        "measurement_md": str(measurement_md),
        "validation_json": str(validation_json),
        "failure_summary_txt": str(failure_summary_txt),
        "refreshed_fd_oct_depth_rows": refreshed,
        "status": payload["measurement_contract_refresh_status"],
    }
    if args.no_write:
        print(json.dumps(result, indent=2))
        return 0

    measurement_json.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    if measurement_md.exists():
        measurement_md.write_text(
            refresh_measurement_markdown(measurement_md.read_text(encoding="utf-8"), refreshed) + "\n",
            encoding="utf-8",
        )

    import importlib.util

    validator_path = SCRIPT_DIR / "validate_oct_nonspherical_psf_solver.py"
    spec = importlib.util.spec_from_file_location("round6p1_validator_refresh", validator_path)
    validator = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(validator)

    if validation_json.exists():
        report = json.loads(validation_json.read_text(encoding="utf-8"))
    else:
        report = {}
    measurement_summary = validator.load_measurement_protocol_summary(measurement_json)
    report = validator.apply_measurement_protocol_summary(report, measurement_summary)
    cp310_readiness_json = reports_dir / "round6p1_cp310_evidence_rebuild_readiness.json"
    if cp310_readiness_json.exists():
        cp310_summary = validator.load_cp310_evidence_readiness_summary(cp310_readiness_json)
        report = validator.apply_cp310_evidence_readiness_summary(report, cp310_summary)
    report["measurement_artifact_freshness_status"] = "source_contract_refreshed_existing_numerical_evidence"
    report["measurement_artifact_freshness_note"] = (
        "Measurement depth-axis labels were refreshed to the current geometric-roundtrip contract. "
        "Numerical T-matrix evidence still needs a compatible CPython 3.10 Windows runtime for full regeneration."
    )
    report["measurement_contract_refreshed_row_count"] = int(refreshed)
    validation_payload = json.dumps(report, indent=2) + "\n"
    failure_summary = validator.render_failure_summary(report)
    try:
        validation_json.write_text(validation_payload, encoding="utf-8")
        failure_summary_txt.write_text(failure_summary, encoding="utf-8")
        result["validation_write_status"] = "canonical_artifacts_updated"
    except PermissionError as exc:
        refreshed_validation_json = validation_json.with_name(f"{validation_json.stem}.refreshed{validation_json.suffix}")
        refreshed_failure_summary_txt = failure_summary_txt.with_name(
            f"{failure_summary_txt.stem}.refreshed{failure_summary_txt.suffix}"
        )
        refreshed_validation_json.write_text(validation_payload, encoding="utf-8")
        refreshed_failure_summary_txt.write_text(failure_summary, encoding="utf-8")
        result["validation_write_status"] = "canonical_artifact_permission_denied_refreshed_sidecar_written"
        result["validation_write_error"] = str(exc)
        result["refreshed_validation_json"] = str(refreshed_validation_json)
        result["refreshed_failure_summary_txt"] = str(refreshed_failure_summary_txt)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
