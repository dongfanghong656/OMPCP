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


DEFAULT_REPORT_FOLDER_NAME = "self-review"
SELF_REVIEW_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "review_summary": {"type": "string"},
        "overall_readiness": {"type": "string"},
        "claim_alignment_issues": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "claim_or_section": {"type": "string"},
                    "issue": {"type": "string"},
                    "severity": {"type": "string"},
                    "evidence_gap": {"type": "string"},
                    "revision_direction": {"type": "string"},
                },
                "required": ["claim_or_section", "issue", "severity", "evidence_gap", "revision_direction"],
            },
        },
        "overclaim_risks": {"type": "array", "items": {"type": "string"}},
        "missing_controls_or_evidence": {"type": "array", "items": {"type": "string"}},
        "wording_risks": {"type": "array", "items": {"type": "string"}},
        "salvageable_strengths": {"type": "array", "items": {"type": "string"}},
        "revision_actions": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "review_summary",
        "overall_readiness",
        "claim_alignment_issues",
        "overclaim_risks",
        "missing_controls_or_evidence",
        "wording_risks",
        "salvageable_strengths",
        "revision_actions",
    ],
}
SELF_REVIEW_RULES = [
    "You are performing a skeptical academic self-review on a draft using only the provided evidence context.",
    "Do not invent results, citations, controls, or numerical evidence.",
    "Focus on claim-evidence alignment, overclaim risk, missing controls, and wording that is too strong for the evidence.",
    "Preserve any solid strengths instead of criticizing everything.",
    "Prefer revision directions that are specific and manuscript-usable.",
]


def resolve_self_review_config(config: dict) -> dict:
    qa_runtime = resolve_qa_config(config)
    workflow_cfg = config.get("continuous_research", {}).get("openai", {})
    return {
        "api_key": workflow_cfg.get("api_key", "").strip() or qa_runtime["api_key"],
        "endpoint": workflow_cfg.get("base_url", "").strip() or qa_runtime["endpoint"],
        "model": workflow_cfg.get("self_review_model", "").strip() or qa_runtime["critic_model"],
        "reasoning_effort": workflow_cfg.get("self_review_reasoning_effort", "").strip()
        or qa_runtime["critic_effort"],
        "max_output_tokens": int(workflow_cfg.get("self_review_max_output_tokens", 6000)),
    }


def infer_title(explicit_title: str | None, draft_file: Path) -> str:
    if explicit_title and explicit_title.strip():
        return explicit_title.strip()
    return draft_file.stem


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


def run_self_review(runtime_cfg: dict, payload: dict) -> tuple[dict, dict]:
    request_payload = build_request_payload(
        runtime_cfg["model"],
        runtime_cfg["reasoning_effort"],
        runtime_cfg["max_output_tokens"],
        "self_review_report",
        SELF_REVIEW_SCHEMA,
        json.dumps(payload, ensure_ascii=False),
    )
    response_payload = post_openai_json(runtime_cfg["endpoint"], runtime_cfg["api_key"], request_payload)
    response_text = extract_response_text(response_payload)
    if not response_text:
        raise RuntimeError("Self-review step did not return any text output.")
    return json.loads(response_text), response_payload


def render_self_review_markdown(title: str, review: dict, meta: dict):
    lines = [
        f"# Self Review - {title}",
        "",
        f"- Generated: {meta['generated_at']}",
        f"- Model: {meta['model']}",
        f"- Run directory: `{meta['run_dir']}`",
        "",
        "## Review Summary",
        "",
        review["review_summary"],
        "",
        "## Overall Readiness",
        "",
        review["overall_readiness"],
        "",
        "## Claim Alignment Issues",
        "",
    ]
    for item in review.get("claim_alignment_issues", []):
        lines.append(f"- Claim or section: {item['claim_or_section']}")
        lines.append(f"  Issue: {item['issue']}")
        lines.append(f"  Severity: {item['severity']}")
        lines.append(f"  Evidence gap: {item['evidence_gap']}")
        lines.append(f"  Revision direction: {item['revision_direction']}")
    if not review.get("claim_alignment_issues"):
        lines.append("- None recorded.")
    for title_name, key in [
        ("Overclaim Risks", "overclaim_risks"),
        ("Missing Controls Or Evidence", "missing_controls_or_evidence"),
        ("Wording Risks", "wording_risks"),
        ("Salvageable Strengths", "salvageable_strengths"),
        ("Revision Actions", "revision_actions"),
    ]:
        lines.extend(["", f"## {title_name}", ""])
        values = review.get(key, [])
        lines.extend([f"- {item}" for item in values] or ["- None recorded."])
    lines.append("")
    return "\n".join(lines)


def write_vault_note(config: dict, title: str, review_json_path: Path, markdown_path: Path):
    vault_root = Path(config["vault_root"])
    writing_folder = vault_root / config["obsidian"]["writing_folder"]
    writing_folder.mkdir(parents=True, exist_ok=True)
    note_path = writing_folder / f"Self Review - {safe_filename_component(title, max_length=80)}.md"
    lines = [
        f"# Self Review - {title}",
        "",
        f"- JSON: `{to_portable_path(review_json_path)}`",
        f"- Markdown: `{to_portable_path(markdown_path)}`",
        "",
        "Use this note as the evidence-constrained self-review layer before stronger manuscript claims are locked in.",
        "",
    ]
    write_text(note_path, "\n".join(lines))
    return note_path


def main():
    parser = argparse.ArgumentParser(description="Run an evidence-constrained self review on a draft section or note.")
    parser.add_argument("--config", required=True)
    parser.add_argument("--draft-file", required=True)
    parser.add_argument("--title")
    parser.add_argument("--analysis-json")
    parser.add_argument("--results-report-json")
    parser.add_argument("--writing-memory-json")
    parser.add_argument("--output-dir")
    parser.add_argument("--write-vault-note", action="store_true")
    args = parser.parse_args()

    config = load_json(Path(args.config))
    runtime_cfg = resolve_self_review_config(config)
    draft_file = Path(args.draft_file)
    title = infer_title(args.title, draft_file)
    run_dir = create_run_dir(config, title, args.output_dir)

    payload = {
        "rules": SELF_REVIEW_RULES,
        "title": title,
        "draft_text": read_text(draft_file),
        "analysis": load_optional_json(args.analysis_json),
        "results_report": load_optional_json(args.results_report_json),
        "writing_memory": load_optional_json(args.writing_memory_json),
    }
    review, response_payload = run_self_review(runtime_cfg, payload)

    meta = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "model": runtime_cfg["model"],
        "run_dir": to_portable_path(run_dir),
    }
    review_json_path = run_dir / "self_review.json"
    markdown_path = run_dir / "self_review.md"
    write_json(review_json_path, review)
    write_json(run_dir / "self_review_response.json", response_payload)
    write_text(markdown_path, render_self_review_markdown(title, review, meta))

    outputs = {
        "run_dir": to_portable_path(run_dir),
        "self_review_json": to_portable_path(review_json_path),
        "self_review_markdown": to_portable_path(markdown_path),
    }
    if args.write_vault_note:
        note_path = write_vault_note(config, title, review_json_path, markdown_path)
        outputs["vault_note"] = to_portable_path(note_path)

    print(json.dumps(outputs, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
