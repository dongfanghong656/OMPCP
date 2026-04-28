#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import discovery_to_zotero as discovery
import local_pdf_to_zotero as local_pdf
import paper_dossiers
import seed_paper_note
from path_naming import safe_filename_component, safe_slug


BACKFILL_FOLDER = "04_Item-Backfills"
SYNC_BLOCK_START = "<!-- zotero-sync:start -->"
SYNC_BLOCK_END = "<!-- zotero-sync:end -->"


@dataclass
class PaperNoteRecord:
    path: Path
    doi: str = ""
    title: str = ""
    zotero_key: str = ""
    pdf_paths: list[str] = field(default_factory=list)


@dataclass
class PaperNoteIndex:
    by_doi: dict[str, Path] = field(default_factory=dict)
    by_title: dict[str, Path] = field(default_factory=dict)
    by_zotero_key: dict[str, Path] = field(default_factory=dict)
    by_pdf_path: dict[str, Path] = field(default_factory=dict)

    def add(self, record: PaperNoteRecord) -> None:
        if record.doi and record.doi not in self.by_doi:
            self.by_doi[record.doi] = record.path
        title_key = discovery.canonicalize_title(record.title)
        if title_key and title_key not in self.by_title:
            self.by_title[title_key] = record.path
        if record.zotero_key and record.zotero_key not in self.by_zotero_key:
            self.by_zotero_key[record.zotero_key] = record.path
        for pdf_path in record.pdf_paths:
            key = normalize_path_key(pdf_path)
            if key and key not in self.by_pdf_path:
                self.by_pdf_path[key] = record.path


@dataclass
class VaultSyncRecord:
    title: str
    zotero_key: str
    paper_note_path: str = ""
    zotero_note_path: str = ""
    status: str = "pending"
    message: str = ""
    seeded_paper_note: bool = False
    collection_paths: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    metadata_source: str = "remote"


def to_portable_path(value: str | Path) -> str:
    return str(value).replace("\\", "/")


def normalize_path_key(value: str | Path) -> str:
    return to_portable_path(value).casefold()


def wiki_link(vault_root: Path, path: Path, label: str = "") -> str:
    relative = path.relative_to(vault_root).as_posix()
    if relative.lower().endswith(".md"):
        relative = relative[:-3]
    return f"[[{relative}|{label}]]" if label else f"[[{relative}]]"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def frontmatter_bounds(text: str) -> tuple[int, int] | None:
    match = re.match(r"\A---\r?\n.*?\r?\n---\r?\n?", text, flags=re.DOTALL)
    if not match:
        return None
    return (0, match.end())


def extract_frontmatter_value(frontmatter: str, key: str) -> str:
    match = re.search(rf"(?m)^{re.escape(key)}:\s*(.+)$", frontmatter)
    if not match:
        return ""
    value = match.group(1).strip()
    if value.startswith(("'", '"')) and value.endswith(("'", '"')) and len(value) >= 2:
        value = value[1:-1]
    return discovery.normalize_whitespace(value)


def extract_zotero_key_from_text(text: str, frontmatter: str = "") -> str:
    key = extract_frontmatter_value(frontmatter, "zotero_key")
    if key:
        return key
    match = re.search(r"- Zotero item: `([^`]+)`", text)
    if match:
        return discovery.normalize_whitespace(match.group(1))
    return ""


def paper_note_directories(config: dict[str, Any], paper_note_dir: str = "") -> list[Path]:
    if paper_note_dir:
        return [Path(paper_note_dir)]
    vault_root = Path(config["vault_root"])
    obs = config["obsidian"]
    note_style, primary_dir = seed_paper_note.resolve_note_style(vault_root, obs["paper_folder"], "auto")
    del note_style
    search_dirs = [primary_dir]
    legacy_dir = vault_root / obs["paper_folder"]
    if legacy_dir not in search_dirs and legacy_dir.exists():
        search_dirs.append(legacy_dir)
    return search_dirs


