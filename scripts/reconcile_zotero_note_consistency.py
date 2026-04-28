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
import seed_paper_note
import zotero_to_vault
from path_naming import safe_slug


@dataclass
class ConsistencyRecord:
    item_key: str
    title: str
    paper_path_before: str
    paper_path_after: str
    remote_year: str
    note_year_before: str
    note_year_after: str
    renamed: bool = False
    metadata_updated: bool = False
    status: str = "pending"
    message: str = ""
    duplicate_backfill_paths: list[str] = field(default_factory=list)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reconcile paper-note year metadata with remote Zotero items.")
    parser.add_argument("--config", required=True)
    parser.add_argument("--output-root", default="")
    parser.add_argument("--run-label", default="reconcile-zotero-note-consistency")
    parser.add_argument("--item-key", action="append", default=[])
    parser.add_argument("--write", action="store_true")
    return parser.parse_args()


def resolve_output_root(config: dict[str, Any], output_root: str) -> Path:
    return Path(output_root) if output_root else Path(config["output_root"])


def extract_path_year(path: Path) -> str:
    match = re.match(r"\[(\d{4}|n\.d\.)\]", path.stem)
    return match.group(1) if match else ""


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str, str]:
    bounds = zotero_to_vault.frontmatter_bounds(text)
    if not bounds:
        return {}, "", text
    frontmatter = text[bounds[0] : bounds[1]]
    body = text[bounds[1] :]
    content = frontmatter
    if content.startswith("---"):
        lines = content.splitlines()
        if len(lines) >= 2 and lines[-1].strip() == "---":
            content = "\n".join(lines[1:-1])
    payload = yaml.safe_load(content) or {}
    return payload if isinstance(payload, dict) else {}, frontmatter, body


def dump_frontmatter(data: dict[str, Any]) -> str:
    return "---\n" + yaml.safe_dump(data, sort_keys=False, allow_unicode=True).strip() + "\n---\n"


def normalize_authors(raw: Any, fallback_item: dict[str, Any]) -> list[str]:
    authors: list[str] = []
    if isinstance(raw, list):
        for item in raw:
            normalized = discovery.normalize_whitespace(str(item))
            if normalized:
                authors.append(normalized)
    if authors:
        return authors
    return zotero_to_vault.creators_to_authors(fallback_item.get("creators", []))


def build_citation_key(authors: list[str], year: str, title: str, item_key: str) -> str:
    short_title = seed_paper_note.build_short_title(title)
    primary = seed_paper_note.slugify(f"{seed_paper_note.first_author_label(authors)}-{year}-{short_title}")
    if primary and primary not in {year, "paper", f"paper-{year}"}:
        return primary
    return seed_paper_note.slugify(f"{item_key.lower()}-{year}-{short_title or 'paper'}")


def update_template_metadata_lines(text: str, citation_title: str, year: str, citation_key: str, filename_title: str) -> str:
    replacements = {
        r"(?m)^> citation title：.*$": f"> citation title：{citation_title}",
        r"(?m)^> 年份：.*$": f"> 年份：{year}",
        r"(?m)^> Citation Key：.*$": f"> Citation Key：{citation_key}",
        r"(?m)^> Filename Title：.*$": f"> Filename Title：{filename_title}",
    }
    updated = text
    for pattern, replacement in replacements.items():
        updated = re.sub(pattern, replacement, updated)
    return updated


def replace_vault_note_links(vault_root: Path, old_path: Path, new_path: Path) -> int:
    if old_path == new_path:
        return 0
    old_name = old_path.name
    new_name = new_path.name
    old_stem = old_path.stem
    new_stem = new_path.stem
    old_rel = old_path.relative_to(vault_root).as_posix()
    new_rel = new_path.relative_to(vault_root).as_posix()
    old_rel_no_ext = old_rel[:-3] if old_rel.lower().endswith(".md") else old_rel
    new_rel_no_ext = new_rel[:-3] if new_rel.lower().endswith(".md") else new_rel

    count = 0
    for md_path in sorted(vault_root.rglob("*.md")):
        text = md_path.read_text(encoding="utf-8", errors="replace")
        updated = text
        replacements = [
            (f"[[{old_rel_no_ext}|", f"[[{new_rel_no_ext}|"),
            (f"[[{old_rel_no_ext}]]", f"[[{new_rel_no_ext}]]"),
            (f"[[{old_stem}|", f"[[{new_stem}|"),
            (f"[[{old_stem}]]", f"[[{new_stem}]]"),
            (f"(<{old_name}>)", f"(<{new_name}>)"),
        ]
        for old_value, new_value in replacements:
            updated = updated.replace(old_value, new_value)
        if updated != text:
            md_path.write_text(updated, encoding="utf-8")
            count += 1
    return count


def collect_paper_notes(config: dict[str, Any]) -> list[Path]:
    vault_root = Path(config["vault_root"])
    paper_dir = vault_root / "02_Literature" / "Papers"
    paths: list[Path] = []
    for path in sorted(paper_dir.glob("*.md")):
        if path.name.startswith("_"):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        frontmatter, _, _ = parse_frontmatter(text)
        zotero_key = discovery.normalize_whitespace(str(frontmatter.get("zotero_key", ""))) or zotero_to_vault.extract_zotero_key_from_text(text)
        if zotero_key:
            paths.append(path)
    return paths


