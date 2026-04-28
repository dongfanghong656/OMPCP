#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

DEFAULT_EXCLUDE_SOURCE_PREFIXES = (
    "c:/users/1/onedrive - fzu.edu.cn",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Filter a discovered literature-candidate list into an extraction-ready manifest.")
    parser.add_argument("--input-json", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-md", required=True)
    parser.add_argument("--include-ext", action="append", default=[])
    parser.add_argument("--exclude-token", action="append", default=[])
    return parser.parse_args()


def normalize(value: str) -> str:
    return value.replace("\\", "/").lower()


def build_exclude_tokens(values: list[str]) -> list[str]:
    tokens = [normalize(value) for value in values]
    tokens.extend(DEFAULT_EXCLUDE_SOURCE_PREFIXES)
    return tokens


def render_markdown(summary: dict[str, object], records: list[dict[str, str]]) -> str:
    lines = [
        "# 净化后的本地文献候选清单",
        "",
        f"- 生成时间：`{summary['generated_at']}`",
        f"- 原始候选总数：`{summary['input_total']}`",
        f"- 保留总数：`{summary['kept_total']}`",
        "",
        "## 扩展名统计",
        "",
    ]
    for extension, count in summary["by_extension"].items():
        lines.append(f"- {extension}: {count}")
    lines.extend(["", "## 明细", ""])
    for record in records:
        lines.append(
            f"- {record.get('relative_path', '')} | {record.get('extension', '')} | {record.get('reason', '')}"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    input_path = Path(args.input_json)
    payload = json.loads(input_path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, list):
        raise ValueError("Input candidate JSON must be a JSON array.")

    include_ext = {value.lower() for value in args.include_ext} or None
    exclude_tokens = build_exclude_tokens(args.exclude_token)

    records: list[dict[str, str]] = []
    by_extension: Counter[str] = Counter()
    for item in payload:
        if not isinstance(item, dict):
            continue
        source_path = str(item.get("source_path", "")).strip()
        relative_path = str(item.get("relative_path", "")).strip()
        extension = str(item.get("extension", "")).lower()
        normalized = normalize(source_path or relative_path)
        if include_ext and extension not in include_ext:
            continue
        if any(token in normalized for token in exclude_tokens):
            continue
        records.append(item)
        by_extension[extension] += 1

    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "input_total": len(payload),
        "kept_total": len(records),
        "by_extension": dict(sorted(by_extension.items())),
    }

    output_json = Path(args.output_json)
    output_md = Path(args.output_md)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    output_md.write_text(render_markdown(summary, records), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