def load_paper_note_index(config: dict[str, Any]) -> PaperNoteIndex:
    index = PaperNoteIndex()
    for directory in paper_note_directories(config):
        if not directory.exists():
            continue
        for path in sorted(directory.glob("*.md")):
            if path.name.startswith("_"):
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            bounds = frontmatter_bounds(text)
            frontmatter = text[bounds[0] : bounds[1]] if bounds else ""
            record = PaperNoteRecord(
                path=path,
                doi=discovery.normalize_doi(extract_frontmatter_value(frontmatter, "doi")),
                title=extract_frontmatter_value(frontmatter, "title"),
                zotero_key=extract_zotero_key_from_text(text, frontmatter),
                pdf_paths=[
                    value
                    for value in (
                        extract_frontmatter_value(frontmatter, "source_pdf"),
                        extract_frontmatter_value(frontmatter, "copied_pdf"),
                    )
                    if value
                ],
            )
            index.add(record)
    return index


def collect_candidates_from_paper_notes(config: dict[str, Any], paper_note_dir: str = "") -> list[local_pdf.LocalPdfImportCandidate]:
    candidates: list[local_pdf.LocalPdfImportCandidate] = []
    seen_keys: set[str] = set()
    for directory in paper_note_directories(config, paper_note_dir):
        if not directory.exists():
            continue
        for path in sorted(directory.glob("*.md")):
            if path.name.startswith("_"):
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            bounds = frontmatter_bounds(text)
            frontmatter = text[bounds[0] : bounds[1]] if bounds else ""
            zotero_key = extract_zotero_key_from_text(text, frontmatter)
            if not zotero_key or zotero_key in seen_keys:
                continue
            seen_keys.add(zotero_key)
            pdf_path = extract_frontmatter_value(frontmatter, "source_pdf") or extract_frontmatter_value(frontmatter, "copied_pdf")
            title = extract_frontmatter_value(frontmatter, "title")
            year = extract_frontmatter_value(frontmatter, "year")
            doi = discovery.normalize_doi(extract_frontmatter_value(frontmatter, "doi"))
            fallback_pdf = str((directory / "__missing__" / f"{path.stem}.pdf").resolve())
            effective_pdf = pdf_path or fallback_pdf
            candidate = local_pdf.LocalPdfImportCandidate(
                pdf_path=effective_pdf,
                relative_path=Path(effective_pdf).name,
                file_name=Path(effective_pdf).name,
                title=title,
                year=year,
                doi=doi,
                zotero_parent_key=zotero_key,
                already_in_zotero=True,
                zotero_match_reason="paper-note",
            )
            candidates.append(candidate)
    return candidates


def note_args_from_candidate(candidate: local_pdf.LocalPdfImportCandidate) -> SimpleNamespace:
    return SimpleNamespace(
        year=candidate.year or "1900",
        authors="; ".join(candidate.authors),
        source_tag="zotero-backfill",
        extract_path="",
        translated_note_path="",
        translation_template_path="",
        question_mode="A",
    )


def seed_paper_note_for_candidate(candidate: local_pdf.LocalPdfImportCandidate, config: dict[str, Any]) -> Path:
    vault_root = Path(config["vault_root"])
    obs = config["obsidian"]
    note_style, paper_dir = seed_paper_note.resolve_note_style(vault_root, obs["paper_folder"], "auto")
    paper_dir.mkdir(parents=True, exist_ok=True)

    title = discovery.normalize_whitespace(candidate.title) or candidate.file_name or "Untitled Paper"
    year = candidate.year or "1900"
    authors = candidate.authors[:]
    if note_style == "academic":
        note_stem = seed_paper_note.build_filename(year, authors, seed_paper_note.build_short_title(title))
    else:
        note_stem = seed_paper_note.slugify(f"{year}-{title}")
    note_path = paper_dir / f"{note_stem}.md"

    if note_path.exists():
        return note_path

    source_pdf_for_note = candidate.pdf_path
    copied_pdf = candidate.pdf_path
    args = note_args_from_candidate(candidate)
    if note_style == "academic":
        lines = seed_paper_note.build_academic_note_lines(
            args,
            title,
            authors,
            note_stem,
            source_pdf_for_note,
            copied_pdf,
        )
        index_header = "# Literature Paper Index\n\n"
    else:
        lines = seed_paper_note.build_legacy_note_lines(args, title, source_pdf_for_note, copied_pdf)
        index_header = "# Paper Index\n\n"

    note_path.write_text("\n".join(lines), encoding="utf-8")
    reference = seed_paper_note.build_index_reference(note_path)
    seed_paper_note.update_index(paper_dir / "_Index.md", f"- {reference} | {year} | zotero-backfill", index_header)
    return note_path


