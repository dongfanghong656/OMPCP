#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a triage report for failed literature extractions.")
    parser.add_argument("--inventory", action="append", required=True, help="Format: corpus_name=path/to/inventory.json")
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-md", required=True)
    return parser.parse_args()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def classify_failure(record: dict[str, Any]) -> str:
    message = str(record.get("message") or "").strip()
    relative_path = str(record.get("relative_path") or "")
    filename = Path(relative_path.replace("\\", "/")).name
    if "OneDrive placeholder unavailable" in message:
        return "onedrive-placeholder-unavailable"
    if message == "File is not a zip file":
        return "lock-or-bad-docx" if filename.startswith("~$") else "bad-docx"
    if message == "[Errno 22] Invalid argument":
        return "cloud-path-or-placeholder"
    if "decrypt" in message.lower():
        return "encrypted-pdf"
    if "Stream has ended unexpectedly" in message:
        return "damaged-pdf-stream"
    if "missing at extraction time" in message.lower():
        return "source-missing"
    if "decode text file" in message.lower():
        return "text-decode-failure"
    return "other"


def render_markdown(summary: dict[str, Any], corpora: list[dict[str, Any]]) -> str:
    lines = [
        "# 文献抽取失败分诊报告",
        "",
        f"- 生成时间：`{summary['generated_at']}`",
        f"- 涉及语料库：`{summary['corpus_total']}`",
        f"- 失败项总数：`{summary['failed_total']}`",
        "",
        "## 总体分类",
        "",
    ]
    for label, count in summary["by_category"].items():
        lines.append(f"- {label}: `{count}`")

    for corpus in corpora:
        lines.extend(
            [
                "",
                f"## {corpus['corpus']}",
                "",
                f"- 失败总数：`{corpus['failed_total']}`",
                "",
                "### 分类统计",
                "",
            ]
        )
        for label, count in corpus["by_category"].items():
            lines.append(f"- {label}: `{count}`")
        lines.extend(["", "### 示例", ""])
        for category, examples in corpus["examples"].items():
            lines.append(f"- {category}")
            for example in examples:
                lines.append(f"  - `{example['relative_path']}` | {example['message']}")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    corpus_reports: list[dict[str, Any]] = []
    total_by_category: Counter[str] = Counter()
    failed_total = 0

    for spec in args.inventory:
        if "=" not in spec:
            raise ValueError(f"Invalid inventory spec: {spec}")
        corpus_name, raw_path = spec.split("=", 1)
        path = Path(raw_path)
        payload = load_json(path)
        records = payload.get("records", []) if isinstance(payload, dict) else payload
        failed = [record for record in records if str(record.get("status") or "") == "failed"]
        category_counts: Counter[str] = Counter()
        examples: dict[str, list[dict[str, str]]] = {}
        for record in failed:
            category = classify_failure(record)
            category_counts[category] += 1
            examples.setdefault(category, [])
            if len(examples[category]) < 5:
                examples[category].append(
                    {
                        "relative_path": str(record.get("relative_path") or ""),
                        "message": str(record.get("message") or ""),
                    }
                )
        total_by_category.update(category_counts)
        failed_total += len(failed)
        corpus_reports.append(
            {
                "corpus": corpus_name,
                "inventory_path": path.as_posix(),
                "failed_total": len(failed),
                "by_category": dict(category_counts),
                "examples": examples,
            }
        )

    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "corpus_total": len(corpus_reports),
        "failed_total": failed_total,
        "by_category": dict(total_by_category),
    }
    payload = {
        "summary": summary,
        "corpora": corpus_reports,
    }

    output_json = Path(args.output_json)
    output_md = Path(args.output_md)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    output_md.write_text(render_markdown(summary, corpus_reports), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
