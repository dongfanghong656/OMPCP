#!/usr/bin/env python
import argparse
import json
from datetime import date, datetime, timedelta
from pathlib import Path

DEFAULT_PEOPLE_FOLDER = "13_People"
DEFAULT_RELATIONSHIP_FOLDER = "14_Relationships"
ACADEMIC_PAPER_FOLDER = "02_Literature/Papers"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def recent_files(folder: Path, days: int):
    if not folder.exists():
        return []
    cutoff = datetime.now() - timedelta(days=days)
    files = []
    for path in folder.glob("*.md"):
        if path.name.startswith("_"):
            continue
        modified = datetime.fromtimestamp(path.stat().st_mtime)
        if modified >= cutoff:
            files.append((modified, path))
    return sorted(files, reverse=True)


def recent_files_many(folders, days: int):
    merged = {}
    for folder in folders:
        for modified, path in recent_files(folder, days):
            merged[str(path.resolve())] = (modified, path)
    return sorted(merged.values(), reverse=True)


def list_section(title: str, items):
    lines = [f"## {title}", ""]
    if not items:
        lines.append("- None in the lookback window.")
    else:
        for modified, path in items:
            lines.append(f"- {path.stem} | updated {modified.strftime('%Y-%m-%d %H:%M')}")
    lines.append("")
    return lines


def obsidian_with_defaults(obsidian):
    merged = dict(obsidian)
    merged.setdefault("people_folder", DEFAULT_PEOPLE_FOLDER)
    merged.setdefault("relationship_folder", DEFAULT_RELATIONSHIP_FOLDER)
    return merged


def paper_note_folders(vault_root: Path, obsidian):
    folders = [vault_root / obsidian["paper_folder"]]
    academic_folder = vault_root / ACADEMIC_PAPER_FOLDER
    if str(academic_folder) != str(folders[0]):
        folders.append(academic_folder)
    return folders


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--lookback-days", type=int, default=1)
    args = parser.parse_args()

    config = load_json(Path(args.config))
    vault_root = Path(config["vault_root"])
    output_root = Path(config["output_root"])
    obs = obsidian_with_defaults(config["obsidian"])
    output_root.mkdir(parents=True, exist_ok=True)

    report_lines = [
        f"# Daily Digest {date.today().isoformat()}",
        "",
        "This digest summarizes what changed in the OCT research vault within the configured lookback window.",
        "",
    ]
    report_lines += list_section("Paper Notes", recent_files_many(paper_note_folders(vault_root, obs), args.lookback_days))
    report_lines += list_section("Progress Notes", recent_files(vault_root / obs["progress_folder"], args.lookback_days))
    report_lines += list_section("Task Notes", recent_files(vault_root / obs["task_folder"], args.lookback_days))
    report_lines += list_section("Retrieval Notes", recent_files(vault_root / obs["retrieval_folder"], args.lookback_days))
    report_lines += list_section("Conversation Notes", recent_files(vault_root / obs["conversation_folder"], args.lookback_days))
    report_lines += list_section("People Notes", recent_files(vault_root / obs["people_folder"], args.lookback_days))
    report_lines += list_section(
        "Relationship Event Notes",
        recent_files(vault_root / obs["relationship_folder"], args.lookback_days),
    )

    out_path = output_root / f"{date.today().isoformat()}-daily-digest.md"
    out_path.write_text("\n".join(report_lines), encoding="utf-8")
    print(str(out_path))


if __name__ == "__main__":
    main()