def find_paper_note(candidate: local_pdf.LocalPdfImportCandidate, index: PaperNoteIndex) -> Path | None:
    if candidate.zotero_parent_key and candidate.zotero_parent_key in index.by_zotero_key:
        return index.by_zotero_key[candidate.zotero_parent_key]

    normalized_doi = discovery.normalize_doi(candidate.doi)
    if normalized_doi and normalized_doi in index.by_doi:
        return index.by_doi[normalized_doi]

    normalized_pdf = normalize_path_key(candidate.pdf_path)
    if normalized_pdf and normalized_pdf in index.by_pdf_path:
        return index.by_pdf_path[normalized_pdf]

    title_key = discovery.canonicalize_title(candidate.title)
    if title_key and title_key in index.by_title:
        return index.by_title[title_key]
    return None


def build_sync_block(
    vault_root: Path,
    zotero_key: str,
    item_type: str,
    zotero_note_path: Path,
    tags: list[str],
    collection_paths: list[str],
    attachment_names: list[str],
) -> str:
    lines = [
        SYNC_BLOCK_START,
        "## Zotero Sync",
        "",
        f"- Zotero item: `{zotero_key}` ({item_type or 'item'})",
        f"- Zotero note: {wiki_link(vault_root, zotero_note_path)}",
        f"- Collections: {', '.join(collection_paths) if collection_paths else 'none'}",
        f"- Tags: {', '.join(tags) if tags else 'none'}",
        f"- Attachments: {', '.join(attachment_names) if attachment_names else 'none'}",
        f"- Last synced: `{datetime.now().isoformat(timespec='seconds')}`",
        SYNC_BLOCK_END,
    ]
    return "\n".join(lines)


def upsert_sync_block(text: str, block: str) -> str:
    pattern = re.compile(rf"{re.escape(SYNC_BLOCK_START)}.*?{re.escape(SYNC_BLOCK_END)}\n?", flags=re.DOTALL)
    if pattern.search(text):
        updated = pattern.sub(block + "\n", text)
        return updated if updated.endswith("\n") else updated + "\n"

    bounds = frontmatter_bounds(text)
    if bounds:
        head = text[: bounds[1]]
        tail = text[bounds[1] :].lstrip("\n")
        pieces = [head.rstrip("\n"), "", block]
        if tail:
            pieces.extend(["", tail.rstrip("\n")])
        return "\n".join(pieces) + "\n"

    body = text.rstrip("\n")
    if body:
        return f"{block}\n\n{body}\n"
    return block + "\n"


def update_paper_note_sync_block(
    paper_note_path: Path,
    vault_root: Path,
    zotero_key: str,
    item_type: str,
    zotero_note_path: Path,
    tags: list[str],
    collection_paths: list[str],
    attachment_names: list[str],
) -> None:
    text = paper_note_path.read_text(encoding="utf-8", errors="replace")
    block = build_sync_block(vault_root, zotero_key, item_type, zotero_note_path, tags, collection_paths, attachment_names)
    updated = upsert_sync_block(text, block)
    paper_note_path.write_text(updated, encoding="utf-8")


def load_collection_path_map(sqlite_path: Path) -> dict[str, str]:
    if not sqlite_path.exists():
        return {}
    query = """
    SELECT
        c.key,
        c.collectionName,
        COALESCE(parent.key, '')
    FROM collections c
    LEFT JOIN collections parent ON c.parentCollectionID = parent.collectionID
    """
    entries: dict[str, tuple[str, str]] = {}
    conn = sqlite3.connect(f"file:{sqlite_path.as_posix()}?mode=ro", uri=True)
    try:
        for collection_key, collection_name, parent_key in conn.execute(query):
            entries[str(collection_key)] = (
                discovery.normalize_whitespace(str(collection_name)),
                str(parent_key or ""),
            )
    finally:
        conn.close()

    resolved: dict[str, str] = {}

    def resolve(key: str) -> str:
        if key in resolved:
            return resolved[key]
        name, parent_key = entries.get(key, ("", ""))
        if not name:
            resolved[key] = ""
            return ""
        if parent_key:
            parent_path = resolve(parent_key)
            resolved[key] = f"{parent_path}/{name}" if parent_path else name
        else:
            resolved[key] = name
        return resolved[key]

    for key in list(entries):
        resolve(key)
    return resolved


