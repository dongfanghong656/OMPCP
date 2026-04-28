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


DEFAULT_REPORT_FOLDER_NAME = "journal-targeting"
JOURNAL_TARGETING_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "journal_fit_summary": {"type": "string"},
        "journal_basis_note": {"type": "string"},
        "adaptation_rules": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "section_or_element": {"type": "string"},
                    "keep": {"type": "string"},
                    "adapt_for_journal": {"type": "string"},
                    "risk_if_unchanged": {"type": "string"},
                },
                "required": ["section_or_element", "keep", "adapt_for_journal", "risk_if_unchanged"],
            },
        },
        "citation_actions": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "claim_area": {"type": "string"},
                    "citation_need": {"type": "string"},
                    "evidence_type_needed": {"type": "string"},
                    "priority": {"type": "string"},
                },
                "required": ["claim_area", "citation_need", "evidence_type_needed", "priority"],
            },
        },
        "presentation_priorities": {"type": "array", "items": {"type": "string"}},
        "submission_checklist": {"type": "array", "items": {"type": "string"}},
        "next_journal_targets": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "journal_fit_summary",
        "journal_basis_note",
        "adaptation_rules",
        "citation_actions",
        "presentation_priorities",
        "submission_checklist",
        "next_journal_targets",
    ],
}
JOURNAL_TARGETING_RULES = [
    "You are adapting grounded manuscript artifacts toward a target journal or submission venue.",
    "Do not invent journal guidelines. If journal-specific instructions are not provided, say the advice is generic.",
    "Use the draft builder, self review, and rebuttal scaffold to generate submission-safe adaptation rules.",
    "Include citation-aware polishing actions only when they are grounded in the provided manuscript context.",
    "Prefer concrete, section-level adaptation rules over vague journal-fit commentary.",
]


def resolve_journal_targeting_config(config: dict) -> dict:
    qa_runtime = resolve_qa_config(config)
    workflow_cfg = config.get("continuous_research", {}).get("openai", {})
    return {
        "api_key": workflow_cfg.get("api_key", "").strip() or qa_runtime["api_key"],
        "endpoint": workflow_cfg.get("base_url", "").strip() or qa_runtime["endpoint"],
        "model": workflow_cfg.get("journal_targeting_model", "").strip() or qa_runtime["reason_model"],
        "reasoning_effort": workflow_cfg.get("journal_targeting_reasoning_effort", "").strip()
        or qa_runtime["reason_effort"],
        "max_output_tokens": int(workflow_cfg.get("journal_targeting_max_output_tokens", 7000)),
    }


def infer_title(explicit_title: str | None, journal_name: str | None) -> str:
    if explicit_title and explicit_title.strip():
        return explicit_title.strip()
    if journal_name and journal_name.strip():
        return f"Journal targeting - {journal_name.strip()}"
    return "Journal targeting"


def create_run_dir(config: dict, title: str, explicit_dir: str | None) -> Path:
    if explicit_dir:
        run_dir = Path(explicit_dir)
        run_dir.mkdir(parents=True, exist_ok=True)
        return run_dir

    output_root = Path(config["output_root"])
    safe = safe_filename_component(title, max_length=72)
    run_dir = output_root / DEFAULT_REPORT_FOLDER_NAME / f"{date.today().isoformat()}-{safe}"
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


def run_journal_targeting(runtime_cfg: dict, payload: dict) -> tuple[dict, dict]:
    request_payload = build_request_payload(
        runtime_cfg["model"],
        runtime_cfg["reasoning_effort"],
        runtime_cfg["max_output_tokens"],
        "journal_targeting_report",
        JOURNAL_TARGETING_SCHEMA,
        json.dumps(payload, ensure_ascii=False),
    )
    response_payload = post_openai_json(runtime_cfg["endpoint"], runtime_cfg["api_key"], request_payload)
    response_text = extract_response_text(response_payload)
    if not response_text:
        raise RuntimeError("Journal targeting step did not return any text output.")
    return json.loads(response_text), response_payload


