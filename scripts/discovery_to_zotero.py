#!/usr/bin/env python
from __future__ import annotations

import argparse
import csv
import json
import re
import sqlite3
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from secure_config import load_json


OPENALEX_WORKS_URL = "https://api.openalex.org/works"
ZOTERO_API_BASE = "https://api.zotero.org"


@dataclass
class Candidate:
    title: str = ""
    authors: list[str] = field(default_factory=list)
    year: str = ""
    doi: str = ""
    url: str = ""
    venue: str = ""
    abstract: str = ""
    publication_type: str = ""
    volume: str = ""
    issue: str = ""
    pages: str = ""
    language: str = ""
    cited_by_count: int | None = None
    discovery_sources: list[str] = field(default_factory=list)
    discovery_queries: list[str] = field(default_factory=list)
    lead_paths: list[str] = field(default_factory=list)
    notes: str = ""
    verification_status: str = "lead_only"
    verification_source: str = ""
    openalex_id: str = ""
    already_in_zotero: bool = False
    zotero_item_id: int | None = None
    zotero_match_reason: str = ""
    zotero_write_status: str = "not_attempted"
    zotero_write_message: str = ""


@dataclass
class ZoteroIndex:
    doi_to_item: dict[str, int] = field(default_factory=dict)
    title_to_item: dict[str, int] = field(default_factory=dict)


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def normalize_optional_text(value: Any) -> str:
    if value is None:
        return ""
    text = normalize_whitespace(str(value))
    return "" if text.casefold() in {"none", "null", "nan"} else text


def normalize_doi(value: str) -> str:
    raw = normalize_whitespace(value).lower()
    raw = raw.replace("https://doi.org/", "").replace("http://doi.org/", "")
    raw = raw.replace("doi:", "")
    return raw.strip().rstrip(".")


def extract_doi_from_text(value: str) -> str:
    text = normalize_whitespace(value)
    if not text:
        return ""
    match = re.search(r"(10\.\d{4,9}/[-._;()/:a-z0-9]+)", text, flags=re.IGNORECASE)
    return normalize_doi(match.group(1)) if match else ""


