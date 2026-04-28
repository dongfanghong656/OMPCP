#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import shutil
import zipfile
from pathlib import Path, PurePosixPath

import build_conversation_raw_source_registry as registrymod
import import_chatgpt_backup_to_vault as backupmod


ARCHIVE_FOLDER_NAME = "对话归档"
RAW_ZIP_FOLDER_NAME = "原始压缩包"
BY_AI_FOLDER_NAME = "按AI分类"
REDUNDANT_FOLDER_NAME = "冗余原档"
MANIFEST_NAME = "_archive-move-manifest.json"
RECLASSIFY_MANIFEST_NAME = "_archive-reclassify-manifest.json"


def sanitize_ai_folder(ai_type: str) -> str:
    return backupmod.sanitize_filename(ai_type.replace(":", " - "), max_length=80) or "Unknown"


def ensure_unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    index = 2
    while True:
        candidate = path.with_name(f"{stem} ({index}){suffix}")
        if not candidate.exists():
            return candidate
        index += 1


def ensure_unique_dir(path: Path) -> Path:
    if not path.exists():
        return path
    index = 2
    while True:
        candidate = path.with_name(f"{path.name} ({index})")
        if not candidate.exists():
            return candidate
        index += 1


def safe_member_path(member_name: str) -> Path | None:
    normalized = member_name.replace("\\", "/").strip("/")
    if not normalized:
        return None
    pure = PurePosixPath(normalized)
    if pure.is_absolute() or ".." in pure.parts:
        return None
    return Path(*pure.parts)


def bundle_folder_name(source_name: str) -> str:
    return backupmod.sanitize_filename(Path(source_name).stem, max_length=80) or "archive"


def provider_bundle_dir(archive_root: Path, provider: str, source_name: str) -> Path:
    return archive_root / BY_AI_FOLDER_NAME / sanitize_ai_folder(provider) / bundle_folder_name(source_name)


def extract_zip_safely(source: Path, target_dir: Path) -> dict[str, int]:
    extracted_files = 0
    skipped_entries = 0
    target_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(source) as archive:
        for info in archive.infolist():
            relative = safe_member_path(info.filename)
            if relative is None:
                skipped_entries += 1
                continue
            destination = target_dir / relative
            if info.is_dir():
                destination.mkdir(parents=True, exist_ok=True)
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info, "r") as src, destination.open("wb") as dst:
                shutil.copyfileobj(src, dst)
            extracted_files += 1
    return {"extracted_files": extracted_files, "skipped_entries": skipped_entries}


def extract_zip_to_member_destinations(source: Path, member_destinations: dict[str, Path]) -> dict[str, int]:
    extracted_files = 0
    skipped_entries = 0
    with zipfile.ZipFile(source) as archive:
        for info in archive.infolist():
            relative = safe_member_path(info.filename)
            if relative is None:
                skipped_entries += 1
                continue
            key = backupmod.make_forward_slashes(PurePosixPath(info.filename.replace("\\", "/")))
            destination = member_destinations.get(key)
            if destination is None:
                skipped_entries += 1
                continue
            if info.is_dir():
                destination.mkdir(parents=True, exist_ok=True)
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info, "r") as src, destination.open("wb") as dst:
                shutil.copyfileobj(src, dst)
            extracted_files += 1
    return {"extracted_files": extracted_files, "skipped_entries": skipped_entries}


def build_zip_extract_plan(profile: registrymod.SourceProfile, archive_root: Path) -> dict:
    unique_providers = sorted({record.provider or "Unknown" for record in profile.records})
    provider_roots = {
        provider: provider_bundle_dir(archive_root, provider, profile.path.name) for provider in unique_providers
    }
    member_plans: list[dict[str, str]] = []
    for record in profile.records:
        relative = safe_member_path(record.source_entry)
        if relative is None:
            continue
        member_plans.append(
            {
                "entry": backupmod.make_forward_slashes(PurePosixPath(record.source_entry.replace("\\", "/"))),
                "provider": record.provider or "Unknown",
                "relative_path": backupmod.make_forward_slashes(relative),
            }
        )

    if not member_plans or len(unique_providers) <= 1:
        provider = unique_providers[0] if unique_providers else profile.ai_type
        return {
            "mode": "single-target",
            "providers": [provider],
            "provider_bundle_roots": {provider: backupmod.make_forward_slashes(provider_roots.get(provider) or provider_bundle_dir(archive_root, provider, profile.path.name))},
            "member_plans": [],
        }

    return {
        "mode": "per-provider-members",
        "providers": unique_providers,
        "provider_bundle_roots": {
            provider: backupmod.make_forward_slashes(path) for provider, path in provider_roots.items()
        },
        "member_plans": member_plans,
    }


