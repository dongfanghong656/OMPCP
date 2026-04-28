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
from typing import Any

import paper_dossiers


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = PROJECT_ROOT / "config.json"
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "reports" / "literature-html-pipeline" / "generated"
BUILD_SCRIPT = PROJECT_ROOT / "scripts" / "build_annotated_paper_html.py"
NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


@dataclass
class HtmlBuildRecord:
    paper_note_rel_path: str
    title: str
    year: str
    translated_note_rel_path: str
    output_html: str
    status: str
    message: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Batch-build dual-column annotated HTML from paper notes.")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--course-info", default="OCT 文献精读自动整理")
    parser.add_argument("--skip-existing", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    return parser.parse_args()


def slugify(value: str, limit: int = 96) -> str:
    slug = NON_ALNUM_RE.sub("-", paper_dossiers.normalize_whitespace(value).lower()).strip("-")
    return (slug[:limit].strip("-") or "paper")


def html_target(output_root: Path, dossier: paper_dossiers.PaperDossier) -> Path:
    stem = Path(dossier.paper_note_rel_path).stem
    stem = re.sub(r"^\[(19|20)\d{2}\]\s*", "", stem)
    slug = slugify((dossier.year + " " + stem).strip())
    return output_root / f"{slug}-annotated.html"


def decode_output(payload: bytes) -> str:
    if not payload:
        return ""
    return payload.decode("utf-8", errors="replace").strip()


def build_for_dossier(
    *,
    vault_root: Path,
    dossier: paper_dossiers.PaperDossier,
    output_root: Path,
    course_info: str,
    skip_existing: bool,
) -> HtmlBuildRecord:
    output_html = html_target(output_root, dossier)
    if skip_existing and output_html.exists():
        return HtmlBuildRecord(
            paper_note_rel_path=dossier.paper_note_rel_path,
            title=dossier.title,
            year=dossier.year,
            translated_note_rel_path=dossier.translated_note_rel_path,
            output_html=output_html.as_posix(),
            status="skipped-existing",
            message="HTML already exists.",
        )

    paper_note_path = vault_root / dossier.paper_note_rel_path
    command = [
        sys.executable,
        str(BUILD_SCRIPT),
        "--paper-note",
        str(paper_note_path),
        "--course-info",
        course_info,
        "--output-html",
        str(output_html),
    ]
    if dossier.translated_note_rel_path:
        command.extend(["--translated-md", str(vault_root / dossier.translated_note_rel_path)])
    if dossier.extract_rel_path:
        command.extend(["--source-md", str(vault_root / dossier.extract_rel_path)])
    if dossier.translation_template_rel_path:
        command.extend(["--translation-template", str(vault_root / dossier.translation_template_rel_path)])

    completed = subprocess.run(command, capture_output=True, text=False)
    if completed.returncode == 0:
        message = paper_dossiers.normalize_whitespace(decode_output(completed.stdout)) or "built"
        status = "built"
    else:
        message = paper_dossiers.normalize_whitespace(
            decode_output(completed.stderr) or decode_output(completed.stdout)
        ) or "failed"
        status = "failed"
    return HtmlBuildRecord(
        paper_note_rel_path=dossier.paper_note_rel_path,
        title=dossier.title,
        year=dossier.year,
        translated_note_rel_path=dossier.translated_note_rel_path,
        output_html=output_html.as_posix(),
        status=status,
        message=message,
    )


def render_markdown(summary: dict[str, Any], rows: list[HtmlBuildRecord]) -> str:
    lines = [
        "# 双栏批注 HTML 批量生成结果",
        "",
        f"- 生成时间：`{summary['generated_at']}`",
        f"- 候选总数：`{summary['candidate_total']}`",
        f"- 已生成：`{summary['built_total']}`",
        f"- 已跳过：`{summary['skipped_total']}`",
        f"- 失败：`{summary['failed_total']}`",
        "",
    ]
    for row in rows:
        lines.extend(
            [
                f"- [{row.status}] `{row.paper_note_rel_path}` -> `{row.output_html}`",
                f"  - title: {row.title}",
                f"  - note: {row.message}",
            ]
        )
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    config = paper_dossiers.load_json(Path(args.config))
    vault_root = Path(config["vault_root"])
    output_root = Path(args.output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    dossiers = [
        dossier
        for dossier in sorted(paper_dossiers.build_dossiers(config), key=lambda item: (item.year or "", item.paper_note_rel_path.lower()))
        if dossier.translated_note_rel_path
    ]
    if args.limit and args.limit > 0:
        dossiers = dossiers[: args.limit]

    rows: list[HtmlBuildRecord] = []
    for dossier in dossiers:
        rows.append(
            build_for_dossier(
                vault_root=vault_root,
                dossier=dossier,
                output_root=output_root,
                course_info=args.course_info,
                skip_existing=args.skip_existing,
            )
        )

    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "candidate_total": len(rows),
        "built_total": sum(1 for row in rows if row.status == "built"),
        "skipped_total": sum(1 for row in rows if row.status == "skipped-existing"),
        "failed_total": sum(1 for row in rows if row.status == "failed"),
    }
    payload = {
        "summary": summary,
        "records": [asdict(row) for row in rows],
    }
    (output_root / "batch_inventory.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_root / "batch_inventory.md").write_text(render_markdown(summary, rows), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
