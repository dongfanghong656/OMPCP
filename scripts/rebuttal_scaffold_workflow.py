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


DEFAULT_REPORT_FOLDER_NAME = "rebuttal-scaffold"
REBUTTAL_SCAFFOLD_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "review_risk_summary": {"type": "string"},
        "likely_reviewer_concerns": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "concern": {"type": "string"},
                    "why_it_is_likely": {"type": "string"},
                    "evidence_backed_response": {"type": "string"},
                    "concession_if_needed": {"type": "string"},
                    "follow_up_action": {"type": "string"},
                },
                "required": [
                    "concern",
                    "why_it_is_likely",
                    "evidence_backed_response",
                    "concession_if_needed",
                    "follow_up_action",
                ],
            },
        },
        "manuscript_changes_to_preempt": {"type": "array", "items": {"type": "string"}},
        "response_letter_phrases": {"type": "array", "items": {"type": "string"}},
        "high_priority_evidence_requests": {"type": "array", "items": {"type": "string"}},
        "next_rebuttal_targets": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "review_risk_summary",
        "likely_reviewer_concerns",
        "manuscript_changes_to_preempt",
        "response_letter_phrases",
        "high_priority_evidence_requests",
        "next_rebuttal_targets",
    ],
}
REBUTTAL_SCAFFOLD_RULES = [
    "You are preparing a rebuttal and reviewer-response scaffold using only the provided evidence context.",
    "Do not invent studies, citations, experimental results, or reviewer comments.",
    "Turn self-review risks into reviewer-likely concerns and evidence-bounded response language.",
    "Prefer honest concessions plus clear next-step actions over defensive overclaiming.",
    "Keep the output practical for both manuscript revision and future response-letter drafting.",
]


def resolve_rebuttal_scaffold_config(config: dict) -> dict:
    qa_runtime = resolve_qa_config(config)
    workflow_cfg = config.get("continuous_research", {}).get("openai", {})
    return {
        "api_key": workflow_cfg.get("api_key", "").strip() or qa_runtime["api_key"],
        "endpoint": workflow_cfg.get("base_url", "").strip() or qa_runtime["endpoint"],
        "model": workflow_cfg.get("rebuttal_scaffold_model", "").strip() or qa_runtime["critic_model"],
        "reasoning_effort": workflow_cfg.get("rebuttal_scaffold_reasoning_effort", "").strip()
        or qa_runtime["critic_effort"],
        "max_output_tokens": int(workflow_cfg.get("rebuttal_scaffold_max_output_tokens", 7000)),
    }


def infer_title(explicit_title: str | None, self_review_json_path: Path | None, draft_file_path: Path | None) -> str:
    if explicit_title and explicit_title.strip():
        return explicit_title.strip()
    if draft_file_path:
        return draft_file_path.stem
    if self_review_json_path and self_review_json_path.exists():
        try:
            payload = load_json(self_review_json_path)
            summary = payload.get("review_summary", "").strip()
            if summary:
                return summary[:72]
        except (OSError, json.JSONDecodeError):
            pass
    return "Rebuttal scaffold"


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


def run_rebuttal_scaffold(runtime_cfg: dict, payload: dict) -> tuple[dict, dict]:
    request_payload = build_request_payload(
        runtime_cfg["model"],
        runtime_cfg["reasoning_effort"],
        runtime_cfg["max_output_tokens"],
        "rebuttal_scaffold_report",
        REBUTTAL_SCAFFOLD_SCHEMA,
        json.dumps(payload, ensure_ascii=False),
    )
    response_payload = post_openai_json(runtime_cfg["endpoint"], runtime_cfg["api_key"], request_payload)
    response_text = extract_response_text(response_payload)
    if not response_text:
        raise RuntimeError("Rebuttal scaffold step did not return any text output.")
    return json.loads(response_text), response_payload


