#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import batch_build_translated_papers as batch_translate
import paper_dossiers
import translate_paper


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = PROJECT_ROOT / "config.json"
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "reports" / "literature-html-pipeline" / "local-translated-papers"


@dataclass
class LocalTranslationRecord:
    note_path: str
    title: str
    year: str
    status: str
    extract_path: str
    normalized_extract_path: str
    translated_note_path: str
    translation_template_path: str
    message: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build local translated-paper copies without modifying the OneDrive vault.")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--manifest", required=True, help="JSON list of note targets with optional fallback paths.")
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--report-out", default="")
    parser.add_argument("--target-language", default="zh-CN")
    parser.add_argument("--batch-chars", type=int, default=1400)
    parser.add_argument("--skip-existing", action="store_true")
    return parser.parse_args()


def local_slug(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", paper_dossiers.normalize_whitespace(value).lower()).strip("-")
    return cleaned[:96].strip("-") or "paper"


def dump_frontmatter(data: dict[str, Any]) -> str:
    return "---\n" + json.dumps(data, ensure_ascii=False, indent=2) + "\n---\n"


def manifest_items(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, list):
        raise ValueError("Manifest must be a JSON array.")
    return [item for item in payload if isinstance(item, dict)]


def build_output_dir(output_root: Path, title: str, year: str) -> Path:
    folder = local_slug(f"{year}-{title}" if year else title)
    target = output_root / folder
    target.mkdir(parents=True, exist_ok=True)
    return target


def build_for_item(
    *,
    config: dict[str, Any],
    item: dict[str, Any],
    output_root: Path,
    target_language: str,
    batch_chars: int,
    skip_existing: bool,
) -> LocalTranslationRecord:
    vault_root = Path(config["vault_root"])
    note_path = batch_translate.resolve_note_path(vault_root, item["note_path"]).resolve()
    note_text = note_path.read_text(encoding="utf-8", errors="replace")
    frontmatter, _body = paper_dossiers.split_frontmatter(note_text)
    title = paper_dossiers.normalize_whitespace(frontmatter.get("title")) or note_path.stem
    title_original = (
        paper_dossiers.normalize_whitespace(frontmatter.get("title_original"))
        or paper_dossiers.normalize_whitespace(frontmatter.get("title_en"))
        or title
    )
    year = paper_dossiers.normalize_whitespace(frontmatter.get("year"))
    authors = ", ".join(paper_dossiers.coerce_list(frontmatter.get("authors")))

    out_dir = build_output_dir(output_root, title, year)
    translated_note_path = out_dir / "translated.md"
    template_path = out_dir / "translation-template.json"
    normalized_extract_path = out_dir / "normalized-extract.md"

    if skip_existing and translated_note_path.exists():
        source_md = paper_dossiers.normalize_whitespace(item.get("fallback_extract") or frontmatter.get("extract_path"))
        return LocalTranslationRecord(
            note_path=str(note_path),
            title=title,
            year=year,
            status="skipped-existing",
            extract_path=source_md,
            normalized_extract_path=normalized_extract_path.as_posix() if normalized_extract_path.exists() else "",
            translated_note_path=translated_note_path.as_posix(),
            translation_template_path=template_path.as_posix() if template_path.exists() else "",
            message="Local translated copy already exists.",
        )

    fallback_pdf = batch_translate.resolve_optional_path(item.get("fallback_pdf", ""))
    fallback_extract = batch_translate.resolve_optional_path(item.get("fallback_extract", ""))
    extract_path, generated_extract = batch_translate.choose_extract(frontmatter, fallback_pdf, fallback_extract, vault_root)
    skip_normalization = bool(item.get("skip_normalization"))
    if skip_normalization:
        working_extract = extract_path
    else:
        working_extract = batch_translate.normalize_extract_markdown(
            extract_path,
            title,
            normalized_extract_path,
            start_marker=paper_dossiers.normalize_whitespace(item.get("start_marker")),
            end_marker=paper_dossiers.normalize_whitespace(item.get("end_marker")),
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

    source_pdf = paper_dossiers.normalize_whitespace(frontmatter.get("source_pdf") or frontmatter.get("copied_pdf"))
    translated_note_path, _translated_title = translate_paper.render_markdown(
        blocks=blocks,
        translations=translations,
        extract_dir=working_extract.parent,
        output_dir=out_dir,
        title=title,
        year=year,
        authors=authors,
        source_pdf=source_pdf,
        source_md=extract_path,
        target_language=target_language,
        translation_mode="google-gtx-fallback-local",
        include_original_blocks=False,
    )

    callout = (
        "> [!note]\n"
        "> 译注说明：本页为工作区本地译注副本，用于批量 HTML 生成与精读整理。\n"
        f"> 原论文笔记：`{note_path.as_posix()}`\n"
        f"> 源文抽取：`{extract_path.as_posix()}`\n"
        f"> 生成路径：`google-gtx-fallback-local` + `{'generated full-text extract' if generated_extract else 'existing extract'}`\n\n"
    )
    text = translated_note_path.read_text(encoding="utf-8")
    translated_note_path.write_text(text + ("\n" if not text.endswith("\n") else "") + callout, encoding="utf-8")

    meta = {
        "paper_note_path": note_path.as_posix(),
        "paper_title_original": title_original,
        "paper_title": title,
        "year": year,
        "source_md": extract_path.as_posix(),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }
    meta_path = out_dir / "local-metadata.json"
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    return LocalTranslationRecord(
        note_path=str(note_path),
        title=title,
        year=year,
        status="built",
        extract_path=extract_path.as_posix(),
        normalized_extract_path=working_extract.as_posix() if working_extract != extract_path else "",
        translated_note_path=translated_note_path.as_posix(),
        translation_template_path=template_path.as_posix(),
        message="Built local translated-paper copy in workspace.",
    )


def main() -> None:
    args = parse_args()
    config = paper_dossiers.load_json(Path(args.config))
    output_root = Path(args.output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    rows: list[LocalTranslationRecord] = []
    for item in manifest_items(Path(args.manifest)):
        try:
            rows.append(
                build_for_item(
                    config=config,
                    item=item,
                    output_root=output_root,
                    target_language=args.target_language,
                    batch_chars=args.batch_chars,
                    skip_existing=args.skip_existing,
                )
            )
        except Exception as exc:  # noqa: BLE001
            rows.append(
                LocalTranslationRecord(
                    note_path=str(item.get("note_path", "")),
                    title="",
                    year="",
                    status="error",
                    extract_path="",
                    normalized_extract_path="",
                    translated_note_path="",
                    translation_template_path="",
                    message=str(exc),
                )
            )

    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "candidate_total": len(rows),
        "built_total": sum(1 for row in rows if row.status == "built"),
        "skipped_total": sum(1 for row in rows if row.status == "skipped-existing"),
        "failed_total": sum(1 for row in rows if row.status == "error"),
    }
    payload = {
        "summary": summary,
        "records": [asdict(row) for row in rows],
    }
    report_path = Path(args.report_out) if args.report_out else output_root / "batch_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
