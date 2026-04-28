from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
DEFAULT_REPORTS_DIR = PROJECT_ROOT / "reports"
DEFAULT_REBUILD_DIR_NAME = "round6p1_cp310_ci_rebuild"
MANIFEST_JSON_NAME = "round6p1_ci_evidence_import_manifest.json"
MANIFEST_MD_NAME = "round6p1_ci_evidence_import_manifest.md"
SUPPORTED_SUFFIXES = {".json", ".md", ".txt"}
SUPPORT_TOP_LEVEL_FILES = {
    "round6p1_cp310_evidence_rebuild_readiness.json",
    "round6p1_cp310_evidence_rebuild_readiness.md",
    "pytmatrix-diagnose.json",
    "pytmatrix-built-files.json",
    "particle_size_sweep_ci_backend_provenance.json",
}
RUN_ID_RE = re.compile(r"actions_run_(\d+)")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def infer_run_id(path: Path) -> str | None:
    for part in path.resolve().parts:
        match = RUN_ID_RE.search(part)
        if match:
            return match.group(1)
    return None


def find_rebuild_dir(artifact_dir: Path) -> Path:
    direct = artifact_dir / DEFAULT_REBUILD_DIR_NAME
    if direct.is_dir():
        return direct
    if (artifact_dir / "round6p1_validation_summary.json").exists():
        return artifact_dir
    candidates = [
        candidate
        for candidate in artifact_dir.rglob(DEFAULT_REBUILD_DIR_NAME)
        if candidate.is_dir()
    ]
    if len(candidates) == 1:
        return candidates[0]
    if not candidates:
        raise FileNotFoundError(
            f"Could not find {DEFAULT_REBUILD_DIR_NAME!r} under {artifact_dir}"
        )
    raise ValueError(
        f"Multiple {DEFAULT_REBUILD_DIR_NAME!r} directories found under {artifact_dir}: "
        + ", ".join(str(candidate) for candidate in candidates)
    )


def _is_supported_rebuild_file(path: Path, *, include_npz: bool) -> bool:
    if path.name in {MANIFEST_JSON_NAME, MANIFEST_MD_NAME}:
        return False
    if path.suffix.lower() in SUPPORTED_SUFFIXES:
        return True
    return include_npz and path.suffix.lower() == ".npz"


def iter_rebuild_files(rebuild_dir: Path, *, include_npz: bool = False) -> list[Path]:
    return sorted(
        path
        for path in rebuild_dir.rglob("*")
        if path.is_file() and _is_supported_rebuild_file(path, include_npz=include_npz)
    )


def iter_support_files(artifact_dir: Path) -> list[Path]:
    paths: list[Path] = []
    for name in sorted(SUPPORT_TOP_LEVEL_FILES):
        path = artifact_dir / name
        if path.is_file():
            paths.append(path)
    sweep_dir = artifact_dir / "particle_size_sweep_ci"
    if sweep_dir.is_dir():
        paths.extend(
            sorted(
                path
                for path in sweep_dir.rglob("*")
                if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES
            )
        )
    return paths


