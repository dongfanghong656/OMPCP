#!/usr/bin/env python
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import mimetypes
import re
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from pypdf import PdfReader
import yaml

import discovery_to_zotero as discovery


ZOTERO_API_BASE = "https://api.zotero.org"


@dataclass
class LocalPdfImportCandidate:
    pdf_path: str
    relative_path: str = ""
    file_name: str = ""
    title: str = ""
    authors: list[str] = field(default_factory=list)
    year: str = ""
    doi: str = ""
    url: str = ""
    venue: str = ""
    abstract: str = ""
    publication_type: str = "article"
    volume: str = ""
    issue: str = ""
    pages: str = ""
    language: str = ""
    cited_by_count: int | None = None
    source: str = "local_pdf"
    query: str = ""
    notes: str = ""
    tags: list[str] = field(default_factory=list)
    collection_paths: list[str] = field(default_factory=list)
    collection_keys: list[str] = field(default_factory=list)
    classification_reasons: list[str] = field(default_factory=list)
    verification_status: str = "lead_only"
    verification_source: str = ""
    openalex_id: str = ""
    already_in_zotero: bool = False
    zotero_parent_id: int | None = None
    zotero_parent_key: str = ""
    zotero_match_reason: str = ""
    parent_write_status: str = "not_attempted"
    parent_write_message: str = ""
    attachment_exists: bool = False
    attachment_complete: bool = False
    attachment_match_reason: str = ""
    attachment_item_key: str = ""
    attachment_write_status: str = "not_attempted"
    attachment_write_message: str = ""


@dataclass
class ExistingItem:
    item_id: int
    item_key: str
    title: str = ""
    doi: str = ""
    attachment_hashes: set[str] = field(default_factory=set)
    attachment_filenames: set[str] = field(default_factory=set)


@dataclass
class ZoteroLocalIndex:
    doi_to_item: dict[str, ExistingItem] = field(default_factory=dict)
    title_to_item: dict[str, ExistingItem] = field(default_factory=dict)
    collections_by_parent_and_name: dict[tuple[str, str], str] = field(default_factory=dict)


@dataclass
class InputPdf:
    path: Path
    root: Path


class HttpFailure(RuntimeError):
    def __init__(self, status: int, message: str, body: str = "") -> None:
        super().__init__(message)
        self.status = status
        self.body = body


def parse_string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [discovery.normalize_whitespace(str(item)) for item in value if discovery.normalize_whitespace(str(item))]
    text = discovery.normalize_whitespace(str(value))
    if not text:
        return []
    parts = re.split(r"\s*[;|\n]\s*|\s*,\s*", text)
    return [discovery.normalize_whitespace(part) for part in parts if discovery.normalize_whitespace(part)]


def unique_extend(target: list[str], values: list[str]) -> None:
    for value in values:
        discovery.unique_append(target, value)


def normalize_collection_path(path: str) -> str:
    cleaned = "/".join(part for part in [discovery.normalize_whitespace(part) for part in str(path).split("/")] if part)
    return cleaned.strip("/")


def sanitize_folder_tag(value: str) -> str:
    return discovery.normalize_whitespace(value).replace("\\", "/")


def normalize_source_path_key(value: str | Path) -> str:
    return str(value).replace("\\", "/").casefold()


def compute_md5(path: Path) -> str:
    md5 = hashlib.md5()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            md5.update(chunk)
    return md5.hexdigest()


def should_prefer_authoritative_title(value: str) -> bool:
    text = discovery.normalize_whitespace(value)
    lowered = text.casefold()
    return (
        not text
        or looks_placeholder_title(text)
        or lowered.startswith("ocis codes:")
        or lowered.startswith("license:")
        or (text[:1].islower() and len(text) > 80)
        or len(text) > 180
    )


def safe_file_name_from_attachment_path(path: str) -> str:
    text = discovery.normalize_whitespace(path)
    if text.startswith("storage:"):
        return text.split(":", 1)[1].strip().lower()
    return Path(text).name.lower()


def looks_placeholder_title(value: str) -> bool:
    text = discovery.normalize_whitespace(value)
    if not text:
        return True
    lowered = text.casefold()
    if lowered.startswith(("title:", "pii:", "doi:")):
        return True
    if lowered.startswith(
        (
            "some of the authors of this publication",
            "we describe ",
            "1. d. huang",
            "5. n. nassif",
            "endomicroscopy of the human colon",
            "noninvasivecross-sectionalimaging",
            "pacs:",
            "中图分类号",
        )
    ):
        return True
    if re.fullmatch(r"[a-z]+\d{4}", lowered):
        return True
    return len(text) < 8 or len(text) > 180


def guess_title_from_filename(path: Path) -> str:
    title = path.stem
    title = re.sub(r"^\[\d+\]\s*", "", title)
    title = title.replace("_", " ")
    return discovery.normalize_whitespace(title.strip(" -"))


def title_line_score(line: str) -> int:
    line = discovery.normalize_whitespace(line)
    if not line:
        return -999
    lowered = line.casefold()
    bad_prefixes = (
        "abstract",
        "introduction",
        "department",
        "school of",
        "university",
        "received",
        "accepted",
        "keywords",
        "key words",
        "doi",
        "www.",
        "http",
        "email",
    )
    if any(lowered.startswith(prefix) for prefix in bad_prefixes):
        return -999
    if "researchgate.net" in lowered or "see discussions, stats, and author profiles" in lowered:
        return -999
    if "@" in line:
        return -999
    if re.search(r"\b(vol\.?|no\.?|issue|pages?)\b", lowered):
        return -200
    if re.fullmatch(r"\d+", line):
        return -999
    if len(line) < 20 or len(line) > 220:
        return -200
    if re.search(r"[A-Za-z\u4e00-\u9fff]", line) is None:
        return -999
    score = len(line)
    if ":" in line:
        score += 8
    if line.count(",") <= 2:
        score += 5
    if re.search(r"\b(optical|coherence|tomography|interferometry|imaging|spectral|swept|deconvolution|phantom|psf)\b", lowered):
        score += 20
    if line[0].isupper():
        score += 5
    return score


def guess_title_from_text(pdf_path: Path, page_texts: list[str]) -> str:
    filename_guess = guess_title_from_filename(pdf_path)
    if not page_texts:
        return filename_guess
    lines = []
    for raw in page_texts[0].splitlines()[:40]:
        line = discovery.normalize_whitespace(raw)
        if line:
            lines.append(line)
    best = ""
    best_score = -999
    for idx, line in enumerate(lines):
        combined = line
        if idx + 1 < len(lines):
            next_line = lines[idx + 1]
            if len(combined) + len(next_line) < 220 and not re.search(
                r"\b(university|department|school|institute|abstract|received|accepted)\b",
                next_line.casefold(),
            ):
                combined = discovery.normalize_whitespace(f"{line} {next_line}")
        for candidate_text in {line, combined}:
            score = title_line_score(candidate_text)
            if score > best_score:
                best = candidate_text
                best_score = score
    return best if best_score > 30 else filename_guess


