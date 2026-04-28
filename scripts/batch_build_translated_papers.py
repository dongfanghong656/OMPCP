#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import re
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import requests
import yaml

import batch_seed_pdf_folder as batch_seed
import paper_dossiers
import translate_paper
from secure_config import load_json

requests.packages.urllib3.disable_warnings()  # type: ignore[attr-defined]


GOOGLE_TRANSLATE_URL = "https://translate.googleapis.com/translate_a/single"
SUMMARY_EXTRACT_NAMES = {"web-summary-extract.md"}
NOISE_PATTERNS = (
    re.compile(r"^Get PDF$", re.I),
    re.compile(r"^Email$", re.I),
    re.compile(r"^Share$", re.I),
    re.compile(r"^Get Citation$", re.I),
    re.compile(r"^Citation alert$", re.I),
    re.compile(r"^Save article$", re.I),
    re.compile(r"^PDF Article$", re.I),
    re.compile(r"^Article Outline$", re.I),
    re.compile(r"^Back to Top$", re.I),
    re.compile(r"^Open Access$", re.I),
    re.compile(r"^Download Full Size \| PDF$", re.I),
    re.compile(r"^Download Full Size$", re.I),
    re.compile(r"^Top$", re.I),
    re.compile(r"^More Like This$", re.I),
    re.compile(r"^Related Topics$", re.I),
    re.compile(r"^About this Article$", re.I),
    re.compile(r"^History$", re.I),
    re.compile(r"^Figures \(\d+\)$", re.I),
    re.compile(r"^Suppl\. Mat\.", re.I),
    re.compile(r"^Equations \(\d+\)$", re.I),
    re.compile(r"^References \(\d+\)$", re.I),
    re.compile(r"^Cited By \(\d+\)$", re.I),
    re.compile(r"^Metrics$", re.I),
    re.compile(r"^Author manuscript; available in PMC", re.I),
    re.compile(r"^PMCID:", re.I),
    re.compile(r"^PMID:", re.I),
    re.compile(r"^Crossref$", re.I),
    re.compile(r"^SEE PROFILE$", re.I),
    re.compile(r"^View project$", re.I),
    re.compile(r"^\d+\s+PUBLICATIONS\b", re.I),
    re.compile(r"^\d+\s+CITATIONS\b", re.I),
    re.compile(r"^\d+\s+authors,\s+including:", re.I),
    re.compile(r"^Some\s*of the authors of this publication are also working on these related projects:", re.I),
    re.compile(r"^PubReader$", re.I),
    re.compile(r"^Print View$", re.I),
    re.compile(r"^Cite this Page$", re.I),
    re.compile(r"^Add to Collections$", re.I),
    re.compile(r"^Save$", re.I),
)
STOP_MARKERS = (
    "Previous Article",
    "Publishing Home",
    "Privacy | Terms of Use",
    "Our website uses cookies",
    "Follow NCBI",
    "View publication stats",
    "Downloaded from",
)
HEADING_WORDS = {
    "abstract",
    "introduction",
    "method",
    "methods",
    "results",
    "discussion",
    "discussions",
    "conclusion",
    "conclusions",
    "acknowledgments",
    "acknowledgements",
    "references",
    "references and links",
    "supplementary material",
}
SECTION_RE = re.compile(r"^(\d+)(\.\d+)*\.?\s+\S")
PAGE_HEADING_RE = re.compile(r"^##\s+Page\s+\d+\s*$", re.I)
ONLY_SYMBOLS_RE = re.compile(r"^[^\w\u4e00-\u9fffA-Za-z]+$")
BLOCK_MARKER_RE = re.compile(r"\[\[\[\s*([A-Za-z0-9_-]+)\s*\]\]\]")


