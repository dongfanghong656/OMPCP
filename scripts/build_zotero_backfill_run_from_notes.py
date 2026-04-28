#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

import discovery_to_zotero as discovery
import local_pdf_to_zotero as local_pdf
from path_naming import safe_slug


def frontmatter_bounds(text: str) -> tuple[int, int] | None:
    match = re.match(r"\A---\r?\n.*?\r?\n---\r?\n?", text, flags=re.DOTALL)
    if not match:
        return None
    return (0, match.end())


def extract_frontmatter_value(frontmatter: str, key: str) -> str:
    match = re.search(rf"(?m)^{re.escape(key)}:\s*(.+)$", frontmatter)
    if not match:
        return ""
    value = match.group(1).strip()
    if value.startswith(("'", '"')) and value.endswith(("'", '"')) and len(value) >= 2:
        value = value[1:-1]
    return discovery.normalize_whitespace(value)


def extract_sync_zotero_key(text: str) -> str:
    match = re.search(r"- Zotero item: `([^`]+)`", text)
    if match:
        return discovery.normalize_whitespace(match.group(1))
    return ""


def extract_frontmatter_authors(frontmatter: str) -> list[str]:
    match = re.search(r"(?ms)^authors:\s*\n((?:\s+-\s*.+\n?)*)", frontmatter)
    if match:
        authors: list[str] = []
        for raw_line in match.group(1).splitlines():
            cleaned = discovery.normalize_whitespace(raw_line.lstrip("- ").strip())
            if cleaned.startswith(("'", '"')) and cleaned.endswith(("'", '"')) and len(cleaned) >= 2:
                cleaned = cleaned[1:-1]
            if cleaned:
                authors.append(cleaned)
        if authors:
            return authors
    inline = extract_frontmatter_value(frontmatter, "authors")
    if inline:
        return [part for part in local_pdf.parse_string_list(inline) if part]
    return []


def collect_candidates(vault_root: Path) -> list[local_pdf.LocalPdfImportCandidate]:
    paper_dir = vault_root / "02_Literature" / "Papers"
    candidates: list[local_pdf.LocalPdfImportCandidate] = []
    for path in sorted(paper_dir.glob("*.md")):
        if path.name.startswith("_"):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        bounds = frontmatter_bounds(text)
        frontmatter = text[bounds[0] : bounds[1]] if bounds else ""
        zotero_key = extract_frontmatter_value(frontmatter, "zotero_key") or extract_sync_zotero_key(text)
        if not zotero_key:
            continue
        pdf_path = extract_frontmatter_value(frontmatter, "source_pdf") or extract_frontmatter_value(frontmatter, "copied_pdf")
        candidate = local_pdf.LocalPdfImportCandidate(
            pdf_path=pdf_path,
            relative_path=Path(pdf_path).name if pdf_path else "",
            file_name=Path(pdf_path).name if pdf_path else "",
            title=extract_frontmatter_value(frontmatter, "title") or path.stem,
            authors=extract_frontmatter_authors(frontmatter),
            year=extract_frontmatter_value(frontmatter, "year"),
            doi=extract_frontmatter_value(frontmatter, "doi"),
            zotero_parent_key=zotero_key,
            already_in_zotero=True,
            zotero_match_reason="note-key",
        )
        candidates.append(candidate)
    return candidates


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a zotero_to_vault run.json from existing paper notes.")
    parser.add_argument("--config", required=True)
    parser.add_argument("--output-file", default="")
    parser.add_argument("--output-root", default="")
    parser.add_argument("--run-label", default="build-zotero-backfill-run-from-notes")
    return parser


def resolve_output_root(config: dict[str, Any], output_root: str) -> Path:
    return Path(output_root) if output_root else Path(config["output_root"])


def write_run_report(path: Path, run_id: str, candidates: list[local_pdf.LocalPdfImportCandidate]) -> None:
    lines = [
        "# Build Zotero Backfill Run From Notes",
        "",
        f"- Run ID: `{run_id}`",
        f"- Generated: `{datetime.now().isoformat(timespec='seconds')}`",
        f"- Candidates: {len(candidates)}",
        "",
        "## Items",
        "",
    ]
    for candidate in candidates:
        lines.append(f"- {candidate.title or '[untitled]'} | `{candidate.zotero_parent_key}` | pdf: {candidate.pdf_path or 'none'}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    config = discovery.load_json(Path(args.config))
    vault_root = Path(config["vault_root"])
    candidates = collect_candidates(vault_root)
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "run_id": safe_slug(args.run_label),
        "mode": "write-zotero",
        "candidates": [asdict(candidate) for candidate in candidates],
    }

    output_root = resolve_output_root(config, args.output_root)
    run_id = f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{safe_slug(args.run_label)}"
    run_dir = output_root / "zotero-to-vault" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    output_file = Path(args.output_file) if args.output_file else run_dir / "backfill-run.json"
    output_file.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (run_dir / "run.json").write_text(json.dumps({"run_id": run_id, "output_file": str(output_file), "candidates": len(candidates)}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_run_report(run_dir / "run.md", run_id, candidates)
    print(str(output_file))
    print(str(run_dir / "run.md"))


if __name__ == "__main__":
    main()