def clean_authors(value: str) -> str:
    text = discovery.normalize_whitespace(value)
    text = re.sub(r"[*0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip(" ,;")


def guess_authors(meta_author: str, page_texts: list[str], title: str) -> list[str]:
    cleaned_meta = clean_authors(meta_author)
    if cleaned_meta:
        return discovery.split_authors(cleaned_meta)
    if not page_texts:
        return []
    title_key = discovery.normalize_whitespace(title).casefold()
    lines = [discovery.normalize_whitespace(line) for line in page_texts[0].splitlines()[:45] if discovery.normalize_whitespace(line)]
    for idx, line in enumerate(lines):
        if title_key and title_key in line.casefold():
            for probe in lines[idx + 1 : idx + 6]:
                lowered = probe.casefold()
                if any(token in lowered for token in ("abstract", "department", "university", "school", "institute", "@")):
                    break
                if len(probe) < 4 or len(probe) > 180:
                    continue
                if re.search(r"[A-Za-z]", probe) is None:
                    continue
                if probe.count(",") >= 1 or " and " in lowered or ";" in probe:
                    return discovery.split_authors(clean_authors(probe))
    return []


def guess_year(pdf_path: Path, meta_title: str, page_texts: list[str], metadata: dict[str, Any]) -> str:
    candidates = [
        str(metadata.get("/CreationDate") or ""),
        str(metadata.get("/ModDate") or ""),
        meta_title,
        guess_title_from_filename(pdf_path),
        page_texts[0] if page_texts else "",
    ]
    for item in candidates:
        match = re.search(r"(19|20)\d{2}", item)
        if match:
            return match.group(0)
    return ""


def read_pdf_probe(pdf_path: Path, max_pages: int) -> tuple[dict[str, Any], list[str]]:
    reader = PdfReader(str(pdf_path))
    metadata = dict(reader.metadata or {})
    page_texts: list[str] = []
    for page in reader.pages[:max_pages]:
        try:
            page_texts.append(page.extract_text() or "")
        except Exception:
            page_texts.append("")
    return metadata, page_texts


def extract_doi_from_pdf(metadata: dict[str, Any], page_texts: list[str], pdf_path: Path) -> str:
    probes = [
        metadata.get("/doi", ""),
        metadata.get("/DOI", ""),
        metadata.get("/Subject", ""),
        metadata.get("/Keywords", ""),
        metadata.get("/Title", ""),
        pdf_path.name,
    ]
    probes.extend(page_texts[:3])
    for probe in probes:
        doi = discovery.extract_doi_from_text(str(probe))
        if doi:
            return doi
    return ""


def parse_optional_int(value: Any) -> int | None:
    return discovery.parse_optional_int(value)


def http_request(
    url: str,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    data: bytes | None = None,
    timeout: int = 60,
) -> tuple[int, bytes, dict[str, str]]:
    request = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.getcode(), response.read(), dict(response.headers.items())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise HttpFailure(exc.code, f"HTTP {exc.code} for {method} {url}", body) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"URL error for {method} {url}: {exc.reason}") from exc


def http_json(
    url: str,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    data: bytes | None = None,
    timeout: int = 60,
) -> tuple[Any, dict[str, str]]:
    _, body, response_headers = http_request(url, method=method, headers=headers, data=data, timeout=timeout)
    if not body:
        return {}, response_headers
    return json.loads(body.decode("utf-8")), response_headers


def zotero_api_headers(config: dict[str, Any], include_json: bool = True, extra: dict[str, str] | None = None) -> dict[str, str]:
    zotero_cfg = config.get("zotero") or {}
    api_key = discovery.normalize_whitespace(str(zotero_cfg.get("api_key", "")))
    if not api_key:
        raise SystemExit("Zotero api_key is required for local PDF upload.")
    headers = {
        "Zotero-API-Version": "3",
        "Zotero-API-Key": api_key,
    }
    if include_json:
        headers["Content-Type"] = "application/json"
    if extra:
        headers.update(extra)
    return headers