def _relative_to(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def build_import_plan(
    artifact_dir: Path,
    reports_dir: Path,
    *,
    include_npz: bool = False,
) -> dict:
    artifact_dir = artifact_dir.resolve()
    reports_dir = reports_dir.resolve()
    rebuild_dir = find_rebuild_dir(artifact_dir).resolve()
    run_id = infer_run_id(artifact_dir)
    planned_files: list[dict] = []

    for source in iter_rebuild_files(rebuild_dir, include_npz=include_npz):
        rel = source.relative_to(rebuild_dir).as_posix()
        planned_files.append(
            {
                "category": "cp310_rebuild_report",
                "source": str(source),
                "source_relative_path": f"{DEFAULT_REBUILD_DIR_NAME}/{rel}",
                "destination": str(reports_dir / rel),
                "destination_relative_path": rel,
            }
        )

    for source in iter_support_files(artifact_dir):
        rel = source.relative_to(artifact_dir).as_posix()
        planned_files.append(
            {
                "category": "ci_support_report",
                "source": str(source),
                "source_relative_path": rel,
                "destination": str(reports_dir / rel),
                "destination_relative_path": rel,
            }
        )

    return {
        "artifact_dir": str(artifact_dir),
        "rebuild_dir": str(rebuild_dir),
        "reports_dir": str(reports_dir),
        "source_run_id": run_id,
        "planned_files": planned_files,
    }


def _read_json_if_exists(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def stamp_validation_summary(
    summary_path: Path,
    *,
    manifest_path: Path,
    imported_at_utc: str,
    source_run_id: str | None,
    source_head_sha: str | None,
    source_artifact_dir: Path,
    copied_file_count: int,
) -> bool:
    if not summary_path.exists():
        return False
    summary = _read_json_if_exists(summary_path)
    summary.update(
        {
            "ci_evidence_import_status": "imported_from_github_actions_artifact",
            "ci_evidence_source_run_id": source_run_id,
            "ci_evidence_source_head_sha": source_head_sha,
            "ci_evidence_source_artifact_dir": str(source_artifact_dir),
            "ci_evidence_imported_at_utc": imported_at_utc,
            "ci_evidence_import_manifest_path": str(manifest_path),
            "ci_evidence_import_copied_file_count": copied_file_count,
        }
    )
    _write_json(summary_path, summary)
    return True


def render_manifest_markdown(manifest: dict) -> str:
    lines = [
        "# round6p1 CI Evidence Import Manifest",
        "",
        f"- import_status: `{manifest.get('import_status')}`",
        f"- source_run_id: `{manifest.get('source_run_id')}`",
        f"- source_head_sha: `{manifest.get('source_head_sha')}`",
        f"- source_artifact_dir: `{manifest.get('source_artifact_dir')}`",
        f"- source_rebuild_dir: `{manifest.get('source_rebuild_dir')}`",
        f"- copied_file_count: `{manifest.get('copied_file_count')}`",
        f"- skipped_existing_count: `{len(manifest.get('skipped_existing_files') or [])}`",
        "",
        "## Scope",
        "",
        "This manifest records a local import of CPython 3.10 + T-matrix evidence generated by GitHub Actions.",
        "It prevents source/report drift by attaching CI provenance and checksums to the canonical reports directory.",
        "",
        "## Copied Files",
        "",
    ]
    for item in manifest.get("copied_files", []):
        lines.append(
            f"- `{item.get('destination_relative_path')}` "
            f"({item.get('category')}, sha256 `{item.get('sha256')}`)"
        )
    return "\n".join(lines) + "\n"


def import_ci_evidence_artifacts(
    artifact_dir: Path,
    reports_dir: Path,
    *,
    dry_run: bool = False,
    overwrite: bool = True,
    include_npz: bool = False,
    source_run_id: str | None = None,
    source_head_sha: str | None = None,
) -> dict:
    plan = build_import_plan(artifact_dir, reports_dir, include_npz=include_npz)
    imported_at_utc = datetime.now(timezone.utc).isoformat()
    reports_dir = Path(plan["reports_dir"])
    copied: list[dict] = []
    skipped: list[dict] = []

    for item in plan["planned_files"]:
        source = Path(item["source"])
        destination = Path(item["destination"])
        if destination.exists() and not overwrite:
            skipped.append({**item, "reason": "destination_exists"})
            continue
        if not dry_run:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            item = {
                **item,
                "size_bytes": destination.stat().st_size,
                "sha256": sha256_file(destination),
            }
        else:
            item = {
                **item,
                "size_bytes": source.stat().st_size,
                "sha256": sha256_file(source),
            }
        copied.append(item)

    manifest_json = reports_dir / MANIFEST_JSON_NAME
    manifest_md = reports_dir / MANIFEST_MD_NAME
    effective_run_id = source_run_id or plan.get("source_run_id")
    stamped_files: list[str] = []

    if not dry_run:
        if stamp_validation_summary(
            reports_dir / "round6p1_validation_summary.json",
            manifest_path=manifest_json,
            imported_at_utc=imported_at_utc,
            source_run_id=effective_run_id,
            source_head_sha=source_head_sha,
            source_artifact_dir=Path(plan["artifact_dir"]),
            copied_file_count=len(copied),
        ):
            stamped_files.append("round6p1_validation_summary.json")
            for item in copied:
                if item["destination_relative_path"] == "round6p1_validation_summary.json":
                    destination = Path(item["destination"])
                    item["size_bytes"] = destination.stat().st_size
                    item["sha256"] = sha256_file(destination)

    manifest = {
        "report_kind": "round6p1_ci_evidence_import_manifest",
        "timestamp_utc": imported_at_utc,
        "import_status": "dry_run" if dry_run else "imported",
        "source_artifact_dir": plan["artifact_dir"],
        "source_rebuild_dir": plan["rebuild_dir"],
        "reports_dir": plan["reports_dir"],
        "source_run_id": effective_run_id,
        "source_head_sha": source_head_sha,
        "include_npz": include_npz,
        "overwrite": overwrite,
        "copied_file_count": len(copied),
        "copied_files": copied,
        "skipped_existing_files": skipped,
        "stamped_files": stamped_files,
        "manifest_json_path": str(manifest_json),
        "manifest_md_path": str(manifest_md),
    }
    if not dry_run:
        _write_json(manifest_json, manifest)
        manifest_md.write_text(render_manifest_markdown(manifest), encoding="utf-8")
    return manifest


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Import GitHub Actions CPython 3.10 T-matrix evidence artifacts into canonical reports.",
    )
    parser.add_argument("--artifact-dir", type=Path, required=True)
    parser.add_argument("--reports-dir", type=Path, default=DEFAULT_REPORTS_DIR)
    parser.add_argument("--source-run-id", default=None)
    parser.add_argument("--source-head-sha", default=None)
    parser.add_argument("--include-npz", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-overwrite", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    try:
        manifest = import_ci_evidence_artifacts(
            args.artifact_dir,
            args.reports_dir,
            dry_run=args.dry_run,
            overwrite=not args.no_overwrite,
            include_npz=args.include_npz,
            source_run_id=args.source_run_id,
            source_head_sha=args.source_head_sha,
        )
    except Exception as exc:
        print(f"ci_evidence_import_status=failed", file=sys.stderr)
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