def render_journal_targeting_markdown(title: str, report: dict, meta: dict):
    lines = [
        f"# Journal Targeting - {title}",
        "",
        f"- Generated: {meta['generated_at']}",
        f"- Model: {meta['model']}",
        f"- Run directory: `{meta['run_dir']}`",
        "",
        "## Journal Fit Summary",
        "",
        report["journal_fit_summary"],
        "",
        "## Journal Basis Note",
        "",
        report["journal_basis_note"],
        "",
        "## Adaptation Rules",
        "",
    ]
    for item in report.get("adaptation_rules", []):
        lines.append(f"- Section or element: {item['section_or_element']}")
        lines.append(f"  Keep: {item['keep']}")
        lines.append(f"  Adapt for journal: {item['adapt_for_journal']}")
        lines.append(f"  Risk if unchanged: {item['risk_if_unchanged']}")
    if not report.get("adaptation_rules"):
        lines.append("- None recorded.")
    lines.extend(["", "## Citation Actions", ""])
    for item in report.get("citation_actions", []):
        lines.append(f"- Claim area: {item['claim_area']}")
        lines.append(f"  Citation need: {item['citation_need']}")
        lines.append(f"  Evidence type needed: {item['evidence_type_needed']}")
        lines.append(f"  Priority: {item['priority']}")
    if not report.get("citation_actions"):
        lines.append("- None recorded.")
    for section_title, key in [
        ("Presentation Priorities", "presentation_priorities"),
        ("Submission Checklist", "submission_checklist"),
        ("Next Journal Targets", "next_journal_targets"),
    ]:
        lines.extend(["", f"## {section_title}", ""])
        values = report.get(key, [])
        lines.extend([f"- {item}" for item in values] or ["- None recorded."])
    lines.append("")
    return "\n".join(lines)


def write_vault_note(config: dict, title: str, report_json_path: Path, markdown_path: Path):
    vault_root = Path(config["vault_root"])
    writing_folder = vault_root / config["obsidian"]["writing_folder"]
    writing_folder.mkdir(parents=True, exist_ok=True)
    note_path = writing_folder / f"Journal Targeting - {safe_filename_component(title, max_length=80)}.md"
    lines = [
        f"# Journal Targeting - {title}",
        "",
        f"- JSON: `{to_portable_path(report_json_path)}`",
        f"- Markdown: `{to_portable_path(markdown_path)}`",
        "",
        "Use this note to keep journal-fit adaptation rules and submission checklist items visible during paper finishing.",
        "",
    ]
    write_text(note_path, "\n".join(lines))
    return note_path


def main():
    parser = argparse.ArgumentParser(description="Adapt grounded manuscript artifacts toward a target journal or submission venue.")
    parser.add_argument("--config", required=True)
    parser.add_argument("--title")
    parser.add_argument("--journal-name")
    parser.add_argument("--journal-notes-file")
    parser.add_argument("--draft-builder-json")
    parser.add_argument("--self-review-json")
    parser.add_argument("--rebuttal-scaffold-json")
    parser.add_argument("--draft-file")
    parser.add_argument("--output-dir")
    parser.add_argument("--write-vault-note", action="store_true")
    args = parser.parse_args()

    config = load_json(Path(args.config))
    runtime_cfg = resolve_journal_targeting_config(config)
    title = infer_title(args.title, args.journal_name)
    run_dir = create_run_dir(config, title, args.output_dir)

    payload = {
        "rules": JOURNAL_TARGETING_RULES,
        "title": title,
        "journal_name": (args.journal_name or "").strip(),
        "journal_notes_text": load_optional_text(args.journal_notes_file),
        "draft_builder": load_optional_json(args.draft_builder_json),
        "self_review": load_optional_json(args.self_review_json),
        "rebuttal_scaffold": load_optional_json(args.rebuttal_scaffold_json),
        "draft_text": load_optional_text(args.draft_file),
    }
    report, response_payload = run_journal_targeting(runtime_cfg, payload)

    meta = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "model": runtime_cfg["model"],
        "run_dir": to_portable_path(run_dir),
    }
    report_json_path = run_dir / "journal_targeting.json"
    markdown_path = run_dir / "journal_targeting.md"
    write_json(report_json_path, report)
    write_json(run_dir / "journal_targeting_response.json", response_payload)
    write_text(markdown_path, render_journal_targeting_markdown(title, report, meta))

    outputs = {
        "run_dir": to_portable_path(run_dir),
        "journal_targeting_json": to_portable_path(report_json_path),
        "journal_targeting_markdown": to_portable_path(markdown_path),
    }
    if args.write_vault_note:
        note_path = write_vault_note(config, title, report_json_path, markdown_path)
        outputs["vault_note"] = to_portable_path(note_path)

    print(json.dumps(outputs, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