def collect_zip_profiles(scan_dir: Path) -> tuple[list[registrymod.SourceProfile], dict]:
    profiles = registrymod.collect_source_profiles(scan_dir, {})
    if not profiles:
        raise SystemExit(f"No supported conversation source files found in: {scan_dir}")
    payload = registrymod.build_registry(profiles, scan_dir)
    return profiles, payload


def build_operation_plan(scan_dir: Path, archive_root: Path) -> dict:
    profiles, payload = collect_zip_profiles(scan_dir)
    profile_by_path = {backupmod.make_forward_slashes(item.path): item for item in profiles}
    zip_extract_plans = {
        row["path"]: build_zip_extract_plan(profile_by_path[row["path"]], archive_root)
        for row in payload["canonical_sources"]
        if row["extension"] == ".zip"
    }

    operations: list[dict] = []
    for row in payload["all_sources"]:
        source_path = Path(row["path"])
        status = row["status"]
        ai_type = row["ai_type"]
        if row["extension"] == ".zip":
            raw_zip_target = archive_root / RAW_ZIP_FOLDER_NAME / source_path.name
            extract_plan = None
            if status == "canonical":
                extract_plan = zip_extract_plans.get(row["path"])
            elif row["final_target"] in zip_extract_plans:
                extract_plan = zip_extract_plans[row["final_target"]]
            operations.append(
                {
                    "source": backupmod.make_forward_slashes(source_path),
                    "status": status,
                    "ai_type": ai_type,
                    "is_zip": True,
                    "move_target": backupmod.make_forward_slashes(raw_zip_target),
                    "extract_mode": extract_plan["mode"] if extract_plan else None,
                    "extract_providers": extract_plan["providers"] if extract_plan else [],
                    "provider_bundle_roots": extract_plan["provider_bundle_roots"] if extract_plan else {},
                    "member_plans": extract_plan["member_plans"] if (extract_plan and status == "canonical") else [],
                }
            )
            continue

        destination_root = archive_root / BY_AI_FOLDER_NAME / sanitize_ai_folder(ai_type)
        if status != "canonical":
            destination_root = destination_root / REDUNDANT_FOLDER_NAME
        move_target = destination_root / source_path.name
        operations.append(
            {
                "source": backupmod.make_forward_slashes(source_path),
                "status": status,
                "ai_type": ai_type,
                "is_zip": False,
                "move_target": backupmod.make_forward_slashes(move_target),
                "extract_mode": None,
                "extract_providers": [],
                "provider_bundle_roots": {},
                "member_plans": [],
            }
        )

    return {
        "generated_at": backupmod.current_display_timestamp(),
        "scan_dir": backupmod.make_forward_slashes(scan_dir),
        "archive_root": backupmod.make_forward_slashes(archive_root),
        "registry_summary": {
            "raw_source_count": payload["raw_source_count"],
            "canonical_source_count": payload["canonical_source_count"],
            "exact_duplicate_group_count": payload["exact_duplicate_group_count"],
            "covered_file_count": payload["covered_file_count"],
        },
        "operations": operations,
    }


