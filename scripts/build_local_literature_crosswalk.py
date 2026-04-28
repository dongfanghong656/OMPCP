#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import paper_dossiers


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = PROJECT_ROOT / "config.json"
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "reports" / "literature-html-pipeline"
INVENTORY_SPECS = [
    ("local-literature-corpus", PROJECT_ROOT / "reports" / "local-literature-corpus" / "inventory.json"),
    ("additional-literature-corpus", PROJECT_ROOT / "reports" / "additional-literature-corpus" / "inventory.json"),
    ("additional-literature-corpus-fixes", PROJECT_ROOT / "reports" / "additional-literature-corpus-fixes" / "inventory.json"),
    ("knowledge-base-literature", PROJECT_ROOT / "reports" / "knowledge-base-literature" / "inventory.json"),
    ("full-local-literature-corpus", PROJECT_ROOT / "reports" / "full-local-literature-corpus" / "inventory.json"),
    (
        "archive-literature-corpus-sciencedirect-20250320",
        PROJECT_ROOT / "reports" / "archive-literature-corpus" / "sciencedirect-20250320" / "extracted" / "inventory.json",
    ),
]
PAGE_TITLE_RE = re.compile(r"^##\s*Page\s+\d+\s*$", flags=re.IGNORECASE)
YEAR_RE = re.compile(r"(19|20)\d{2}")
NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


@dataclass
class LocalExtractRecord:
    corpus: str
    source_path: str
    relative_path: str
    extract_path: str
    extension: str
    status: str
    title: str
    char_count: int
    page_count: int
    filename_key: str
    title_key: str
    basename: str
    year_hint: str


@dataclass
class LocalMatch:
    corpus: str
    relative_path: str
    source_path: str
    extract_path: str
    score: float
    reason: str


@dataclass
class CrosswalkRecord:
    paper_note_rel_path: str
    paper_note_path: str
    title: str
    title_original: str
    year: str
    doi: str
    source_tag: str
    source_pdf_rel_path: str
    source_pdf_external_path: str
    extract_rel_path: str
    translated_note_rel_path: str
    translated_note_path: str
    translation_template_rel_path: str
    html_target_path: str
    html_exists: bool
    local_match: LocalMatch | None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a crosswalk between local literature extracts and vault paper notes.")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    return parser.parse_args()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def normalize_key(value: str) -> str:
    return NON_ALNUM_RE.sub(" ", paper_dossiers.normalize_whitespace(value).lower()).strip()


def slugify(value: str, limit: int = 96) -> str:
    slug = NON_ALNUM_RE.sub("-", paper_dossiers.normalize_whitespace(value).lower()).strip("-")
    return (slug[:limit].strip("-") or "paper")


def key_from_path_stem(path_value: str) -> str:
    if not path_value:
        return ""
    stem = Path(path_value.replace("\\", "/")).stem
    return paper_dossiers.canonicalize_title(stem)


def title_key_from_record_title(title: str) -> str:
    cleaned = paper_dossiers.normalize_whitespace(title)
    if not cleaned or PAGE_TITLE_RE.match(cleaned):
        return ""
    return paper_dossiers.canonicalize_title(cleaned)


def first_year(value: str) -> str:
    match = YEAR_RE.search(value or "")
    return match.group(0) if match else ""


def inventory_records(specs: list[tuple[str, Path]]) -> list[LocalExtractRecord]:
    records: list[LocalExtractRecord] = []
    for corpus_name, inventory_path in specs:
        if not inventory_path.exists():
            continue
        payload = load_json(inventory_path)
        for item in payload.get("records", []):
            status = paper_dossiers.normalize_whitespace(item.get("status"))
            extract_path = paper_dossiers.normalize_whitespace(item.get("extract_path"))
            if status == "failed" or not extract_path:
                continue
            extract_file = Path(extract_path.replace("\\", "/"))
            if not extract_file.exists():
                continue
            source_path = paper_dossiers.normalize_whitespace(item.get("source_path"))
            relative_path = paper_dossiers.normalize_whitespace(item.get("relative_path"))
            title = paper_dossiers.normalize_whitespace(item.get("title"))
            basename = Path(source_path.replace("\\", "/")).name if source_path else Path(relative_path).name
            records.append(
                LocalExtractRecord(
                    corpus=corpus_name,
                    source_path=source_path,
                    relative_path=relative_path,
                    extract_path=extract_path,
                    extension=paper_dossiers.normalize_whitespace(item.get("extension")),
                    status=status,
                    title=title,
                    char_count=int(item.get("char_count") or 0),
                    page_count=int(item.get("page_count") or 0),
                    filename_key=key_from_path_stem(source_path or relative_path),
                    title_key=title_key_from_record_title(title),
                    basename=basename,
                    year_hint=first_year(relative_path or source_path or title),
                )
            )
    return records


