#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BUILD_SCRIPT = PROJECT_ROOT / "scripts" / "build_annotated_paper_html.py"
DEFAULT_REPORT = PROJECT_ROOT / "reports" / "literature-html-pipeline" / "local-translated-papers" / "batch1-report.json"
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "reports" / "literature-html-pipeline" / "generated-local"
NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


@dataclass
class LocalHtmlRecord:
    translated_note_path: str
    output_html: str
    status: str
    title: str
    message: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build annotated HTML from local translated-paper copies.")
    parser.add_argument("--report-json", default=str(DEFAULT_REPORT))
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--course-info", default="OCT 文献精读自动整理")
    parser.add_argument("--skip-existing", action="store_true")
    return parser.parse_args()


def slugify(value: str) -> str:
    cleaned = NON_ALNUM_RE.sub("-", value.lower()).strip("-")
    return cleaned[:96].strip("-") or "paper"


def decode_output(payload: bytes) -> str:
    return payload.decode("utf-8", errors="replace").strip() if payload else ""


def load_report(path: Path) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    records = payload.get("records", payload)
    if not isinstance(records, list):
        raise ValueError("Report must contain a list of records.")
    return [item for item in records if isinstance(item, dict)]


def html_name(title: str, year: str, translated_path: Path) -> str:
    # Keep the HTML filename aligned with build_annotated_html_library.py, which
    # indexes local records by the translated-paper folder name. This avoids CJK
    # titles collapsing to generic names such as "paper-annotated.html".
    return f"{translated_path.parent.name}-annotated.html"


def build_one(record: dict, output_root: Path, course_info: str, skip_existing: bool) -> LocalHtmlRecord:
    translated_note_path = Path(str(record.get("translated_note_path", "")).replace("\\", "/"))
    metadata_path = translated_note_path.parent / "local-metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    title = str(metadata.get("paper_title", "")).strip() or translated_note_path.parent.name
    title_original = str(metadata.get("paper_title_original", "")).strip() or title
    year = str(metadata.get("year", "")).strip()
    source_md = str(metadata.get("source_md", "")).strip()
    output_html = output_root / html_name(title, year, translated_note_path)

    if skip_existing and output_html.exists():
        return LocalHtmlRecord(
            translated_note_path=translated_note_path.as_posix(),
            output_html=output_html.as_posix(),
            status="skipped-existing",
            title=title,
            message="HTML already exists.",
        )

    command = [
        sys.executable,
        str(BUILD_SCRIPT),
        "--translated-md",
        str(translated_note_path),
        "--source-md",
        source_md,
        "--paper-title",
        title,
        "--paper-title-original",
        title_original,
        "--course-info",
        course_info,
        "--output-html",
        str(output_html),
    ]
    completed = subprocess.run(command, capture_output=True, text=False)
    if completed.returncode == 0:
        return LocalHtmlRecord(
            translated_note_path=translated_note_path.as_posix(),
            output_html=output_html.as_posix(),
            status="built",
            title=title,
            message=decode_output(completed.stdout) or "built",
        )
    return LocalHtmlRecord(
        translated_note_path=translated_note_path.as_posix(),
        output_html=output_html.as_posix(),
        status="failed",
        title=title,
        message=decode_output(completed.stderr) or decode_output(completed.stdout) or "failed",
    )


def main() -> None:
    args = parse_args()
    output_root = Path(args.output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    rows: list[LocalHtmlRecord] = []
    allowed_statuses = {"built", "skipped-existing"}
    for record in load_report(Path(args.report_json)):
        if str(record.get("status", "")).strip() not in allowed_statuses:
            continue
        rows.append(build_one(record, output_root, args.course_info, args.skip_existing))

    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "candidate_total": len(rows),
        "built_total": sum(1 for row in rows if row.status == "built"),
        "skipped_total": sum(1 for row in rows if row.status == "skipped-existing"),
        "failed_total": sum(1 for row in rows if row.status == "failed"),
    }
    payload = {"summary": summary, "records": [asdict(row) for row in rows]}
    (output_root / "batch_inventory.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_root / "batch_inventory.md").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