@dataclass
class BuildRecord:
    note_path: str
    title: str
    status: str
    extract_path: str
    translated_note_path: str
    translation_template_path: str
    source_pdf: str
    message: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build translated-papers notes from existing paper notes.")
    parser.add_argument("--config", required=True)
    parser.add_argument("--manifest", required=True, help="JSON list of note targets with optional fallback_pdf.")
    parser.add_argument("--report-out", default="")
    parser.add_argument("--target-language", default="zh-CN")
    parser.add_argument("--batch-chars", type=int, default=1400)
    parser.add_argument("--skip-existing", action="store_true")
    return parser.parse_args()


def read_manifest(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, list):
        raise ValueError("Manifest must be a JSON array.")
    return [item for item in payload if isinstance(item, dict)]


def dump_frontmatter(data: dict[str, Any]) -> str:
    return "---\n" + yaml.safe_dump(data, sort_keys=False, allow_unicode=True).strip() + "\n---\n"


def resolve_note_path(vault_root: Path, raw_value: str) -> Path:
    portable = str(raw_value).replace("\\", "/")
    path = Path(portable)
    if path.is_absolute():
        return path
    return vault_root / portable


def resolve_optional_path(raw_value: str) -> Path | None:
    portable = str(raw_value or "").replace("\\", "/").strip()
    if not portable:
        return None
    return Path(portable)


def resolve_note_pdf(frontmatter: dict[str, Any], vault_root: Path) -> Path | None:
    for key in ("source_pdf", "copied_pdf"):
        raw = paper_dossiers.normalize_whitespace(frontmatter.get(key))
        if not raw:
            continue
        candidate = Path(raw.replace("\\", "/"))
        if not candidate.is_absolute():
            candidate = vault_root / candidate
        if candidate.exists() and candidate.suffix.lower() == ".pdf":
            return candidate
    return None


def choose_extract(
    frontmatter: dict[str, Any],
    fallback_pdf: Path | None,
    fallback_extract: Path | None,
    vault_root: Path,
) -> tuple[Path, Path | None]:
    if fallback_extract is not None and fallback_extract.exists():
        return fallback_extract, None

    note_pdf = resolve_note_pdf(frontmatter, vault_root)
    if note_pdf is not None:
        reader, page_texts = batch_seed.extract_page_texts(note_pdf)
        title = paper_dossiers.normalize_whitespace(frontmatter.get("title")) or note_pdf.stem
        generated = batch_seed.write_pypdf_extract(vault_root, note_pdf, title, page_texts)
        return generated, generated

    raw_extract = paper_dossiers.normalize_whitespace(frontmatter.get("extract_path"))
    existing = None
    if raw_extract:
        existing = Path(raw_extract.replace("\\", "/"))
        if not existing.is_absolute():
            existing = vault_root / existing
        if not existing.exists():
            existing = None

    generated = None
    if existing is not None and existing.name not in SUMMARY_EXTRACT_NAMES:
        return existing, generated

    if fallback_pdf is not None:
        reader, page_texts = batch_seed.extract_page_texts(fallback_pdf)
        title = paper_dossiers.normalize_whitespace(frontmatter.get("title")) or fallback_pdf.stem
        generated = batch_seed.write_pypdf_extract(vault_root, fallback_pdf, title, page_texts)
        return generated, generated

    if existing is not None:
        return existing, generated

    raise FileNotFoundError("No usable extract or fallback PDF available.")


def strip_extract_scaffolding(text: str) -> str:
    lines = text.splitlines()
    cleaned: list[str] = []
    for line in lines:
        if line.startswith("# "):
            continue
        if line.startswith("- Source PDF:"):
            continue
        if PAGE_HEADING_RE.match(line):
            cleaned.append("")
            continue
        cleaned.append(line)
    return "\n".join(cleaned)


