#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

import extract_local_literature_corpus as ext


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Retry failed OneDrive-backed literature extracts with improved placeholder handling.")
    parser.add_argument("--inventory", action="append", required=True, help="Path to an inventory.json file.")
    parser.add_argument("--source-contains", default="", help="Retry only records whose source_path contains this text.")
    parser.add_argument("--limit", type=int, default=0, help="Optional max number of records to retry per inventory.")
    parser.add_argument("--report-json", default="", help="Optional output report path.")
    return parser.parse_args()


def load_inventory(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def should_retry(record: dict, source_contains: str) -> bool:
    if str(record.get("status") or "") != "failed":
        return False
    source_path = str(record.get("source_path") or "")
    if "OneDrive" not in source_path:
        return False
    if source_contains and source_contains not in source_path:
        return False
    if source_contains:
        return True
    message = str(record.get("message") or "")
    return (
        message == "[Errno 22] Invalid argument"
        or "OneDrive placeholder unavailable" in message
        or "Unable to decode text file: [Errno 22] Invalid argument" in message
        or "Unable to decode text file: OneDrive placeholder unavailable" in message
    )


def update_record_after_extract(record: dict, body: str, extractor: str, page_count: int) -> None:
    source_path = Path(str(record["source_path"]))
    record["size_bytes"] = source_path.stat().st_size
    record["modified_at"] = datetime.fromtimestamp(source_path.stat().st_mtime).isoformat(timespec="seconds")
    record["extractor"] = extractor
    record["status"] = "extracted"
    record["char_count"] = len(body)
    record["page_count"] = page_count
    record["title"] = ext.best_effort_title(body, source_path.stem)
    record["message"] = ""

    extract_path = Path(str(record["extract_path"]))
    extract_path.parent.mkdir(parents=True, exist_ok=True)
    extract_record = ext.ExtractRecord(**record)
    ext.write_utf8_text(extract_path, ext.build_extract_markdown(extract_record, body))


def write_inventory(path: Path, payload: dict) -> None:
    records = [ext.ExtractRecord(**record) for record in payload["records"]]
    summary = payload["summary"]
    ext.write_utf8_text(path, json.dumps(payload, ensure_ascii=False, indent=2))
    ext.write_utf8_text(path.with_suffix(".md"), ext.render_inventory_markdown(summary, records))


def rebuild_summary(payload: dict) -> None:
    records = payload["records"]
    by_extension = Counter(str(record.get("extension") or "") for record in records)
    by_status = Counter(str(record.get("status") or "") for record in records)
    payload["summary"] = {
        **payload.get("summary", {}),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "candidate_total": len(records),
        "extracted_total": by_status.get("extracted", 0),
        "skipped_total": by_status.get("skipped-existing", 0),
        "failed_total": by_status.get("failed", 0),
        "by_extension": dict(sorted(by_extension.items())),
        "by_status": dict(sorted(by_status.items())),
    }


def retry_inventory(path: Path, source_contains: str, limit: int) -> dict:
    payload = load_inventory(path)
    records = payload.get("records", [])
    retried = rescued = still_failed = 0
    updated_examples: list[dict] = []

    for record in records:
        if not should_retry(record, source_contains):
            continue
        if limit and retried >= limit:
            break
        retried += 1
        source_path = Path(str(record["source_path"]))
        try:
            body, extractor, page_count = ext.extract_source(source_path)
            body = ext.sanitize_text(body)
            update_record_after_extract(record, body, extractor, page_count)
            rescued += 1
            if len(updated_examples) < 10:
                updated_examples.append(
                    {
                        "status": "rescued",
                        "source_path": str(source_path),
                        "extractor": extractor,
                        "char_count": len(body),
                    }
                )
        except Exception as exc:  # noqa: BLE001
            record["message"] = str(exc)
            still_failed += 1
            if len(updated_examples) < 10:
                updated_examples.append(
                    {
                        "status": "still-failed",
                        "source_path": str(source_path),
                        "message": str(exc),
                    }
                )

    rebuild_summary(payload)
    write_inventory(path, payload)
    return {
        "inventory": path.as_posix(),
        "retried_total": retried,
        "rescued_total": rescued,
        "still_failed_total": still_failed,
        "examples": updated_examples,
    }


def main() -> None:
    args = parse_args()
    reports = [retry_inventory(Path(raw), args.source_contains, args.limit) for raw in args.inventory]
    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "inventory_total": len(reports),
        "retried_total": sum(report["retried_total"] for report in reports),
        "rescued_total": sum(report["rescued_total"] for report in reports),
        "still_failed_total": sum(report["still_failed_total"] for report in reports),
        "source_contains": args.source_contains,
    }
    payload = {"summary": summary, "inventories": reports}
    if args.report_json:
        report_path = Path(args.report_json)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
