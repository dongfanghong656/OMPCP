#!/usr/bin/env python
import argparse
import json
from datetime import date, datetime
from pathlib import Path

from research_question_flow import (
    build_request_payload,
    extract_response_text,
    load_json,
    post_openai_json,
    read_text,
    resolve_qa_config,
    safe_filename_component,
    to_portable_path,
    write_json,
    write_text,
)


DEFAULT_TRACKER_FOLDER_NAME = "response-letter-tracker"
RESPONSE_LETTER_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "round_label": {"type": "string"},
        "response_strategy_summary": {"type": "string"},
        "tracked_points": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "reviewer_point": {"type": "string"},
                    "response_text": {"type": "string"},
                    "manuscript_change": {"type": "string"},
                    "evidence_anchor": {"type": "string"},
                    "status": {"type": "string"},
                },
                "required": [
                    "reviewer_point",
                    "response_text",
                    "manuscript_change",
                    "evidence_anchor",
                    "status",
                ],
            },
        },
        "tone_guardrails": {"type": "array", "items": {"type": "string"}},
        "open_items": {"type": "array", "items": {"type": "string"}},
        "next_round_preparation": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "round_label",
        "response_strategy_summary",
        "tracked_points",
        "tone_guardrails",
        "open_items",
        "next_round_preparation",
    ],
}
RESPONSE_LETTER_RULES = [
    "You are preparing a versioned response-letter package from grounded revision artifacts.",
    "Do not invent reviewer comments, experiments, citations, or completed manuscript changes.",
    "If no external reviewer comments are provided, build a pre-submission response package from the internal rebuttal scaffold.",
    "Keep the tone respectful, specific, and evidence-bounded.",
    "Make the tracked points practical for future revision rounds and response-letter reuse.",
]


def resolve_response_letter_config(config: dict) -> dict:
    qa_runtime = resolve_qa_config(config)
    workflow_cfg = config.get("continuous_research", {}).get("openai", {})
    return {
        "api_key": workflow_cfg.get("api_key", "").strip() or qa_runtime["api_key"],
        "endpoint": workflow_cfg.get("base_url", "").strip() or qa_runtime["endpoint"],
        "model": workflow_cfg.get("response_letter_model", "").strip() or qa_runtime["critic_model"],
        "reasoning_effort": workflow_cfg.get("response_letter_reasoning_effort", "").strip()
        or qa_runtime["critic_effort"],
        "max_output_tokens": int(workflow_cfg.get("response_letter_max_output_tokens", 7000)),
    }


def infer_title(explicit_title: str | None) -> str:
    if explicit_title and explicit_title.strip():
        return explicit_title.strip()
    return "Response letter"


def tracker_dir(config: dict, title: str, explicit_tracker_dir: str | None) -> Path:
    if explicit_tracker_dir:
        target = Path(explicit_tracker_dir)
        target.mkdir(parents=True, exist_ok=True)
        return target

    output_root = Path(config["output_root"])
    target = output_root / DEFAULT_TRACKER_FOLDER_NAME / safe_filename_component(title, max_length=72)
    target.mkdir(parents=True, exist_ok=True)
    return target


def create_run_dir(base_tracker_dir: Path, round_label: str) -> Path:
    stamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    safe_round = safe_filename_component(round_label, max_length=48)
    run_dir = base_tracker_dir / f"{stamp}-{safe_round}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def load_optional_json(path_str: str | None):
    if not path_str:
        return {}
    path = Path(path_str)
    if not path.exists():
        return {}
    return load_json(path)


def load_optional_text(path_str: str | None):
    if not path_str:
        return ""
    path = Path(path_str)
    if not path.exists():
        return ""
    return read_text(path)


def run_response_letter(runtime_cfg: dict, payload: dict) -> tuple[dict, dict]:
    request_payload = build_request_payload(
        runtime_cfg["model"],
        runtime_cfg["reasoning_effort"],
        runtime_cfg["max_output_tokens"],
        "response_letter_report",
        RESPONSE_LETTER_SCHEMA,
        json.dumps(payload, ensure_ascii=False),
    )
    response_payload = post_openai_json(runtime_cfg["endpoint"], runtime_cfg["api_key"], request_payload)
    response_text = extract_response_text(response_payload)
    if not response_text:
        raise RuntimeError("Response letter step did not return any text output.")
    return json.loads(response_text), response_payload


def render_response_letter_markdown(title: str, payload: dict, meta: dict):
    lines = [
        f"# Response Letter - {title}",
        "",
        f"- Round: {payload['round_label']}",
        f"- Generated: {meta['generated_at']}",
        f"- Model: {meta['model']}",
        f"- Run directory: `{meta['run_dir']}`",
        "",
        "## Response Strategy Summary",
        "",
        payload["response_strategy_summary"],
        "",
        "## Tracked Points",
        "",
    ]
    for item in payload.get("tracked_points", []):
        lines.append(f"- Reviewer point: {item['reviewer_point']}")
        lines.append(f"  Response text: {item['response_text']}")
        lines.append(f"  Manuscript change: {item['manuscript_change']}")
        lines.append(f"  Evidence anchor: {item['evidence_anchor']}")
        lines.append(f"  Status: {item['status']}")
    if not payload.get("tracked_points"):
        lines.append("- None recorded.")
    for section_title, key in [
        ("Tone Guardrails", "tone_guardrails"),
        ("Open Items", "open_items"),
        ("Next Round Preparation", "next_round_preparation"),
    ]:
        lines.extend(["", f"## {section_title}", ""])
        values = payload.get(key, [])
        lines.extend([f"- {item}" for item in values] or ["- None recorded."])
    lines.append("")
    return "\n".join(lines)