def line_is_noise(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    return any(pattern.match(stripped) for pattern in NOISE_PATTERNS)


def find_flexible_marker(text: str, marker: str) -> int:
    tokens = [re.escape(token) for token in marker.split() if token]
    if not tokens:
        return -1
    pattern = re.compile(r"\s*".join(tokens), re.I | re.S)
    match = pattern.search(text)
    return match.start() if match else -1


def heading_level_for_line(line: str) -> int | None:
    text = line.strip()
    lowered = text.lower().rstrip(":")
    if lowered in HEADING_WORDS:
        return 2
    match = SECTION_RE.match(text)
    if not match:
        return None
    dots = text.split(" ", 1)[0].count(".")
    return min(2 + dots, 6)


def normalize_extract_markdown(
    source_md: Path,
    title: str,
    output_path: Path,
    *,
    start_marker: str = "",
    end_marker: str = "",
) -> Path:
    raw = source_md.read_text(encoding="utf-8", errors="replace")
    raw = strip_extract_scaffolding(raw)

    found_start = False
    explicit_start = start_marker.strip()
    if explicit_start:
        idx = find_flexible_marker(raw, explicit_start)
        if idx != -1:
            raw = raw[idx:]
            found_start = True

    explicit_end = end_marker.strip()
    if explicit_end:
        idx = find_flexible_marker(raw, explicit_end)
        if idx != -1:
            raw = raw[:idx]

    for marker in STOP_MARKERS:
        idx = raw.find(marker)
        if idx != -1:
            raw = raw[:idx]
            break

    lines = raw.splitlines()
    title_keywords = {
        token
        for token in re.findall(r"[A-Za-z]+", title.lower())
        if len(token) >= 5 and token not in {"using", "study", "human", "three", "high"}
    }
    start = 0
    if not found_start:
        for idx, line in enumerate(lines):
            stripped = line.strip()
            if stripped.lower() == "abstract":
                start = idx
                found_start = True
                break
            if SECTION_RE.match(stripped):
                start = idx
                found_start = True
                break
    if not found_start:
        for idx, line in enumerate(lines):
            stripped = line.strip()
            lowered = stripped.lower()
            if line_is_noise(stripped):
                continue
            keyword_hits = sum(1 for token in title_keywords if token in lowered)
            if len(stripped) >= 80 and keyword_hits >= max(2, min(3, len(title_keywords))):
                start = idx
                found_start = True
                break
    if not found_start:
        for idx, line in enumerate(lines):
            stripped = line.strip()
            if line_is_noise(stripped):
                continue
            if len(stripped) < 90:
                continue
            if not re.search(r"[A-Za-z]", stripped):
                continue
            if stripped.endswith((".", ".”", '".')):
                start = idx
                found_start = True
                break
    lines = lines[start:]

    normalized_lines: list[str] = [f"# {title}", ""]
    paragraph_parts: list[str] = []

    def flush_paragraph() -> None:
        nonlocal paragraph_parts
        if not paragraph_parts:
            return
        merged = " ".join(part.strip() for part in paragraph_parts if part.strip())
        merged = re.sub(r"\s+", " ", merged).strip()
        if merged:
            normalized_lines.append(merged)
            normalized_lines.append("")
        paragraph_parts = []

    for raw_line in lines:
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped:
            flush_paragraph()
            continue
        if line_is_noise(stripped):
            flush_paragraph()
            continue
        level = heading_level_for_line(stripped)
        if level is not None:
            flush_paragraph()
            normalized_lines.append("#" * level + f" {stripped}")
            normalized_lines.append("")
            continue
        if stripped.startswith("Fig.") or stripped.startswith("Figure"):
            flush_paragraph()
            normalized_lines.append(stripped)
            normalized_lines.append("")
            continue
        if ONLY_SYMBOLS_RE.match(stripped):
            flush_paragraph()
            normalized_lines.append(stripped)
            normalized_lines.append("")
            continue
        paragraph_parts.append(stripped)

    flush_paragraph()

    rendered = "\n".join(normalized_lines).strip() + "\n"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(rendered, encoding="utf-8")
    return output_path


def google_translate_text(text: str, *, source_language: str = "en", target_language: str = "zh-CN") -> str:
    last_error: Exception | None = None
    for attempt in range(6):
        try:
            response = requests.get(
                GOOGLE_TRANSLATE_URL,
                params={
                    "client": "gtx",
                    "sl": source_language,
                    "tl": target_language,
                    "dt": "t",
                    "q": text,
                },
                timeout=45,
                verify=False,
                headers={"User-Agent": "Mozilla/5.0"},
            )
            response.raise_for_status()
            payload = response.json()
            return "".join(part[0] for part in payload[0] if isinstance(part, list) and part)
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            time.sleep(min(20, 2 * (attempt + 1)))
    raise RuntimeError(f"Google translate fallback failed: {last_error}")


def batched_items(items: list[dict[str, str]], max_chars: int) -> list[list[dict[str, str]]]:
    batches: list[list[dict[str, str]]] = []
    current: list[dict[str, str]] = []
    current_chars = 0

    for item in items:
        item_text = f"[[[{item['id']}]]]\n{item['source_text']}\n"
        item_chars = len(item_text)
        if current and current_chars + item_chars > max_chars:
            batches.append(current)
            current = []
            current_chars = 0
        current.append(item)
        current_chars += item_chars

    if current:
        batches.append(current)
    return batches


def parse_batched_translation(text: str) -> dict[str, str]:
    pieces = BLOCK_MARKER_RE.split(text)
    parsed: dict[str, str] = {}
    for index in range(1, len(pieces), 2):
        block_id = pieces[index].strip()
        block_text = pieces[index + 1].strip()
        if block_id:
            parsed[block_id] = block_text
    return parsed


def load_translation_cache(cache_path: Path | None) -> dict[str, str]:
    if cache_path is None or not cache_path.exists():
        return {}
    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}
    raw_translations = payload.get("translations", payload) if isinstance(payload, dict) else {}
    if not isinstance(raw_translations, dict):
        return {}
    return {str(key): str(value) for key, value in raw_translations.items() if str(value).strip()}


