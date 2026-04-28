#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import re
import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import discovery_to_zotero as discovery
import local_pdf_to_zotero as local_pdf
from path_naming import safe_slug


@dataclass
class NoteTarget:
    path: Path
    zotero_key: str
    title: str
    pdf_path: str


def normalize_text(value: Any) -> str:
    return discovery.normalize_whitespace(str(value))


def parse_list(value: str) -> list[str]:
    return [normalize_text(part) for part in local_pdf.parse_string_list(value) if normalize_text(part)]


def extract_frontmatter_title(text: str) -> str:
    match = re.search(r'(?m)^title:\s*"([^"]+)"', text)
    if match:
        return normalize_text(match.group(1))
    match = re.search(r"(?m)^title:\s*'([^']+)'", text)
    if match:
        return normalize_text(match.group(1))
    return ""


def extract_frontmatter_pdf(text: str) -> str:
    for key in ("source_pdf", "copied_pdf"):
        match = re.search(rf'(?m)^{re.escape(key)}:\s*"([^"]+)"', text)
        if match:
            return normalize_text(match.group(1))
    return ""


def extract_legacy_source_note(text: str) -> str:
    match = re.search(r'(?m)^legacy_source_note:\s*["\']?\[\[([^\]]+)\]\]["\']?$', text)
    if match:
        return normalize_text(match.group(1))
    return ""


def resolve_pdf_path(path: Path, text: str, vault_root: Path) -> str:
    direct_pdf = extract_frontmatter_pdf(text)
    if direct_pdf:
        return direct_pdf
    legacy_note = extract_legacy_source_note(text)
    if not legacy_note:
        return ""
    legacy_path = vault_root / Path(legacy_note + ("" if legacy_note.endswith(".md") else ".md"))
    if not legacy_path.exists():
        return ""
    legacy_text = legacy_path.read_text(encoding="utf-8", errors="replace")
    return extract_frontmatter_pdf(legacy_text)


def extract_zotero_key(text: str) -> str:
    match = re.search(r"- Zotero item: `([^`]+)`", text)
    if match:
        return normalize_text(match.group(1))
    match = re.search(r'(?m)^zotero_key:\s*"([^"]+)"', text)
    if match:
        return normalize_text(match.group(1))
    return ""


def collect_note_targets(vault_root: Path) -> list[NoteTarget]:
    paper_dir = vault_root / "02_Literature" / "Papers"
    targets: list[NoteTarget] = []
    for path in sorted(paper_dir.glob("*.md")):
        if path.name.startswith("_"):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        zotero_key = extract_zotero_key(text)
        if not zotero_key:
            continue
        title = extract_frontmatter_title(text)
        pdf_path = resolve_pdf_path(path, text, vault_root)
        targets.append(NoteTarget(path=path, zotero_key=zotero_key, title=title or path.stem, pdf_path=pdf_path))
    return targets


def fetch_item(config: dict[str, Any], item_key: str) -> dict[str, Any]:
    prefix = discovery.zotero_library_prefix(config)
    headers = local_pdf.zotero_api_headers(config, include_json=False)
    url = f"{local_pdf.ZOTERO_API_BASE}/{prefix}/items/{item_key}"
    last_error: Exception | None = None
    for attempt in range(4):
        try:
            payload, _ = local_pdf.http_json(url, headers=headers, timeout=90)
            return payload.get("data", {})
        except Exception as exc:  # pragma: no cover - live retry path
            last_error = exc
            if attempt == 3:
                raise
            time.sleep(1.5 * (attempt + 1))
    raise last_error or RuntimeError(f"Failed to fetch {item_key}")