def load_upload_metadata_records(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    suffix = path.suffix.casefold()
    defaults: dict[str, Any] = {}
    records: list[dict[str, Any]] = []
    if suffix == ".json":
        payload = discovery.load_json(path)
        if isinstance(payload, list):
            records = payload
        else:
            defaults = payload.get("defaults") or {}
            records = discovery.first_nonempty(payload, "records", "items", "papers", "leads", "entries") or []
            if not records:
                records = [payload]
    elif suffix == ".jsonl":
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped:
                records.append(json.loads(stripped))
    elif suffix == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            records = list(reader)
    else:
        raise SystemExit(f"Unsupported metadata file format: {path}")
    normalized = [record for record in records if isinstance(record, dict)]
    return defaults, normalized


def match_override_record(pdf_path: Path, relative_path: str, records: list[dict[str, Any]]) -> dict[str, Any] | None:
    normalized_abs = str(pdf_path.resolve()).replace("\\", "/").casefold()
    normalized_rel = relative_path.replace("\\", "/").casefold()
    file_name = pdf_path.name.casefold()
    stem = pdf_path.stem.casefold()
    for record in records:
        keys = [
            discovery.normalize_whitespace(str(record.get(field, ""))).replace("\\", "/").casefold()
            for field in ("path", "pdf_path", "file", "filename", "relative_path")
        ]
        keys = [key for key in keys if key]
        if normalized_abs in keys or normalized_rel in keys or file_name in keys or stem in keys:
            return record
    return None


def parse_rule_list(rules: Any) -> list[dict[str, Any]]:
    if not isinstance(rules, list):
        return []
    return [rule for rule in rules if isinstance(rule, dict)]


def frontmatter_text(note_text: str) -> str:
    match = re.match(r"\A---\r?\n(.*?)\r?\n---\r?\n?", note_text, flags=re.DOTALL)
    return match.group(1) if match else ""


def extract_frontmatter_scalar(frontmatter: str, key: str) -> str:
    match = re.search(rf"(?m)^{re.escape(key)}:\s*(.+)$", frontmatter)
    if not match:
        return ""
    value = match.group(1).strip()
    if value.startswith(("'", '"')) and value.endswith(("'", '"')) and len(value) >= 2:
        value = value[1:-1]
    return discovery.normalize_whitespace(value)


def extract_frontmatter_list(frontmatter: str, key: str) -> list[str]:
    lines = frontmatter.splitlines()
    values: list[str] = []
    active = False
    indent = ""
    for line in lines:
        if not active:
            if re.match(rf"^{re.escape(key)}:\s*$", line):
                active = True
                indent = ""
                continue
            if line.startswith(f"{key}: ") and not line.startswith(f"{key}: []"):
                inline = line.split(":", 1)[1].strip()
                return parse_string_list(inline)
            continue
        if not line.strip():
            continue
        if not line.lstrip().startswith("- "):
            if re.match(r"^\S", line):
                break
            continue
        item = line.split("- ", 1)[1].strip()
        if item.startswith(("'", '"')) and item.endswith(("'", '"')) and len(item) >= 2:
            item = item[1:-1]
        cleaned = discovery.normalize_whitespace(item)
        if cleaned:
            values.append(cleaned)
    return values


def load_paper_note_overrides(config: dict[str, Any]) -> dict[str, dict[str, Any]]:
    vault_root = Path(str(config.get("vault_root", "")))
    if not vault_root.exists():
        return {}

    obs = config.get("obsidian") or {}
    search_dirs = [vault_root / "02_Literature" / "Papers"]
    if obs.get("paper_folder"):
        search_dirs.append(vault_root / str(obs["paper_folder"]))

    overrides: dict[str, dict[str, Any]] = {}
    seen_dirs: set[str] = set()
    for directory in search_dirs:
        directory_key = normalize_source_path_key(directory)
        if directory_key in seen_dirs or not directory.exists():
            continue
        seen_dirs.add(directory_key)
        for note_path in sorted(directory.glob("*.md")):
            if note_path.name.startswith("_"):
                continue
            note_text = note_path.read_text(encoding="utf-8", errors="replace")
            frontmatter = frontmatter_text(note_text)
            if not frontmatter:
                continue
            payload: dict[str, Any] = {}
            try:
                loaded = yaml.safe_load(frontmatter)
                if isinstance(loaded, dict):
                    payload = loaded
            except Exception:
                payload = {}

            title = discovery.normalize_whitespace(
                str(
                    payload.get("title_display")
                    or payload.get("title_en")
                    or payload.get("title_original")
                    or payload.get("title")
                    or extract_frontmatter_scalar(frontmatter, "title_display")
                    or extract_frontmatter_scalar(frontmatter, "title_en")
                    or extract_frontmatter_scalar(frontmatter, "title_original")
                    or extract_frontmatter_scalar(frontmatter, "title")
                )
            )
            authors_value = payload.get("authors", [])
            authors = (
                [discovery.normalize_whitespace(str(item)) for item in authors_value if discovery.normalize_whitespace(str(item))]
                if isinstance(authors_value, list)
                else extract_frontmatter_list(frontmatter, "authors")
            )
            record = {
                "title": title,
                "authors": authors,
                "year": discovery.normalize_whitespace(str(payload.get("year", "") or extract_frontmatter_scalar(frontmatter, "year"))),
                "doi": discovery.normalize_doi(str(payload.get("doi", "") or extract_frontmatter_scalar(frontmatter, "doi"))),
                "url": discovery.normalize_whitespace(str(payload.get("url", "") or extract_frontmatter_scalar(frontmatter, "url"))),
                "venue": discovery.normalize_whitespace(str(payload.get("venue", "") or extract_frontmatter_scalar(frontmatter, "venue"))),
                "language": discovery.normalize_whitespace(str(payload.get("language", "") or extract_frontmatter_scalar(frontmatter, "language"))),
                "zotero_key": discovery.normalize_whitespace(str(payload.get("zotero_key", "") or extract_frontmatter_scalar(frontmatter, "zotero_key"))),
            }
            for raw_path in (
                payload.get("source_pdf", "") or extract_frontmatter_scalar(frontmatter, "source_pdf"),
                payload.get("copied_pdf", "") or extract_frontmatter_scalar(frontmatter, "copied_pdf"),
            ):
                normalized = normalize_source_path_key(raw_path)
                if normalized:
                    overrides[normalized] = record
    return overrides


def apply_paper_note_override(candidate: LocalPdfImportCandidate, override: dict[str, Any] | None) -> None:
    if not override:
        return
    title = discovery.normalize_whitespace(str(override.get("title", "")))
    if title and looks_placeholder_title(candidate.title):
        candidate.title = title

    authors = [discovery.normalize_whitespace(str(item)) for item in override.get("authors", []) if discovery.normalize_whitespace(str(item))]
    if authors and not candidate.authors:
        candidate.authors = authors

    year = discovery.normalize_whitespace(str(override.get("year", "")))
    if year and not candidate.year:
        candidate.year = year

    doi = discovery.normalize_doi(str(override.get("doi", "")))
    if doi and not candidate.doi:
        candidate.doi = doi
        candidate.verification_status = "verified_doi"
        candidate.verification_source = "vault_paper_note"

    url = discovery.normalize_whitespace(str(override.get("url", "")))
    if url and not candidate.url:
        candidate.url = url

    venue = discovery.normalize_whitespace(str(override.get("venue", "")))
    if venue and not candidate.venue:
        candidate.venue = venue

    language = discovery.normalize_whitespace(str(override.get("language", "")))
    if language and not candidate.language:
        candidate.language = language


def apply_known_zotero_key_override(candidate: LocalPdfImportCandidate, override: dict[str, Any] | None) -> None:
    if not override:
        return
    key = discovery.normalize_whitespace(
        str(
            override.get("zotero_parent_key", "")
            or override.get("zotero_key", "")
            or override.get("known_zotero_key", "")
        )
    )
    if not key:
        return
    candidate.zotero_parent_key = key
    candidate.already_in_zotero = True
    if not candidate.zotero_match_reason:
        candidate.zotero_match_reason = "override-key"


def load_local_import_settings(config: dict[str, Any]) -> dict[str, Any]:
    zotero_cfg = config.get("zotero") or {}
    local_cfg = zotero_cfg.get("local_pdf_import") or {}
    return {
        "root_collection": normalize_collection_path(local_cfg.get("root_collection", "Local PDF Imports")),
        "path_collection_depth": int(local_cfg.get("path_collection_depth", 2) or 0),
        "tag_from_path": bool(local_cfg.get("tag_from_path", True)),
        "path_tag_prefix": discovery.normalize_whitespace(str(local_cfg.get("path_tag_prefix", "folder:"))) or "folder:",
        "default_tags": parse_string_list(local_cfg.get("default_tags", ["local-pdf-import"])),
        "classification_rules": parse_rule_list(local_cfg.get("classification_rules", [])),
    }


def extract_candidate_from_source(candidate: LocalPdfImportCandidate) -> discovery.Candidate:
    zotero_candidate = discovery.Candidate(
        title=candidate.title,
        authors=candidate.authors[:],
        year=candidate.year,
        doi=candidate.doi,
        url=candidate.url,
        venue=candidate.venue,
        abstract=candidate.abstract,
        publication_type=candidate.publication_type,
        volume=candidate.volume,
        issue=candidate.issue,
        pages=candidate.pages,
        language=candidate.language,
        cited_by_count=candidate.cited_by_count,
        notes=candidate.notes,
        verification_status=candidate.verification_status,
        verification_source=candidate.verification_source,
        openalex_id=candidate.openalex_id,
    )
    discovery.unique_append(zotero_candidate.discovery_sources, candidate.source)
    if candidate.query:
        discovery.unique_append(zotero_candidate.discovery_queries, candidate.query)
    discovery.unique_append(zotero_candidate.lead_paths, candidate.pdf_path)
    return zotero_candidate


def merge_back(candidate: LocalPdfImportCandidate, merged: discovery.Candidate) -> None:
    candidate.title = merged.title
    candidate.authors = merged.authors[:]
    candidate.year = merged.year
    candidate.doi = merged.doi
    candidate.url = merged.url
    candidate.venue = merged.venue
    candidate.abstract = merged.abstract
    candidate.publication_type = merged.publication_type or candidate.publication_type
    candidate.volume = merged.volume
    candidate.issue = merged.issue
    candidate.pages = merged.pages
    candidate.language = merged.language
    candidate.cited_by_count = merged.cited_by_count
    candidate.notes = merged.notes
    candidate.verification_status = merged.verification_status
    candidate.verification_source = merged.verification_source
    candidate.openalex_id = merged.openalex_id


def apply_authoritative_openalex_metadata(candidate: LocalPdfImportCandidate, mailto: str) -> None:
    work = None
    try:
        if candidate.doi:
            work = discovery.openalex_lookup_by_doi(candidate.doi, mailto)
        elif candidate.title:
            work = discovery.openalex_lookup_by_title(candidate.title, mailto)
    except (urllib.error.HTTPError, urllib.error.URLError):
        work = None
    if not work:
        return
    authoritative = discovery.openalex_work_to_candidate(work, "openalex", candidate.query, candidate.pdf_path)
    if should_prefer_authoritative_title(candidate.title) and authoritative.title:
        candidate.title = authoritative.title
    if not candidate.authors and authoritative.authors:
        candidate.authors = authoritative.authors[:]
    if not candidate.venue and authoritative.venue:
        candidate.venue = authoritative.venue
    if not candidate.abstract and authoritative.abstract:
        candidate.abstract = authoritative.abstract
    if not candidate.publication_type and authoritative.publication_type:
        candidate.publication_type = authoritative.publication_type
    if not candidate.volume and authoritative.volume:
        candidate.volume = authoritative.volume
    if not candidate.issue and authoritative.issue:
        candidate.issue = authoritative.issue
    if not candidate.pages and authoritative.pages:
        candidate.pages = authoritative.pages
    if not candidate.language and authoritative.language:
        candidate.language = authoritative.language
    if candidate.cited_by_count is None and authoritative.cited_by_count is not None:
        candidate.cited_by_count = authoritative.cited_by_count
    if candidate.verification_status == "lead_only":
        candidate.verification_status = "verified_title" if not candidate.doi else "verified_doi"
    candidate.verification_source = authoritative.verification_source
    candidate.openalex_id = authoritative.openalex_id


def build_candidate(
    pdf: InputPdf,
    override: dict[str, Any] | None,
    defaults: dict[str, Any],
    local_settings: dict[str, Any],
    max_pages: int,
) -> LocalPdfImportCandidate:
    relative_path = str(pdf.path.relative_to(pdf.root)) if pdf.path.is_relative_to(pdf.root) else pdf.path.name
    metadata, page_texts = read_pdf_probe(pdf.path, max_pages)
    override = override or {}
    lookup = lambda *keys: discovery.first_nonempty_from_mappings([override, defaults], *keys)

    meta_title = discovery.normalize_whitespace(str(metadata.get("/Title") or ""))
    title = discovery.normalize_whitespace(
        str(
            lookup(
                "title",
                "paper_title",
                "english_title",
                "resolved_title",
                "display_name",
            )
        )
    )
    if not title:
        title = meta_title if not looks_placeholder_title(meta_title) else guess_title_from_text(pdf.path, page_texts)

    authors = discovery.split_authors(
        lookup("authors", "author", "creator", "creators", "author_string", "author_names", "authors_text")
    )
    if not authors:
        authors = guess_authors(str(metadata.get("/Author") or ""), page_texts, title)

    year = discovery.parse_year(lookup("year", "publication_year", "published_year", "pub_year", "date"))
    if not year:
        year = guess_year(pdf.path, meta_title, page_texts, metadata)

    url = discovery.normalize_whitespace(
        str(
            lookup(
                "url",
                "link",
                "publisher_url",
                "paper_url",
                "doi_url",
                "scholar_url",
                "xmol_url",
                "consensus_url",
            )
        )
    )
    doi = discovery.normalize_doi(str(lookup("doi", "DOI", "doi_url")))
    if not doi:
        doi = extract_doi_from_pdf(metadata, page_texts, pdf.path)
    if not doi and url:
        doi = discovery.extract_doi_from_text(url)

    abstract = discovery.normalize_whitespace(
        str(lookup("abstract", "summary", "snippet", "excerpt", "description", "tldr"))
    )
    venue = discovery.normalize_whitespace(
        str(
            lookup(
                "venue",
                "journal",
                "publication",
                "publication_title",
                "source_title",
                "journal_name",
                "journal_title",
                "conference_name",
                "book_title",
            )
        )
    )
    publication_type = discovery.normalize_whitespace(
        str(lookup("publication_type", "itemType", "type", "document_type", "content_type"))
    ) or "article"
    volume = discovery.normalize_whitespace(str(lookup("volume", "journal_volume")))
    issue = discovery.normalize_whitespace(str(lookup("issue", "journal_issue", "number")))
    pages = discovery.normalize_whitespace(str(lookup("pages", "page_range", "pagination")))
    language = discovery.normalize_whitespace(str(lookup("language", "lang")))
    source = discovery.normalize_whitespace(str(lookup("source", "discovery_source", "platform", "origin"))) or "local_pdf"
    query = discovery.normalize_whitespace(str(lookup("query", "search_query", "topic")))
    notes = " | ".join(
        [
            note
            for note in [
                discovery.normalize_whitespace(str(lookup("notes", "note", "comment", "selection_reason", "relevance_note"))),
                f"Local PDF: {pdf.path}",
            ]
            if note
        ]
    )

    candidate = LocalPdfImportCandidate(
        pdf_path=str(pdf.path),
        relative_path=relative_path.replace("\\", "/"),
        file_name=pdf.path.name,
        title=title,
        authors=authors,
        year=year,
        doi=doi,
        url=url,
        venue=venue,
        abstract=abstract,
        publication_type=publication_type,
        volume=volume,
        issue=issue,
        pages=pages,
        language=language,
        cited_by_count=parse_optional_int(lookup("cited_by_count", "cited_by", "citations", "citation_count")),
        source=source,
        query=query,
        notes=notes,
    )

    if candidate.doi:
        candidate.verification_status = "verified_doi"
        candidate.verification_source = "local_pdf_doi"

    unique_extend(candidate.tags, parse_string_list(local_settings.get("default_tags", [])))
    unique_extend(candidate.tags, parse_string_list(lookup("tags", "tag_list")))
    unique_extend(candidate.collection_paths, [normalize_collection_path(path) for path in parse_string_list(lookup("collections", "collection_paths"))])

    path_parts = [part for part in Path(candidate.relative_path).parent.parts if part not in (".", "")]
    if local_settings.get("tag_from_path"):
        prefix = local_settings.get("path_tag_prefix", "folder:")
        for part in path_parts:
            discovery.unique_append(candidate.tags, f"{prefix}{sanitize_folder_tag(part)}")

    root_collection = normalize_collection_path(str(local_settings.get("root_collection", "")))
    depth = int(local_settings.get("path_collection_depth", 0) or 0)
    if root_collection:
        if path_parts and depth > 0:
            suffix = "/".join(path_parts[:depth])
            discovery.unique_append(candidate.collection_paths, normalize_collection_path(f"{root_collection}/{suffix}"))
        else:
            discovery.unique_append(candidate.collection_paths, root_collection)

    return candidate


def apply_classification_rules(candidate: LocalPdfImportCandidate, rules: list[dict[str, Any]]) -> None:
    haystack = " ".join(
        [
            candidate.title,
            candidate.doi,
            candidate.url,
            candidate.venue,
            candidate.abstract,
            candidate.notes,
            candidate.relative_path,
        ]
    ).casefold()
    for rule in rules:
        name = discovery.normalize_whitespace(str(rule.get("name", "rule"))) or "rule"
        match_any = [term.casefold() for term in parse_string_list(rule.get("match_any", []))]
        match_all = [term.casefold() for term in parse_string_list(rule.get("match_all", []))]
        if match_any and not any(term in haystack for term in match_any):
            continue
        if match_all and not all(term in haystack for term in match_all):
            continue
        unique_extend(candidate.tags, parse_string_list(rule.get("tags", [])))
        unique_extend(candidate.collection_paths, [normalize_collection_path(path) for path in parse_string_list(rule.get("collections", []))])
        discovery.unique_append(candidate.classification_reasons, name)


def enumerate_pdfs(pdf_files: list[str], pdf_dirs: list[str], recursive: bool, max_files: int) -> list[InputPdf]:
    discovered: dict[str, InputPdf] = {}
    for file_arg in pdf_files:
        path = Path(file_arg).resolve()
        if path.is_file() and path.suffix.casefold() == ".pdf":
            discovered[str(path).casefold()] = InputPdf(path=path, root=path.parent)
    for dir_arg in pdf_dirs:
        root = Path(dir_arg).resolve()
        if not root.exists():
            continue
        iterator = root.rglob("*.pdf") if recursive else root.glob("*.pdf")
        for path in iterator:
            if path.is_file():
                discovered[str(path.resolve()).casefold()] = InputPdf(path=path.resolve(), root=root)
    values = sorted(discovered.values(), key=lambda item: str(item.path).casefold())
    return values[:max_files] if max_files > 0 else values


def load_zotero_local_index(sqlite_path: Path) -> ZoteroLocalIndex:
    index = ZoteroLocalIndex()
    if not sqlite_path.exists():
        return index

    item_query = """
    SELECT
        i.itemID,
        i.key,
        COALESCE(MAX(CASE WHEN f.fieldName = 'title' THEN v.value END), '') AS title,
        COALESCE(MAX(CASE WHEN f.fieldName = 'DOI' THEN v.value END), '') AS doi
    FROM items i
    LEFT JOIN deletedItems di ON i.itemID = di.itemID
    LEFT JOIN itemData d ON i.itemID = d.itemID
    LEFT JOIN fieldsCombined f ON d.fieldID = f.fieldID
    LEFT JOIN itemDataValues v ON d.valueID = v.valueID
    LEFT JOIN itemTypesCombined it ON i.itemTypeID = it.itemTypeID
    WHERE di.itemID IS NULL
      AND it.typeName NOT IN ('attachment', 'note', 'annotation')
    GROUP BY i.itemID
    """
    attachment_query = """
    SELECT
        parent.key,
        COALESCE(ia.storageHash, ''),
        COALESCE(ia.path, '')
    FROM itemAttachments ia
    JOIN items child ON ia.itemID = child.itemID
    JOIN items parent ON ia.parentItemID = parent.itemID
    LEFT JOIN deletedItems di ON child.itemID = di.itemID
    WHERE di.itemID IS NULL
      AND ia.parentItemID IS NOT NULL
    """
    collection_query = """
    SELECT
        c.key,
        c.collectionName,
        COALESCE(parent.key, '')
    FROM collections c
    LEFT JOIN collections parent ON c.parentCollectionID = parent.collectionID
    """

    conn = sqlite3.connect(f"file:{sqlite_path.as_posix()}?mode=ro", uri=True)
    try:
        items_by_key: dict[str, ExistingItem] = {}
        for item_id, item_key, title, doi in conn.execute(item_query):
            existing = ExistingItem(
                item_id=int(item_id),
                item_key=str(item_key),
                title=discovery.normalize_whitespace(str(title)),
                doi=discovery.normalize_doi(str(doi)),
            )
            items_by_key[existing.item_key] = existing
            if existing.doi and existing.doi not in index.doi_to_item:
                index.doi_to_item[existing.doi] = existing
            title_key = discovery.canonicalize_title(existing.title)
            if title_key and title_key not in index.title_to_item:
                index.title_to_item[title_key] = existing
        for parent_key, storage_hash, path in conn.execute(attachment_query):
            existing = items_by_key.get(str(parent_key))
            if not existing:
                continue
            normalized_hash = discovery.normalize_whitespace(str(storage_hash)).casefold()
            if normalized_hash:
                existing.attachment_hashes.add(normalized_hash)
            filename = safe_file_name_from_attachment_path(str(path))
            if filename:
                existing.attachment_filenames.add(filename)
        for collection_key, collection_name, parent_key in conn.execute(collection_query):
            key = (str(parent_key or ""), discovery.normalize_whitespace(str(collection_name)))
            if key not in index.collections_by_parent_and_name:
                index.collections_by_parent_and_name[key] = str(collection_key)
    finally:
        conn.close()
    return index


def mark_existing_items(candidates: list[LocalPdfImportCandidate], index: ZoteroLocalIndex) -> None:
    for candidate in candidates:
        normalized_doi = discovery.normalize_doi(candidate.doi)
        normalized_title = discovery.canonicalize_title(candidate.title)
        match: ExistingItem | None = None
        if normalized_doi and normalized_doi in index.doi_to_item:
            match = index.doi_to_item[normalized_doi]
            candidate.zotero_match_reason = "doi"
        elif normalized_title and normalized_title in index.title_to_item:
            match = index.title_to_item[normalized_title]
            candidate.zotero_match_reason = "title"
        if not match:
            continue
        candidate.already_in_zotero = True
        candidate.zotero_parent_id = match.item_id
        candidate.zotero_parent_key = match.item_key
        file_hash = compute_md5(Path(candidate.pdf_path))
        file_name = Path(candidate.pdf_path).name.casefold()
        if file_hash in match.attachment_hashes:
            candidate.attachment_exists = True
            candidate.attachment_complete = True
            candidate.attachment_match_reason = "md5"
        elif file_name in match.attachment_filenames:
            candidate.attachment_exists = True
            candidate.attachment_complete = True
            candidate.attachment_match_reason = "filename"


def load_remote_zotero_index(config: dict[str, Any], max_items: int = 500) -> ZoteroLocalIndex:
    index = ZoteroLocalIndex()
    prefix = discovery.zotero_library_prefix(config)
    headers = zotero_api_headers(config, include_json=False)
    fetched = 0
    for start in range(0, max_items, 100):
        url = f"{ZOTERO_API_BASE}/{prefix}/items?itemType=-attachment&limit=100&start={start}"
        payload, _ = http_json(url, headers=headers)
        if not payload:
            break
        for item in payload:
            data = item.get("data", {})
            existing = ExistingItem(
                item_id=0,
                item_key=str(data.get("key", "")),
                title=discovery.normalize_whitespace(str(data.get("title", ""))),
                doi=discovery.normalize_doi(str(data.get("DOI", ""))),
            )
            if existing.doi and existing.doi not in index.doi_to_item:
                index.doi_to_item[existing.doi] = existing
            title_key = discovery.canonicalize_title(existing.title)
            if title_key and title_key not in index.title_to_item:
                index.title_to_item[title_key] = existing
            fetched += 1
        if len(payload) < 100:
            break
    return index


def mark_existing_items_from_remote(candidates: list[LocalPdfImportCandidate], index: ZoteroLocalIndex) -> None:
    for candidate in candidates:
        if candidate.already_in_zotero:
            continue
        normalized_doi = discovery.normalize_doi(candidate.doi)
        normalized_title = discovery.canonicalize_title(candidate.title)
        match: ExistingItem | None = None
        if normalized_doi and normalized_doi in index.doi_to_item:
            match = index.doi_to_item[normalized_doi]
            candidate.zotero_match_reason = "doi-remote"
        elif normalized_title and normalized_title in index.title_to_item:
            match = index.title_to_item[normalized_title]
            candidate.zotero_match_reason = "title-remote"
        if match:
            candidate.already_in_zotero = True
            candidate.zotero_parent_key = match.item_key


def ensure_collection_path(collection_path: str, cache: ZoteroLocalIndex, config: dict[str, Any], write_zotero: bool) -> str:
    normalized_path = normalize_collection_path(collection_path)
    if not normalized_path:
        return ""
    parent_key = ""
    for name in normalized_path.split("/"):
        cache_key = (parent_key, name)
        existing_key = cache.collections_by_parent_and_name.get(cache_key)
        if existing_key:
            parent_key = existing_key
            continue
        if not write_zotero:
            parent_key = ""
            continue
        payload: dict[str, Any] = {"name": name}
        if parent_key:
            payload["parentCollection"] = parent_key
        url = f"{ZOTERO_API_BASE}/{discovery.zotero_library_prefix(config)}/collections"
        response, _ = http_json(
            url,
            method="POST",
            headers=zotero_api_headers(config, include_json=True, extra={"Zotero-Write-Token": uuid.uuid4().hex}),
            data=json.dumps([payload]).encode("utf-8"),
        )
        successful = response.get("successful", {}) or response.get("success", {})
        saved = successful.get("0")
        if isinstance(saved, dict):
            collection_key = saved.get("key") or (saved.get("data") or {}).get("key", "")
        else:
            collection_key = str(saved or "")
        if not collection_key:
            raise RuntimeError(f"Failed to create collection path: {normalized_path}")
        cache.collections_by_parent_and_name[cache_key] = collection_key
        parent_key = collection_key
    return parent_key


def build_parent_payload(candidate: LocalPdfImportCandidate, config: dict[str, Any]) -> dict[str, Any]:
    zotero_cfg = config.get("zotero") or {}
    tags = list(zotero_cfg.get("default_tags", []))
    unique_extend(tags, candidate.tags)
    unique_tags = [{"tag": tag} for tag in dict.fromkeys(tag for tag in tags if discovery.normalize_whitespace(tag))]
    collection_keys = []
    if zotero_cfg.get("scope_collection"):
        collection_keys.append(str(zotero_cfg["scope_collection"]))
    unique_extend(collection_keys, candidate.collection_keys)

    extra_lines = [
        f"Local PDF Path: {candidate.pdf_path}",
        f"Relative PDF Path: {candidate.relative_path}",
        f"Import Source: {candidate.source}",
        f"Verification Status: {candidate.verification_status}",
        f"Verification Source: {candidate.verification_source or 'manual'}",
    ]
    if candidate.query:
        extra_lines.append(f"Source Query: {candidate.query}")
    if candidate.openalex_id:
        extra_lines.append(f"OpenAlex ID: {candidate.openalex_id}")
    if candidate.classification_reasons:
        extra_lines.append(f"Classification Rules: {', '.join(candidate.classification_reasons)}")
    if candidate.notes:
        extra_lines.append(f"Pipeline Notes: {candidate.notes}")

    payload: dict[str, Any] = {
        "itemType": discovery.zotero_item_type(extract_candidate_from_source(candidate)),
        "title": candidate.title,
        "creators": discovery.zotero_creators(candidate.authors),
        "date": candidate.year,
        "DOI": candidate.doi,
        "url": candidate.url,
        "abstractNote": candidate.abstract,
        "extra": "\n".join(extra_lines),
        "tags": unique_tags,
        "collections": collection_keys,
    }

    if payload["itemType"] in {"journalArticle", "conferencePaper", "bookSection"}:
        payload["publicationTitle"] = candidate.venue
        payload["volume"] = candidate.volume
        payload["issue"] = candidate.issue
        payload["pages"] = candidate.pages
    elif payload["itemType"] == "report":
        payload["institution"] = candidate.venue
    elif payload["itemType"] == "book":
        payload["publisher"] = candidate.venue
    elif payload["itemType"] == "preprint":
        payload["repository"] = candidate.venue

    if candidate.language:
        payload["language"] = candidate.language

    return payload


def create_parent_item(candidate: LocalPdfImportCandidate, config: dict[str, Any]) -> None:
    payload = build_parent_payload(candidate, config)
    url = f"{ZOTERO_API_BASE}/{discovery.zotero_library_prefix(config)}/items"
    response, _ = http_json(
        url,
        method="POST",
        headers=zotero_api_headers(config, include_json=True, extra={"Zotero-Write-Token": uuid.uuid4().hex}),
        data=json.dumps([payload]).encode("utf-8"),
    )
    successful = response.get("successful", {}) or response.get("success", {})
    failed = response.get("failed", {})
    if "0" in successful:
        saved = successful["0"]
        candidate.parent_write_status = "created"
        candidate.parent_write_message = str(saved)
        if isinstance(saved, dict):
            candidate.zotero_parent_key = saved.get("key") or (saved.get("data") or {}).get("key", "")
        else:
            candidate.zotero_parent_key = str(saved)
        return
    failure = failed.get("0", {})
    candidate.parent_write_status = "failed"
    candidate.parent_write_message = discovery.normalize_whitespace(str(failure.get("message", "unknown error")))


def refresh_remote_attachment_status(candidate: LocalPdfImportCandidate, config: dict[str, Any]) -> None:
    if candidate.attachment_complete or not candidate.zotero_parent_key:
        return
    url = f"{ZOTERO_API_BASE}/{discovery.zotero_library_prefix(config)}/items/{candidate.zotero_parent_key}/children?itemType=attachment&limit=100"
    payload, _ = http_json(url, headers=zotero_api_headers(config, include_json=False))
    file_name = Path(candidate.pdf_path).name.casefold()
    incomplete_pdf_children: list[dict[str, Any]] = []
    for item in payload or []:
        data = item.get("data", {})
        if discovery.normalize_whitespace(str(data.get("contentType", ""))).casefold() != "application/pdf":
            continue
        attachment_name = discovery.normalize_whitespace(str(data.get("filename") or data.get("title") or data.get("path") or "")).casefold()
        child_key = str(data.get("key", ""))
        is_complete = bool(data.get("md5") or data.get("mtime"))
        if is_complete:
            if attachment_name.endswith(file_name) or attachment_name == file_name:
                candidate.attachment_exists = True
                candidate.attachment_complete = True
                candidate.attachment_item_key = child_key
                candidate.attachment_match_reason = "remote-filename"
                return
            incomplete_pdf_children = []
            candidate.attachment_exists = True
            candidate.attachment_complete = True
            candidate.attachment_item_key = child_key
            candidate.attachment_match_reason = "remote-pdf"
            return
        incomplete_pdf_children.append(data)

    if len(incomplete_pdf_children) == 1:
        child = incomplete_pdf_children[0]
        candidate.attachment_item_key = str(child.get("key", ""))
        if candidate.attachment_item_key:
            candidate.attachment_match_reason = "remote-incomplete"
            return
    for child in incomplete_pdf_children:
        attachment_name = discovery.normalize_whitespace(str(child.get("filename") or child.get("title") or child.get("path") or "")).casefold()
        if attachment_name.endswith(file_name) or attachment_name == file_name:
            candidate.attachment_exists = False
            candidate.attachment_complete = False
            candidate.attachment_item_key = str(child.get("key", ""))
            candidate.attachment_match_reason = "remote-incomplete"
            return


def update_existing_item(candidate: LocalPdfImportCandidate, config: dict[str, Any]) -> None:
    if not candidate.zotero_parent_key:
        return
    item_url = f"{ZOTERO_API_BASE}/{discovery.zotero_library_prefix(config)}/items/{candidate.zotero_parent_key}"
    item_payload, _ = http_json(item_url, headers=zotero_api_headers(config, include_json=False))
    current = item_payload.get("data", {})
    current_item_type = discovery.normalize_whitespace(str(current.get("itemType", "")))
    current_tags = [tag.get("tag", "") for tag in current.get("tags", []) if isinstance(tag, dict)]
    current_collections = [str(key) for key in current.get("collections", [])]

    merged_tags = current_tags[:]
    unique_extend(merged_tags, candidate.tags)
    merged_collections = current_collections[:]
    zotero_cfg = config.get("zotero") or {}
    if zotero_cfg.get("scope_collection"):
        discovery.unique_append(merged_collections, str(zotero_cfg["scope_collection"]))
    unique_extend(merged_collections, candidate.collection_keys)

    patch: dict[str, Any] = {}
    if merged_tags != current_tags:
        patch["tags"] = [{"tag": tag} for tag in dict.fromkeys(tag for tag in merged_tags if discovery.normalize_whitespace(tag))]
    if merged_collections != current_collections:
        patch["collections"] = list(dict.fromkeys(key for key in merged_collections if discovery.normalize_whitespace(key)))

    parent_payload = build_parent_payload(candidate, config)
    for field_name in ("DOI", "url", "date", "language", "abstractNote", "extra"):
        if parent_payload.get(field_name) and not current.get(field_name):
            patch[field_name] = parent_payload[field_name]
    if parent_payload.get("creators") and not current.get("creators"):
        patch["creators"] = parent_payload["creators"]

    publication_field_map: dict[str, str] = {}
    if current_item_type in {"journalArticle", "conferencePaper", "bookSection"}:
        publication_field_map = {
            "publicationTitle": candidate.venue,
            "volume": candidate.volume,
            "issue": candidate.issue,
            "pages": candidate.pages,
        }
    elif current_item_type == "report":
        publication_field_map = {"institution": candidate.venue}
    elif current_item_type == "book":
        publication_field_map = {"publisher": candidate.venue}
    elif current_item_type == "preprint":
        publication_field_map = {"repository": candidate.venue}
    for field_name, value in publication_field_map.items():
        if value and not current.get(field_name):
            patch[field_name] = value

    if not patch:
        candidate.parent_write_status = "existing"
        candidate.parent_write_message = "Existing Zotero item already had the requested metadata, tags, and collections."
        return

    http_request(
        item_url,
        method="PATCH",
        headers=zotero_api_headers(
            config,
            include_json=True,
            extra={"If-Unmodified-Since-Version": str(current.get("version", item_payload.get("version", 0)))},
        ),
        data=json.dumps(patch).encode("utf-8"),
    )
    candidate.parent_write_status = "updated"
    candidate.parent_write_message = f"Updated existing item {candidate.zotero_parent_key}"


def create_attachment_item(candidate: LocalPdfImportCandidate, config: dict[str, Any]) -> str:
    content_type = mimetypes.guess_type(candidate.pdf_path)[0] or "application/pdf"
    payload = {
        "itemType": "attachment",
        "parentItem": candidate.zotero_parent_key,
        "linkMode": "imported_file",
        "title": Path(candidate.pdf_path).name,
        "contentType": content_type,
        "charset": "",
        "filename": Path(candidate.pdf_path).name,
        "tags": [],
        "relations": {},
        "md5": None,
        "mtime": None,
    }
    url = f"{ZOTERO_API_BASE}/{discovery.zotero_library_prefix(config)}/items"
    response, _ = http_json(
        url,
        method="POST",
        headers=zotero_api_headers(config, include_json=True, extra={"Zotero-Write-Token": uuid.uuid4().hex}),
        data=json.dumps([payload]).encode("utf-8"),
    )
    successful = response.get("successful", {}) or response.get("success", {})
    saved = successful.get("0")
    if isinstance(saved, dict):
        return saved.get("key") or (saved.get("data") or {}).get("key", "")
    return str(saved or "")


def upload_attachment_file(candidate: LocalPdfImportCandidate, config: dict[str, Any]) -> None:
    if candidate.attachment_exists and candidate.attachment_complete:
        candidate.attachment_write_status = "existing"
        candidate.attachment_write_message = f"Skipped attachment upload because a matching attachment already exists ({candidate.attachment_match_reason})."
        return
    attachment_key = candidate.attachment_item_key or create_attachment_item(candidate, config)
    if not attachment_key:
        candidate.attachment_write_status = "failed"
        candidate.attachment_write_message = "Failed to create attachment item."
        return
    candidate.attachment_item_key = attachment_key

    pdf_path = Path(candidate.pdf_path)
    file_md5 = compute_md5(pdf_path)
    payload = urllib.parse.urlencode(
        {
            "md5": file_md5,
            "filename": pdf_path.name,
            "filesize": pdf_path.stat().st_size,
            "mtime": int(pdf_path.stat().st_mtime * 1000),
        }
    ).encode("utf-8")
    auth_url = f"{ZOTERO_API_BASE}/{discovery.zotero_library_prefix(config)}/items/{attachment_key}/file"

    retries = 2
    while True:
        try:
            auth_response, _ = http_json(
                auth_url,
                method="POST",
                headers=zotero_api_headers(
                    config,
                    include_json=False,
                    extra={
                        "Content-Type": "application/x-www-form-urlencoded",
                        "If-None-Match": "*",
                    },
                ),
                data=payload,
            )
            break
        except HttpFailure as exc:
            if exc.status == 429 and retries > 0:
                time.sleep(5)
                retries -= 1
                continue
            candidate.attachment_write_status = "failed"
            candidate.attachment_write_message = exc.body or str(exc)
            return

    if auth_response.get("exists") == 1:
        candidate.attachment_write_status = "uploaded"
        candidate.attachment_complete = True
        candidate.attachment_write_message = "File already existed remotely and was associated with the attachment item."
        return

    upload_url = str(auth_response["url"])
    upload_body = auth_response["prefix"].encode("utf-8") + pdf_path.read_bytes() + auth_response["suffix"].encode("utf-8")
    upload_error = ""
    for attempt in range(3):
        try:
            http_request(
                upload_url,
                method="POST",
                headers={"Content-Type": auth_response["contentType"]},
                data=upload_body,
                timeout=300,
            )
            upload_error = ""
            break
        except Exception as exc:
            upload_error = str(exc)
            if attempt < 2:
                time.sleep(3 * (attempt + 1))
                continue
    if upload_error:
        candidate.attachment_write_status = "failed"
        candidate.attachment_write_message = upload_error
        return

    register_body = urllib.parse.urlencode({"upload": auth_response["uploadKey"]}).encode("utf-8")
    http_request(
        auth_url,
        method="POST",
        headers=zotero_api_headers(
            config,
            include_json=False,
            extra={
                "Content-Type": "application/x-www-form-urlencoded",
                "If-None-Match": "*",
            },
        ),
        data=register_body,
    )
    candidate.attachment_write_status = "uploaded"
    candidate.attachment_complete = True
    candidate.attachment_write_message = f"Uploaded file to attachment item {attachment_key}"


def resolve_collection_keys(
    candidates: list[LocalPdfImportCandidate],
    cache: ZoteroLocalIndex,
    config: dict[str, Any],
    write_zotero: bool,
) -> None:
    for candidate in candidates:
        normalized_paths = [normalize_collection_path(path) for path in candidate.collection_paths if normalize_collection_path(path)]
        candidate.collection_paths = list(dict.fromkeys(normalized_paths))
        collection_keys: list[str] = []
        for path in candidate.collection_paths:
            key = ensure_collection_path(path, cache, config, write_zotero)
            if key:
                discovery.unique_append(collection_keys, key)
        candidate.collection_keys = collection_keys


def process_candidates(
    candidates: list[LocalPdfImportCandidate],
    config: dict[str, Any],
    write_zotero: bool,
) -> None:
    for candidate in candidates:
        if not write_zotero:
            if candidate.already_in_zotero:
                candidate.parent_write_status = "existing"
                candidate.parent_write_message = "Dry run only."
            continue
        try:
            if candidate.already_in_zotero:
                update_existing_item(candidate, config)
            else:
                create_parent_item(candidate, config)
        except Exception as exc:
            if candidate.parent_write_status == "not_attempted":
                candidate.parent_write_status = "failed"
            if not candidate.parent_write_message:
                candidate.parent_write_message = str(exc)

        try:
            if candidate.zotero_parent_key and not candidate.attachment_complete:
                upload_attachment_file(candidate, config)
            elif candidate.attachment_exists and candidate.attachment_complete:
                candidate.attachment_write_status = "existing"
                candidate.attachment_write_message = f"Skipped attachment upload because a matching attachment already exists ({candidate.attachment_match_reason})."
        except Exception as exc:
            if candidate.attachment_write_status == "not_attempted":
                candidate.attachment_write_status = "failed"
                candidate.attachment_write_message = str(exc)


def write_summary(path: Path, run_id: str, candidates: list[LocalPdfImportCandidate], write_zotero: bool) -> None:
    existing = sum(1 for candidate in candidates if candidate.already_in_zotero)
    created = sum(1 for candidate in candidates if candidate.parent_write_status == "created")
    updated = sum(1 for candidate in candidates if candidate.parent_write_status == "updated")
    attachments_uploaded = sum(1 for candidate in candidates if candidate.attachment_write_status == "uploaded")
    attachment_existing = sum(1 for candidate in candidates if candidate.attachment_write_status == "existing")
    lines = [
        "# Local PDF To Zotero Run",
        "",
        f"- Run ID: `{run_id}`",
        f"- Generated: `{datetime.now().isoformat(timespec='seconds')}`",
        f"- PDF candidates: {len(candidates)}",
        f"- Existing Zotero parents: {existing}",
        f"- New parent items created: {created}",
        f"- Existing parent items updated: {updated}",
        f"- Attachments uploaded: {attachments_uploaded}",
        f"- Attachments skipped as existing: {attachment_existing}",
        f"- Mode: {'write-zotero' if write_zotero else 'dry-run'}",
        "",
        "## Candidates",
        "",
    ]
    if not candidates:
        lines.append("- No PDF files discovered")
    else:
        for candidate in candidates:
            collections = ", ".join(candidate.collection_paths) or "none"
            tags = ", ".join(candidate.tags) or "none"
            lines.append(
                f"- {candidate.title or candidate.file_name} | {candidate.year or 'n.d.'} | "
                f"{candidate.parent_write_status}/{candidate.attachment_write_status} | "
                f"tags: {tags} | collections: {collections}"
            )
    discovery.ensure_parent(path)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Import local PDF papers into Zotero with metadata inference, tagging, and collection classification."
    )
    parser.add_argument("--config", required=True)
    parser.add_argument("--pdf", action="append", default=[])
    parser.add_argument("--pdf-dir", action="append", default=[])
    parser.add_argument("--recursive", action="store_true")
    parser.add_argument("--metadata-file", default="")
    parser.add_argument("--tag", action="append", default=[])
    parser.add_argument("--collection", action="append", default=[])
    parser.add_argument("--skip-openalex-enrich", action="store_true")
    parser.add_argument("--skip-zotero-sqlite", action="store_true")
    parser.add_argument("--write-zotero", action="store_true")
    parser.add_argument("--run-label", default="local-pdf-import")
    parser.add_argument("--output-root", default="")
    parser.add_argument("--max-pages", type=int, default=3)
    parser.add_argument("--max-files", type=int, default=0)
    return parser