def save_translation_cache(cache_path: Path | None, translations: dict[str, str]) -> None:
    if cache_path is None:
        return
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "translated_total": len(translations),
        "translations": translations,
    }
    temp_path = cache_path.with_suffix(cache_path.suffix + ".tmp")
    temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        temp_path.replace(cache_path)
    except PermissionError:
        cache_path.write_text(temp_path.read_text(encoding="utf-8"), encoding="utf-8")
        try:
            temp_path.unlink()
        except OSError:
            pass


def translate_items_with_gtx(
    items: list[dict[str, str]],
    target_language: str,
    max_chars: int,
    cache_path: Path | None = None,
) -> dict[str, str]:
    translations: dict[str, str] = load_translation_cache(cache_path)
    item_ids = {item["id"] for item in items}
    translations = {key: value for key, value in translations.items() if key in item_ids}
    pending_items = [item for item in items if item["id"] not in translations]

    for batch in batched_items(pending_items, max_chars):
        joined = "\n\n".join(f"[[[{item['id']}]]]\n{item['source_text']}" for item in batch)
        try:
            translated = google_translate_text(joined, target_language=target_language)
            parsed = parse_batched_translation(translated)
            translations.update({key: value for key, value in parsed.items() if value})
            save_translation_cache(cache_path, translations)
            time.sleep(0.5)
        except Exception:  # noqa: BLE001
            # When the batch request flakes or markers are lost, fall back to per-block translation.
            for item in batch:
                if item["id"] in translations:
                    continue
                try:
                    translated = google_translate_text(item["source_text"], target_language=target_language).strip()
                except Exception as exc:  # noqa: BLE001
                    save_translation_cache(cache_path, translations)
                    raise RuntimeError(
                        "Google translate fallback failed while resuming "
                        f"{len(translations)}/{len(items)} cached blocks; last block={item['id']}: {exc}"
                    ) from exc
                translations[item["id"]] = translated or item["source_text"]
                save_translation_cache(cache_path, translations)
                time.sleep(0.5)

    missing = [item for item in items if item["id"] not in translations]
    for item in missing:
        try:
            translated = google_translate_text(item["source_text"], target_language=target_language).strip()
        except Exception as exc:  # noqa: BLE001
            save_translation_cache(cache_path, translations)
            raise RuntimeError(
                "Google translate fallback failed while filling missing "
                f"{len(translations)}/{len(items)} cached blocks; last block={item['id']}: {exc}"
            ) from exc
        translations[item["id"]] = translated or item["source_text"]
        save_translation_cache(cache_path, translations)
        time.sleep(0.2)

    return translations


