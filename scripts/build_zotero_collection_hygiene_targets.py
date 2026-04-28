#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import build_zotero_tag_hygiene_targets as tag_hygiene
import discovery_to_zotero as discovery
import local_pdf_to_zotero as local_pdf
import zotero_to_vault
from path_naming import safe_slug


@dataclass
class CollectionRecord:
    item_key: str
    title: str
    collection_paths: list[str]


def normalize_collection_path_list(value: Any) -> list[str]:
    paths: list[str] = []
    for path in local_pdf.parse_string_list(value):
        normalized = local_pdf.normalize_collection_path(path)
        if normalized:
            discovery.unique_append(paths, normalized)
    return paths


def clean_collection_paths(paths: list[str], remove_paths: list[str]) -> list[str]:
    removed = {local_pdf.normalize_collection_path(path) for path in remove_paths if local_pdf.normalize_collection_path(path)}
    cleaned: list[str] = []
    seen: set[str] = set()
    for path in paths:
        normalized = local_pdf.normalize_collection_path(path)
        if not normalized or normalized in removed or normalized in seen:
            continue
        seen.add(normalized)
        cleaned.append(normalized)
    return cleaned


def current_collection_paths(item: dict[str, Any], collection_map: dict[str, str]) -> list[str]:
    paths: list[str] = []
    for key in item.get("collections", []):
        normalized_key = tag_hygiene.normalize_text(key)
        if not normalized_key:
            continue
        path = local_pdf.normalize_collection_path(collection_map.get(normalized_key, normalized_key))
        if path:
            discovery.unique_append(paths, path)
    return paths


def prepare_record(
    item_key: str,
    title: str,
    collection_paths: list[str],
    remove_paths: list[str],
) -> tuple[CollectionRecord, list[str]]:
    cleaned = clean_collection_paths(collection_paths, remove_paths)
    removed = [path for path in collection_paths if local_pdf.normalize_collection_path(path) not in set(cleaned)]
    return CollectionRecord(item_key=item_key, title=title, collection_paths=cleaned), removed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build a zotero_curate collection-hygiene target file from the current vault paper notes."
    )
    parser.add_argument("--config", required=True)
    parser.add_argument("--output-file", default="")
    parser.add_argument("--run-label", default="build-zotero-collection-hygiene-targets")
    parser.add_argument("--output-root", default="")
    parser.add_argument("--remove-collections", default="Local PDF Imports,111111111")
    parser.add_argument("--max-collections", type=int, default=2000)
    return parser


def write_run_report(
    path: Path,
    run_id: str,
    records: list[CollectionRecord],
    removed_summary: dict[str, int],
) -> None:
    lines = [
        "# Build Zotero Collection Hygiene Targets",
        "",
        f"- Run ID: `{run_id}`",
        f"- Generated: `{datetime.now().isoformat(timespec='seconds')}`",
        f"- Targets: {len(records)}",
        "",
        "## Removed Collection Summary",
        "",
    ]
    if removed_summary:
        for collection_path, count in sorted(removed_summary.items(), key=lambda item: (-item[1], item[0])):
            lines.append(f"- {collection_path}: {count}")
    else:
        lines.append("- None")
    lines.extend(["", "## Items", ""])
    for record in records:
        collections = ", ".join(record.collection_paths) if record.collection_paths else "none"
        lines.append(f"- {record.title} | `{record.item_key}` | collections: {collections}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    config = discovery.load_json(Path(args.config))
    remove_paths = normalize_collection_path_list(args.remove_collections)
    output_root = tag_hygiene.resolve_output_root(config, args.output_root)
    run_id = f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{safe_slug(args.run_label)}"
    run_dir = output_root / "zotero-curation" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    collection_map = zotero_to_vault.fetch_remote_collection_path_map(config, max_items=args.max_collections)
    targets = tag_hygiene.collect_note_targets(Path(config["vault_root"]))

    records: list[CollectionRecord] = []
    removed_counter: Counter[str] = Counter()
    for target in targets:
        item = tag_hygiene.fetch_item(config, target.zotero_key)
        paths = current_collection_paths(item, collection_map)
        record, removed_paths = prepare_record(
            target.zotero_key,
            tag_hygiene.normalize_text(item.get("title", "")) or target.title,
            paths,
            remove_paths,
        )
        for removed_path in removed_paths:
            removed_counter[local_pdf.normalize_collection_path(removed_path)] += 1
        records.append(record)

    payload = {
        "defaults": {
            "preserve_existing_tags": True,
            "preserve_existing_collections": False,
            "remove_collection_paths": remove_paths,
        },
        "items": [
            {
                "item_key": record.item_key,
                "title": record.title,
                "collection_paths": record.collection_paths,
            }
            for record in records
        ],
    }

    output_file = Path(args.output_file) if args.output_file else run_dir / "zotero-collection-hygiene-targets.json"
    output_file.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    backfill_payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "run_id": f"{run_id}-backfill",
        "mode": "write-zotero",
        "candidates": [
            {
                "pdf_path": target.pdf_path,
                "relative_path": Path(target.pdf_path).name if target.pdf_path else "",
                "file_name": Path(target.pdf_path).name if target.pdf_path else "",
                "title": record.title,
                "zotero_parent_key": record.item_key,
            }
            for target, record in zip(targets, records)
            if target.pdf_path
        ],
    }
    backfill_run_json = run_dir / "zotero-backfill-run.json"
    backfill_run_json.write_text(json.dumps(backfill_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    run_json = {
        "run_id": run_id,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "output_file": str(output_file),
        "backfill_run_json": str(backfill_run_json),
        "targets": len(records),
        "removed_collection_summary": dict(removed_counter),
    }
    (run_dir / "run.json").write_text(json.dumps(run_json, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_run_report(run_dir / "run.md", run_id, records, dict(removed_counter))
    print(str(output_file))
    print(str(run_dir / "run.md"))


if __name__ == "__main__":
    main()