def clean_tags(tags: list[str], remove_tags: list[str], remove_prefixes: list[str]) -> list[str]:
    removed = {normalize_text(tag) for tag in remove_tags if normalize_text(tag)}
    prefixes = [normalize_text(prefix) for prefix in remove_prefixes if normalize_text(prefix)]
    cleaned: list[str] = []
    seen: set[str] = set()
    for tag in tags:
        normalized = normalize_text(tag)
        if not normalized:
            continue
        if normalized in removed:
            continue
        if any(normalized.startswith(prefix) for prefix in prefixes):
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        cleaned.append(normalized)
    return cleaned


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a zotero_curate tag-hygiene target file from the current vault paper notes.")
    parser.add_argument("--config", required=True)
    parser.add_argument("--output-file", default="")
    parser.add_argument("--run-label", default="build-zotero-tag-hygiene-targets")
    parser.add_argument("--output-root", default="")
    parser.add_argument("--remove-tags", default="local-pdf-import,oct-research-assist,oct-scholar-seed")
    parser.add_argument("--remove-tag-prefixes", default="discovery:,verification:")
    return parser


def resolve_output_root(config: dict[str, Any], output_root: str) -> Path:
    return Path(output_root) if output_root else Path(config["output_root"])


def write_run_report(path: Path, run_id: str, records: list[dict[str, Any]], removed_summary: dict[str, int]) -> None:
    lines = [
        "# Build Zotero Tag Hygiene Targets",
        "",
        f"- Run ID: `{run_id}`",
        f"- Generated: `{datetime.now().isoformat(timespec='seconds')}`",
        f"- Targets: {len(records)}",
        "",
        "## Removed Tag Summary",
        "",
    ]
    if removed_summary:
        for tag, count in sorted(removed_summary.items(), key=lambda item: (-item[1], item[0])):
            lines.append(f"- {tag}: {count}")
    else:
        lines.append("- None")
    lines.extend(["", "## Items", ""])
    for record in records:
        lines.append(f"- {record['title']} | `{record['item_key']}` | tags: {', '.join(record['tags']) if record['tags'] else 'none'}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    config = discovery.load_json(Path(args.config))
    vault_root = Path(config["vault_root"])
    remove_tags = parse_list(args.remove_tags)
    remove_prefixes = parse_list(args.remove_tag_prefixes)
    targets = collect_note_targets(vault_root)

    records: list[dict[str, Any]] = []
    removed_counter: Counter[str] = Counter()
    for target in targets:
        item = fetch_item(config, target.zotero_key)
        current_tags = [normalize_text(tag.get("tag", "")) for tag in item.get("tags", []) if isinstance(tag, dict) and normalize_text(tag.get("tag", ""))]
        cleaned_tags = clean_tags(current_tags, remove_tags, remove_prefixes)
        for tag in current_tags:
            if tag not in cleaned_tags:
                removed_counter[tag] += 1
        records.append(
            {
                "item_key": target.zotero_key,
                "title": normalize_text(item.get("title", "")) or target.title,
                "tags": cleaned_tags,
            }
        )

    payload = {
        "defaults": {
            "preserve_existing_tags": True,
            "preserve_existing_collections": True,
            "remove_tag_prefixes": remove_prefixes,
            "remove_tags": remove_tags,
        },
        "items": records,
    }

    output_root = resolve_output_root(config, args.output_root)
    run_id = f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{safe_slug(args.run_label)}"
    run_dir = output_root / "zotero-curation" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    output_file = Path(args.output_file) if args.output_file else run_dir / "zotero-tag-hygiene-targets.json"
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
                "title": record["title"],
                "zotero_parent_key": record["item_key"],
            }
            for target, record in zip(targets, records)
            if target.pdf_path
        ],
    }
    (run_dir / "zotero-backfill-run.json").write_text(json.dumps(backfill_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    run_json = {
        "run_id": run_id,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "output_file": str(output_file),
        "backfill_run_json": str(run_dir / "zotero-backfill-run.json"),
        "targets": len(records),
        "removed_tag_summary": dict(removed_counter),
    }
    (run_dir / "run.json").write_text(json.dumps(run_json, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_run_report(run_dir / "run.md", run_id, records, dict(removed_counter))
    print(str(output_file))
    print(str(run_dir / "run.md"))


if __name__ == "__main__":
    main()