def fetch_remote_collection_path_map(config: dict[str, Any], max_items: int = 500) -> dict[str, str]:
    prefix = discovery.zotero_library_prefix(config)
    headers = local_pdf.zotero_api_headers(config, include_json=False)
    entries: dict[str, tuple[str, str]] = {}
    for start in range(0, max_items, 100):
        url = f"{local_pdf.ZOTERO_API_BASE}/{prefix}/collections?limit=100&start={start}"
        payload, _ = local_pdf.http_json(url, headers=headers)
        if not payload:
            break
        for entry in payload:
            if not isinstance(entry, dict):
                continue
            data = entry.get("data", {})
            key = discovery.normalize_whitespace(str(data.get("key", "")))
            name = discovery.normalize_whitespace(str(data.get("name") or data.get("collectionName") or ""))
            parent_key = discovery.normalize_whitespace(str(data.get("parentCollection") or ""))
            if key and name:
                entries[key] = (name, parent_key)
        if len(payload) < 100:
            break

    resolved: dict[str, str] = {}

    def resolve(key: str) -> str:
        if key in resolved:
            return resolved[key]
        name, parent_key = entries.get(key, ("", ""))
        if not name:
            resolved[key] = ""
            return ""
        if parent_key:
            parent_path = resolve(parent_key)
            resolved[key] = f"{parent_path}/{name}" if parent_path else name
        else:
            resolved[key] = name
        return resolved[key]

    for key in list(entries):
        resolve(key)
    return resolved


def creators_to_authors(creators: list[dict[str, Any]]) -> list[str]:
    authors: list[str] = []
    for creator in creators:
        if not isinstance(creator, dict):
            continue
        if creator.get("name"):
            authors.append(discovery.normalize_whitespace(str(creator.get("name"))))
            continue
        first = discovery.normalize_whitespace(str(creator.get("firstName", "")))
        last = discovery.normalize_whitespace(str(creator.get("lastName", "")))
        full = discovery.normalize_whitespace(f"{first} {last}")
        if full:
            authors.append(full)
    return authors


def item_year(item_data: dict[str, Any], fallback: str = "") -> str:
    for value in (item_data.get("date"), item_data.get("year"), fallback):
        match = re.search(r"(19|20)\d{2}", discovery.normalize_whitespace(str(value)))
        if match:
            return match.group(0)
    return fallback or "n.d."