def canonicalize_title(value: str) -> str:
    cleaned = normalize_whitespace(value).casefold()
    cleaned = re.sub(r"[^\w\s]", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def safe_slug(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", "-", value).strip("-").lower()
    return cleaned or "run"


def unique_append(values: list[str], item: str) -> None:
    normalized = normalize_whitespace(item)
    if normalized and normalized not in values:
        values.append(normalized)


def split_authors(value: Any) -> list[str]:
    if isinstance(value, list):
        return [normalize_whitespace(str(item)) for item in value if normalize_whitespace(str(item))]
    text = normalize_whitespace(str(value))
    if not text:
        return []
    if ";" in text:
        parts = text.split(";")
    elif " and " in text:
        parts = text.split(" and ")
    elif "|" in text:
        parts = text.split("|")
    else:
        parts = [text]
    return [normalize_whitespace(part) for part in parts if normalize_whitespace(part)]


def parse_year(value: Any) -> str:
    text = normalize_whitespace(str(value))
    match = re.search(r"(19|20)\d{2}", text)
    return match.group(0) if match else ""


def parse_optional_int(value: Any) -> int | None:
    text = normalize_optional_text(value)
    if not text:
        return None
    match = re.search(r"-?\d+", text.replace(",", ""))
    return int(match.group(0)) if match else None


def first_nonempty(mapping: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in mapping and mapping[key] not in (None, ""):
            return mapping[key]
    return ""


def first_nonempty_from_mappings(mappings: list[dict[str, Any]], *keys: str) -> Any:
    for mapping in mappings:
        value = first_nonempty(mapping, *keys)
        if value not in (None, ""):
            return value
    return ""


def fetch_json(url: str, headers: dict[str, str] | None = None, data: bytes | None = None) -> Any:
    request = urllib.request.Request(url, headers=headers or {}, data=data)
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def openalex_query_params(mailto: str, max_results: int) -> dict[str, str]:
    params = {"per-page": str(max_results)}
    if mailto:
        params["mailto"] = mailto
    return params


def openalex_search(query: str, max_results: int, mailto: str) -> list[dict[str, Any]]:
    params = openalex_query_params(mailto, max_results)
    params["search"] = query
    url = OPENALEX_WORKS_URL + "?" + urllib.parse.urlencode(params)
    payload = fetch_json(url)
    return payload.get("results", [])


def openalex_lookup_by_doi(doi: str, mailto: str) -> dict[str, Any] | None:
    normalized = normalize_doi(doi)
    if not normalized:
        return None
    params = openalex_query_params(mailto, 1)
    params["filter"] = f"doi:https://doi.org/{normalized}"
    url = OPENALEX_WORKS_URL + "?" + urllib.parse.urlencode(params)
    payload = fetch_json(url)
    results = payload.get("results", [])
    return results[0] if results else None


def openalex_lookup_by_title(title: str, mailto: str) -> dict[str, Any] | None:
    normalized_title = canonicalize_title(title)
    if not normalized_title:
        return None
    candidates = openalex_search(title, 5, mailto)
    for item in candidates:
        candidate_title = canonicalize_title(item.get("display_name", ""))
        if candidate_title == normalized_title:
            return item
    return None


def inverted_index_to_text(inverted_index: dict[str, list[int]] | None) -> str:
    if not inverted_index:
        return ""
    max_position = -1
    for positions in inverted_index.values():
        if positions:
            max_position = max(max_position, max(positions))
    if max_position < 0:
        return ""
    words = [""] * (max_position + 1)
    for token, positions in inverted_index.items():
        for position in positions:
            if 0 <= position < len(words):
                words[position] = token
    return normalize_whitespace(" ".join(words))


def normalize_page_range(first_page: Any, last_page: Any) -> str:
    first = normalize_optional_text(first_page)
    last = normalize_optional_text(last_page)
    if first and last:
        return first if first == last else f"{first}-{last}"
    return first or last


def openalex_work_to_candidate(
    work: dict[str, Any],
    discovery_source: str,
    discovery_query: str,
    lead_path: str,
) -> Candidate:
    biblio = work.get("biblio") or {}
    primary_location = work.get("primary_location") or {}
    source = primary_location.get("source") or {}
    pages = normalize_page_range(biblio.get("first_page", ""), biblio.get("last_page", ""))

    candidate = Candidate(
        title=normalize_whitespace(work.get("display_name", "")),
        authors=[
            normalize_whitespace((authorship.get("author") or {}).get("display_name", ""))
            for authorship in work.get("authorships", [])
            if normalize_whitespace((authorship.get("author") or {}).get("display_name", ""))
        ],
        year=str(work.get("publication_year", "") or ""),
        doi=normalize_doi(work.get("doi", "")),
        url=normalize_whitespace(primary_location.get("landing_page_url", "") or work.get("doi", "")),
        venue=normalize_whitespace(source.get("display_name", "")),
        abstract=inverted_index_to_text(work.get("abstract_inverted_index")),
        publication_type=normalize_whitespace(work.get("type_crossref", "") or work.get("type", "")),
        volume=normalize_optional_text(biblio.get("volume", "")),
        issue=normalize_optional_text(biblio.get("issue", "")),
        pages=pages,
        language=normalize_whitespace(work.get("language", "")),
        cited_by_count=work.get("cited_by_count"),
        verification_status="verified_openalex",
        verification_source="openalex",
        openalex_id=normalize_whitespace(work.get("id", "")),
    )
    unique_append(candidate.discovery_sources, discovery_source)
    unique_append(candidate.discovery_queries, discovery_query)
    unique_append(candidate.lead_paths, lead_path)
    return candidate


def merge_candidates(primary: Candidate, incoming: Candidate) -> Candidate:
    fillable = (
        "title",
        "year",
        "doi",
        "url",
        "venue",
        "abstract",
        "publication_type",
        "volume",
        "issue",
        "pages",
        "language",
        "verification_source",
        "openalex_id",
    )
    for field_name in fillable:
        current = getattr(primary, field_name)
        if not current and getattr(incoming, field_name):
            setattr(primary, field_name, getattr(incoming, field_name))

    if not primary.authors and incoming.authors:
        primary.authors = incoming.authors[:]

    if primary.cited_by_count is None and incoming.cited_by_count is not None:
        primary.cited_by_count = incoming.cited_by_count

    for source in incoming.discovery_sources:
        unique_append(primary.discovery_sources, source)
    for query in incoming.discovery_queries:
        unique_append(primary.discovery_queries, query)
    for lead_path in incoming.lead_paths:
        unique_append(primary.lead_paths, lead_path)

    notes = [segment for segment in [primary.notes, incoming.notes] if normalize_whitespace(segment)]
    primary.notes = " | ".join(dict.fromkeys(notes))

    rank = {"lead_only": 0, "verified_title": 1, "verified_doi": 2, "verified_openalex": 3}
    if rank.get(incoming.verification_status, -1) > rank.get(primary.verification_status, -1):
        primary.verification_status = incoming.verification_status

    return primary


def parse_ris_file(path: Path) -> list[dict[str, Any]]:
    raw = path.read_text(encoding="utf-8", errors="replace")
    records: list[dict[str, Any]] = []
    current: dict[str, Any] = {}
    authors: list[str] = []
    keywords: list[str] = []

    for line in raw.splitlines():
        if not line.strip():
            continue
        if line.startswith("ER  -"):
            if authors:
                current["authors"] = authors[:]
            if keywords:
                current["keywords"] = keywords[:]
            if current:
                records.append(current)
            current = {}
            authors = []
            keywords = []
            continue

        if "  - " not in line:
            continue
        tag, value = line.split("  - ", 1)
        value = normalize_whitespace(value)
        if tag in {"TI", "T1"}:
            current["title"] = value
        elif tag in {"T2", "JO", "JF"}:
            current["venue"] = value
        elif tag in {"AU", "A1"}:
            if value:
                authors.append(value)
        elif tag in {"PY", "Y1", "DA"}:
            current["year"] = parse_year(value)
        elif tag == "DO":
            current["doi"] = value
        elif tag == "UR":
            current["url"] = value
        elif tag in {"AB", "N2"}:
            current["abstract"] = value
        elif tag == "KW":
            if value:
                keywords.append(value)
        elif tag == "TY":
            current["publication_type"] = value

    return records


def normalize_lead_record(
    record: dict[str, Any],
    default_source: str,
    default_query: str,
    lead_path: Path,
    defaults: dict[str, Any] | None = None,
) -> Candidate:
    defaults = defaults or {}
    lookup = lambda *keys: first_nonempty_from_mappings([record, defaults], *keys)

    title = normalize_whitespace(
        str(
            lookup(
                "title",
                "paper_title",
                "display_name",
                "article_title",
                "result_title",
                "english_title",
                "translated_title",
                "resolved_title",
            )
        )
    )
    authors = split_authors(
        lookup("authors", "author", "creator", "creators", "author_line", "author_string", "authors_text", "author_names")
    )
    url = normalize_whitespace(
        str(
            lookup(
                "url",
                "link",
                "landing_page_url",
                "publisher_url",
                "paper_url",
                "result_url",
                "scholar_url",
                "xmol_url",
                "consensus_url",
                "doi_url",
            )
        )
    )
    doi = normalize_doi(str(lookup("doi", "DOI", "doi_url")))
    if not doi:
        doi = extract_doi_from_text(url) or extract_doi_from_text(str(record))

    abstract = normalize_whitespace(
        str(lookup("abstract", "summary", "abstract_text", "description", "ai_summary", "tldr"))
    )
    snippet = normalize_whitespace(str(lookup("snippet", "excerpt")))
    if not abstract and snippet:
        abstract = snippet

    note_segments: list[str] = []
    for key in ("notes", "note", "comment", "why_relevant", "relevance_note", "selection_reason", "source_note"):
        value = normalize_whitespace(str(lookup(key)))
        if value and value not in note_segments:
            note_segments.append(value)
    if snippet and snippet != abstract and snippet not in note_segments:
        note_segments.append(f"Snippet: {snippet}")

    candidate = Candidate(
        title=title,
        authors=authors,
        year=parse_year(lookup("year", "publication_year", "date", "published_year", "pub_year")),
        doi=doi,
        url=url,
        venue=normalize_whitespace(
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
        ),
        abstract=abstract,
        publication_type=normalize_whitespace(
            str(lookup("publication_type", "itemType", "type", "document_type", "content_type"))
        ),
        language=normalize_whitespace(str(lookup("language", "lang"))),
        cited_by_count=parse_optional_int(lookup("cited_by_count", "cited_by", "citations", "citation_count")),
        notes=" | ".join(note_segments),
    )
    if candidate.doi:
        candidate.verification_status = "verified_doi"
        candidate.verification_source = "lead_doi"
    source = (
        normalize_whitespace(str(lookup("source", "discovery_source", "platform", "origin", "provider")))
        or default_source
        or "manual"
    )
    query = normalize_whitespace(str(lookup("query", "search_query", "search_term", "question", "prompt", "topic")))
    if not query:
        query = default_query
    unique_append(candidate.discovery_sources, source)
    unique_append(candidate.discovery_queries, query)
    unique_append(candidate.lead_paths, str(lead_path))
    return candidate


def load_candidates_from_json(path: Path, default_source: str) -> list[Candidate]:
    payload = load_json(path)
    if isinstance(payload, list):
        records = payload
        default_query = ""
        defaults: dict[str, Any] = {}
    else:
        defaults = payload.get("defaults") or {}
        if any(key in payload for key in ("leads", "items", "results", "papers", "entries")):
            records = first_nonempty(payload, "leads", "items", "results", "papers", "entries") or []
        else:
            records = [payload]
        default_query = normalize_whitespace(str(first_nonempty(payload, "query", "search_query", "search_term")))
        payload_source = normalize_whitespace(str(first_nonempty(payload, "source", "discovery_source", "platform")))
        if payload_source:
            default_source = payload_source
    return [normalize_lead_record(record, default_source, default_query, path, defaults) for record in records]


def load_candidates_from_jsonl(path: Path, default_source: str) -> list[Candidate]:
    candidates: list[Candidate] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        record = json.loads(stripped)
        candidates.append(normalize_lead_record(record, default_source, "", path, {}))
    return candidates


def load_candidates_from_csv(path: Path, default_source: str) -> list[Candidate]:
    candidates: list[Candidate] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            candidates.append(normalize_lead_record(row, default_source, "", path, {}))
    return candidates


def load_candidates_from_path(path: Path, default_source: str) -> list[Candidate]:
    suffix = path.suffix.lower()
    if suffix == ".json":
        return load_candidates_from_json(path, default_source)
    if suffix == ".jsonl":
        return load_candidates_from_jsonl(path, default_source)
    if suffix == ".csv":
        return load_candidates_from_csv(path, default_source)
    if suffix == ".ris":
        records = parse_ris_file(path)
        return [normalize_lead_record(record, default_source, "", path, {}) for record in records]
    raise SystemExit(f"Unsupported lead file format: {path}")


def deduplicate_candidates(candidates: list[Candidate]) -> list[Candidate]:
    deduped: dict[str, Candidate] = {}
    for candidate in candidates:
        key = candidate.doi or f"title:{canonicalize_title(candidate.title)}|year:{candidate.year}"
        if key in deduped:
            merge_candidates(deduped[key], candidate)
        else:
            deduped[key] = candidate
    return list(deduped.values())


def enrich_candidate(candidate: Candidate, mailto: str, skip_openalex: bool) -> Candidate:
    if skip_openalex:
        return candidate
    try:
        if candidate.doi:
            work = openalex_lookup_by_doi(candidate.doi, mailto)
            if work:
                verified = openalex_work_to_candidate(work, "openalex", "", "")
                verified.verification_status = "verified_doi"
                return merge_candidates(candidate, verified)
        if candidate.title:
            work = openalex_lookup_by_title(candidate.title, mailto)
            if work:
                verified = openalex_work_to_candidate(work, "openalex", "", "")
                verified.verification_status = "verified_title"
                return merge_candidates(candidate, verified)
    except urllib.error.HTTPError as exc:
        candidate.notes = " | ".join(filter(None, [candidate.notes, f"OpenAlex HTTP error: {exc.code}"]))
    except urllib.error.URLError as exc:
        candidate.notes = " | ".join(filter(None, [candidate.notes, f"OpenAlex URL error: {exc.reason}"]))
    return candidate


def query_profile_candidates(config: dict[str, Any], max_results: int) -> list[Candidate]:
    profile = load_json(Path(config["profile_path"]))
    mailto = normalize_whitespace(str((config.get("retrieval") or {}).get("openalex_mailto", "")))
    candidates: list[Candidate] = []
    for interest in profile.get("interests", []):
        query = ", ".join(interest.get("keywords", []))
        for work in openalex_search(query, max_results, mailto):
            candidates.append(openalex_work_to_candidate(work, "openalex", query, ""))
    return candidates


def load_zotero_index(sqlite_path: Path) -> ZoteroIndex:
    if not sqlite_path.exists():
        return ZoteroIndex()

    query = """
    SELECT
        i.itemID,
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

    index = ZoteroIndex()
    conn = sqlite3.connect(f"file:{sqlite_path.as_posix()}?mode=ro", uri=True)
    try:
        for item_id, title, doi in conn.execute(query):
            normalized_doi = normalize_doi(doi)
            normalized_title = canonicalize_title(title)
            if normalized_doi and normalized_doi not in index.doi_to_item:
                index.doi_to_item[normalized_doi] = int(item_id)
            if normalized_title and normalized_title not in index.title_to_item:
                index.title_to_item[normalized_title] = int(item_id)
    finally:
        conn.close()
    return index


def mark_existing_zotero_items(candidates: list[Candidate], index: ZoteroIndex) -> None:
    for candidate in candidates:
        normalized_doi = normalize_doi(candidate.doi)
        normalized_title = canonicalize_title(candidate.title)
        if normalized_doi and normalized_doi in index.doi_to_item:
            candidate.already_in_zotero = True
            candidate.zotero_item_id = index.doi_to_item[normalized_doi]
            candidate.zotero_match_reason = "doi"
            continue
        if normalized_title and normalized_title in index.title_to_item:
            candidate.already_in_zotero = True
            candidate.zotero_item_id = index.title_to_item[normalized_title]
            candidate.zotero_match_reason = "title"


def select_candidates_for_export(
    candidates: list[Candidate],
    include_existing: bool,
    include_unverified: bool,
) -> list[Candidate]:
    selected: list[Candidate] = []
    for candidate in candidates:
        if candidate.already_in_zotero and not include_existing:
            continue
        if candidate.verification_status == "lead_only" and not include_unverified:
            continue
        selected.append(candidate)
    return selected


def ris_type_for_candidate(candidate: Candidate) -> str:
    publication_type = candidate.publication_type.lower()
    if "report" in publication_type:
        return "RPRT"
    if "proceed" in publication_type or "conference" in publication_type:
        return "CPAPER"
    if "book" in publication_type and "chapter" not in publication_type:
        return "BOOK"
    if "chapter" in publication_type:
        return "CHAP"
    if "thesis" in publication_type or "dissertation" in publication_type:
        return "THES"
    return "JOUR"


def render_ris(candidates: list[Candidate]) -> str:
    blocks: list[str] = []
    for candidate in candidates:
        lines = [f"TY  - {ris_type_for_candidate(candidate)}"]
        if candidate.title:
            lines.append(f"TI  - {candidate.title}")
        for author in candidate.authors:
            lines.append(f"AU  - {author}")
        if candidate.venue:
            lines.append(f"T2  - {candidate.venue}")
        if candidate.year:
            lines.append(f"PY  - {candidate.year}")
        if candidate.volume:
            lines.append(f"VL  - {candidate.volume}")
        if candidate.issue:
            lines.append(f"IS  - {candidate.issue}")
        if candidate.pages:
            lines.append(f"SP  - {candidate.pages}")
        if candidate.doi:
            lines.append(f"DO  - {candidate.doi}")
        if candidate.url:
            lines.append(f"UR  - {candidate.url}")
        if candidate.abstract:
            lines.append(f"AB  - {candidate.abstract}")
        for source in candidate.discovery_sources:
            lines.append(f"KW  - discovery:{source}")
        lines.append(f"KW  - verification:{candidate.verification_status}")
        lines.append("ER  -")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks) + ("\n" if blocks else "")


def zotero_item_type(candidate: Candidate) -> str:
    publication_type = candidate.publication_type.lower()
    if "report" in publication_type:
        return "report"
    if "conference" in publication_type or "proceed" in publication_type:
        return "conferencePaper"
    if "book" in publication_type and "chapter" not in publication_type:
        return "book"
    if "chapter" in publication_type:
        return "bookSection"
    if "thesis" in publication_type or "dissertation" in publication_type:
        return "thesis"
    if "preprint" in publication_type or "posted" in publication_type:
        return "preprint"
    return "journalArticle"


def zotero_creators(authors: list[str]) -> list[dict[str, str]]:
    creators: list[dict[str, str]] = []
    for author in authors:
        parts = normalize_whitespace(author).split()
        if not parts:
            continue
        if len(parts) == 1 or re.search(r"[\u4e00-\u9fff]", author):
            creators.append({"creatorType": "author", "name": author})
        else:
            creators.append(
                {
                    "creatorType": "author",
                    "firstName": " ".join(parts[:-1]),
                    "lastName": parts[-1],
                }
            )
    return creators


def zotero_item_payload(candidate: Candidate, config: dict[str, Any], extra_tags: list[str]) -> dict[str, Any]:
    zotero_cfg = config.get("zotero") or {}
    tags = list(zotero_cfg.get("default_tags", []))
    tags.extend(extra_tags)
    tags.extend([f"discovery:{source}" for source in candidate.discovery_sources])
    tags.append(f"verification:{candidate.verification_status}")
    unique_tags = [{"tag": tag} for tag in dict.fromkeys(tag for tag in tags if normalize_whitespace(tag))]

    extra_lines = [
        f"Discovery Sources: {', '.join(candidate.discovery_sources)}",
        f"Discovery Queries: {' || '.join(candidate.discovery_queries)}",
        f"Verification Status: {candidate.verification_status}",
        f"Verification Source: {candidate.verification_source or 'manual'}",
    ]
    if candidate.openalex_id:
        extra_lines.append(f"OpenAlex ID: {candidate.openalex_id}")
    if candidate.notes:
        extra_lines.append(f"Pipeline Notes: {candidate.notes}")

    payload: dict[str, Any] = {
        "itemType": zotero_item_type(candidate),
        "title": candidate.title,
        "creators": zotero_creators(candidate.authors),
        "date": candidate.year,
        "DOI": candidate.doi,
        "url": candidate.url,
        "abstractNote": candidate.abstract,
        "extra": "\n".join(extra_lines),
        "tags": unique_tags,
        "collections": [zotero_cfg["scope_collection"]] if zotero_cfg.get("scope_collection") else [],
    }

    if payload["itemType"] in {"journalArticle", "conferencePaper", "bookSection"}:
        payload["publicationTitle"] = candidate.venue
        payload["volume"] = candidate.volume
        payload["issue"] = candidate.issue
        payload["pages"] = candidate.pages
    elif payload["itemType"] == "preprint":
        payload["repository"] = candidate.venue
    elif payload["itemType"] == "book":
        payload["publisher"] = candidate.venue
    elif payload["itemType"] == "report":
        payload["institution"] = candidate.venue

    if candidate.language:
        payload["language"] = candidate.language

    return payload


def zotero_library_prefix(config: dict[str, Any]) -> str:
    zotero_cfg = config.get("zotero") or {}
    library_type = normalize_whitespace(str(zotero_cfg.get("library_type", "user"))).lower() or "user"
    library_id = normalize_whitespace(str(zotero_cfg.get("library_id", "")))
    if library_type not in {"user", "group"}:
        raise SystemExit(f"Unsupported Zotero library_type: {library_type}")
    if not library_id:
        raise SystemExit("Zotero library_id is required for Web API writeback.")
    return f"{library_type}s/{library_id}"


def write_candidates_to_zotero(candidates: list[Candidate], config: dict[str, Any], extra_tags: list[str]) -> None:
    zotero_cfg = config.get("zotero") or {}
    api_key = normalize_whitespace(str(zotero_cfg.get("api_key", "")))
    if not api_key:
        raise SystemExit("Zotero api_key is required for Web API writeback.")

    prefix = zotero_library_prefix(config)
    headers = {
        "Zotero-API-Version": "3",
        "Zotero-API-Key": api_key,
        "Content-Type": "application/json",
        "Zotero-Write-Token": uuid.uuid4().hex,
    }

    for start in range(0, len(candidates), 50):
        batch = candidates[start : start + 50]
        payload = [zotero_item_payload(candidate, config, extra_tags) for candidate in batch]
        url = f"{ZOTERO_API_BASE}/{prefix}/items"
        response = fetch_json(url, headers=headers, data=json.dumps(payload).encode("utf-8"))
        successful = response.get("successful", {}) or response.get("success", {})
        failed = response.get("failed", {})
        for index, candidate in enumerate(batch):
            idx = str(index)
            if idx in successful:
                candidate.zotero_write_status = "created"
                candidate.zotero_write_message = str(successful[idx])
            elif idx in failed:
                failure = failed[idx]
                candidate.zotero_write_status = "failed"
                candidate.zotero_write_message = normalize_whitespace(str(failure.get("message", "unknown failure")))
            else:
                candidate.zotero_write_status = "unknown"
                candidate.zotero_write_message = "No explicit success or failure entry returned by Zotero."


def write_markdown_summary(
    path: Path,
    run_id: str,
    candidates: list[Candidate],
    selected: list[Candidate],
    ris_path: Path | None,
) -> None:
    total = len(candidates)
    verified = sum(1 for candidate in candidates if candidate.verification_status != "lead_only")
    existing = sum(1 for candidate in candidates if candidate.already_in_zotero)
    created = sum(1 for candidate in candidates if candidate.zotero_write_status == "created")
    failed = sum(1 for candidate in candidates if candidate.zotero_write_status == "failed")

    lines = [
        "# Discovery To Zotero Run",
        "",
        f"- Run ID: `{run_id}`",
        f"- Generated: `{datetime.now().isoformat(timespec='seconds')}`",
        f"- Candidates after dedupe: {total}",
        f"- Verified by OpenAlex/title match: {verified}",
        f"- Already in Zotero: {existing}",
        f"- Selected for RIS/API: {len(selected)}",
        f"- Zotero Web API created: {created}",
        f"- Zotero Web API failed: {failed}",
    ]
    if ris_path:
        lines.append(f"- RIS export: `{ris_path}`")
    lines.extend(["", "## Candidates", ""])

    if not candidates:
        lines.append("- No candidates")
    else:
        for candidate in candidates:
            sources = ", ".join(candidate.discovery_sources) or "manual"
            status = candidate.verification_status
            zotero_state = "existing" if candidate.already_in_zotero else candidate.zotero_write_status
            doi_part = f" | DOI {candidate.doi}" if candidate.doi else ""
            lines.append(
                f"- {candidate.title or '[untitled]'} | {candidate.year or 'n.d.'} | {sources} | {status} | {zotero_state}{doi_part}"
            )

    ensure_parent(path)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Normalize literature leads from Consensus/X-MOL/Google Scholar/OpenAlex and prepare verified Zotero imports."
    )
    parser.add_argument("--config", required=True)
    parser.add_argument("--query", action="append", default=[])
    parser.add_argument("--from-profile", action="store_true")
    parser.add_argument("--lead-file", action="append", default=[])
    parser.add_argument("--lead-source", default="manual")
    parser.add_argument("--max-results", type=int, default=10)
    parser.add_argument("--output-root", default="")
    parser.add_argument("--run-label", default="literature-discovery")
    parser.add_argument("--tag", action="append", default=[])
    parser.add_argument("--skip-openalex-enrich", action="store_true")
    parser.add_argument("--skip-zotero-sqlite", action="store_true")
    parser.add_argument("--include-existing", action="store_true")
    parser.add_argument("--include-unverified", action="store_true")
    parser.add_argument("--write-zotero", action="store_true")
    return parser


def resolve_output_root(config: dict[str, Any], output_root: str) -> Path:
    if output_root:
        return Path(output_root)
    return Path(config["output_root"])


def main() -> None:
    parser = build_argument_parser()
    args = parser.parse_args()

    config = load_json(Path(args.config))
    output_root = resolve_output_root(config, args.output_root)
    run_id = f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{safe_slug(args.run_label)}"
    run_dir = output_root / "discovery-to-zotero" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    candidates: list[Candidate] = []
    mailto = normalize_whitespace(str((config.get("retrieval") or {}).get("openalex_mailto", "")))

    if args.from_profile:
        candidates.extend(query_profile_candidates(config, args.max_results))

    for query in args.query:
        for work in openalex_search(query, args.max_results, mailto):
            candidates.append(openalex_work_to_candidate(work, "openalex", query, ""))

    for lead_file in args.lead_file:
        path = Path(lead_file)
        candidates.extend(load_candidates_from_path(path, args.lead_source))

    if not candidates:
        raise SystemExit("No discovery inputs were provided. Use --query, --from-profile, and/or --lead-file.")

    deduped = deduplicate_candidates(candidates)
    enriched = [enrich_candidate(candidate, mailto, args.skip_openalex_enrich) for candidate in deduped]

    if not args.skip_zotero_sqlite:
        zotero_cfg = config.get("zotero") or {}
        sqlite_path_raw = normalize_whitespace(str(zotero_cfg.get("sqlite_path", "")))
        if sqlite_path_raw:
            sqlite_path = Path(sqlite_path_raw)
            index = load_zotero_index(sqlite_path)
            mark_existing_zotero_items(enriched, index)

    selected = select_candidates_for_export(enriched, args.include_existing, args.include_unverified)

    if args.write_zotero and selected:
        write_candidates_to_zotero(selected, config, args.tag)

    json_path = run_dir / "run.json"
    md_path = run_dir / "run.md"
    ris_path = run_dir / "zotero-import.ris"

    payload = {
        "run_id": run_id,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "selected_count": len(selected),
        "candidates": [asdict(candidate) for candidate in enriched],
    }
    ensure_parent(json_path)
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    if selected:
        ris_path.write_text(render_ris(selected), encoding="utf-8")
    else:
        ris_path = None

    write_markdown_summary(md_path, run_id, enriched, selected, ris_path)
    print(str(md_path))


if __name__ == "__main__":
    main()
