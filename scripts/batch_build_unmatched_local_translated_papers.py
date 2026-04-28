#!/usr/bin/env python
from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import batch_build_local_translated_papers as local_translate
import batch_build_translated_papers as batch_translate
import paper_dossiers
import translate_paper


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_QUEUE = PROJECT_ROOT / "reports" / "literature-html-pipeline" / "unmatched_high_value_queue.json"
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "reports" / "literature-html-pipeline" / "local-translated-papers"
YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")


@dataclass
class QueueTranslationRecord:
    queue_rank: int
    corpus: str
    title: str
    year: str
    score: int
    status: str
    extract_path: str
    source_path: str
    relative_path: str
    normalized_extract_path: str
    translated_note_path: str
    translation_template_path: str
    metadata_path: str
    message: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build local translated-paper copies from an unmatched literature queue."
    )
    parser.add_argument("--queue-json", default=str(DEFAULT_QUEUE))
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--report-out", default="")
    parser.add_argument("--target-language", default="zh-CN")
    parser.add_argument("--batch-chars", type=int, default=1400)
    parser.add_argument("--limit", type=int, default=2)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--min-score", type=int, default=16)
    parser.add_argument("--only-missing", action="store_true")
    parser.add_argument("--skip-existing", action="store_true")
    return parser.parse_args()