def build_title_candidates(dossier: paper_dossiers.PaperDossier) -> list[str]:
    candidates = [
        dossier.title_original,
        dossier.title,
        key_from_path_stem(dossier.source_pdf_rel_path),
        key_from_path_stem(dossier.source_pdf_external_path),
        key_from_path_stem(dossier.copied_pdf_rel_path),
        key_from_path_stem(dossier.paper_note_rel_path),
    ]
    cleaned: list[str] = []
    seen: set[str] = set()
    for value in candidates:
        key = paper_dossiers.canonicalize_title(value)
        if key and key not in seen:
            cleaned.append(key)
            seen.add(key)
    return cleaned


def similarity(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    return SequenceMatcher(None, normalize_key(left), normalize_key(right)).ratio()


def find_best_local_match(
    dossier: paper_dossiers.PaperDossier,
    local_records: list[LocalExtractRecord],
) -> LocalMatch | None:
    title_candidates = build_title_candidates(dossier)
    if not title_candidates:
        return None

    source_pdf_key = key_from_path_stem(dossier.source_pdf_rel_path) or key_from_path_stem(dossier.source_pdf_external_path)
    copied_pdf_key = key_from_path_stem(dossier.copied_pdf_rel_path)
    year_hint = paper_dossiers.normalize_whitespace(dossier.year)

    best_record: LocalExtractRecord | None = None
    best_score = 0.0
    best_reason = ""

    for record in local_records:
        score = 0.0
        reason = ""

        if source_pdf_key and source_pdf_key == record.filename_key:
            score = 1.0
            reason = "source-pdf-basename"
        elif copied_pdf_key and copied_pdf_key == record.filename_key:
            score = 0.995
            reason = "copied-pdf-basename"
        else:
            candidate_score = 0.0
            candidate_reason = ""
            for note_key in title_candidates:
                for record_key, record_reason in ((record.filename_key, "title-vs-filename"), (record.title_key, "title-vs-record-title")):
                    if not record_key:
                        continue
                    if note_key == record_key:
                        candidate_score = 0.98
                        candidate_reason = record_reason + "-exact"
                        break
                    ratio = similarity(note_key, record_key)
                    if ratio > candidate_score:
                        candidate_score = ratio
                        candidate_reason = record_reason + "-fuzzy"
                if candidate_score >= 0.98:
                    break
            score = candidate_score
            reason = candidate_reason

        if year_hint and record.year_hint and year_hint == record.year_hint:
            score += 0.015

        if score > best_score:
            best_score = score
            best_record = record
            best_reason = reason

    if best_record is None or best_score < 0.84:
        return None

    return LocalMatch(
        corpus=best_record.corpus,
        relative_path=best_record.relative_path,
        source_path=best_record.source_path,
        extract_path=best_record.extract_path,
        score=round(best_score, 4),
        reason=best_reason,
    )


def html_target_for_dossier(output_root: Path, dossier: paper_dossiers.PaperDossier) -> Path:
    stem = Path(dossier.paper_note_rel_path).stem
    stem = re.sub(r"^\[(19|20)\d{2}\]\s*", "", stem)
    return output_root / "generated" / f"{slugify((dossier.year + ' ' + stem).strip())}-annotated.html"


def build_crosswalk_records(
    config: dict[str, Any],
    output_root: Path,
    local_records: list[LocalExtractRecord],
) -> list[CrosswalkRecord]:
    vault_root = Path(config["vault_root"])
    dossiers = sorted(paper_dossiers.build_dossiers(config), key=lambda item: (item.year or "", item.paper_note_rel_path.lower()))
    rows: list[CrosswalkRecord] = []
    for dossier in dossiers:
        paper_note_path = vault_root / dossier.paper_note_rel_path
        translated_note_path = (vault_root / dossier.translated_note_rel_path) if dossier.translated_note_rel_path else None
        html_target = html_target_for_dossier(output_root, dossier)
        rows.append(
            CrosswalkRecord(
                paper_note_rel_path=dossier.paper_note_rel_path,
                paper_note_path=paper_note_path.as_posix(),
                title=dossier.title,
                title_original=dossier.title_original,
                year=dossier.year,
                doi=dossier.doi,
                source_tag=dossier.source_tag,
                source_pdf_rel_path=dossier.source_pdf_rel_path,
                source_pdf_external_path=dossier.source_pdf_external_path,
                extract_rel_path=dossier.extract_rel_path,
                translated_note_rel_path=dossier.translated_note_rel_path,
                translated_note_path=translated_note_path.as_posix() if translated_note_path else "",
                translation_template_rel_path=dossier.translation_template_rel_path,
                html_target_path=html_target.as_posix(),
                html_exists=html_target.exists(),
                local_match=find_best_local_match(dossier, local_records),
            )
        )
    return rows


def render_markdown(summary: dict[str, Any], rows: list[CrosswalkRecord]) -> str:
    lines = [
        "# 本地文献抽取与论文笔记映射表",
        "",
        f"- 生成时间：`{summary['generated_at']}`",
        f"- 论文笔记总数：`{summary['paper_note_total']}`",
        f"- 有中文译注：`{summary['with_translation_total']}`",
        f"- 有现成抽取路径：`{summary['with_note_extract_total']}`",
        f"- 已匹配到本地语料抽取：`{summary['with_local_match_total']}`",
        f"- 已存在批注 HTML：`{summary['html_exists_total']}`",
        "",
        "## 本地语料库规模",
        "",
    ]
    for corpus_name, corpus_count in summary["local_corpus_totals"].items():
        lines.append(f"- {corpus_name}: `{corpus_count}`")

    matched_rows = [row for row in rows if row.local_match]
    unmatched_rows = [row for row in rows if not row.local_match]

    lines.extend(["", "## 已匹配论文", ""])
    for row in matched_rows:
        assert row.local_match is not None
        lines.extend(
            [
                f"### {row.title or Path(row.paper_note_rel_path).stem}",
                f"- 论文笔记：`{row.paper_note_rel_path}`",
                f"- 年份：`{row.year or '未知'}`",
                f"- 本地语料：`{row.local_match.corpus}`",
                f"- 匹配来源：`{row.local_match.relative_path}`",
                f"- 匹配置信：`{row.local_match.score}` / `{row.local_match.reason}`",
                f"- 中文译注：`{'有' if row.translated_note_rel_path else '无'}`",
                f"- HTML 状态：`{'已存在' if row.html_exists else '待生成'}` -> `{row.html_target_path}`",
                "",
            ]
        )

    lines.extend(["## 暂未匹配论文", ""])
    for row in unmatched_rows:
        lines.extend(
            [
                f"- `{row.paper_note_rel_path}` | `{row.year or '未知'}` | 译注：`{'有' if row.translated_note_rel_path else '无'}` | 目标 HTML：`{row.html_target_path}`",
            ]
        )
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    config = paper_dossiers.load_json(Path(args.config))
    output_root = Path(args.output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    local_records = inventory_records(INVENTORY_SPECS)
    rows = build_crosswalk_records(config, output_root, local_records)
    corpus_totals: dict[str, int] = {}
    for record in local_records:
        corpus_totals[record.corpus] = corpus_totals.get(record.corpus, 0) + 1

    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "paper_note_total": len(rows),
        "with_translation_total": sum(1 for row in rows if row.translated_note_rel_path),
        "with_note_extract_total": sum(1 for row in rows if row.extract_rel_path),
        "with_local_match_total": sum(1 for row in rows if row.local_match is not None),
        "html_exists_total": sum(1 for row in rows if row.html_exists),
        "local_corpus_totals": corpus_totals,
    }

    payload = {
        "summary": summary,
        "records": [asdict(row) for row in rows],
    }
    (output_root / "local_literature_crosswalk.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_root / "local_literature_crosswalk.md").write_text(
        render_markdown(summary, rows),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