def write_translation_template(template_path: Path, payload: dict[str, Any], translations: dict[str, str]) -> Path:
    blocks = payload.get("blocks", [])
    for block in blocks:
        block_id = str(block.get("id", "")).strip()
        if block_id:
            block["translation"] = translations.get(block_id, "")
    template_path.parent.mkdir(parents=True, exist_ok=True)
    template_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return template_path


def add_annotation_callout(note_path: Path, paper_note_wikilink: str, extract_source: str) -> None:
    text = note_path.read_text(encoding="utf-8")
    marker = "\n\n## "
    insert_at = text.find(marker)
    callout = (
        "> [!note]\n"
        "> 译注说明：本页为全文中文译注页，主要用于精读、引用核对和段落回溯。\n"
        f"> 生成路径：`google-gtx-fallback` + `{extract_source}`。\n"
        "> 公式、单位、DOI、URL 尽量保持原样；若个别符号异常，请以源文为准。\n"
        f"> 配套研究笔记：[[{paper_note_wikilink}]]\n\n"
    )
    if insert_at == -1:
        note_path.write_text(text + "\n" + callout, encoding="utf-8")
        return
    note_path.write_text(text[:insert_at] + "\n\n" + callout + text[insert_at + 2 :], encoding="utf-8")


def update_note_frontmatter(
    note_path: Path,
    frontmatter: dict[str, Any],
    body: str,
    *,
    translated_note_path: Path,
    translation_template_path: Path,
    extract_path: Path,
) -> None:
    frontmatter["translated_note_path"] = paper_dossiers.to_portable_path(translated_note_path)
    frontmatter["translation_template_path"] = paper_dossiers.to_portable_path(translation_template_path)
    frontmatter["extract_path"] = paper_dossiers.to_portable_path(extract_path)
    if "updated" in frontmatter:
        frontmatter["updated"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    rendered = dump_frontmatter(frontmatter) + body.lstrip("\n")
    note_path.write_text(rendered if rendered.endswith("\n") else rendered + "\n", encoding="utf-8")


def build_for_item(
    *,
    config: dict[str, Any],
    item: dict[str, Any],
    target_language: str,
    batch_chars: int,
    skip_existing: bool,
) -> BuildRecord:
    vault_root = Path(config["vault_root"])
    note_path = resolve_note_path(vault_root, item["note_path"]).resolve()
    note_text = note_path.read_text(encoding="utf-8", errors="replace")
    frontmatter, body = paper_dossiers.split_frontmatter(note_text)
    title = paper_dossiers.normalize_whitespace(frontmatter.get("title")) or note_path.stem
    year = paper_dossiers.normalize_whitespace(frontmatter.get("year"))
    authors = ", ".join(paper_dossiers.coerce_list(frontmatter.get("authors")))

    output_dir = translate_paper.build_output_dir(config, title, year)
    translated_note_path = output_dir / "translated.md"
    template_path = output_dir / "translation-template.json"
    normalized_extract_path = output_dir / "normalized-extract.md"

    if skip_existing and translated_note_path.exists():
        return BuildRecord(
            note_path=str(note_path),
            title=title,
            status="skipped",
            extract_path=paper_dossiers.normalize_whitespace(frontmatter.get("extract_path")),
            translated_note_path=str(translated_note_path),
            translation_template_path=str(template_path),
            source_pdf=paper_dossiers.normalize_whitespace(frontmatter.get("source_pdf") or frontmatter.get("copied_pdf")),
            message="Translated page already exists.",
        )

    fallback_pdf = resolve_optional_path(item.get("fallback_pdf", ""))
    fallback_extract = resolve_optional_path(item.get("fallback_extract", ""))
    extract_path, generated_extract = choose_extract(frontmatter, fallback_pdf, fallback_extract, vault_root)
    skip_normalization = bool(item.get("skip_normalization"))
    if skip_normalization:
        working_extract = extract_path
    else:
        working_extract = normalize_extract_markdown(
            extract_path,
            title,
            normalized_extract_path,
            start_marker=paper_dossiers.normalize_whitespace(item.get("start_marker")),
            end_marker=paper_dossiers.normalize_whitespace(item.get("end_marker")),
        )
    blocks = translate_paper.parse_markdown_blocks(working_extract)
    items_to_translate = translate_paper.collect_translatable_items(title, blocks)
    translations = translate_items_with_gtx(
        items_to_translate,
        target_language,
        batch_chars,
        cache_path=template_path.with_name("translation-cache.json"),
    )
    template_payload = translate_paper.build_template_payload(title, target_language, extract_path, items_to_translate)
    write_translation_template(template_path, template_payload, translations)

    source_pdf = (
        paper_dossiers.normalize_whitespace(frontmatter.get("source_pdf") or frontmatter.get("copied_pdf"))
        or (fallback_pdf.as_posix() if fallback_pdf else "")
    )
    translated_note_path.parent.mkdir(parents=True, exist_ok=True)
    translated_note_path, _translated_title = translate_paper.render_markdown(
        blocks=blocks,
        translations=translations,
        extract_dir=working_extract.parent,
        output_dir=output_dir,
        title=title,
        year=year,
        authors=authors,
        source_pdf=source_pdf,
        source_md=extract_path,
        target_language=target_language,
        translation_mode="google-gtx-fallback",
        include_original_blocks=False,
    )

    paper_note_rel = note_path.relative_to(vault_root).with_suffix("").as_posix()
    extract_source_label = "generated full-text extract" if generated_extract else "existing extract"
    add_annotation_callout(translated_note_path, paper_note_rel, extract_source_label)
    update_note_frontmatter(
        note_path,
        frontmatter,
        body,
        translated_note_path=translated_note_path,
        translation_template_path=template_path,
        extract_path=extract_path,
    )

    return BuildRecord(
        note_path=str(note_path),
        title=title,
        status="built",
        extract_path=str(extract_path),
        translated_note_path=str(translated_note_path),
        translation_template_path=str(template_path),
        source_pdf=source_pdf,
        message="Built translated paper page and updated paper note links.",
    )


def main() -> None:
    args = parse_args()
    config = load_json(Path(args.config))
    manifest = read_manifest(Path(args.manifest))
    records: list[BuildRecord] = []

    for item in manifest:
        try:
            records.append(
                build_for_item(
                    config=config,
                    item=item,
                    target_language=args.target_language,
                    batch_chars=args.batch_chars,
                    skip_existing=args.skip_existing,
                )
            )
        except Exception as exc:  # noqa: BLE001
            records.append(
                BuildRecord(
                    note_path=str(item.get("note_path", "")),
                    title="",
                    status="error",
                    extract_path="",
                    translated_note_path="",
                    translation_template_path="",
                    source_pdf="",
                    message=str(exc),
                )
            )

    if args.report_out:
        report_path = Path(args.report_out)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps([record.__dict__ for record in records], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    print(json.dumps([record.__dict__ for record in records], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