def queue_items(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    records = payload.get("records", payload)
    if not isinstance(records, list):
        raise ValueError("Queue JSON must contain a records list.")
    return [item for item in records if isinstance(item, dict)]


def infer_year(record: dict[str, Any]) -> str:
    explicit = paper_dossiers.normalize_whitespace(record.get("year_guess"))
    if explicit:
        match = YEAR_RE.search(explicit)
        if match:
            return match.group(0)

    for field in (
        paper_dossiers.normalize_whitespace(record.get("relative_path")),
        paper_dossiers.normalize_whitespace(record.get("source_path")),
        paper_dossiers.normalize_whitespace(record.get("display_title")),
    ):
        match = YEAR_RE.search(field)
        if match:
            return match.group(0)
    return ""


def extract_title(record: dict[str, Any]) -> str:
    candidates = [
        paper_dossiers.normalize_whitespace(record.get("display_title")),
        paper_dossiers.normalize_whitespace(record.get("normalized_title")),
        Path(str(record.get("source_path", "")).replace("\\", "/")).stem,
        Path(str(record.get("extract_path", "")).replace("\\", "/")).parent.name,
    ]
    for candidate in candidates:
        if candidate:
            return candidate
    return "Untitled Paper"


def build_output_dir(output_root: Path, title: str, year: str) -> Path:
    folder = local_translate.local_slug(f"{year}-{title}" if year else title)
    target = output_root / folder
    target.mkdir(parents=True, exist_ok=True)
    return target


def normalized_path_value(value: object) -> str:
    return str(value or "").replace("\\", "/").strip().lower()


def record_identity_digest(record: dict[str, Any], title: str, year: str) -> str:
    identity = "|".join(
        [
            year,
            title,
            paper_dossiers.normalize_whitespace(record.get("extract_path")),
            paper_dossiers.normalize_whitespace(record.get("source_path")),
            paper_dossiers.normalize_whitespace(record.get("relative_path")),
        ]
    )
    return hashlib.sha1(identity.encode("utf-8")).hexdigest()[:10]


def output_slug_for_record(record: dict[str, Any], title: str, year: str) -> str:
    base = local_translate.local_slug(f"{year}-{title}" if year else title)
    has_non_ascii = any(ord(char) > 127 for char in title)
    if has_non_ascii and len(base) < 24:
        digest = record_identity_digest(record, title, year)
        prefix = base[:85].strip("-") or "paper"
        return f"{prefix}-{digest}"
    return base


def resolve_output_paths(
    output_root: Path,
    title: str,
    year: str,
    record: dict[str, Any] | None = None,
) -> tuple[Path, Path, Path]:
    folder = (
        output_slug_for_record(record, title, year)
        if record is not None
        else local_translate.local_slug(f"{year}-{title}" if year else title)
    )
    target = output_root / folder
    return target, target / "translated.md", target / "local-metadata.json"


def legacy_output_paths(output_root: Path, title: str, year: str) -> tuple[Path, Path, Path]:
    folder = local_translate.local_slug(f"{year}-{title}" if year else title)
    target = output_root / folder
    return target, target / "translated.md", target / "local-metadata.json"


def metadata_matches_record(metadata_path: Path, record: dict[str, Any]) -> bool:
    if not metadata_path.exists():
        return False
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return False
    extract_path = normalized_path_value(record.get("extract_path"))
    source_path = normalized_path_value(record.get("source_path"))
    record_title = extract_title(record)
    record_title_slug = local_translate.local_slug(record_title)
    metadata_title_slug = local_translate.local_slug(
        paper_dossiers.normalize_whitespace(metadata.get("paper_title"))
    )
    return (
        bool(extract_path and normalized_path_value(metadata.get("source_md")) == extract_path)
        or bool(source_path and normalized_path_value(metadata.get("source_pdf")) == source_path)
        # Old batches used a 96-char title slug without source identity. Keep long-title
        # duplicate coverage, but do not let short CJK-derived slugs such as "ofdr"
        # suppress unrelated records.
        or bool(
            len(record_title_slug) >= 24
            and record_title_slug == metadata_title_slug
        )
        or (
            int(metadata.get("queue_rank", -1)) == int(record.get("_queue_rank", -2))
            and paper_dossiers.normalize_whitespace(metadata.get("paper_title"))
            == record_title
        )
    )


def output_exists_for_record(record: dict[str, Any], output_root: Path) -> bool:
    title = extract_title(record)
    year = infer_year(record)
    _target, translated_note_path, metadata_path = resolve_output_paths(output_root, title, year, record)
    if translated_note_path.exists() and metadata_matches_record(metadata_path, record):
        return True
    _legacy_target, legacy_translated_note_path, legacy_metadata_path = legacy_output_paths(output_root, title, year)
    return legacy_translated_note_path.exists() and metadata_matches_record(legacy_metadata_path, record)


def append_queue_callout(
    translated_note_path: Path,
    *,
    queue_rank: int,
    corpus: str,
    score: int,
    source_path: str,
    extract_path: str,
    why_selected: str,
) -> None:
    callout = (
        "> [!note]\n"
        "> 译注说明：本页为工作区本地译注副本，由未入链文献候选队列直连生成。\n"
        f"> 队列位置：`#{queue_rank}` | 语料库：`{corpus}` | 评分：`{score}`\n"
        f"> 原始文件：`{source_path}`\n"
        f"> 源文抽取：`{extract_path}`\n"
        f"> 选入原因：`{why_selected}`\n\n"
    )
    text = translated_note_path.read_text(encoding="utf-8")
    translated_note_path.write_text(text + ("\n" if not text.endswith("\n") else "") + callout, encoding="utf-8")


def build_metadata(
    *,
    record: dict[str, Any],
    title: str,
    year: str,
    source_md: Path,
    translated_note_path: Path,
) -> dict[str, Any]:
    return {
        "paper_title": title,
        "paper_title_original": title,
        "year": year,
        "source_md": source_md.as_posix(),
        "source_pdf": paper_dossiers.normalize_whitespace(record.get("source_path")),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "queue_rank": int(record.get("_queue_rank", 0)),
        "score": int(record.get("score", 0)),
        "corpus": paper_dossiers.normalize_whitespace(record.get("corpus")),
        "relative_path": paper_dossiers.normalize_whitespace(record.get("relative_path")),
        "why_selected": paper_dossiers.normalize_whitespace(record.get("why_selected")),
        "translated_note_path": translated_note_path.as_posix(),
    }


def build_for_record(
    *,
    record: dict[str, Any],
    output_root: Path,
    target_language: str,
    batch_chars: int,
    skip_existing: bool,
) -> QueueTranslationRecord:
    title = extract_title(record)
    year = infer_year(record)
    corpus = paper_dossiers.normalize_whitespace(record.get("corpus"))
    score = int(record.get("score", 0))
    extract_path = Path(str(record.get("extract_path", "")).replace("\\", "/"))
    source_path = paper_dossiers.normalize_whitespace(record.get("source_path"))
    relative_path = paper_dossiers.normalize_whitespace(record.get("relative_path"))
    queue_rank = int(record.get("_queue_rank", 0))
    why_selected = paper_dossiers.normalize_whitespace(record.get("why_selected"))

    if not extract_path.exists():
        raise FileNotFoundError(f"Extract path not found: {extract_path}")

    out_dir, _translated_note_path, _metadata_path = resolve_output_paths(output_root, title, year, record)
    out_dir.mkdir(parents=True, exist_ok=True)
    translated_note_path = out_dir / "translated.md"
    template_path = out_dir / "translation-template.json"
    normalized_extract_path = out_dir / "normalized-extract.md"
    metadata_path = out_dir / "local-metadata.json"

    if skip_existing and translated_note_path.exists() and metadata_path.exists():
        return QueueTranslationRecord(
            queue_rank=queue_rank,
            corpus=corpus,
            title=title,
            year=year,
            score=score,
            status="skipped-existing",
            extract_path=extract_path.as_posix(),
            source_path=source_path,
            relative_path=relative_path,
            normalized_extract_path=normalized_extract_path.as_posix() if normalized_extract_path.exists() else "",
            translated_note_path=translated_note_path.as_posix(),
            translation_template_path=template_path.as_posix() if template_path.exists() else "",
            metadata_path=metadata_path.as_posix(),
            message="Local translated copy already exists.",
        )

    working_extract = batch_translate.normalize_extract_markdown(
        extract_path,
        title,
        normalized_extract_path,
    )
    blocks = translate_paper.parse_markdown_blocks(working_extract)
    items_to_translate = translate_paper.collect_translatable_items(title, blocks)
    translations = batch_translate.translate_items_with_gtx(
        items_to_translate,
        target_language,
        batch_chars,
        cache_path=template_path.with_name("translation-cache.json"),
    )
    template_payload = translate_paper.build_template_payload(title, target_language, extract_path, items_to_translate)
    batch_translate.write_translation_template(template_path, template_payload, translations)

    translated_note_path.parent.mkdir(parents=True, exist_ok=True)
    translated_note_path, _translated_title = translate_paper.render_markdown(
        blocks=blocks,
        translations=translations,
        extract_dir=working_extract.parent,
        output_dir=out_dir,
        title=title,
        year=year,
        authors="",
        source_pdf=source_path,
        source_md=extract_path,
        target_language=target_language,
        translation_mode="google-gtx-fallback-local-unmatched",
        include_original_blocks=False,
    )
    append_queue_callout(
        translated_note_path,
        queue_rank=queue_rank,
        corpus=corpus,
        score=score,
        source_path=source_path,
        extract_path=extract_path.as_posix(),
        why_selected=why_selected,
    )

    metadata = build_metadata(
        record=record,
        title=title,
        year=year,
        source_md=extract_path,
        translated_note_path=translated_note_path,
    )
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    return QueueTranslationRecord(
        queue_rank=queue_rank,
        corpus=corpus,
        title=title,
        year=year,
        score=score,
        status="built",
        extract_path=extract_path.as_posix(),
        source_path=source_path,
        relative_path=relative_path,
        normalized_extract_path=working_extract.as_posix(),
        translated_note_path=translated_note_path.as_posix(),
        translation_template_path=template_path.as_posix(),
        metadata_path=metadata_path.as_posix(),
        message="Built local translated-paper copy from unmatched literature queue.",
    )


def main() -> None:
    args = parse_args()
    output_root = Path(args.output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    scored_candidates = []
    for queue_rank, record in enumerate(queue_items(Path(args.queue_json)), start=1):
        if int(record.get("score", 0)) < args.min_score:
            continue
        record = dict(record)
        record["_queue_rank"] = queue_rank
        scored_candidates.append(record)

    candidates = scored_candidates
    if args.only_missing:
        candidates = [
            record
            for record in scored_candidates
            if not output_exists_for_record(record, output_root)
        ]

    selected = candidates[args.offset : args.offset + args.limit] if args.limit > 0 else candidates[args.offset :]

    rows: list[QueueTranslationRecord] = []
    for record in selected:
        try:
            rows.append(
                build_for_record(
                    record=record,
                    output_root=output_root,
                    target_language=args.target_language,
                    batch_chars=args.batch_chars,
                    skip_existing=args.skip_existing,
                )
            )
        except Exception as exc:  # noqa: BLE001
            rows.append(
                QueueTranslationRecord(
                    queue_rank=int(record.get("_queue_rank", 0)),
                    corpus=paper_dossiers.normalize_whitespace(record.get("corpus")),
                    title=extract_title(record),
                    year=infer_year(record),
                    score=int(record.get("score", 0)),
                    status="error",
                    extract_path=paper_dossiers.normalize_whitespace(record.get("extract_path")),
                    source_path=paper_dossiers.normalize_whitespace(record.get("source_path")),
                    relative_path=paper_dossiers.normalize_whitespace(record.get("relative_path")),
                    normalized_extract_path="",
                    translated_note_path="",
                    translation_template_path="",
                    metadata_path="",
                    message=str(exc),
                )
            )

    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "eligible_total": len(scored_candidates),
        "filtered_total": len(candidates),
        "candidate_total": len(selected),
        "built_total": sum(1 for row in rows if row.status == "built"),
        "skipped_total": sum(1 for row in rows if row.status == "skipped-existing"),
        "failed_total": sum(1 for row in rows if row.status == "error"),
        "offset": args.offset,
        "limit": args.limit,
        "min_score": args.min_score,
        "only_missing": args.only_missing,
    }
    payload = {
        "summary": summary,
        "records": [asdict(row) for row in rows],
    }
    report_path = Path(args.report_out) if args.report_out else output_root / "batch-unmatched-report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