def fetch_remote_item(item_key: str, config: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    prefix = discovery.zotero_library_prefix(config)
    headers = local_pdf.zotero_api_headers(config, include_json=False)
    item_url = f"{local_pdf.ZOTERO_API_BASE}/{prefix}/items/{item_key}"
    child_url = f"{local_pdf.ZOTERO_API_BASE}/{prefix}/items/{item_key}/children?limit=100"
    item_payload, _ = local_pdf.http_json(item_url, headers=headers)
    children_payload, _ = local_pdf.http_json(child_url, headers=headers)
    return item_payload.get("data", {}), [entry.get("data", {}) for entry in children_payload if isinstance(entry, dict)]


def build_fallback_item_data(candidate: local_pdf.LocalPdfImportCandidate, config: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    tags = list((config.get("zotero") or {}).get("default_tags", []))
    local_pdf.unique_extend(tags, candidate.tags)
    item_data = {
        "key": candidate.zotero_parent_key,
        "title": candidate.title or candidate.file_name or "[untitled]",
        "itemType": discovery.zotero_item_type(local_pdf.extract_candidate_from_source(candidate)),
        "date": candidate.year,
        "DOI": candidate.doi,
        "url": candidate.url,
        "abstractNote": candidate.abstract,
        "creators": [{"name": author} for author in candidate.authors],
        "tags": [{"tag": tag} for tag in tags if discovery.normalize_whitespace(str(tag))],
        "collections": candidate.collection_keys[:],
    }
    attachments: list[dict[str, Any]] = []
    pdf_path = Path(candidate.pdf_path)
    if pdf_path.exists():
        attachments.append(
            {
                "contentType": "application/pdf",
                "filename": pdf_path.name,
                "title": "PDF",
            }
        )
    return item_data, attachments


def build_zotero_note_lines(
    vault_root: Path,
    zotero_note_path: Path,
    item_data: dict[str, Any],
    attachments: list[dict[str, Any]],
    paper_note_path: Path | None,
    collection_paths: list[str],
) -> list[str]:
    title = discovery.normalize_whitespace(str(item_data.get("title", ""))) or "[untitled]"
    doi = discovery.normalize_doi(str(item_data.get("DOI", "")))
    url = discovery.normalize_whitespace(str(item_data.get("url", "")))
    item_type = discovery.normalize_whitespace(str(item_data.get("itemType", "")))
    authors = creators_to_authors(item_data.get("creators", []))
    year = item_year(item_data)
    tags = [tag.get("tag", "") for tag in item_data.get("tags", []) if isinstance(tag, dict) and tag.get("tag")]
    lines = [
        "---",
        'type: "zotero-item"',
        f'title: "{seed_paper_note.sanitize(title)}"',
        f'zotero_key: "{seed_paper_note.sanitize(str(item_data.get("key", "")))}"',
        f'zotero_item_type: "{seed_paper_note.sanitize(item_type)}"',
        f'year: "{year}"',
        f'doi: "{seed_paper_note.sanitize(doi)}"',
        f'url: "{seed_paper_note.sanitize(url)}"',
        f'synced_at: "{datetime.now().isoformat(timespec="seconds")}"',
        "---",
        "",
        f"# {title}",
        "",
        "## Metadata",
        "",
        f"- Zotero key: `{item_data.get('key', '')}`",
        f"- Item type: `{item_type or 'unknown'}`",
        f"- Year: `{year}`",
        f"- DOI: `{doi or 'n/a'}`",
        f"- URL: {url if url else 'n/a'}",
        "",
        "## Links",
        "",
    ]
    if paper_note_path:
        lines.append(f"- Related paper note: {wiki_link(vault_root, paper_note_path)}")
    lines.append(f"- Backfill note path: `{to_portable_path(zotero_note_path)}`")
    lines.extend(["", "## Authors", ""])
    if authors:
        for author in authors:
            lines.append(f"- {author}")
    else:
        lines.append("- None")
    lines.extend(["", "## Collections", ""])
    if collection_paths:
        for path in collection_paths:
            lines.append(f"- {path}")
    else:
        lines.append("- None")
    lines.extend(["", "## Tags", ""])
    if tags:
        for tag in tags:
            lines.append(f"- {tag}")
    else:
        lines.append("- None")
    lines.extend(["", "## Attachments", ""])
    pdf_children = [attachment for attachment in attachments if attachment.get("contentType") == "application/pdf"]
    if pdf_children:
        for attachment in pdf_children:
            filename = discovery.normalize_whitespace(str(attachment.get("filename", ""))) or attachment.get("title", "PDF")
            lines.append(f"- {filename}")
    else:
        lines.append("- None")
    abstract = discovery.normalize_whitespace(str(item_data.get("abstractNote", "")))
    lines.extend(["", "## Abstract", ""])
    lines.append(abstract or "No abstract available.")
    return lines


def remove_duplicate_backfill_notes(folder: Path, item_key: str, keep_path: Path) -> list[Path]:
    removed: list[Path] = []
    if not folder.exists():
        return removed
    for candidate in sorted(folder.glob("*.md")):
        if candidate == keep_path:
            continue
        text = candidate.read_text(encoding="utf-8", errors="replace")
        bounds = frontmatter_bounds(text)
        frontmatter = text[bounds[0] : bounds[1]] if bounds else ""
        if extract_frontmatter_value(frontmatter, "zotero_key") != item_key:
            continue
        candidate.unlink()
        removed.append(candidate)
    return removed


def write_zotero_note(
    config: dict[str, Any],
    item_data: dict[str, Any],
    attachments: list[dict[str, Any]],
    paper_note_path: Path | None,
    collection_paths: list[str],
) -> Path:
    vault_root = Path(config["vault_root"])
    obs = config["obsidian"]
    folder = vault_root / obs["zotero_folder"] / BACKFILL_FOLDER
    folder.mkdir(parents=True, exist_ok=True)

    title = discovery.normalize_whitespace(str(item_data.get("title", ""))) or "Untitled Zotero Item"
    year = item_year(item_data)
    short_title = seed_paper_note.build_short_title(title)
    stem = safe_filename_component(f"[{year}] {item_data.get('key', 'ITEM')} - {short_title}", max_length=96, fallback=str(item_data.get("key", "item")))
    note_path = folder / f"{stem}.md"
    remove_duplicate_backfill_notes(folder, str(item_data.get("key", "")), note_path)
    lines = build_zotero_note_lines(vault_root, note_path, item_data, attachments, paper_note_path, collection_paths)
    note_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return note_path


def ensure_root_index_entry(vault_root: Path, obs: dict[str, Any]) -> None:
    index_path = vault_root / obs["zotero_folder"] / "_Index.md"
    if index_path.exists():
        text = index_path.read_text(encoding="utf-8", errors="replace")
    else:
        text = "# Zotero Index\n\n"
    obsolete_line = f"- [[{obs['zotero_folder']}/{BACKFILL_FOLDER}/_Index|Item Backfills]]"
    if obsolete_line in text:
        text = text.replace(obsolete_line + "\n", "").replace(obsolete_line, "")
    line = f"- [[{BACKFILL_FOLDER}/_Index|Item Backfills]]"
    if line not in text:
        if not text.endswith("\n"):
            text += "\n"
        text += line + "\n"
    index_path.write_text(text, encoding="utf-8")


def write_backfill_index(config: dict[str, Any], records: list[VaultSyncRecord]) -> Path:
    vault_root = Path(config["vault_root"])
    obs = config["obsidian"]
    folder = vault_root / obs["zotero_folder"] / BACKFILL_FOLDER
    folder.mkdir(parents=True, exist_ok=True)
    index_path = folder / "_Index.md"
    unique_records: list[VaultSyncRecord] = []
    seen: set[str] = set()
    for record in records:
        key = record.zotero_note_path or record.zotero_key
        if key in seen:
            continue
        seen.add(key)
        unique_records.append(record)

    lines = [
        "# Zotero Item Backfills",
        "",
        f"- Updated: `{datetime.now().isoformat(timespec='seconds')}`",
        f"- Synced items: {len(unique_records)}",
        "",
    ]
    if not unique_records:
        lines.append("- None")
    else:
        for record in unique_records:
            note_path = Path(record.zotero_note_path) if record.zotero_note_path else None
            paper_note = Path(record.paper_note_path) if record.paper_note_path else None
            zotero_ref = wiki_link(vault_root, note_path) if note_path and note_path.exists() else record.title
            suffix = f" | paper: {wiki_link(vault_root, paper_note)}" if paper_note and paper_note.exists() else ""
            lines.append(f"- {zotero_ref} | `{record.zotero_key}` | {record.status}{suffix}")
    index_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    ensure_root_index_entry(vault_root, obs)
    return index_path


def load_candidates_from_run(path: Path) -> list[local_pdf.LocalPdfImportCandidate]:
    payload = load_json(path)
    records = payload.get("candidates", []) if isinstance(payload, dict) else []
    candidates: list[local_pdf.LocalPdfImportCandidate] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        candidates.append(local_pdf.LocalPdfImportCandidate(**record))
    return candidates


def collect_candidates_from_inputs(args: argparse.Namespace, config: dict[str, Any]) -> list[local_pdf.LocalPdfImportCandidate]:
    if args.scan_paper_notes or args.paper_note_dir:
        candidates = collect_candidates_from_paper_notes(config, args.paper_note_dir)
        if candidates:
            return candidates
        raise SystemExit("No Zotero-linked paper notes were found. Use --run-json, --pdf, --pdf-dir, or --scan-paper-notes.")

    inputs = local_pdf.enumerate_pdfs(args.pdf, args.pdf_dir, args.recursive, args.max_files)
    if not inputs:
        raise SystemExit("No PDF files were provided. Use --run-json, --pdf, or --pdf-dir.")

    defaults: dict[str, Any] = {}
    metadata_records: list[dict[str, Any]] = []
    if args.metadata_file:
        defaults, metadata_records = local_pdf.load_upload_metadata_records(Path(args.metadata_file))

    local_settings = local_pdf.load_local_import_settings(config)
    local_index = local_pdf.ZoteroLocalIndex()
    sqlite_raw = discovery.normalize_whitespace(str((config.get("zotero") or {}).get("sqlite_path", "")))
    if sqlite_raw:
        local_index = local_pdf.load_zotero_local_index(Path(sqlite_raw))

    mailto = discovery.normalize_whitespace(str((config.get("retrieval") or {}).get("openalex_mailto", "")))
    candidates: list[local_pdf.LocalPdfImportCandidate] = []
    for pdf in inputs:
        relative_path = str(pdf.path.relative_to(pdf.root)) if pdf.path.is_relative_to(pdf.root) else pdf.path.name
        override = local_pdf.match_override_record(pdf.path, relative_path, metadata_records)
        candidate = local_pdf.build_candidate(pdf, override, defaults, local_settings, args.max_pages)
        local_pdf.apply_classification_rules(candidate, local_settings.get("classification_rules", []))
        enriched = discovery.enrich_candidate(local_pdf.extract_candidate_from_source(candidate), mailto, False)
        local_pdf.merge_back(candidate, enriched)
        local_pdf.apply_authoritative_openalex_metadata(candidate, mailto)
        candidates.append(candidate)

    local_pdf.mark_existing_items(candidates, local_index)
    try:
        remote_index = local_pdf.load_remote_zotero_index(config)
        local_pdf.mark_existing_items_from_remote(candidates, remote_index)
    except Exception:
        remote_index = None
    if remote_index is not None:
        for candidate in candidates:
            if candidate.already_in_zotero and candidate.zotero_parent_key:
                try:
                    local_pdf.refresh_remote_attachment_status(candidate, config)
                except Exception:
                    pass
    local_pdf.resolve_collection_keys(candidates, local_index, config, False)
    return candidates


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Backfill Zotero item metadata into the OCT vault note system.")
    parser.add_argument("--config", required=True)
    parser.add_argument("--run-json", default="")
    parser.add_argument("--pdf", action="append", default=[])
    parser.add_argument("--pdf-dir", action="append", default=[])
    parser.add_argument("--paper-note-dir", default="")
    parser.add_argument("--scan-paper-notes", action="store_true")
    parser.add_argument("--recursive", action="store_true")
    parser.add_argument("--metadata-file", default="")
    parser.add_argument("--run-label", default="zotero-to-vault")
    parser.add_argument("--output-root", default="")
    parser.add_argument("--max-pages", type=int, default=3)
    parser.add_argument("--max-files", type=int, default=0)
    return parser


def resolve_output_root(config: dict[str, Any], output_root: str) -> Path:
    return Path(output_root) if output_root else Path(config["output_root"])


def write_run_report(path: Path, run_id: str, records: list[VaultSyncRecord]) -> None:
    lines = [
        "# Zotero To Vault Run",
        "",
        f"- Run ID: `{run_id}`",
        f"- Generated: `{datetime.now().isoformat(timespec='seconds')}`",
        f"- Candidates: {len(records)}",
        f"- Synced: {sum(1 for record in records if record.status == 'synced')}",
        f"- Seeded paper notes: {sum(1 for record in records if record.seeded_paper_note)}",
        f"- Local fallback metadata: {sum(1 for record in records if record.metadata_source == 'local-fallback')}",
        f"- Skipped: {sum(1 for record in records if record.status == 'skipped')}",
        f"- Failed: {sum(1 for record in records if record.status == 'failed')}",
        "",
        "## Items",
        "",
    ]
    if not records:
        lines.append("- None")
    else:
        for record in records:
            paper = record.paper_note_path or "none"
            zotero_note = record.zotero_note_path or "none"
            lines.append(
                f"- {record.title or '[untitled]'} | `{record.zotero_key or 'missing'}` | "
                f"{record.status} | source: {record.metadata_source} | paper: {paper} | zotero: {zotero_note}"
            )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = build_argument_parser()
    args = parser.parse_args()

    config = discovery.load_json(Path(args.config))
    output_root = resolve_output_root(config, args.output_root)
    run_id = f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{safe_slug(args.run_label)}"
    run_dir = output_root / "zotero-to-vault" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    if args.run_json:
        candidates = load_candidates_from_run(Path(args.run_json))
    else:
        candidates = collect_candidates_from_inputs(args, config)

    sqlite_raw = discovery.normalize_whitespace(str((config.get("zotero") or {}).get("sqlite_path", "")))
    collection_path_map = load_collection_path_map(Path(sqlite_raw)) if sqlite_raw else {}
    try:
        remote_collection_path_map = fetch_remote_collection_path_map(config)
        for key, path in remote_collection_path_map.items():
            if path and key not in collection_path_map:
                collection_path_map[key] = path
    except Exception:
        pass
    note_index = load_paper_note_index(config)
    vault_root = Path(config["vault_root"])

    records: list[VaultSyncRecord] = []
    for candidate in candidates:
        record = VaultSyncRecord(title=candidate.title or candidate.file_name, zotero_key=candidate.zotero_parent_key)
        try:
            if not candidate.zotero_parent_key:
                record.status = "skipped"
                record.message = "No Zotero parent key resolved."
                records.append(record)
                continue

            paper_note_path = find_paper_note(candidate, note_index)
            if paper_note_path is None:
                paper_note_path = seed_paper_note_for_candidate(candidate, config)
                note_index = load_paper_note_index(config)
                record.seeded_paper_note = True

            try:
                item_data, attachments = fetch_remote_item(candidate.zotero_parent_key, config)
                record.metadata_source = "remote"
            except Exception:
                item_data, attachments = build_fallback_item_data(candidate, config)
                record.metadata_source = "local-fallback"
            collection_paths = [
                collection_path_map.get(key, key)
                for key in item_data.get("collections", [])
                if discovery.normalize_whitespace(str(key))
            ]
            if not collection_paths:
                collection_paths = candidate.collection_paths[:]
            tags = [tag.get("tag", "") for tag in item_data.get("tags", []) if isinstance(tag, dict) and tag.get("tag")]
            attachment_names = [
                discovery.normalize_whitespace(str(attachment.get("filename", ""))) or discovery.normalize_whitespace(str(attachment.get("title", "")))
                for attachment in attachments
                if attachment.get("contentType") == "application/pdf"
            ]

            zotero_note_path = write_zotero_note(config, item_data, attachments, paper_note_path, collection_paths)
            update_paper_note_sync_block(
                paper_note_path,
                vault_root,
                candidate.zotero_parent_key,
                discovery.normalize_whitespace(str(item_data.get("itemType", ""))),
                zotero_note_path,
                tags,
                collection_paths,
                attachment_names,
            )

            record.paper_note_path = str(paper_note_path)
            record.zotero_note_path = str(zotero_note_path)
            record.collection_paths = collection_paths
            record.tags = tags
            record.status = "synced"
            if record.metadata_source == "remote":
                record.message = "Vault note and Zotero backfill note updated."
            else:
                record.message = "Vault note updated with local fallback metadata while Zotero API was unavailable."
            records.append(record)
        except Exception as exc:
            record.status = "failed"
            record.message = str(exc)
            records.append(record)

    index_path = write_backfill_index(config, [record for record in records if record.status == "synced"])
    payload = {
        "run_id": run_id,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "index_path": str(index_path),
        "records": [asdict(record) for record in records],
    }
    (run_dir / "run.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_run_report(run_dir / "run.md", run_id, records)
    try:
        paper_dossiers.sync_dossiers(config)
    except Exception as exc:
        print(f"Warning: paper dossier sync failed: {exc}", file=sys.stderr)
    print(str(run_dir / "run.md"))


if __name__ == "__main__":
    main()