def execute_operation_plan(plan: dict, dry_run: bool) -> dict:
    archive_root = Path(plan["archive_root"])
    executed: list[dict] = []
    moved_count = 0
    extracted_count = 0

    if not dry_run:
        (archive_root / RAW_ZIP_FOLDER_NAME).mkdir(parents=True, exist_ok=True)
        (archive_root / BY_AI_FOLDER_NAME).mkdir(parents=True, exist_ok=True)

    for operation in plan["operations"]:
        source = Path(operation["source"])
        if not source.exists():
            executed.append({**operation, "result": "missing_source"})
            continue

        current = dict(operation)
        if operation["is_zip"] and operation["status"] == "canonical" and operation["extract_mode"]:
            if not dry_run:
                if operation["extract_mode"] == "single-target":
                    provider, root_str = next(iter(operation["provider_bundle_roots"].items()))
                    bundle_root = ensure_unique_dir(Path(root_str))
                    extract_result = extract_zip_safely(source, bundle_root)
                    current["provider_bundle_roots"] = {provider: backupmod.make_forward_slashes(bundle_root)}
                    current.update(extract_result)
                else:
                    allocated_roots: dict[str, Path] = {}
                    for provider, root_str in operation["provider_bundle_roots"].items():
                        allocated_roots[provider] = ensure_unique_dir(Path(root_str))
                        allocated_roots[provider].mkdir(parents=True, exist_ok=True)
                    member_destinations: dict[str, Path] = {}
                    for item in operation["member_plans"]:
                        relative = Path(*PurePosixPath(item["relative_path"]).parts)
                        member_destinations[item["entry"]] = allocated_roots[item["provider"]] / relative
                    extract_result = extract_zip_to_member_destinations(source, member_destinations)
                    current["provider_bundle_roots"] = {
                        provider: backupmod.make_forward_slashes(path) for provider, path in allocated_roots.items()
                    }
                    current.update(extract_result)
            extracted_count += 1

        move_target = Path(operation["move_target"])
        if not dry_run:
            move_target.parent.mkdir(parents=True, exist_ok=True)
            move_target = ensure_unique_path(move_target)
            shutil.move(str(source), str(move_target))
            current["move_target"] = backupmod.make_forward_slashes(move_target)
        moved_count += 1
        current["result"] = "planned" if dry_run else "moved"
        executed.append(current)

    return {
        **plan,
        "dry_run": dry_run,
        "moved_count": moved_count,
        "extracted_archive_count": extracted_count,
        "operations": executed,
    }


def rebuild_classification_from_raw_zips(archive_root: Path, dry_run: bool) -> dict:
    raw_zip_root = archive_root / RAW_ZIP_FOLDER_NAME
    if not raw_zip_root.is_dir():
        raise SystemExit(f"Raw zip folder not found: {raw_zip_root}")

    profiles, payload = collect_zip_profiles(raw_zip_root)
    by_ai_root = archive_root / BY_AI_FOLDER_NAME
    profile_by_path = {backupmod.make_forward_slashes(item.path): item for item in profiles}
    canonical_profiles = [
        profile_by_path[row["path"]] for row in payload["canonical_sources"] if row["extension"] == ".zip"
    ]

    bundle_names = {bundle_folder_name(profile.path.name) for profile in profiles if profile.extension == ".zip"}
    removed_dirs: list[str] = []
    if by_ai_root.exists():
        for ai_dir in by_ai_root.iterdir():
            if not ai_dir.is_dir():
                continue
            for bundle_name in bundle_names:
                candidate = ai_dir / bundle_name
                if candidate.is_dir():
                    removed_dirs.append(backupmod.make_forward_slashes(candidate))
                    if not dry_run:
                        shutil.rmtree(candidate)
            if not dry_run and ai_dir.exists() and not any(ai_dir.iterdir()):
                ai_dir.rmdir()

    operations: list[dict] = []
    if not dry_run:
        by_ai_root.mkdir(parents=True, exist_ok=True)

    for profile in canonical_profiles:
        extract_plan = build_zip_extract_plan(profile, archive_root)
        operation = {
            "source_zip": backupmod.make_forward_slashes(profile.path),
            "extract_mode": extract_plan["mode"],
            "providers": extract_plan["providers"],
            "provider_bundle_roots": extract_plan["provider_bundle_roots"],
            "result": "planned" if dry_run else "re-extracted",
        }
        if not dry_run:
            if extract_plan["mode"] == "single-target":
                provider, root_str = next(iter(extract_plan["provider_bundle_roots"].items()))
                bundle_root = ensure_unique_dir(Path(root_str))
                operation["provider_bundle_roots"] = {provider: backupmod.make_forward_slashes(bundle_root)}
                operation.update(extract_zip_safely(profile.path, bundle_root))
            else:
                allocated_roots: dict[str, Path] = {}
                for provider, root_str in extract_plan["provider_bundle_roots"].items():
                    allocated_roots[provider] = ensure_unique_dir(Path(root_str))
                    allocated_roots[provider].mkdir(parents=True, exist_ok=True)
                member_destinations: dict[str, Path] = {}
                for item in extract_plan["member_plans"]:
                    relative = Path(*PurePosixPath(item["relative_path"]).parts)
                    member_destinations[item["entry"]] = allocated_roots[item["provider"]] / relative
                operation["provider_bundle_roots"] = {
                    provider: backupmod.make_forward_slashes(path) for provider, path in allocated_roots.items()
                }
                operation.update(extract_zip_to_member_destinations(profile.path, member_destinations))
        operations.append(operation)

    return {
        "generated_at": backupmod.current_display_timestamp(),
        "archive_root": backupmod.make_forward_slashes(archive_root),
        "dry_run": dry_run,
        "raw_zip_count": sum(1 for profile in profiles if profile.extension == ".zip"),
        "canonical_zip_count": len(canonical_profiles),
        "removed_bundle_dir_count": len(removed_dirs),
        "removed_bundle_dirs": removed_dirs,
        "reclassified_archives": operations,
    }


