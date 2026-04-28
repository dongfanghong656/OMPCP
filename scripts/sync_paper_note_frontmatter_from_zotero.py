#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

import discovery_to_zotero as discovery
import local_pdf_to_zotero as local_pdf
import zotero_to_vault
from path_naming import safe_slug


@dataclass
class SyncRecord:
    item_key: str
    title: str
    paper_path: str
    status: str = "pending"
    updated_fields: list[str] = field(default_factory=list)
    message: str = ""


ZOTERO_ITEM_TYPE_LABELS = {
    "journalarticle": "期刊论文",
    "thesis": "学位论文",
    "preprint": "预印本",
    "conferencepaper": "会议论文",
    "report": "报告",
    "book": "书籍",
    "booksection": "书章",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fill missing paper-note frontmatter fields from remote Zotero metadata.")
    parser.add_argument("--config", required=True)
    parser.add_argument("--output-root", default="")
    parser.add_argument("--run-label", default="sync-paper-note-frontmatter-from-zotero")
    parser.add_argument("--item-key", action="append", default=[])
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--write", action="store_true")
    return parser.parse_args()


def resolve_output_root(config: dict[str, Any], output_root: str) -> Path:
    return Path(output_root) if output_root else Path(config["output_root"])


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    bounds = zotero_to_vault.frontmatter_bounds(text)
    if not bounds:
        return {}, text
    frontmatter = text[bounds[0] : bounds[1]]
    body = text[bounds[1] :]
    content = frontmatter
    if content.startswith("---"):
        lines = content.splitlines()
        if len(lines) >= 2 and lines[-1].strip() == "---":
            content = "\n".join(lines[1:-1])
    payload = yaml.safe_load(content) or {}
    return payload if isinstance(payload, dict) else {}, body


def dump_frontmatter(data: dict[str, Any]) -> str:
    return "---\n" + yaml.safe_dump(data, sort_keys=False, allow_unicode=True).strip() + "\n---\n"


def collect_paper_notes(config: dict[str, Any]) -> list[Path]:
    vault_root = Path(config["vault_root"])
    paper_dir = vault_root / "02_Literature" / "Papers"
    return [path for path in sorted(paper_dir.glob("*.md")) if not path.name.startswith("_")]


def normalize_authors(raw: Any) -> list[str]:
    if isinstance(raw, list):
        return [discovery.normalize_whitespace(str(item)) for item in raw if discovery.normalize_whitespace(str(item))]
    if isinstance(raw, str):
        value = discovery.normalize_whitespace(raw)
        return [value] if value else []
    return []


def remote_metadata(item_data: dict[str, Any]) -> dict[str, Any]:
    venue = discovery.normalize_whitespace(
        str(
            item_data.get("publicationTitle")
            or item_data.get("proceedingsTitle")
            or item_data.get("conferenceName")
            or item_data.get("university")
            or item_data.get("publisher")
            or ""
        )
    )
    return {
        "venue": venue,
        "doi": discovery.normalize_doi(str(item_data.get("DOI", ""))),
        "url": discovery.normalize_whitespace(str(item_data.get("url", ""))),
        "authors": zotero_to_vault.creators_to_authors(item_data.get("creators", [])),
        "publication_type": publication_type_from_item_data(item_data),
    }


def publication_type_from_item_data(item_data: dict[str, Any]) -> str:
    item_type = discovery.normalize_whitespace(str(item_data.get("itemType", ""))).lower()
    if item_type in ZOTERO_ITEM_TYPE_LABELS:
        return ZOTERO_ITEM_TYPE_LABELS[item_type]
    if item_data.get("university"):
        return "学位论文"
    if item_data.get("proceedingsTitle") or item_data.get("conferenceName"):
        return "会议论文"
    if item_data.get("publicationTitle"):
        return "期刊论文"
    return ""


def publication_type_from_note(frontmatter: dict[str, Any], text: str, remote_publication_type: str = "") -> str:
    if remote_publication_type:
        return remote_publication_type
    current = discovery.normalize_whitespace(str(frontmatter.get("publication_type", "")))
    if current:
        return current
    match = re.search(r"Zotero item:\s*`[^`]+`\s*\(([^)]+)\)", text)
    if match:
        item_type = discovery.normalize_whitespace(match.group(1)).lower()
        if item_type in ZOTERO_ITEM_TYPE_LABELS:
            return ZOTERO_ITEM_TYPE_LABELS[item_type]
    venue = discovery.normalize_whitespace(str(frontmatter.get("venue", "")))
    url = discovery.normalize_whitespace(str(frontmatter.get("url", "")))
    if any(token in venue for token in ("大学", "学院", "研究所")) or "dissertation" in url.lower() or "thesis" in url.lower():
        return "学位论文"
    if venue:
        return "期刊论文"
    return ""


def maybe_update_scalar(frontmatter: dict[str, Any], key: str, value: str, overwrite: bool) -> bool:
    current = discovery.normalize_whitespace(str(frontmatter.get(key, "")))
    if not value:
        return False
    if current and not overwrite:
        return False
    if current == value:
        return False
    frontmatter[key] = value
    return True


def maybe_update_authors(frontmatter: dict[str, Any], authors: list[str], overwrite: bool) -> bool:
    current = normalize_authors(frontmatter.get("authors", []))
    if not authors:
        return False
    if current and not overwrite:
        return False
    if current == authors:
        return False
    frontmatter["authors"] = authors
    related = normalize_authors(frontmatter.get("related_authors", []))
    if not related or overwrite:
        frontmatter["related_authors"] = authors
    return True


def replace_or_insert_info_line(text: str, label: str, value: str, *, after_label: str | None = None) -> str:
    replacement = f"> {label}：{value or 'TBD'}"
    pattern = rf"(?m)^> {re.escape(label)}：.*$"
    if re.search(pattern, text):
        return re.sub(pattern, replacement, text)
    if after_label:
        after_pattern = rf"(?m)^(> {re.escape(after_label)}：.*)$"
        if re.search(after_pattern, text):
            return re.sub(after_pattern, rf"\1\n{replacement}", text, count=1)
    return text


def update_info_block_lines(text: str, authors: list[str], publication_type: str, venue: str, doi: str, url: str) -> str:
    updated = text
    updated = replace_or_insert_info_line(updated, "作者", ", ".join(authors) if authors else "TBD")
    updated = replace_or_insert_info_line(updated, "文献类型", publication_type or "TBD", after_label="年份")
    updated = replace_or_insert_info_line(updated, "期刊 / 会议", venue or "TBD", after_label="文献类型")
    updated = replace_or_insert_info_line(updated, "DOI", doi or "TBD", after_label="期刊 / 会议")
    updated = replace_or_insert_info_line(updated, "URL", url or "TBD", after_label="DOI")
    return updated


def write_run_report(path: Path, run_id: str, records: list[SyncRecord]) -> None:
    lines = [
        "# Sync Paper Note Frontmatter From Zotero",
        "",
        f"- Run ID: `{run_id}`",
        f"- Generated: `{datetime.now().isoformat(timespec='seconds')}`",
        f"- Checked: {len(records)}",
        f"- Updated: {sum(1 for record in records if record.status == 'updated')}",
        f"- Unchanged: {sum(1 for record in records if record.status == 'unchanged')}",
        f"- Failed: {sum(1 for record in records if record.status == 'failed')}",
        "",
        "## Items",
        "",
    ]
    for record in records:
        lines.append(
            f"- {record.title} | `{record.item_key}` | {record.status} | "
            f"{', '.join(record.updated_fields) if record.updated_fields else 'no field changes'}"
        )
        if record.message:
            lines.append(f"  - Message: {record.message}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    config = discovery.load_json(Path(args.config))
    output_root = resolve_output_root(config, args.output_root)
    run_id = f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{safe_slug(args.run_label)}"
    run_dir = output_root / "zotero-frontmatter-sync" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    headers = local_pdf.zotero_api_headers(config, include_json=False)
    prefix = discovery.zotero_library_prefix(config)
    only_keys = {discovery.normalize_whitespace(value) for value in args.item_key if discovery.normalize_whitespace(value)}
    records: list[SyncRecord] = []

    for paper_path in collect_paper_notes(config):
        text = paper_path.read_text(encoding="utf-8", errors="replace")
        frontmatter, body = parse_frontmatter(text)
        item_key = discovery.normalize_whitespace(str(frontmatter.get("zotero_key", ""))) or zotero_to_vault.extract_zotero_key_from_text(text)
        if only_keys and item_key not in only_keys:
            continue
        record = SyncRecord(
            item_key=item_key or "-",
            title=discovery.normalize_whitespace(str(frontmatter.get("title", ""))) or paper_path.stem,
            paper_path=str(paper_path),
        )
        try:
            remote = {"venue": "", "doi": "", "url": "", "authors": [], "publication_type": ""}
            if item_key:
                payload, _ = local_pdf.http_json(f"{local_pdf.ZOTERO_API_BASE}/{prefix}/items/{item_key}", headers=headers, timeout=90)
                item_data = payload.get("data", {})
                remote = remote_metadata(item_data)
            updated_fields: list[str] = []
            if maybe_update_scalar(frontmatter, "venue", remote["venue"], args.overwrite):
                updated_fields.append("venue")
            if maybe_update_scalar(frontmatter, "doi", remote["doi"], args.overwrite):
                updated_fields.append("doi")
            if maybe_update_scalar(frontmatter, "url", remote["url"], args.overwrite):
                updated_fields.append("url")
            if maybe_update_authors(frontmatter, remote["authors"], args.overwrite):
                updated_fields.append("authors")
            publication_type = publication_type_from_note(frontmatter, text, remote["publication_type"])
            if maybe_update_scalar(frontmatter, "publication_type", publication_type, args.overwrite):
                updated_fields.append("publication_type")
            if updated_fields:
                if "updated" in frontmatter:
                    frontmatter["updated"] = datetime.now().strftime("%Y-%m-%d %H:%M")
                updated_text = dump_frontmatter(frontmatter) + body.lstrip("\n")
                updated_text = update_info_block_lines(
                    updated_text,
                    normalize_authors(frontmatter.get("authors", [])),
                    discovery.normalize_whitespace(str(frontmatter.get("publication_type", ""))),
                    str(frontmatter.get("venue", "")),
                    str(frontmatter.get("doi", "")),
                    str(frontmatter.get("url", "")),
                )
                if args.write:
                    paper_path.write_text(updated_text if updated_text.endswith("\n") else updated_text + "\n", encoding="utf-8")
                    record.status = "updated"
                    record.message = "Filled missing frontmatter fields from remote Zotero metadata and inferred publication type."
                else:
                    record.status = "planned"
                    record.message = "Would fill missing frontmatter fields from remote Zotero metadata and infer publication type."
                record.updated_fields = updated_fields
            else:
                record.status = "unchanged"
                record.message = "No missing frontmatter fields were eligible for sync."
        except Exception as exc:
            record.status = "failed"
            record.message = str(exc)
        records.append(record)

    payload = {
        "run_id": run_id,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "records": [asdict(record) for record in records],
    }
    (run_dir / "run.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_run_report(run_dir / "run.md", run_id, records)
    print(str(run_dir / "run.md"))


if __name__ == "__main__":
    main()
