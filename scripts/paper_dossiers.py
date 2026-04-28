#!/usr/bin/env python
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml


ACADEMIC_PAPER_FOLDER = Path("02_Literature") / "Papers"
DOSSIER_ROOT = Path("02_Literature") / "Paper-Dossiers"
FRONTMATTER_RE = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n?", flags=re.DOTALL)
HEADING_RE = re.compile(r"(?m)^#\s+(.+?)\s*$")
WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")
YEAR_RE = re.compile(r"(19|20)\d{2}")
NON_WORD_RE = re.compile(r"[^a-z0-9]+")


@dataclass
class NoteRecord:
    path: Path
    rel_path: str
    frontmatter: dict[str, Any]
    title: str
    normalized_title: str


@dataclass
class PaperDossier:
    folder_name: str
    dossier_rel_path: str
    title: str
    title_original: str
    year: str
    venue: str
    doi: str
    zotero_key: str
    authors: list[str]
    status: str
    reading_stage: str
    source_tag: str
    tags: list[str]
    paper_note_rel_path: str
    paper_note_rel_paths: list[str]
    zotero_note_rel_path: str
    legacy_note_rel_path: str
    translated_note_rel_path: str
    extract_rel_path: str
    translation_template_rel_path: str
    copied_pdf_rel_path: str
    source_pdf_rel_path: str
    source_pdf_external_path: str


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def default_config(vault_root: Path) -> dict[str, Any]:
    return {
        "vault_root": str(vault_root),
        "obsidian": {
            "paper_folder": "02_Papers",
            "zotero_folder": "12_Zotero",
            "attachment_folder": "08_Attachments",
            "writing_folder": "06_Writing",
        },
        "translation": {
            "render": {
                "translated_folder_name": "translated-papers",
            }
        },
    }


