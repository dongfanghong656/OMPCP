#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

import paper_dossiers


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a local literature inventory summary.")
    parser.add_argument("--pdf-root", required=True)
    parser.add_argument("--vault-root", default="")
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-md", default="")
    return parser.parse_args()


def scan_pdf_root(pdf_root: Path) -> tuple[list[dict[str, Any]], dict[str, int]]:
    pdf_entries: list[dict[str, Any]] = []
    category_counter: Counter[str] = Counter()

    for path in sorted(pdf_root.rglob("*.pdf")):
        rel_path = path.relative_to(pdf_root).as_posix()
        top_category = rel_path.split("/", 1)[0] if "/" in rel_path else "(root)"
        category_counter[top_category] += 1
        pdf_entries.append(
            {
                "path": str(path),
                "relative_path": rel_path,
                "top_category": top_category,
                "size_bytes": path.stat().st_size,
            }
        )

    return pdf_entries, dict(sorted(category_counter.items()))


def scan_dossiers(vault_root: Path) -> list[dict[str, Any]]:
    config = {
        "vault_root": str(vault_root),
        "obsidian": {
            "paper_folder": "02_Papers",
            "zotero_folder": "12_Zotero",
            "attachment_folder": "08_Attachments",
            "writing_folder": "06_Writing",
        },
        "translation": {"render": {"translated_folder_name": "translated-papers"}},
    }
    dossiers = paper_dossiers.build_dossiers(config)
    payload: list[dict[str, Any]] = []
    for dossier in dossiers:
        payload.append(
            {
                "title": dossier.title,
                "title_original": dossier.title_original,
                "year": dossier.year,
                "translated_available": bool(dossier.translated_note_rel_path),
                "extract_available": bool(dossier.extract_rel_path),
                "pdf_available": bool(
                    dossier.copied_pdf_rel_path or dossier.source_pdf_rel_path or dossier.source_pdf_external_path
                ),
                "paper_note": dossier.paper_note_rel_path,
                "translated_note": dossier.translated_note_rel_path,
                "source_pdf_external_path": dossier.source_pdf_external_path,
            }
        )
    return payload


def markdown_report(payload: dict[str, Any]) -> str:
    lines = [
        "# 本地文献库存清单",
        "",
        f"- PDF 总数：`{payload['summary']['pdf_total']}`",
        f"- 已建主笔记：`{payload['summary']['paper_note_total']}`",
        f"- 已有中文译注：`{payload['summary']['translated_total']}`",
        f"- 已有原文抽取：`{payload['summary']['extract_total']}`",
        "",
        "## PDF 分类统计",
        "",
    ]
    for category, count in payload["summary"]["pdf_by_category"].items():
        lines.append(f"- {category}: {count}")
    lines.extend(["", "## 论文状态概览", ""])
    for item in payload.get("papers", [])[:40]:
        lines.append(
            f"- {item['year'] or 'n.d.'} | {item['title']} | 译注={item['translated_available']} | 抽取={item['extract_available']}"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    pdf_root = Path(args.pdf_root)
    vault_root = Path(args.vault_root) if args.vault_root else None

    pdf_entries, pdf_by_category = scan_pdf_root(pdf_root)
    papers = scan_dossiers(vault_root) if vault_root and vault_root.exists() else []
    translated_total = sum(1 for item in papers if item["translated_available"])
    extract_total = sum(1 for item in papers if item["extract_available"])

    payload = {
        "pdf_root": str(pdf_root),
        "vault_root": str(vault_root) if vault_root else "",
        "summary": {
            "pdf_total": len(pdf_entries),
            "pdf_by_category": pdf_by_category,
            "paper_note_total": len(papers),
            "translated_total": translated_total,
            "extract_total": extract_total,
        },
        "papers": papers,
        "pdf_entries": pdf_entries,
    }

    output_json = Path(args.output_json)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.output_md:
        output_md = Path(args.output_md)
        output_md.parent.mkdir(parents=True, exist_ok=True)
        output_md.write_text(markdown_report(payload), encoding="utf-8")

    print(json.dumps(payload["summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
