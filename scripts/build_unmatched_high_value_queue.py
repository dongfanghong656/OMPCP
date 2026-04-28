#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
REPORTS_ROOT = WORKSPACE_ROOT / "reports"
PIPELINE_ROOT = REPORTS_ROOT / "literature-html-pipeline"
CONFIG_PATH = WORKSPACE_ROOT / "config.json"

CORPUS_SPECS = [
    ("local-literature-corpus", REPORTS_ROOT / "local-literature-corpus" / "inventory.json"),
    ("additional-literature-corpus", REPORTS_ROOT / "additional-literature-corpus" / "inventory.json"),
    ("additional-literature-corpus-fixes", REPORTS_ROOT / "additional-literature-corpus-fixes" / "inventory.json"),
    ("knowledge-base-literature", REPORTS_ROOT / "knowledge-base-literature" / "inventory.json"),
    ("full-local-literature-corpus", REPORTS_ROOT / "full-local-literature-corpus" / "inventory.json"),
    (
        "archive-literature-corpus-sciencedirect-20250320",
        REPORTS_ROOT / "archive-literature-corpus" / "sciencedirect-20250320" / "extracted" / "inventory.json",
    ),
]

RULE_WEIGHTS = {
    "oct-core": 8,
    "deconvolution": 10,
    "blind-deconvolution": 12,
    "resolution-validation": 6,
    "superresolution": 9,
    "wigner": 7,
    "spectral-domain": 6,
    "review": 4,
    "elastography": 4,
}

NOISE_PATTERNS = [
    "知乎",
    "bilibili",
    "z-library",
    "课后习题",
    "工作簿",
    "论文规范",
    "教程",
    "processon",
    "游客的凝视",
    "若干重大决策",
    "新建 microsoft word 文档",
]

PLACEHOLDER_TITLES = {"## page 1"}
YEAR_RE = re.compile(r"(19|20)\d{2}")
BRACKET_PREFIX_RE = re.compile(r"^\[\d+\]\s*")
LEADING_YEAR_PREFIX_RE = re.compile(r"^(19|20)\d{2}[-_ ]+")
NON_WORD_RE = re.compile(r"[^a-z0-9\u4e00-\u9fff]+")
SHORTLIST_MIN_SCORE = 16
KNOWN_TITLE_SIMILARITY_THRESHOLD = 0.90
DEFAULT_MD_TOP_LIMIT = 40


@dataclass
class Candidate:
    corpus: str
    relative_path: str
    source_path: str
    extract_path: str
    extension: str
    char_count: int
    page_count: int
    display_title: str
    normalized_title: str
    year_guess: str
    score: int
    matched_rules: list[str]
    matched_phrases: list[str]
    why_selected: str


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def normalize_title(value: str) -> str:
    return NON_WORD_RE.sub(" ", normalize_text(value).lower()).strip()


def load_config() -> dict[str, Any]:
    return load_json(CONFIG_PATH)


def load_crosswalk_payload() -> dict[str, Any]:
    return load_json(PIPELINE_ROOT / "local_literature_crosswalk.json")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a scored unmatched literature queue from local extracted corpora."
    )
    parser.add_argument("--min-score", type=int, default=SHORTLIST_MIN_SCORE)
    parser.add_argument("--max-score", type=int, default=None)
    parser.add_argument(
        "--output-json",
        default=str(PIPELINE_ROOT / "unmatched_high_value_queue.json"),
    )
    parser.add_argument(
        "--output-md",
        default=str(PIPELINE_ROOT / "unmatched_high_value_queue.md"),
    )
    parser.add_argument("--heading", default="未入链高价值文献候选队列")
    parser.add_argument("--top-limit", type=int, default=DEFAULT_MD_TOP_LIMIT)
    return parser.parse_args()


def build_known_title_set(crosswalk_records: list[dict[str, Any]]) -> tuple[set[str], list[str], set[str]]:
    known_titles: set[str] = set()
    known_title_list: list[str] = []
    known_source_paths: set[str] = set()
    for record in crosswalk_records:
        for key in ("title", "title_original"):
            normalized = normalize_title(str(record.get(key) or ""))
            if normalized and normalized not in known_titles:
                known_titles.add(normalized)
                known_title_list.append(normalized)
        local_match = record.get("local_match") or {}
        source_path = str(local_match.get("source_path") or "")
        if source_path:
            known_source_paths.add(source_path)
        external_source = str(record.get("source_pdf_external_path") or "")
        if external_source:
            known_source_paths.add(external_source.replace("/", "\\"))
    return known_titles, known_title_list, known_source_paths


