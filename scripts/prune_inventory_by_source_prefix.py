#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

import extract_local_literature_corpus as ext


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prune inventory records whose source_path or basename matches configured rules.")
    parser.add_argument("--inventory", required=True)
    parser.add_argument("--source-prefix", action="append", default=[], help="Remove records whose source_path starts with this prefix.")
    parser.add_argument("--source-contains", action="append", default=[], help="Remove records whose source_path contains this text.")
    parser.add_argument("--basename-prefix", action="append", default=[], help="Remove records whose source filename starts with this prefix.")
    parser.add_argument("--archive-json", required=True, help="Write removed records and summary here.")
    args = parser.parse_args()
    if not args.source_prefix and not args.source_contains and not args.basename_prefix:
        parser.error("at least one of --source-prefix, --source-contains, or --basename-prefix is required")
    return args


def normalize_prefix(value: str) -> str:
    return value.replace("/", "\\").rstrip("\\") + "\\"


def load_inventory(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def split_records(records: list[dict], prefixes: list[str], source_contains: list[str], basename_prefixes: list[str]) -> tuple[list[dict], list[dict]]:
    kept: list[dict] = []
    removed: list[dict] = []
    for record in records:
        source_path = str(record.get("source_path") or "").replace("/", "\\")
        basename = Path(source_path).name
        if (
            any(source_path.startswith(prefix) for prefix in prefixes)
            or any(token in source_path for token in source_contains)
            or any(basename.startswith(prefix) for prefix in basename_prefixes)
        ):
            removed.append(record)
        else:
            kept.append(record)
    return kept, removed


def rebuild_summary(payload: dict) -> dict:
    records = payload["records"]
    by_extension = Counter(str(record.get("extension") or "") for record in records)
    by_status = Counter(str(record.get("status") or "") for record in records)
    return {
        **payload.get("summary", {}),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "candidate_total": len(records),
        "extracted_total": by_status.get("extracted", 0),
        "skipped_total": by_status.get("skipped-existing", 0),
        "failed_total": by_status.get("failed", 0),
        "by_extension": dict(sorted(by_extension.items())),
        "by_status": dict(sorted(by_status.items())),
    }


def write_inventory(inventory_path: Path, payload: dict) -> None:
    records = [ext.ExtractRecord(**record) for record in payload["records"]]
    ext.write_utf8_text(inventory_path, json.dumps(payload, ensure_ascii=False, indent=2))
    ext.write_utf8_text(inventory_path.with_suffix(".md"), ext.render_inventory_markdown(payload["summary"], records))


def build_archive_payload(inventory_path: Path, prefixes: list[str], source_contains: list[str], basename_prefixes: list[str], removed: list[dict]) -> dict:
    by_status = Counter(str(record.get("status") or "") for record in removed)
    by_extension = Counter(str(record.get("extension") or "") for record in removed)
    return {
        "summary": {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "inventory": inventory_path.as_posix(),
            "removed_total": len(removed),
            "source_prefixes": prefixes,
            "source_contains": source_contains,
            "basename_prefixes": basename_prefixes,
            "by_status": dict(sorted(by_status.items())),
            "by_extension": dict(sorted(by_extension.items())),
        },
        "records": removed,
    }


def main() -> None:
    args = parse_args()
    inventory_path = Path(args.inventory)
    prefixes = [normalize_prefix(value) for value in args.source_prefix]
    source_contains = [value.replace("/", "\\") for value in args.source_contains]
    basename_prefixes = list(args.basename_prefix)
    payload = load_inventory(inventory_path)
    records = payload.get("records", [])
    kept, removed = split_records(records, prefixes, source_contains, basename_prefixes)
    payload["records"] = kept
    payload["summary"] = rebuild_summary(payload)
    write_inventory(inventory_path, payload)

    archive_payload = build_archive_payload(inventory_path, prefixes, source_contains, basename_prefixes, removed)
    archive_path = Path(args.archive_json)
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    archive_path.write_text(json.dumps(archive_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(
        json.dumps(
            {
                "inventory": inventory_path.as_posix(),
                "removed_total": len(removed),
                "kept_total": len(kept),
                "source_prefixes": prefixes,
                "source_contains": source_contains,
                "basename_prefixes": basename_prefixes,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
