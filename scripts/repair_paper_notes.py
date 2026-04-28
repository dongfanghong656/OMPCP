#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

import paper_dossiers
from path_naming import safe_slug


@dataclass
class RepairRecord:
    paper_path: str
    title: str
    status: str
    message: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Repair malformed paper-note frontmatter and mark synthetic examples.")
    parser.add_argument("--config", required=True)
    parser.add_argument("--output-root", default="")
    parser.add_argument("--run-label", default="repair-paper-notes")
    parser.add_argument("--write", action="store_true")
    return parser.parse_args()


def resolve_output_root(config: dict[str, Any], output_root: str) -> Path:
    return Path(output_root) if output_root else Path(config["output_root"])


def dump_frontmatter(data: dict[str, Any]) -> str:
    return "---\n" + yaml.safe_dump(data, sort_keys=False, allow_unicode=True).strip() + "\n---\n"


def paper_note_paths(config: dict[str, Any]) -> list[Path]:
    vault_root = Path(config["vault_root"])
    paper_dir = paper_dossiers.paper_note_directory(vault_root, config)
    return [path for path in sorted(paper_dir.glob("*.md")) if not path.name.startswith("_")]


def normalize_note_text(text: str) -> tuple[str, dict[str, Any], bool]:
    decoded = text.lstrip("\ufeff")
    frontmatter, body = paper_dossiers.split_frontmatter(decoded)
    if not frontmatter:
        return decoded, {}, False

    changed = decoded != text
    if paper_dossiers.is_synthetic_example_note(frontmatter):
        if paper_dossiers.normalize_whitespace(frontmatter.get("library_status")) != "synthetic-example":
            frontmatter["library_status"] = "synthetic-example"
            changed = True

    rendered = dump_frontmatter(frontmatter) + body.lstrip("\n")
    if rendered != decoded:
        changed = True
    return rendered if rendered.endswith("\n") else rendered + "\n", frontmatter, changed


def repair_paper_notes(config: dict[str, Any], *, write: bool = False) -> list[RepairRecord]:
    records: list[RepairRecord] = []
    for note_path in paper_note_paths(config):
        original = note_path.read_text(encoding="utf-8", errors="replace")
        normalized, frontmatter, changed = normalize_note_text(original)
        title = paper_dossiers.pick_title(note_path, normalized, frontmatter) if frontmatter else note_path.stem
        if not frontmatter:
            records.append(RepairRecord(str(note_path), title, "unchanged", "No parseable frontmatter detected."))
            continue
        if changed and write:
            note_path.write_text(normalized, encoding="utf-8")
            status = "repaired"
            message = "Normalized BOM/duplicate frontmatter or marked a synthetic example."
        elif changed:
            status = "planned"
            message = "Would normalize BOM/duplicate frontmatter or mark a synthetic example."
        else:
            status = "unchanged"
            message = "Note frontmatter is already normalized."
        records.append(RepairRecord(str(note_path), title, status, message))
    return records


def write_run_report(path: Path, run_id: str, records: list[RepairRecord]) -> None:
    lines = [
        "# Repair Paper Notes",
        "",
        f"- Run ID: `{run_id}`",
        f"- Generated: `{datetime.now().isoformat(timespec='seconds')}`",
        f"- Checked: {len(records)}",
        f"- Repaired: {sum(1 for record in records if record.status in {'repaired', 'planned'})}",
        f"- Unchanged: {sum(1 for record in records if record.status == 'unchanged')}",
        "",
        "## Notes",
        "",
    ]
    for record in records:
        lines.append(f"- {record.title} | {record.status}")
        lines.append(f"  - Note: {record.message}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    config = paper_dossiers.load_json(Path(args.config))
    output_root = resolve_output_root(config, args.output_root)
    run_id = f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{safe_slug(args.run_label)}"
    run_dir = output_root / "vault-reorg" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    records = repair_paper_notes(config, write=args.write)
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