def derive_display_title(record: dict[str, Any]) -> str:
    raw_title = normalize_text(str(record.get("title") or ""))
    if raw_title and raw_title.lower() not in PLACEHOLDER_TITLES and not raw_title.lower().startswith("source_path:"):
        return raw_title

    path_hint = Path(str(record.get("relative_path") or record.get("source_path") or ""))
    stem = path_hint.stem
    stem = BRACKET_PREFIX_RE.sub("", stem)
    stem = LEADING_YEAR_PREFIX_RE.sub("", stem)
    stem = stem.replace("_", " ").replace("  ", " ").strip(" ._-")
    stem = stem.replace("  ", " ")
    return normalize_text(stem)


def looks_like_noise(text: str) -> bool:
    lowered = text.lower()
    return any(pattern.lower() in lowered for pattern in NOISE_PATTERNS)


def looks_like_known_title(title: str, known_titles: list[str]) -> bool:
    if not title:
        return False
    for known in known_titles:
        if title == known:
            return True
        if len(title) >= 24 and len(known) >= 24 and (title.startswith(known) or known.startswith(title)):
            return True
        ratio = SequenceMatcher(None, title, known).ratio()
        if ratio >= KNOWN_TITLE_SIMILARITY_THRESHOLD:
            return True
    return False


def score_candidate(record: dict[str, Any], display_title: str, rules: list[dict[str, Any]]) -> tuple[int, list[str], list[str]]:
    search_text = " | ".join(
        [
            display_title,
            str(record.get("relative_path") or ""),
            str(record.get("source_path") or ""),
        ]
    ).lower()
    matched_rules: list[str] = []
    matched_phrases: list[str] = []
    score = 0
    for rule in rules:
        name = str(rule.get("name") or "")
        matches = []
        for phrase in rule.get("match_any") or []:
            lowered = str(phrase).lower()
            if lowered and lowered in search_text:
                matches.append(lowered)
        if not matches:
            continue
        matched_rules.append(name)
        matched_phrases.extend(matches)
        score += RULE_WEIGHTS.get(name, 3)
        if any(match in display_title.lower() for match in matches):
            score += 2

    extension = str(record.get("extension") or "").lower()
    if extension == ".pdf":
        score += 1
    char_count = int(record.get("char_count") or 0)
    if char_count >= 50000:
        score += 3
    elif char_count >= 15000:
        score += 2
    elif char_count >= 5000:
        score += 1
    return score, sorted(set(matched_rules)), sorted(set(matched_phrases))


