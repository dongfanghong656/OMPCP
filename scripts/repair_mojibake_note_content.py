#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import discovery_to_zotero as discovery
from path_naming import safe_slug


MOJIBAKE_TOKENS = (
    "鍩",
    "鍏",
    "绯",
    "鏂",
    "鐨",
    "锛",
    "銆",
    "璇",
    "鏈",
    "闂",
    "鎴",
    "浠",
    "绗",
    "閭",
    "瀹",
    "鏍",
    "缁",
    "鐩",
    "骞",
)


@dataclass
class RepairRecord:
    path: str
    score_before: int
    score_after: int
    changed: bool = False
    status: str = "pending"
    message: str = ""
    replacements: list[str] = field(default_factory=list)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Repair reversible mojibake text inside vault markdown notes.")
    parser.add_argument("--vault-root", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--run-label", default="repair-mojibake-note-content")
    parser.add_argument("--min-score", type=int, default=20)
    parser.add_argument("--path-contains", action="append", default=[])
    parser.add_argument("--write", action="store_true")
    return parser.parse_args()


def mojibake_score(text: str) -> int:
    return sum(text.count(token) for token in MOJIBAKE_TOKENS)


def is_reversible_pair(original: str, repaired: str) -> bool:
    for encoding in ("gbk", "cp936", "latin1"):
        try:
            if repaired.encode("utf-8").decode(encoding) == original:
                return True
        except Exception:
            continue
    return False


def looks_better(original: str, repaired: str) -> bool:
    if not repaired or repaired == original:
        return False
    before = mojibake_score(original)
    after = mojibake_score(repaired)
    if after > before:
        return False
    original_private = len(re.findall(r"[\ue000-\uf8ff]", original))
    repaired_private = len(re.findall(r"[\ue000-\uf8ff]", repaired))
    if repaired_private > original_private:
        return False
    if is_reversible_pair(original, repaired):
        return True
    if after == before:
        return False
    return True


def reverse_mojibake_segment(value: str) -> str:
    candidates: list[str] = []
    for source_encoding in ("gbk", "cp936", "latin1"):
        try:
            repaired = value.encode(source_encoding).decode("utf-8")
            candidates.append(repaired)
        except Exception:
            continue
    if not candidates:
        return value
    best = value
    for candidate in candidates:
        if looks_better(value, candidate):
            if best == value or mojibake_score(candidate) < mojibake_score(best):
                best = candidate
    return best


def repair_text(text: str) -> tuple[str, list[str]]:
    repaired = text
    replacements: list[str] = []
    segments = sorted(set(re.findall(r"[\u0080-\uffff]{4,}", text)), key=len, reverse=True)
    for segment in segments:
        fixed = reverse_mojibake_segment(segment)
        if fixed != segment:
            repaired = repaired.replace(segment, fixed)
            replacements.append(f"{segment[:24]} -> {fixed[:24]}")
    return repaired, replacements


def write_run_report(path: Path, run_id: str, records: list[RepairRecord]) -> None:
    lines = [
        "# Repair Mojibake Note Content",
        "",
        f"- Run ID: `{run_id}`",
        f"- Generated: `{datetime.now().isoformat(timespec='seconds')}`",
        f"- Checked: {len(records)}",
        f"- Updated: {sum(1 for record in records if record.status == 'updated')}",
        f"- Unchanged: {sum(1 for record in records if record.status == 'unchanged')}",
        f"- Failed: {sum(1 for record in records if record.status == 'failed')}",
        "",
        "## Items",
        "",
    ]
    for record in records:
        lines.append(
            f"- {record.path} | {record.status} | score {record.score_before} -> {record.score_after}"
        )
        if record.message:
            lines.append(f"  - Message: {record.message}")
        if record.replacements:
            for replacement in record.replacements[:5]:
                lines.append(f"  - {replacement}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def path_allowed(path: Path, path_filters: list[str]) -> bool:
    if not path_filters:
        return True
    as_posix = path.as_posix()
    return any(token in as_posix for token in path_filters)


def main() -> None:
    args = parse_args()
    vault_root = Path(args.vault_root)
    output_root = Path(args.output_root)
    run_id = f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{safe_slug(args.run_label)}"
    run_dir = output_root / "mojibake-repair" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    records: list[RepairRecord] = []
    for path in sorted(vault_root.rglob("*.md")):
        if not path_allowed(path, args.path_contains):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
            score_before = mojibake_score(text)
            if score_before < args.min_score:
                continue
            repaired, replacements = repair_text(text)
            score_after = mojibake_score(repaired)
            record = RepairRecord(
                path=str(path),
                score_before=score_before,
                score_after=score_after,
                changed=repaired != text,
                replacements=replacements,
            )
            if repaired != text and score_after < score_before:
                if args.write:
                    path.write_text(repaired, encoding="utf-8")
                    record.status = "updated"
                    record.message = "Repaired reversible mojibake segments."
                else:
                    record.status = "planned"
                    record.message = "Would repair reversible mojibake segments."
            else:
                record.status = "unchanged"
                record.message = "No safe reversible mojibake repair detected."
            records.append(record)
        except Exception as exc:
            records.append(
                RepairRecord(
                    path=str(path),
                    score_before=0,
                    score_after=0,
                    changed=False,
                    status="failed",
                    message=str(exc),
                )
            )

    payload = {
        "run_id": run_id,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "records": [asdict(record) for record in records],
    }
    (run_dir / "run.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_run_report(run_dir / "run.md", run_id, records)
    print(str(run_dir / "run.md"))


if __name__ == "__main__":
    main()