def render_rebuttal_scaffold_markdown(title: str, scaffold: dict, meta: dict):
    lines = [
        f"# Rebuttal Scaffold - {title}",
        "",
        f"- Generated: {meta['generated_at']}",
        f"- Model: {meta['model']}",
        f"- Run directory: `{meta['run_dir']}`",
        "",
        "## Review Risk Summary",
        "",
        scaffold["review_risk_summary"],
        "",
        "## Likely Reviewer Concerns",
        "",
    ]
    for item in scaffold.get("likely_reviewer_concerns", []):
        lines.append(f"- Concern: {item['concern']}")
        lines.append(f"  Why it is likely: {item['why_it_is_likely']}")
        lines.append(f"  Evidence-backed response: {item['evidence_backed_response']}")
        lines.append(f"  Concession if needed: {item['concession_if_needed']}")
        lines.append(f"  Follow-up action: {item['follow_up_action']}")
    if not scaffold.get("likely_reviewer_concerns"):
        lines.append("- None recorded.")
    for section_title, key in [
        ("Manuscript Changes To Preempt", "manuscript_changes_to_preempt"),
        ("Response Letter Phrases", "response_letter_phrases"),
        ("High Priority Evidence Requests", "high_priority_evidence_requests"),
        ("Next Rebuttal Targets", "next_rebuttal_targets"),
    ]:
        lines.extend(["", f"## {section_title}", ""])
        values = scaffold.get(key, [])
        lines.extend([f"- {item}" for item in values] or ["- None recorded."])
    lines.append("")
    return "\n".join(lines)


def write_vault_note(config: dict, title: str, scaffold_json_path: Path, markdown_path: Path):
    vault_root = Path(config["vault_root"])
    writing_folder = vault_root / config["obsidian"]["writing_folder"]
    writing_folder.mkdir(parents=True, exist_ok=True)
    note_path = writing_folder / f"Rebuttal Scaffold - {safe_filename_component(title, max_length=80)}.md"
    lines = [
        f"# Rebuttal Scaffold - {title}",
        "",
        f"- JSON: `{to_portable_path(scaffold_json_path)}`",
        f"- Markdown: `{to_portable_path(markdown_path)}`",
        "",
        "Use this note as the bridge from self-review findings into revision planning and future response-letter drafting.",
        "",
    ]
    write_text(note_path, "\n".join(lines))
    return note_path


def main():
    parser = argparse.ArgumentParser(description="Turn self-review outputs into a rebuttal and reviewer-response scaffold.")
    parser.add_argument("--config", required=True)
    parser.add_argument("--title")
    parser.add_argument("--self-review-json")
    parser.add_argument("--writing-memory-json")
    parser.add_argument("--results-report-json")
    parser.add_argument("--draft-file")
    parser.add_argument("--output-dir")
    parser.add_argument("--write-vault-note", action="store_true")
    args = parser.parse_args()

    config = load_json(Path(args.config))
    runtime_cfg = resolve_rebuttal_scaffold_config(config)
    title = infer_title(
        args.title,
        Path(args.self_review_json) if args.self_review_json else None,
        Path(args.draft_file) if args.draft_file else None,
    )
    run_dir = create_run_dir(config, title, args.output_dir)

    payload = {
        "rules": REBUTTAL_SCAFFOLD_RULES,
        "title": title,
        "self_review": load_optional_json(args.self_review_json),
        "writing_memory": load_optional_json(args.writing_memory_json),
        "results_report": load_optional_json(args.results_report_json),
        "draft_text": load_optional_text(args.draft_file),
    }
    scaffold, response_payload = run_rebuttal_scaffold(runtime_cfg, payload)

    meta = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "model": runtime_cfg["model"],
        "run_dir": to_portable_path(run_dir),
    }
    scaffold_json_path = run_dir / "rebuttal_scaffold.json"
    markdown_path = run_dir / "rebuttal_scaffold.md"
    write_json(scaffold_json_path, scaffold)
    write_json(run_dir / "rebuttal_scaffold_response.json", response_payload)
    write_text(markdown_path, render_rebuttal_scaffold_markdown(title, scaffold, meta))

    outputs = {
        "run_dir": to_portable_path(run_dir),
        "rebuttal_scaffold_json": to_portable_path(scaffold_json_path),
        "rebuttal_scaffold_markdown": to_portable_path(markdown_path),
    }
    if args.write_vault_note:
        note_path = write_vault_note(config, title, scaffold_json_path, markdown_path)
        outputs["vault_note"] = to_portable_path(note_path)

    print(json.dumps(outputs, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