def write_manifest(plan_result: dict, manifest_path: Path | None, dry_run: bool) -> Path | None:
    if dry_run or manifest_path is None:
        return None
    manifest_path.write_text(json.dumps(plan_result, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Organize conversation source files from Downloads into a dedicated archive folder."
    )
    parser.add_argument("--scan-dir", help="Directory to scan. Defaults to the user's Downloads folder.")
    parser.add_argument("--archive-root", help="Target archive root. Defaults to <scan-dir>/对话归档.")
    parser.add_argument("--dry-run", action="store_true", help="Only print the planned moves and extractions.")
    parser.add_argument(
        "--reclassify-existing-archive",
        action="store_true",
        help="Rebuild extracted archive folders from 原始压缩包 using the actual provider of each inner conversation file.",
    )
    args = parser.parse_args()

    scan_dir = Path(args.scan_dir).resolve() if args.scan_dir else Path.home() / "Downloads"
    if not scan_dir.is_dir():
        raise SystemExit(f"Scan directory not found: {scan_dir}")
    archive_root = Path(args.archive_root).resolve() if args.archive_root else scan_dir / ARCHIVE_FOLDER_NAME

    if args.reclassify_existing_archive:
        result = rebuild_classification_from_raw_zips(archive_root, dry_run=args.dry_run)
        manifest_path = write_manifest(result, archive_root / RECLASSIFY_MANIFEST_NAME, args.dry_run)
        output = {
            "archive_root": result["archive_root"],
            "dry_run": result["dry_run"],
            "raw_zip_count": result["raw_zip_count"],
            "canonical_zip_count": result["canonical_zip_count"],
            "removed_bundle_dir_count": result["removed_bundle_dir_count"],
            "reclassified_archive_count": len(result["reclassified_archives"]),
            "manifest_path": backupmod.make_forward_slashes(manifest_path) if manifest_path else None,
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return

    plan = build_operation_plan(scan_dir, archive_root)
    result = execute_operation_plan(plan, dry_run=args.dry_run)
    manifest_path = write_manifest(result, archive_root / MANIFEST_NAME, args.dry_run)

    output = {
        "scan_dir": result["scan_dir"],
        "archive_root": result["archive_root"],
        "dry_run": result["dry_run"],
        "raw_source_count": result["registry_summary"]["raw_source_count"],
        "canonical_source_count": result["registry_summary"]["canonical_source_count"],
        "exact_duplicate_group_count": result["registry_summary"]["exact_duplicate_group_count"],
        "covered_file_count": result["registry_summary"]["covered_file_count"],
        "moved_count": result["moved_count"],
        "extracted_archive_count": result["extracted_archive_count"],
        "manifest_path": backupmod.make_forward_slashes(manifest_path) if manifest_path else None,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