def build_candidates(min_score: int = SHORTLIST_MIN_SCORE, max_score: int | None = None) -> tuple[dict[str, Any], list[Candidate]]:
    config = load_config()
    rules = config.get("zotero", {}).get("local_pdf_import", {}).get("classification_rules", [])
    crosswalk_payload = load_crosswalk_payload()
    crosswalk_records = crosswalk_payload.get("records", [])
    known_titles, known_title_list, known_source_paths = build_known_title_set(crosswalk_records)

    chosen: dict[str, Candidate] = {}
    scanned_total = 0
    usable_total = 0
    skipped_existing_note = 0
    skipped_noise = 0
    skipped_low_score = 0

    for corpus_name, inventory_path in CORPUS_SPECS:
        payload = load_json(inventory_path)
        records = payload.get("records", []) if isinstance(payload, dict) else payload
        for record in records:
            scanned_total += 1
            status = str(record.get("status") or "")
            if status not in {"extracted", "skipped-existing"}:
                continue
            extension = str(record.get("extension") or "").lower()
            if extension not in {".pdf", ".docx"}:
                continue
            usable_total += 1

            source_path = str(record.get("source_path") or "")
            if source_path in known_source_paths:
                skipped_existing_note += 1
                continue

            display_title = derive_display_title(record)
            normalized = normalize_title(display_title)
            if not normalized:
                skipped_low_score += 1
                continue
            if normalized in known_titles or looks_like_known_title(normalized, known_title_list):
                skipped_existing_note += 1
                continue
            if looks_like_noise(f"{display_title} | {record.get('relative_path') or ''}"):
                skipped_noise += 1
                continue

            score, matched_rules, matched_phrases = score_candidate(record, display_title, rules)
            if score < min_score:
                skipped_low_score += 1
                continue
            if max_score is not None and score > max_score:
                skipped_low_score += 1
                continue

            year_match = YEAR_RE.search(display_title)
            candidate = Candidate(
                corpus=corpus_name,
                relative_path=str(record.get("relative_path") or ""),
                source_path=source_path,
                extract_path=str(record.get("extract_path") or ""),
                extension=extension,
                char_count=int(record.get("char_count") or 0),
                page_count=int(record.get("page_count") or 0),
                display_title=display_title,
                normalized_title=normalized,
                year_guess=year_match.group(0) if year_match else "",
                score=score,
                matched_rules=matched_rules,
                matched_phrases=matched_phrases,
                why_selected="; ".join(matched_rules) if matched_rules else "keyword hit",
            )
            current = chosen.get(normalized)
            if current is None or (
                candidate.score,
                candidate.char_count,
                candidate.page_count,
            ) > (
                current.score,
                current.char_count,
                current.page_count,
            ):
                chosen[normalized] = candidate

    ordered = sorted(
        chosen.values(),
        key=lambda item: (
            -item.score,
            -item.char_count,
            -item.page_count,
            item.display_title.lower(),
        ),
    )
    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "scanned_total": scanned_total,
        "usable_pdf_docx_total": usable_total,
        "queue_total": len(ordered),
        "min_score": min_score,
        "max_score": max_score,
        "shortlist_min_score": SHORTLIST_MIN_SCORE,
        "skipped_existing_note_total": skipped_existing_note,
        "skipped_noise_total": skipped_noise,
        "skipped_low_score_total": skipped_low_score,
        "top_score": ordered[0].score if ordered else 0,
    }
    return summary, ordered


def render_markdown(summary: dict[str, Any], candidates: list[Candidate], *, heading: str, top_limit: int) -> str:
    lines = [
        f"# {heading}",
        "",
        f"- 生成时间：`{summary['generated_at']}`",
        f"- 扫描记录：`{summary['scanned_total']}`",
        f"- 可用 PDF/DOCX：`{summary['usable_pdf_docx_total']}`",
        f"- 候选总数：`{summary['queue_total']}`",
        f"- 分数下限：`{summary['min_score']}`",
        f"- 分数上限：`{summary['max_score'] if summary['max_score'] is not None else 'None'}`",
        f"- 因已有 note/本地映射而跳过：`{summary['skipped_existing_note_total']}`",
        f"- 因明显噪声而跳过：`{summary['skipped_noise_total']}`",
        f"- 因分值不在目标区间而跳过：`{summary['skipped_low_score_total']}`",
        "",
        "## Top Queue",
        "",
    ]
    for index, item in enumerate(candidates[:top_limit], start=1):
        lines.extend(
            [
                f"### {index}. {item.display_title}",
                "",
                f"- score: `{item.score}`",
                f"- corpus: `{item.corpus}`",
                f"- year_guess: `{item.year_guess}`",
                f"- matched_rules: `{', '.join(item.matched_rules) or 'none'}`",
                f"- matched_phrases: `{', '.join(item.matched_phrases) or 'none'}`",
                f"- relative_path: `{item.relative_path}`",
                f"- extract_path: `{item.extract_path}`",
                f"- char_count: `{item.char_count}` | page_count: `{item.page_count}`",
                "",
            ]
        )
    if not candidates:
        lines.append("- 当前没有新的高价值未入链候选。")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    summary, candidates = build_candidates(min_score=args.min_score, max_score=args.max_score)
    output_json = Path(args.output_json)
    output_md = Path(args.output_md)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(
        json.dumps(
            {
                "summary": summary,
                "records": [candidate.__dict__ for candidate in candidates],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    output_md.write_text(
        render_markdown(summary, candidates, heading=args.heading, top_limit=args.top_limit),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