def load_tracker_index(path: Path):
    if not path.exists():
        return {"rounds": []}
    return load_json(path)


def update_tracker_index(index_path: Path, round_label: str, run_dir: Path, outputs: dict):
    index = load_tracker_index(index_path)
    entry = {
        "round_label": round_label,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "run_dir": to_portable_path(run_dir),
        "response_letter_json": outputs["response_letter_json"],
        "response_letter_markdown": outputs["response_letter_markdown"],
    }
    index["rounds"].insert(0, entry)
    index["rounds"] = index["rounds"][:20]
    write_json(index_path, index)
    return index


def render_tracker_markdown(title: str, tracker_index: dict):
    lines = [
        f"# Response Letter Tracker - {title}",
        "",
        "## Rounds",
        "",
    ]
    for item in tracker_index.get("rounds", []):
        lines.append(f"- {item['generated_at']} | {item['round_label']}")
        lines.append(f"  JSON: `{item['response_letter_json']}`")
        lines.append(f"  Markdown: `{item['response_letter_markdown']}`")
    if not tracker_index.get("rounds"):
        lines.append("- None recorded.")
    lines.append("")
    return "\n".join(lines)


def write_vault_note(config: dict, title: str, tracker_markdown_path: Path, latest_markdown_path: Path):
    vault_root = Path(config["vault_root"])
    writing_folder = vault_root / config["obsidian"]["writing_folder"]
    writing_folder.mkdir(parents=True, exist_ok=True)
    note_path = writing_folder / f"Response Letter Tracker - {safe_filename_component(title, max_length=80)}.md"
    lines = [
        f"# Response Letter Tracker - {title}",
        "",
        f"- Tracker: `{to_portable_path(tracker_markdown_path)}`",
        f"- Latest round markdown: `{to_portable_path(latest_markdown_path)}`",
        "",
        "Use this note to keep response-letter versions visible across revision rounds.",
        "",
    ]
    write_text(note_path, "\n".join(lines))
    return note_path


def main():
    parser = argparse.ArgumentParser(description="Build a versioned response-letter package from grounded revision artifacts.")
    parser.add_argument("--config", required=True)
    parser.add_argument("--title")
    parser.add_argument("--round-label", default="round-1")
    parser.add_argument("--review-comments-file")
    parser.add_argument("--current-changes-file")
    parser.add_argument("--rebuttal-scaffold-json")
    parser.add_argument("--journal-targeting-json")
    parser.add_argument("--draft-builder-json")
    parser.add_argument("--draft-file")
    parser.add_argument("--tracker-dir")
    parser.add_argument("--write-vault-note", action="store_true")
    args = parser.parse_args()

    config = load_json(Path(args.config))
    runtime_cfg = resolve_response_letter_config(config)
    title = infer_title(args.title)
    base_tracker_dir = tracker_dir(config, title, args.tracker_dir)
    run_dir = create_run_dir(base_tracker_dir, args.round_label)

    payload = {
        "rules": RESPONSE_LETTER_RULES,
        "title": title,
        "round_label": args.round_label,
        "review_comments_text": load_optional_text(args.review_comments_file),
        "current_changes_text": load_optional_text(args.current_changes_file),
        "rebuttal_scaffold": load_optional_json(args.rebuttal_scaffold_json),
        "journal_targeting": load_optional_json(args.journal_targeting_json),
        "draft_builder": load_optional_json(args.draft_builder_json),
        "draft_text": load_optional_text(args.draft_file),
    }
    report, response_payload = run_response_letter(runtime_cfg, payload)

    meta = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "model": runtime_cfg["model"],
        "run_dir": to_portable_path(run_dir),
    }
    response_json_path = run_dir / "response_letter.json"
    response_markdown_path = run_dir / "response_letter.md"
    write_json(response_json_path, report)
    write_json(run_dir / "response_letter_response.json", response_payload)
    write_text(response_markdown_path, render_response_letter_markdown(title, report, meta))

    outputs = {
        "tracker_dir": to_portable_path(base_tracker_dir),
        "run_dir": to_portable_path(run_dir),
        "response_letter_json": to_portable_path(response_json_path),
        "response_letter_markdown": to_portable_path(response_markdown_path),
    }
    tracker_index_path = base_tracker_dir / "response_rounds_index.json"
    tracker_index = update_tracker_index(tracker_index_path, args.round_label, run_dir, outputs)
    tracker_markdown_path = base_tracker_dir / "response_rounds.md"
    write_text(tracker_markdown_path, render_tracker_markdown(title, tracker_index))
    outputs["tracker_index_json"] = to_portable_path(tracker_index_path)
    outputs["tracker_markdown"] = to_portable_path(tracker_markdown_path)

    if args.write_vault_note:
        note_path = write_vault_note(config, title, tracker_markdown_path, response_markdown_path)
        outputs["vault_note"] = to_portable_path(note_path)

    print(json.dumps(outputs, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
