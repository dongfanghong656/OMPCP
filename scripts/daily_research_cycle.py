#!/usr/bin/env python
import argparse
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

from research_question_flow import append_text, ensure_daily_note, load_json, timestamp_slug, to_portable_path, write_json, write_text


SCRIPT_DIR = Path(__file__).resolve().parent
RETRIEVAL_SCRIPT = SCRIPT_DIR / "retrieve_recent_papers.py"
QUESTION_RADAR_SCRIPT = SCRIPT_DIR / "question_radar.py"
DAILY_DIGEST_SCRIPT = SCRIPT_DIR / "daily_digest.py"
DEFAULT_REPORT_FOLDER_NAME = "daily-research-cycle"
DEFAULT_DAILY_SECTION_TITLE = "Daily Research Cycle"


def run_python_script(script_path: Path, *args: str):
    completed = subprocess.run(
        [sys.executable, str(script_path), *args],
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"{script_path.name} failed with return code {completed.returncode}\n"
            f"STDOUT:\n{completed.stdout}\nSTDERR:\n{completed.stderr}"
        )
    return completed.stdout.strip()


def create_run_dir(config: dict, explicit_dir: str | None) -> Path:
    if explicit_dir:
        run_dir = Path(explicit_dir)
        run_dir.mkdir(parents=True, exist_ok=True)
        return run_dir

    output_root = Path(config["output_root"])
    run_dir = output_root / DEFAULT_REPORT_FOLDER_NAME / f"{date.today().isoformat()}-{timestamp_slug()}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def today_retrieval_paths(config: dict):
    vault_root = Path(config["vault_root"])
    retrieval_folder = vault_root / config["obsidian"]["retrieval_folder"]
    stem = date.today().isoformat() + "-retrieval"
    return {
        "json": retrieval_folder / f"{stem}.json",
        "markdown": retrieval_folder / f"{stem}.md",
    }


def today_digest_path(config: dict):
    output_root = Path(config["output_root"])
    return output_root / f"{date.today().isoformat()}-daily-digest.md"


def append_cycle_summary_to_daily(config: dict, outputs: dict, errors):
    vault_root = Path(config["vault_root"])
    daily_path = vault_root / config["obsidian"]["daily_folder"] / f"{date.today().isoformat()}.md"
    ensure_daily_note(daily_path)

    lines = [f"\n## {DEFAULT_DAILY_SECTION_TITLE}\n"]
    retrieval_md = outputs.get("retrieval_markdown")
    if retrieval_md:
        retrieval_path = Path(retrieval_md)
        lines.append(f"- Retrieval note: [[{retrieval_path.stem}]]")
    question_radar_note = outputs.get("question_radar_note")
    if question_radar_note:
        radar_path = Path(question_radar_note)
        lines.append(f"- Question radar note: [[{radar_path.stem}]]")
    if outputs.get("daily_digest"):
        lines.append(f"- Daily digest report: `{outputs['daily_digest']}`")
    if errors:
        lines.append("- Errors:")
        for item in errors:
            lines.append(f"  - {item}")
    lines.append("")
    append_text(daily_path, "\n".join(lines))
    return daily_path


def render_summary_markdown(outputs: dict, errors):
    lines = [
        f"# Daily Research Cycle {date.today().isoformat()}",
        "",
    ]
    if outputs.get("retrieval_markdown"):
        lines.append(f"- Retrieval note: `{outputs['retrieval_markdown']}`")
    if outputs.get("retrieval_json"):
        lines.append(f"- Retrieval json: `{outputs['retrieval_json']}`")
    if outputs.get("question_radar_note"):
        lines.append(f"- Question radar note: `{outputs['question_radar_note']}`")
    if outputs.get("question_radar_markdown"):
        lines.append(f"- Question radar markdown: `{outputs['question_radar_markdown']}`")
    if outputs.get("daily_digest"):
        lines.append(f"- Daily digest report: `{outputs['daily_digest']}`")
    if outputs.get("daily_note"):
        lines.append(f"- Daily note: `{outputs['daily_note']}`")
    if errors:
        lines.extend(["", "## Errors", ""])
        lines.extend([f"- {item}" for item in errors])
    else:
        lines.extend(["", "## Errors", "", "- None recorded."])
    return "\n".join(lines).strip() + "\n"


def main():
    parser = argparse.ArgumentParser(description="Run the daily OCT research cycle: retrieval, question radar, and digest.")
    parser.add_argument("--config", required=True)
    parser.add_argument("--output-dir")
    parser.add_argument("--lookback-days", type=int, default=1)
    parser.add_argument("--skip-retrieval", action="store_true")
    parser.add_argument("--skip-question-radar", action="store_true")
    parser.add_argument("--skip-digest", action="store_true")
    parser.add_argument("--latest-literature-file")
    args = parser.parse_args()

    config = load_json(Path(args.config))
    run_dir = create_run_dir(config, args.output_dir)
    outputs = {
        "run_dir": to_portable_path(run_dir),
    }
    errors = []

    retrieval_paths = today_retrieval_paths(config)
    latest_literature_file = args.latest_literature_file

    if not args.skip_retrieval:
        try:
            run_python_script(RETRIEVAL_SCRIPT, "--config", args.config)
            if retrieval_paths["markdown"].exists():
                outputs["retrieval_markdown"] = to_portable_path(retrieval_paths["markdown"])
            if retrieval_paths["json"].exists():
                outputs["retrieval_json"] = to_portable_path(retrieval_paths["json"])
                latest_literature_file = latest_literature_file or str(retrieval_paths["json"])
        except RuntimeError as exc:
            errors.append(str(exc))
    else:
        if retrieval_paths["markdown"].exists():
            outputs["retrieval_markdown"] = to_portable_path(retrieval_paths["markdown"])
        if retrieval_paths["json"].exists():
            outputs["retrieval_json"] = to_portable_path(retrieval_paths["json"])

    if not args.skip_question_radar:
        radar_args = ["daily", "--config", args.config]
        if latest_literature_file:
            radar_args.extend(["--latest-literature-file", latest_literature_file, "--skip-live-literature"])
        try:
            radar_stdout = run_python_script(QUESTION_RADAR_SCRIPT, *radar_args)
            radar_outputs = json.loads(radar_stdout)
            outputs.update(
                {
                    "question_radar_json": radar_outputs.get("question_radar_json"),
                    "question_radar_markdown": radar_outputs.get("question_radar_markdown"),
                    "question_radar_note": radar_outputs.get("question_radar_note"),
                }
            )
        except (RuntimeError, json.JSONDecodeError) as exc:
            errors.append(str(exc))

    if not args.skip_digest:
        try:
            run_python_script(DAILY_DIGEST_SCRIPT, "--config", args.config, "--lookback-days", str(args.lookback_days))
            digest_path = today_digest_path(config)
            if digest_path.exists():
                outputs["daily_digest"] = to_portable_path(digest_path)
        except RuntimeError as exc:
            errors.append(str(exc))

    daily_path = append_cycle_summary_to_daily(config, outputs, errors)
    outputs["daily_note"] = to_portable_path(daily_path)

    write_json(run_dir / "daily_research_cycle.json", {"outputs": outputs, "errors": errors})
    write_text(run_dir / "daily_research_cycle.md", render_summary_markdown(outputs, errors))
    outputs["summary_json"] = to_portable_path(run_dir / "daily_research_cycle.json")
    outputs["summary_markdown"] = to_portable_path(run_dir / "daily_research_cycle.md")

    print(json.dumps(outputs, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
