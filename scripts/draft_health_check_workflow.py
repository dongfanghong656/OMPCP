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


DEFAULT_REPORT_FOLDER_NAME = "draft-health"
DRAFT_HEALTH_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "health_summary": {"type": "string"},
        "overall_status": {"type": "string"},
        "citation_debt_items": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "item": {"type": "string"},
                    "why_it_matters": {"type": "string"},
                    "source_stage": {"type": "string"},
                    "repair_hint": {"type": "string"},
                    "severity": {"type": "string"},
                },
                "required": ["item", "why_it_matters", "source_stage", "repair_hint", "severity"],
            },
        },
        "stability_watchpoints": {"type": "array", "items": {"type": "string"}},
        "recent_strengths": {"type": "array", "items": {"type": "string"}},
        "next_health_checks": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "health_summary",
        "overall_status",
        "citation_debt_items",
        "stability_watchpoints",
        "recent_strengths",
        "next_health_checks",
    ],
}
DRAFT_HEALTH_RULES = [
    "You are performing a recurring draft health check on a manuscript package.",
    "Do not invent reviewer feedback, citations, or completed fixes.",
    "Use the latest quality-control artifacts to identify current debt, health status, and watchpoints.",
    "Treat citation debt and claim-evidence mismatch as first-class health signals.",
    "Prefer recurring checks that are practical for scheduled re-runs.",
]


def resolve_draft_health_config(config: dict) -> dict:
    qa_runtime = resolve_qa_config(config)
    workflow_cfg = config.get("continuous_research", {}).get("openai", {})
    return {
        "api_key": workflow_cfg.get("api_key", "").strip() or qa_runtime["api_key"],
        "endpoint": workflow_cfg.get("base_url", "").strip() or qa_runtime["endpoint"],
        "model": workflow_cfg.get("draft_health_model", "").strip() or qa_runtime["critic_model"],
        "reasoning_effort": workflow_cfg.get("draft_health_reasoning_effort", "").strip()
        or qa_runtime["critic_effort"],
        "max_output_tokens": int(workflow_cfg.get("draft_health_max_output_tokens", 7000)),
    }


def infer_title(explicit_title: str | None, draft_file: Path | None) -> str:
    if explicit_title and explicit_title.strip():
        return explicit_title.strip()
    if draft_file:
        return draft_file.stem
    return "Draft health"


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


def run_draft_health_check(runtime_cfg: dict, payload: dict) -> tuple[dict, dict]:
    request_payload = build_request_payload(
        runtime_cfg["model"],
        runtime_cfg["reasoning_effort"],
        runtime_cfg["max_output_tokens"],
        "draft_health_report",
        DRAFT_HEALTH_SCHEMA,
        json.dumps(payload, ensure_ascii=False),
    )
    response_payload = post_openai_json(runtime_cfg["endpoint"], runtime_cfg["api_key"], request_payload)
    response_text = extract_response_text(response_payload)
    if not response_text:
        raise RuntimeError("Draft health step did not return any text output.")
    return json.loads(response_text), response_payload


def render_draft_health_markdown(title: str, report: dict, meta: dict):
    lines = [
        f"# Draft Health - {title}",
        "",
        f"- Generated: {meta['generated_at']}",
        f"- Model: {meta['model']}",
        f"- Run directory: `{meta['run_dir']}`",
        "",
        "## Health Summary",
        "",
        report["health_summary"],
        "",
        "## Overall Status",
        "",
        report["overall_status"],
        "",
        "## Citation Debt Items",
        "",
    ]
    for item in report.get("citation_debt_items", []):
        lines.append(f"- Item: {item['item']}")
        lines.append(f"  Why it matters: {item['why_it_matters']}")
        lines.append(f"  Source stage: {item['source_stage']}")
        lines.append(f"  Repair hint: {item['repair_hint']}")
        lines.append(f"  Severity: {item['severity']}")
    if not report.get("citation_debt_items"):
        lines.append("- None recorded.")
    for section_title, key in [
        ("Stability Watchpoints", "stability_watchpoints"),
        ("Recent Strengths", "recent_strengths"),
        ("Next Health Checks", "next_health_checks"),
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
    note_path = writing_folder / f"Draft Health - {safe_filename_component(title, max_length=80)}.md"
    lines = [
        f"# Draft Health - {title}",
        "",
        f"- JSON: `{to_portable_path(report_json_path)}`",
        f"- Markdown: `{to_portable_path(markdown_path)}`",
        "",
        "Use this note to track current draft debt and recurring health checks over time.",
        "",
    ]
    write_text(note_path, "\n".join(lines))
    return note_path


def main():
    parser = argparse.ArgumentParser(description="Run a recurring draft health check on the current manuscript package.")
    parser.add_argument("--config", required=True)
    parser.add_argument("--title")
    parser.add_argument("--draft-file")
    parser.add_argument("--citation-audit-json")
    parser.add_argument("--submission-qc-json")
    parser.add_argument("--journal-targeting-json")
    parser.add_argument("--response-letter-json")
    parser.add_argument("--output-dir")
    parser.add_argument("--write-vault-note", action="store_true")
    args = parser.parse_args()

    config = load_json(Path(args.config))
    runtime_cfg = resolve_draft_health_config(config)
    draft_path = Path(args.draft_file) if args.draft_file else None
    title = infer_title(args.title, draft_path)
    run_dir = create_run_dir(config, title, args.output_dir)

    payload = {
        "rules": DRAFT_HEALTH_RULES,
        "title": title,
        "draft_text": load_optional_text(args.draft_file),
        "citation_audit": load_optional_json(args.citation_audit_json),
        "submission_qc": load_optional_json(args.submission_qc_json),
        "journal_targeting": load_optional_json(args.journal_targeting_json),
        "response_letter": load_optional_json(args.response_letter_json),
    }
    report, response_payload = run_draft_health_check(runtime_cfg, payload)

    meta = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "model": runtime_cfg["model"],
        "run_dir": to_portable_path(run_dir),
    }
    report_json_path = run_dir / "draft_health.json"
    markdown_path = run_dir / "draft_health.md"
    write_json(report_json_path, report)
    write_json(run_dir / "draft_health_response.json", response_payload)
    write_text(markdown_path, render_draft_health_markdown(title, report, meta))

    outputs = {
        "run_dir": to_portable_path(run_dir),
        "draft_health_json": to_portable_path(report_json_path),
        "draft_health_markdown": to_portable_path(markdown_path),
    }
    if args.write_vault_note:
        note_path = write_vault_note(config, title, report_json_path, markdown_path)
        outputs["vault_note"] = to_portable_path(note_path)

    print(json.dumps(outputs, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