def resolve_output_root(config: dict[str, Any], output_root: str) -> Path:
    return Path(output_root) if output_root else Path(config["output_root"])


def main() -> None:
    parser = build_argument_parser()
    args = parser.parse_args()

    config = discovery.load_json(Path(args.config))
    output_root = resolve_output_root(config, args.output_root)
    run_id = f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{discovery.safe_slug(args.run_label)}"
    run_dir = output_root / "local-pdf-to-zotero" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    inputs = enumerate_pdfs(args.pdf, args.pdf_dir, args.recursive, args.max_files)
    if not inputs:
        raise SystemExit("No PDF files were provided. Use --pdf and/or --pdf-dir.")

    defaults: dict[str, Any] = {}
    metadata_records: list[dict[str, Any]] = []
    if args.metadata_file:
        defaults, metadata_records = load_upload_metadata_records(Path(args.metadata_file))
    paper_note_overrides = load_paper_note_overrides(config)

    local_settings = load_local_import_settings(config)
    local_index = ZoteroLocalIndex()
    if not args.skip_zotero_sqlite:
        sqlite_raw = discovery.normalize_whitespace(str((config.get("zotero") or {}).get("sqlite_path", "")))
        if sqlite_raw:
            local_index = load_zotero_local_index(Path(sqlite_raw))

    mailto = discovery.normalize_whitespace(str((config.get("retrieval") or {}).get("openalex_mailto", "")))
    candidates: list[LocalPdfImportCandidate] = []
    for pdf in inputs:
        relative_path = str(pdf.path.relative_to(pdf.root)) if pdf.path.is_relative_to(pdf.root) else pdf.path.name
        override = match_override_record(pdf.path, relative_path, metadata_records)
        candidate = build_candidate(pdf, override, defaults, local_settings, args.max_pages)
        paper_note_override = paper_note_overrides.get(normalize_source_path_key(candidate.pdf_path))
        apply_paper_note_override(candidate, paper_note_override)
        apply_known_zotero_key_override(candidate, paper_note_override)
        apply_known_zotero_key_override(candidate, override)
        unique_extend(candidate.tags, parse_string_list(args.tag))
        unique_extend(candidate.collection_paths, [normalize_collection_path(path) for path in args.collection])
        apply_classification_rules(candidate, local_settings.get("classification_rules", []))
        if not args.skip_openalex_enrich:
            enriched = discovery.enrich_candidate(extract_candidate_from_source(candidate), mailto, False)
            merge_back(candidate, enriched)
            apply_authoritative_openalex_metadata(candidate, mailto)
        candidates.append(candidate)

    mark_existing_items(candidates, local_index)
    try:
        remote_index = load_remote_zotero_index(config)
        mark_existing_items_from_remote(candidates, remote_index)
    except Exception:
        remote_index = None
    if remote_index is not None:
        for candidate in candidates:
            if candidate.already_in_zotero and candidate.zotero_parent_key:
                try:
                    refresh_remote_attachment_status(candidate, config)
                except Exception:
                    pass
    resolve_collection_keys(candidates, local_index, config, args.write_zotero)
    process_candidates(candidates, config, args.write_zotero)

    json_path = run_dir / "run.json"
    md_path = run_dir / "run.md"
    payload = {
        "run_id": run_id,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "mode": "write-zotero" if args.write_zotero else "dry-run",
        "candidates": [asdict(candidate) for candidate in candidates],
    }
    discovery.ensure_parent(json_path)
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_summary(md_path, run_id, candidates, args.write_zotero)
    print(str(md_path))


if __name__ == "__main__":
    main()