def duplicate_backfill_paths(config: dict[str, Any], item_key: str) -> list[Path]:
    vault_root = Path(config["vault_root"])
    folder = vault_root / config["obsidian"]["zotero_folder"] / zotero_to_vault.BACKFILL_FOLDER
    matches: list[Path] = []
    for candidate in sorted(folder.glob("*.md")):
        text = candidate.read_text(encoding="utf-8", errors="replace")
        frontmatter, _, _ = parse_frontmatter(text)
        if discovery.normalize_whitespace(str(frontmatter.get("zotero_key", ""))) == item_key:
            matches.append(candidate)
    return matches


def write_run_report(path: Path, run_id: str, records: list[ConsistencyRecord]) -> None:
    lines = [
        "# Zotero Note Consistency Reconcile",
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
            f"{record.note_year_before or 'n.d.'} -> {record.note_year_after or record.remote_year or 'n.d.'}"
        )
        if record.paper_path_before != record.paper_path_after:
            lines.append(f"  - Renamed: {record.paper_path_before} -> {record.paper_path_after}")
        if record.duplicate_backfill_paths:
            lines.append(f"  - Duplicate backfills seen: {len(record.duplicate_backfill_paths)}")
        if record.message:
            lines.append(f"  - Message: {record.message}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    config = discovery.load_json(Path(args.config))
    output_root = resolve_output_root(config, args.output_root)
    run_id = f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{safe_slug(args.run_label)}"
    run_dir = output_root / "zotero-consistency" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    vault_root = Path(config["vault_root"])
    records: list[ConsistencyRecord] = []
    headers = local_pdf.zotero_api_headers(config, include_json=False)
    prefix = discovery.zotero_library_prefix(config)
    only_keys = {discovery.normalize_whitespace(value) for value in args.item_key if discovery.normalize_whitespace(value)}

    for paper_path in collect_paper_notes(config):
        text = paper_path.read_text(encoding="utf-8", errors="replace")
        frontmatter, _, body = parse_frontmatter(text)
        item_key = discovery.normalize_whitespace(str(frontmatter.get("zotero_key", ""))) or zotero_to_vault.extract_zotero_key_from_text(text)
        if not item_key:
            continue
        if only_keys and item_key not in only_keys:
            continue
        title = discovery.normalize_whitespace(str(frontmatter.get("title", ""))) or paper_path.stem
        note_year = discovery.normalize_whitespace(str(frontmatter.get("year", "")))
        record = ConsistencyRecord(
            item_key=item_key,
            title=title,
            paper_path_before=str(paper_path),
            paper_path_after=str(paper_path),
            remote_year="",
            note_year_before=note_year,
            note_year_after=note_year,
            duplicate_backfill_paths=[str(path) for path in duplicate_backfill_paths(config, item_key)],
        )
        try:
            payload, _ = local_pdf.http_json(f"{local_pdf.ZOTERO_API_BASE}/{prefix}/items/{item_key}", headers=headers, timeout=90)
            item_data = payload.get("data", {})
            remote_year = zotero_to_vault.item_year(item_data, fallback=note_year)
            record.remote_year = remote_year
            remote_title = discovery.normalize_whitespace(str(item_data.get("title", ""))) or title
            path_year = extract_path_year(paper_path)

            needs_update = remote_year and (path_year != remote_year or note_year != remote_year)
            if not needs_update:
                record.status = "unchanged"
                record.message = "Paper note year already matches remote Zotero metadata."
                records.append(record)
                continue

            authors = normalize_authors(frontmatter.get("authors", []), item_data)
            citation_title = seed_paper_note.build_citation_title(authors, remote_year)
            citation_key = build_citation_key(authors, remote_year, remote_title, item_key)
            new_stem = seed_paper_note.build_filename(remote_year, authors, seed_paper_note.build_short_title(remote_title))
            new_path = paper_path.with_name(f"{new_stem}.md")

            frontmatter["year"] = int(remote_year) if remote_year.isdigit() else remote_year
            frontmatter["citation_title"] = citation_title
            frontmatter["citation_key"] = citation_key
            frontmatter["filename_title"] = new_stem
            updated_text = dump_frontmatter(frontmatter) + body.lstrip("\n")
            updated_text = update_template_metadata_lines(updated_text, citation_title, remote_year, citation_key, new_stem)

            if args.write:
                paper_path.write_text(updated_text if updated_text.endswith("\n") else updated_text + "\n", encoding="utf-8")
                if new_path != paper_path:
                    if new_path.exists():
                        raise RuntimeError(f"Target note already exists: {new_path}")
                    paper_path.rename(new_path)
                    replace_vault_note_links(vault_root, paper_path, new_path)
                    paper_path = new_path
                record.paper_path_after = str(paper_path)
            else:
                record.paper_path_after = str(new_path)
            record.note_year_after = remote_year
            record.metadata_updated = True
            record.renamed = record.paper_path_before != record.paper_path_after
            record.status = "updated" if args.write else "planned"
            record.message = "Aligned paper-note year metadata to remote Zotero year."
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
