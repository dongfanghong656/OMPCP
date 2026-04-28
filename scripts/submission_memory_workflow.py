#!/usr/bin/env python
import argparse
import json
from datetime import datetime
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
    update_index,
    write_json,
    write_text,
)


MEMORY_FOLDER_NAME = "Submission Memory"
REGISTRY_NAME = "_submission_memory_registry.json"
SUBMISSION_MEMORY_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "memory_summary": {"type": "string"},
        "venue_name": {"type": "string"},
        "round_label": {"type": "string"},
        "durable_lessons": {"type": "array", "items": {"type": "string"}},
        "venue_specific_rules": {"type": "array", "items": {"type": "string"}},
        "recurring_debts": {"type": "array", "items": {"type": "string"}},
        "next_round_memory": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "memory_summary",
        "venue_name",
        "round_label",
        "durable_lessons",
        "venue_specific_rules",
        "recurring_debts",
        "next_round_memory",
    ],
}
SUBMISSION_MEMORY_RULES = [
    "You are distilling durable submission memory from the latest manuscript and revision artifacts.",
    "Do not invent venue rules, reviewer comments, or completed fixes.",
    "Focus on lessons that should remain visible across future rounds, venues, or submission cycles.",
    "Prefer memory items that are actually reusable, not one-off observations.",
    "Keep the output short enough to stay durable and queryable later.",
]


def resolve_submission_memory_config(config: dict) -> dict:
    qa_runtime = resolve_qa_config(config)
    workflow_cfg = config.get("continuous_research", {}).get("openai", {})
    return {
        "api_key": workflow_cfg.get("api_key", "").strip() or qa_runtime["api_key"],
        "endpoint": workflow_cfg.get("base_url", "").strip() or qa_runtime["endpoint"],
        "model": workflow_cfg.get("submission_memory_model", "").strip() or qa_runtime["reason_model"],
        "reasoning_effort": workflow_cfg.get("submission_memory_reasoning_effort", "").strip()
        or qa_runtime["reason_effort"],
        "max_output_tokens": int(workflow_cfg.get("submission_memory_max_output_tokens", 7000)),
    }


def infer_title(explicit_title: str | None, venue_name: str | None, round_label: str) -> str:
    if explicit_title and explicit_title.strip():
        return explicit_title.strip()
    if venue_name and venue_name.strip():
        return f"{venue_name.strip()} {round_label}"
    return f"Submission memory {round_label}"


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


def run_submission_memory(runtime_cfg: dict, payload: dict) -> tuple[dict, dict]:
    request_payload = build_request_payload(
        runtime_cfg["model"],
        runtime_cfg["reasoning_effort"],
        runtime_cfg["max_output_tokens"],
        "submission_memory_report",
        SUBMISSION_MEMORY_SCHEMA,
        json.dumps(payload, ensure_ascii=False),
    )
    response_payload = post_openai_json(runtime_cfg["endpoint"], runtime_cfg["api_key"], request_payload)
    response_text = extract_response_text(response_payload)
    if not response_text:
        raise RuntimeError("Submission memory step did not return any text output.")
    return json.loads(response_text), response_payload


def memory_folder(config: dict):
    vault_root = Path(config["vault_root"])
    folder = vault_root / config["obsidian"]["writing_folder"] / MEMORY_FOLDER_NAME
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def registry_path(config: dict):
    return memory_folder(config) / REGISTRY_NAME


def load_registry(path: Path):
    if not path.exists():
        return {"entries": []}
    return load_json(path)


def upsert_registry_entry(path: Path, entry: dict):
    registry = load_registry(path)
    registry["entries"].insert(0, entry)
    registry["entries"] = registry["entries"][:100]
    write_json(path, registry)
    return registry


def render_submission_memory_markdown(title: str, report: dict, meta: dict):
    lines = [
        f"# Submission Memory - {title}",
        "",
        f"- Generated: {meta['generated_at']}",
        f"- Model: {meta['model']}",
        f"- Venue: {report['venue_name'] or 'Unspecified venue'}",
        f"- Round: {report['round_label']}",
        "",
        "## Memory Summary",
        "",
        report["memory_summary"],
        "",
    ]
    for section_title, key in [
        ("Durable Lessons", "durable_lessons"),
        ("Venue Specific Rules", "venue_specific_rules"),
        ("Recurring Debts", "recurring_debts"),
        ("Next Round Memory", "next_round_memory"),
    ]:
        lines.extend([f"## {section_title}", ""])
        values = report.get(key, [])
        lines.extend([f"- {item}" for item in values] or ["- None recorded."])
        lines.append("")
    return "\n".join(lines)


def note_path_for_report(config: dict, title: str):
    return memory_folder(config) / f"Submission Memory - {safe_filename_component(title, max_length=80)}.md"


def main():
    parser = argparse.ArgumentParser(description="Write durable submission memory by venue and revision round.")
    parser.add_argument("--config", required=True)
    parser.add_argument("--title")
    parser.add_argument("--venue-name")
    parser.add_argument("--round-label", default="round-1")
    parser.add_argument("--draft-health-json")
    parser.add_argument("--submission-qc-json")
    parser.add_argument("--citation-audit-json")
    parser.add_argument("--response-letter-json")
    parser.add_argument("--journal-targeting-json")
    parser.add_argument("--draft-file")
    args = parser.parse_args()

    config = load_json(Path(args.config))
    runtime_cfg = resolve_submission_memory_config(config)
    title = infer_title(args.title, args.venue_name, args.round_label)

    payload = {
        "rules": SUBMISSION_MEMORY_RULES,
        "title": title,
        "venue_name": (args.venue_name or "").strip(),
        "round_label": args.round_label,
        "draft_health": load_optional_json(args.draft_health_json),
        "submission_qc": load_optional_json(args.submission_qc_json),
        "citation_audit": load_optional_json(args.citation_audit_json),
        "response_letter": load_optional_json(args.response_letter_json),
        "journal_targeting": load_optional_json(args.journal_targeting_json),
        "draft_text": load_optional_text(args.draft_file),
    }
    report, response_payload = run_submission_memory(runtime_cfg, payload)

    target_note_path = note_path_for_report(config, title)
    report_json_path = target_note_path.with_suffix(".json")
    response_payload_path = target_note_path.with_name(target_note_path.stem + " Response.json")
    meta = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "model": runtime_cfg["model"],
    }

    write_json(report_json_path, report)
    write_json(response_payload_path, response_payload)
    write_text(target_note_path, render_submission_memory_markdown(title, report, meta))
    update_index(memory_folder(config) / "_Index.md", f"- [[{target_note_path.stem}]]", "# Submission Memory Index\n")

    entry = {
        "timestamp": meta["generated_at"],
        "title": title,
        "venue_name": report["venue_name"],
        "round_label": report["round_label"],
        "note_path": to_portable_path(target_note_path),
        "json_path": to_portable_path(report_json_path),
        "summary": report["memory_summary"],
    }
    registry = upsert_registry_entry(registry_path(config), entry)

    outputs = {
        "submission_memory_note": to_portable_path(target_note_path),
        "submission_memory_json": to_portable_path(report_json_path),
        "submission_memory_response_json": to_portable_path(response_payload_path),
        "submission_memory_registry": to_portable_path(registry_path(config)),
        "entry_count": len(registry.get("entries", [])),
    }
    print(json.dumps(outputs, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