def normalize_whitespace(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def sanitize(value: Any) -> str:
    return normalize_whitespace(value).replace('"', "'")


def to_portable_path(value: str | Path) -> str:
    return str(value).replace("\\", "/")


def canonicalize_title(value: Any) -> str:
    source = normalize_whitespace(value).lower()
    return NON_WORD_RE.sub(" ", source).strip()


def normalize_doi(value: Any) -> str:
    doi = normalize_whitespace(value).lower()
    if not doi:
        return ""
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:", "doi.org/"):
        if doi.startswith(prefix):
            doi = doi[len(prefix) :]
    return doi.strip()


def frontmatter_payload(text: str) -> dict[str, Any]:
    frontmatter, _ = split_frontmatter(text)
    return frontmatter


def strip_leading_bom(text: str) -> str:
    return text[1:] if text.startswith("\ufeff") else text


def parse_frontmatter_block(payload: str) -> dict[str, Any]:
    try:
        loaded = yaml.safe_load(payload) or {}
        return loaded if isinstance(loaded, dict) else {}
    except yaml.YAMLError:
        return fallback_frontmatter_payload(payload)


def merge_frontmatter(existing: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    merged = dict(existing)
    for key, value in incoming.items():
        if isinstance(value, list):
            current = merged.get(key, [])
            merged_list: list[str] = []
            for item in (current if isinstance(current, list) else [current]) + value:
                cleaned = normalize_whitespace(item)
                if cleaned and cleaned not in merged_list:
                    merged_list.append(cleaned)
            if merged_list:
                merged[key] = merged_list
            continue
        if isinstance(value, str):
            cleaned = normalize_whitespace(value)
            if cleaned:
                merged[key] = value
            continue
        if value is not None:
            merged[key] = value
    return merged


def split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    remaining = strip_leading_bom(text)
    merged: dict[str, Any] = {}
    matched = False
    while True:
        match = FRONTMATTER_RE.match(remaining)
        if not match:
            break
        matched = True
        merged = merge_frontmatter(merged, parse_frontmatter_block(match.group(1)))
        remaining = strip_leading_bom(remaining[match.end() :])
    return (merged if matched else {}), remaining


def strip_yaml_quotes(value: str) -> str:
    cleaned = value.strip()
    if len(cleaned) >= 2 and cleaned[0] == cleaned[-1] and cleaned[0] in {'"', "'"}:
        return cleaned[1:-1]
    return cleaned


def fallback_frontmatter_payload(payload: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    current_list_key = ""
    for raw_line in payload.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped:
            continue
        if line.startswith("  - ") and current_list_key:
            result.setdefault(current_list_key, []).append(strip_yaml_quotes(stripped[2:].strip()))
            continue
        if ":" not in line:
            current_list_key = ""
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            current_list_key = ""
            continue
        if not value:
            result[key] = []
            current_list_key = key
            continue
        result[key] = strip_yaml_quotes(value)
        current_list_key = ""
    return result


def pick_title(path: Path, text: str, frontmatter: dict[str, Any]) -> str:
    for key in ("title_display", "title", "title_en", "title_zh", "citation_title"):
        value = normalize_whitespace(frontmatter.get(key))
        if value:
            return value
    heading = HEADING_RE.search(text)
    if heading:
        return normalize_whitespace(heading.group(1))
    return path.stem


def coerce_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [normalize_whitespace(item) for item in value if normalize_whitespace(item)]
    if isinstance(value, str):
        cleaned = normalize_whitespace(value)
        return [cleaned] if cleaned else []
    return []


def parse_wikilink_target(raw: str) -> str:
    match = WIKILINK_RE.search(str(raw))
    if not match:
        return ""
    target = match.group(1).split("|", 1)[0].strip()
    if not target:
        return ""
    if not target.lower().endswith(".md"):
        target += ".md"
    return target.replace("\\", "/")


def path_within_vault(vault_root: Path, value: str | Path) -> str:
    raw = normalize_whitespace(value)
    if not raw:
        return ""
    parsed_wikilink = parse_wikilink_target(raw)
    if parsed_wikilink:
        return parsed_wikilink

    portable = raw.replace("\\", "/")
    candidate = Path(portable)
    if candidate.is_absolute():
        try:
            return candidate.resolve().relative_to(vault_root.resolve()).as_posix()
        except ValueError:
            return ""

    relative = portable.lstrip("./")
    if relative:
        candidate = (vault_root / Path(relative)).resolve()
        try:
            return candidate.relative_to(vault_root.resolve()).as_posix()
        except ValueError:
            return ""
    return ""


def existing_relative_path(vault_root: Path, value: str | Path) -> str:
    rel_path = path_within_vault(vault_root, value)
    if not rel_path:
        return ""
    return rel_path if (vault_root / Path(rel_path)).exists() else ""


def external_path(value: str | Path, vault_root: Path) -> str:
    raw = normalize_whitespace(value)
    if not raw:
        return ""
    if existing_relative_path(vault_root, raw):
        return ""
    return to_portable_path(raw)


def vault_link(rel_path: str, label: str = "") -> str:
    target = rel_path.replace("\\", "/")
    if target.lower().endswith(".md"):
        target = target[:-3]
    return f"[[{target}|{label}]]" if label else f"[[{target}]]"


def render_link_or_missing(rel_path: str, label: str = "") -> str:
    return vault_link(rel_path, label) if rel_path else "未找到"


def render_path_or_missing(value: str) -> str:
    return f"`{value}`" if value else "未找到"


def paper_note_directory(vault_root: Path, config: dict[str, Any]) -> Path:
    obs = config.get("obsidian", {})
    configured_paper_folder = Path(str(obs.get("paper_folder", "02_Papers")))
    academic_dir = vault_root / ACADEMIC_PAPER_FOLDER
    template_exists = (vault_root / "00_System" / "01_Templates" / "Literature Note.md").exists()
    if academic_dir.exists() or template_exists:
        return academic_dir
    return vault_root / configured_paper_folder


def load_note_record(path: Path, vault_root: Path) -> NoteRecord:
    text = path.read_text(encoding="utf-8", errors="replace")
    frontmatter, body = split_frontmatter(text)
    title = pick_title(path, body, frontmatter)
    return NoteRecord(
        path=path,
        rel_path=path.relative_to(vault_root).as_posix(),
        frontmatter=frontmatter,
        title=title,
        normalized_title=canonicalize_title(title),
    )


def is_synthetic_example_note(frontmatter: dict[str, Any]) -> bool:
    explicit_status = normalize_whitespace(frontmatter.get("library_status"))
    if explicit_status == "synthetic-example":
        return True
    doi = normalize_whitespace(frontmatter.get("doi")).lower()
    url = normalize_whitespace(frontmatter.get("url")).lower()
    venue = normalize_whitespace(frontmatter.get("venue")).lower()
    return (
        "example-doi" in doi
        or "example.org" in url
        or venue == "journal of optical imaging methods"
    )


def scan_records(folder: Path, vault_root: Path, recursive: bool = False) -> list[NoteRecord]:
    if not folder.exists():
        return []
    pattern = "**/*.md" if recursive else "*.md"
    records: list[NoteRecord] = []
    for path in sorted(folder.glob(pattern)):
        if path.name.startswith("_"):
            continue
        records.append(load_note_record(path, vault_root))
    return records


def load_zotero_records(vault_root: Path, config: dict[str, Any]) -> list[NoteRecord]:
    obs = config.get("obsidian", {})
    folder = vault_root / str(obs.get("zotero_folder", "12_Zotero")) / "04_Item-Backfills"
    return scan_records(folder, vault_root, recursive=False)


def load_translation_records(vault_root: Path, config: dict[str, Any]) -> list[NoteRecord]:
    obs = config.get("obsidian", {})
    translation_cfg = config.get("translation", {}).get("render", {})
    translated_folder_name = str(translation_cfg.get("translated_folder_name", "translated-papers"))
    candidates = [
        vault_root / str(obs.get("writing_folder", "06_Writing")) / "translated-papers",
        vault_root / str(obs.get("attachment_folder", "08_Attachments")) / translated_folder_name,
    ]
    records: list[NoteRecord] = []
    seen: set[Path] = set()
    for folder in candidates:
        for record in scan_records(folder, vault_root, recursive=True):
            if record.path in seen:
                continue
            seen.add(record.path)
            records.append(record)
    return records


def index_by_key(records: list[NoteRecord], key_name: str, normalizer) -> dict[str, list[NoteRecord]]:
    mapping: dict[str, list[NoteRecord]] = {}
    for record in records:
        key = normalizer(record.frontmatter.get(key_name))
        if not key:
            continue
        mapping.setdefault(key, []).append(record)
    return mapping


def index_translations_by_source(
    records: list[NoteRecord], vault_root: Path
) -> tuple[dict[str, list[NoteRecord]], dict[str, list[NoteRecord]], dict[str, list[NoteRecord]]]:
    by_source_paper: dict[str, list[NoteRecord]] = {}
    by_source_pdf: dict[str, list[NoteRecord]] = {}
    by_title: dict[str, list[NoteRecord]] = {}
    for record in records:
        source_paper = existing_relative_path(vault_root, str(record.frontmatter.get("source_paper_note", "")))
        if source_paper:
            by_source_paper.setdefault(source_paper, []).append(record)
        source_pdf = existing_relative_path(vault_root, str(record.frontmatter.get("source_pdf", "")))
        if source_pdf:
            by_source_pdf.setdefault(source_pdf, []).append(record)
        if record.normalized_title:
            by_title.setdefault(record.normalized_title, []).append(record)
    return by_source_paper, by_source_pdf, by_title


def pick_candidate(candidates: list[NoteRecord], year: str) -> NoteRecord | None:
    if not candidates:
        return None
    if year:
        for candidate in candidates:
            candidate_year = normalize_whitespace(candidate.frontmatter.get("year"))
            if candidate_year == year:
                return candidate
            date_match = YEAR_RE.search(normalize_whitespace(candidate.frontmatter.get("date")))
            if date_match and date_match.group(0) == year:
                return candidate
    return candidates[0]


def resolve_legacy_note_rel_path(vault_root: Path, paper_note: NoteRecord) -> str:
    explicit = existing_relative_path(vault_root, str(paper_note.frontmatter.get("legacy_source_note", "")))
    if explicit:
        return explicit
    legacy_slug = normalize_whitespace(paper_note.frontmatter.get("title_legacy_slug"))
    if legacy_slug:
        candidate = vault_root / "02_Papers" / f"{legacy_slug}.md"
        if candidate.exists():
            return candidate.relative_to(vault_root).as_posix()
    return ""


def available_assets(dossier: PaperDossier) -> list[str]:
    assets = ["主笔记"]
    if dossier.zotero_note_rel_path:
        assets.append("Zotero")
    if dossier.extract_rel_path:
        assets.append("原文")
    if dossier.translated_note_rel_path:
        assets.append("翻译")
    if dossier.legacy_note_rel_path:
        assets.append("解析")
    if dossier.copied_pdf_rel_path or dossier.source_pdf_rel_path or dossier.source_pdf_external_path:
        assets.append("PDF")
    return assets


def first_non_empty(values: list[str]) -> str:
    for value in values:
        if normalize_whitespace(value):
            return value
    return ""


def merge_unique(values: list[str]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = normalize_whitespace(value)
        key = cleaned.casefold()
        if not cleaned or key in seen:
            continue
        seen.add(key)
        merged.append(cleaned)
    return merged


def paper_group_key(note: NoteRecord) -> str:
    doi = normalize_doi(note.frontmatter.get("doi"))
    if doi:
        return f"doi:{doi}"
    zotero_key = normalize_whitespace(note.frontmatter.get("zotero_key"))
    if zotero_key:
        return f"zotero:{zotero_key}"
    if note.normalized_title:
        return f"title:{note.normalized_title}"
    return f"path:{note.rel_path.lower()}"


def paper_note_score(note: NoteRecord) -> tuple[int, int, str]:
    frontmatter = note.frontmatter
    score = 0
    for key, weight in (
        ("translated_note_path", 4),
        ("legacy_source_note", 2),
        ("extract_path", 1),
        ("zotero_key", 1),
        ("copied_pdf", 1),
        ("source_pdf", 1),
    ):
        if normalize_whitespace(frontmatter.get(key)):
            score += weight
    return (score, len(note.path.stem), note.rel_path.lower())


def build_dossiers(config: dict[str, Any]) -> list[PaperDossier]:
    vault_root = Path(config["vault_root"])
    paper_dir = paper_note_directory(vault_root, config)
    paper_notes = [
        record
        for record in scan_records(paper_dir, vault_root, recursive=False)
        if not is_synthetic_example_note(record.frontmatter)
    ]
    zotero_records = load_zotero_records(vault_root, config)
    translation_records = load_translation_records(vault_root, config)

    zotero_by_key = index_by_key(zotero_records, "zotero_key", normalize_whitespace)
    zotero_by_doi = index_by_key(zotero_records, "doi", normalize_doi)
    zotero_by_title: dict[str, list[NoteRecord]] = {}
    for record in zotero_records:
        if record.normalized_title:
            zotero_by_title.setdefault(record.normalized_title, []).append(record)

    translations_by_source_paper, translations_by_source_pdf, translations_by_title = index_translations_by_source(
        translation_records,
        vault_root,
    )

    grouped_notes: dict[str, list[NoteRecord]] = {}
    for paper_note in paper_notes:
        grouped_notes.setdefault(paper_group_key(paper_note), []).append(paper_note)

    dossiers: list[PaperDossier] = []
    for group in grouped_notes.values():
        ordered_notes = sorted(group, key=paper_note_score, reverse=True)
        primary_note = ordered_notes[0]

        year = first_non_empty([normalize_whitespace(note.frontmatter.get("year")) for note in ordered_notes])
        zotero_key = first_non_empty([normalize_whitespace(note.frontmatter.get("zotero_key")) for note in ordered_notes])
        doi = first_non_empty([normalize_doi(note.frontmatter.get("doi")) for note in ordered_notes])
        title_original = first_non_empty([normalize_whitespace(note.frontmatter.get("title")) for note in ordered_notes]) or primary_note.title
        title = (
            first_non_empty([normalize_whitespace(note.frontmatter.get("title_display")) for note in ordered_notes])
            or title_original
            or primary_note.title
        )

        zotero_note = None
        if zotero_key:
            zotero_note = pick_candidate(zotero_by_key.get(zotero_key, []), year)
        if zotero_note is None and doi:
            zotero_note = pick_candidate(zotero_by_doi.get(doi, []), year)
        if zotero_note is None and primary_note.normalized_title:
            zotero_note = pick_candidate(zotero_by_title.get(primary_note.normalized_title, []), year)

        legacy_rel_path = first_non_empty([resolve_legacy_note_rel_path(vault_root, note) for note in ordered_notes])
        copied_pdf_rel_path = first_non_empty(
            [existing_relative_path(vault_root, str(note.frontmatter.get("copied_pdf", ""))) for note in ordered_notes]
        )
        source_pdf_rel_path = first_non_empty(
            [existing_relative_path(vault_root, str(note.frontmatter.get("source_pdf", ""))) for note in ordered_notes]
        )
        source_pdf_external_path = first_non_empty(
            [external_path(str(note.frontmatter.get("source_pdf", "")), vault_root) for note in ordered_notes]
        )
        extract_rel_path = first_non_empty(
            [existing_relative_path(vault_root, str(note.frontmatter.get("extract_path", ""))) for note in ordered_notes]
        )
        translated_note_rel_path = first_non_empty(
            [existing_relative_path(vault_root, str(note.frontmatter.get("translated_note_path", ""))) for note in ordered_notes]
        )
        translation_template_rel_path = existing_relative_path(
            vault_root,
            first_non_empty([str(note.frontmatter.get("translation_template_path", "")) for note in ordered_notes]),
        )

        if not translated_note_rel_path:
            translation_candidate = None
            legacy_candidates = [resolve_legacy_note_rel_path(vault_root, note) for note in ordered_notes]
            for legacy_candidate in legacy_candidates:
                if not legacy_candidate:
                    continue
                translation_candidate = pick_candidate(translations_by_source_paper.get(legacy_candidate, []), year)
                if translation_candidate is not None:
                    break
            if translation_candidate is None:
                for source_pdf_key in merge_unique(
                    [
                        existing_relative_path(vault_root, str(note.frontmatter.get("copied_pdf", "")))
                        or existing_relative_path(vault_root, str(note.frontmatter.get("source_pdf", "")))
                        for note in ordered_notes
                    ]
                ):
                    translation_candidate = pick_candidate(translations_by_source_pdf.get(source_pdf_key, []), year)
                    if translation_candidate is not None:
                        break
            if translation_candidate is None:
                for note in ordered_notes:
                    if not note.normalized_title:
                        continue
                    translation_candidate = pick_candidate(translations_by_title.get(note.normalized_title, []), year)
                    if translation_candidate is not None:
                        break
            if translation_candidate is not None:
                translated_note_rel_path = translation_candidate.rel_path

        effective_zotero_key = zotero_key
        if not effective_zotero_key and zotero_note is not None:
            effective_zotero_key = normalize_whitespace(zotero_note.frontmatter.get("zotero_key"))
        effective_doi = doi
        if not effective_doi and zotero_note is not None:
            effective_doi = normalize_doi(zotero_note.frontmatter.get("doi"))

        folder_name = primary_note.path.stem
        dossier_rel_path = (DOSSIER_ROOT / folder_name / "_Index.md").as_posix()
        dossiers.append(
            PaperDossier(
                folder_name=folder_name,
                dossier_rel_path=dossier_rel_path,
                title=title,
                title_original=title_original,
                year=year,
                venue=first_non_empty([normalize_whitespace(note.frontmatter.get("venue")) for note in ordered_notes]),
                doi=effective_doi,
                zotero_key=effective_zotero_key,
                authors=merge_unique(
                    [author for note in ordered_notes for author in coerce_list(note.frontmatter.get("authors"))]
                ),
                status=first_non_empty([normalize_whitespace(note.frontmatter.get("status")) for note in ordered_notes]),
                reading_stage=first_non_empty(
                    [normalize_whitespace(note.frontmatter.get("reading_stage")) for note in ordered_notes]
                ),
                source_tag=first_non_empty([normalize_whitespace(note.frontmatter.get("source_tag")) for note in ordered_notes]),
                tags=merge_unique([tag for note in ordered_notes for tag in coerce_list(note.frontmatter.get("tags"))]),
                paper_note_rel_path=primary_note.rel_path,
                paper_note_rel_paths=[note.rel_path for note in ordered_notes],
                zotero_note_rel_path=zotero_note.rel_path if zotero_note else "",
                legacy_note_rel_path=legacy_rel_path,
                translated_note_rel_path=translated_note_rel_path,
                extract_rel_path=extract_rel_path,
                translation_template_rel_path=translation_template_rel_path,
                copied_pdf_rel_path=copied_pdf_rel_path,
                source_pdf_rel_path=source_pdf_rel_path,
                source_pdf_external_path=source_pdf_external_path,
            )
        )
    return dossiers


def dossier_sort_key(dossier: PaperDossier) -> tuple[int, str, str]:
    try:
        year_value = int(dossier.year)
    except ValueError:
        year_value = -1
    return (-year_value, canonicalize_title(dossier.title), dossier.paper_note_rel_path.lower())


def build_dossier_note(dossier: PaperDossier) -> str:
    generated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    authors = "、".join(dossier.authors) if dossier.authors else "未补充"
    tags = "、".join(dossier.tags) if dossier.tags else "未补充"
    asset_summary = " / ".join(available_assets(dossier))
    lines = [
        "---",
        'type: "paper-dossier"',
        f'title: "{sanitize(dossier.title)}"',
        f'title_original: "{sanitize(dossier.title_original)}"',
        f'year: "{sanitize(dossier.year)}"',
        f'doi: "{sanitize(dossier.doi)}"',
        f'zotero_key: "{sanitize(dossier.zotero_key)}"',
        f'paper_note_path: "{sanitize(dossier.paper_note_rel_path)}"',
        f'updated: "{generated}"',
        "---",
        "",
        f"# {dossier.title}",
        "",
        f"- 档案目录：`{DOSSIER_ROOT.as_posix()}/{dossier.folder_name}`",
        f"- 聚合时间：`{generated}`",
        f"- 可用材料：`{asset_summary}`",
        "- 这个目录是论文聚合入口，不复制正文，只把同一篇论文的主笔记、原文、翻译、解析与 Zotero 入口收拢到一处。",
        "",
        "## 快速入口",
        "",
        f"- 文献主笔记：{render_link_or_missing(dossier.paper_note_rel_path, '主笔记')}",
        f"- Zotero 回填：{render_link_or_missing(dossier.zotero_note_rel_path, 'Zotero 回填')}",
        f"- 精炼解析：{render_link_or_missing(dossier.legacy_note_rel_path, '精炼解析')}",
        f"- 中文翻译：{render_link_or_missing(dossier.translated_note_rel_path, '中文翻译')}",
        f"- 原文提取：{render_link_or_missing(dossier.extract_rel_path, '原文提取')}",
        f"- 手工翻译模板：{render_link_or_missing(dossier.translation_template_rel_path, '翻译模板')}",
        f"- 归档 PDF：{render_link_or_missing(dossier.copied_pdf_rel_path or dossier.source_pdf_rel_path, 'PDF')}",
        f"- 外部原始 PDF：{render_path_or_missing(dossier.source_pdf_external_path)}",
        "",
        "## 元数据",
        "",
        f"- 题名：{dossier.title_original or dossier.title}",
        f"- 年份：{dossier.year or '未补充'}",
        f"- 作者：{authors}",
        f"- 期刊 / 会议：{dossier.venue or '未补充'}",
        f"- DOI：{dossier.doi or '未补充'}",
        f"- Zotero Key：{dossier.zotero_key or '未补充'}",
        f"- 阅读状态：{dossier.status or '未补充'}",
        f"- 阅读阶段：{dossier.reading_stage or '未补充'}",
        f"- 来源标签：{dossier.source_tag or '未补充'}",
        f"- 标签：{tags}",
        "",
        "## 相关笔记变体",
        "",
    ]
    alternate_paper_notes = [
        rel_path
        for rel_path in dossier.paper_note_rel_paths
        if rel_path != dossier.paper_note_rel_path
    ]
    if alternate_paper_notes:
        for rel_path in alternate_paper_notes:
            lines.append(f"- {vault_link(rel_path)}")
    else:
        lines.append("- 无")
    lines.extend(
        [
            "",
        "## 使用建议",
        "",
        "- 先从这里判断一篇论文当前已经有哪些材料，再点进对应入口继续读。",
        "- 如果以后补了翻译、提取或 Zotero 同步，重新运行论文档案重建脚本即可把这里自动补齐。",
        "",
        ]
    )
    return "\n".join(lines)


def build_root_index(dossiers: list[PaperDossier]) -> str:
    sorted_dossiers = sorted(dossiers, key=dossier_sort_key)
    zotero_count = sum(1 for dossier in dossiers if dossier.zotero_note_rel_path)
    extract_count = sum(1 for dossier in dossiers if dossier.extract_rel_path)
    translation_count = sum(1 for dossier in dossiers if dossier.translated_note_rel_path)
    legacy_count = sum(1 for dossier in dossiers if dossier.legacy_note_rel_path)
    lines = [
        "# 论文档案索引",
        "",
        f"- 目录：`{DOSSIER_ROOT.as_posix()}`",
        f"- 档案数：`{len(dossiers)}`",
        f"- 已关联 Zotero：`{zotero_count}`",
        f"- 已关联原文提取：`{extract_count}`",
        f"- 已关联翻译稿：`{translation_count}`",
        f"- 已关联解析笔记：`{legacy_count}`",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`",
        "- 排序逻辑：按年份从新到旧，再按题名稳定排序。",
        "- 使用方法：先开这页找到论文，再进入对应子目录 `_Index`，不要再去分别猜 Zotero、翻译或原文放在哪。",
        "",
    ]
    for dossier in sorted_dossiers:
        assets = " / ".join(available_assets(dossier))
        year = dossier.year or "n.d."
        lines.append(f"- {vault_link(dossier.dossier_rel_path, dossier.title)} | {year} | {assets}")
    lines.append("")
    return "\n".join(lines)


def build_payload(config: dict[str, Any]) -> tuple[dict[str, str], list[PaperDossier]]:
    dossiers = build_dossiers(config)
    payload = {
        DOSSIER_ROOT.joinpath("_Index.md").as_posix(): build_root_index(dossiers),
    }
    for dossier in dossiers:
        payload[dossier.dossier_rel_path] = build_dossier_note(dossier)
    return payload, dossiers


def write_payload(base_root: Path, payload: dict[str, str]) -> list[str]:
    written: list[str] = []
    for rel_path, content in payload.items():
        target = base_root / Path(rel_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content.rstrip() + "\n", encoding="utf-8")
        written.append(rel_path)
    return written


def sync_dossiers(config: dict[str, Any]) -> list[str]:
    vault_root = Path(config["vault_root"])
    payload, _ = build_payload(config)
    return write_payload(vault_root, payload)


def write_run_report(path: Path, dossiers: list[PaperDossier], written: list[str]) -> None:
    lines = [
        "# Paper Dossier Rebuild",
        "",
        f"- Generated: `{datetime.now().isoformat(timespec='seconds')}`",
        f"- Dossiers: {len(dossiers)}",
        f"- Files written: {len(written)}",
        f"- With Zotero: {sum(1 for dossier in dossiers if dossier.zotero_note_rel_path)}",
        f"- With Extract: {sum(1 for dossier in dossiers if dossier.extract_rel_path)}",
        f"- With Translation: {sum(1 for dossier in dossiers if dossier.translated_note_rel_path)}",
        f"- With Analysis: {sum(1 for dossier in dossiers if dossier.legacy_note_rel_path)}",
        "",
        "## Files",
        "",
    ]
    for rel_path in written:
        lines.append(f"- {rel_path}")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def generate_bundle(vault_root: Path, output_root: Path, run_label: str, config: dict[str, Any] | None = None) -> Path:
    effective_config = config or default_config(vault_root)
    payload, dossiers = build_payload(effective_config)
    run_id = f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{run_label}"
    run_dir = output_root / "vault-reorg" / run_id
    bundle_root = run_dir / "bundle"
    written = write_payload(bundle_root, payload)
    write_run_report(run_dir / "run.md", dossiers, written)
    return run_dir
