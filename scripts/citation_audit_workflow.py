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


DEFAULT_REPORT_FOLDER_NAME = "citation-audit"
CITATION_AUDIT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "citation_risk_summary": {"type": "string"},
        "reference_basis_note": {"type": "string"},
        "claim_audits": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "claim_or_sentence": {"type": "string"},
                    "risk": {"type": "string"},
                    "citation_action": {"type": "string"},
                    "evidence_or_reference_needed": {"type": "string"},
                    "severity": {"type": "string"},
                },
                "required": [
                    "claim_or_sentence",
                    "risk",
                    "citation_action",
                    "evidence_or_reference_needed",
                    "severity",
                ],
            },
        },
        "reference_completeness_checks": {"type": "array", "items": {"type": "string"}},
        "safe_keep_areas": {"type": "array", "items": {"type": "string"}},
        "priority_repairs": {"type": "array", "items": {"type": "string"}},
        "final_citation_targets": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "citation_risk_summary",
        "reference_basis_note",
        "claim_audits",
        "reference_completeness_checks",
        "safe_keep_areas",
        "priority_repairs",
        "final_citation_targets",
    ],
}
CITATION_AUDIT_RULES = [
    "You are auditing a manuscript draft for citation and evidence-linking risk before submission.",
    "Do not invent citations, bibliographic metadata, or claims about journal formatting rules.",
    "If no bibliography or reference notes are provided, say the audit is limited to draft-visible citation and evidence risk.",
    "Focus on claims that look under-supported, missing evidence anchors, or are likely to need stronger reference support.",
    "Prefer concrete repair actions over generic advice.",
]


def resolve_citation_audit_config(config: dict) -> dict:
    qa_runtime = resolve_qa_config(config)
    workflow_cfg = config.get("continuous_research", {}).get("openai", {})
    return {
        "api_key": workflow_cfg.get("api_key", "").strip() or qa_runtime["api_key"],
        "endpoint": workflow_cfg.get("base_url", "").strip() or qa_runtime["endpoint"],
        "model": workflow_cfg.get("citation_audit_model", "").strip() or qa_runtime["critic_model"],
        "reasoning_effort": workflow_cfg.get("citation_audit_reasoning_effort", "").strip()
        or qa_runtime["critic_effort"],
        "max_output_tokens": int(workflow_cfg.get("citation_audit_max_output_tokens", 7000)),
    }


def infer_title(explicit_title: str | None, draft_file: Path | None) -> str:
    if explicit_title and explicit_title.strip():
        return explicit_title.strip()
    if draft_file:
        return draft_file.stem
    return "Citation audit"


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


def run_citation_audit(runtime_cfg: dict, payload: dict) -> tuple[dict, dict]:
    request_payload = build_request_payload(
        runtime_cfg["model"],
        runtime_cfg["reasoning_effort"],
        runtime_cfg["max_output_tokens"],
        "citation_audit_report",
        CITATION_AUDIT_SCHEMA,
        json.dumps(payload, ensure_ascii=False),
    )
    response_payload = post_openai_json(runtime_cfg["endpoint"], runtime_cfg["api_key"], request_payload)
    response_text = extract_response_text(response_payload)
    if not response_text:
        raise RuntimeError("Citation audit step did not return any text output.")
    return json.loads(response_text), response_payload


def render_citation_audit_markdown(title: str, audit: dict, meta: dict):
    lines = [
        f"# Citation Audit - {title}",
        "",
        f"- Generated: {meta['generated_at']}",
        f"- Model: {meta['model']}",
        f"- Run directory: `{meta['run_dir']}`",
        "",
        "## Citation Risk Summary",
        "",
        audit["citation_risk_summary"],
        "",
        "## Reference Basis Note",
        "",
        audit["reference_basis_note"],
        "",
        "## Claim Audits",
        "",
    ]
    for item in audit.get("claim_audits", []):
        lines.append(f"- Claim or sentence: {item['claim_or_sentence']}")
        lines.append(f"  Risk: {item['risk']}")
        lines.append(f"  Citation action: {item['citation_action']}")
        lines.append(f"  Evidence or reference needed: {item['evidence_or_reference_needed']}")
        lines.append(f"  Severity: {item['severity']}")
    if not audit.get("claim_audits"):
        lines.append("- None recorded.")
    for section_title, key in [
        ("Reference Completeness Checks", "reference_completeness_checks"),
        ("Safe Keep Areas", "safe_keep_areas"),
        ("Priority Repairs", "priority_repairs"),
        ("Final Citation Targets", "final_citation_targets"),
    ]:
        lines.extend(["", f"## {section_title}", ""])
        values = audit.get(key, [])
        lines.extend([f"- {item}" for item in values] or ["- None recorded."])
    lines.append("")
    return "\n".join(lines)


def write_vault_note(config: dict, title: str, audit_json_path: Path, markdown_path: Path):
    vault_root = Path(config["vault_root"])
    writing_folder = vault_root / config["obsidian"]["writing_folder"]
    writing_folder.mkdir(parents=True, exist_ok=True)
    note_path = writing_folder / f"Citation Audit - {safe_filename_component(title, max_length=80)}.md"
    lines = [
        f"# Citation Audit - {title}",
        "",
        f"- JSON: `{to_portable_path(audit_json_path)}`",
        f"- Markdown: `{to_portable_path(markdown_path)}`",
        "",
        "Use this note to keep evidence-linking and citation repairs visible before final polishing.",
        "",
    ]
    write_text(note_path, "\n".join(lines))
    return note_path


def main():
    parser = argparse.ArgumentParser(description="Audit a draft for citation and evidence-linking risk before submission.")
    parser.add_argument("--config", required=True)
    parser.add_argument("--title")
    parser.add_argument("--draft-file")
    parser.add_argument("--journal-targeting-json")
    parser.add_argument("--response-letter-json")
    parser.add_argument("--references-file")
    parser.add_argument("--output-dir")
    parser.add_argument("--write-vault-note", action="store_true")
    args = parser.parse_args()

    config = load_json(Path(args.config))
    runtime_cfg = resolve_citation_audit_config(config)
    draft_path = Path(args.draft_file) if args.draft_file else None
    title = infer_title(args.title, draft_path)
    run_dir = create_run_dir(config, title, args.output_dir)

    payload = {
        "rules": CITATION_AUDIT_RULES,
        "title": title,
        "draft_text": load_optional_text(args.draft_file),
        "journal_targeting": load_optional_json(args.journal_targeting_json),
        "response_letter": load_optional_json(args.response_letter_json),
        "references_text": load_optional_text(args.references_file),
    }
    audit, response_payload = run_citation_audit(runtime_cfg, payload)

    meta = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "model": runtime_cfg["model"],
        "run_dir": to_portable_path(run_dir),
    }
    audit_json_path = run_dir / "citation_audit.json"
    markdown_path = run_dir / "citation_audit.md"
    write_json(audit_json_path, audit)
    write_json(run_dir / "citation_audit_response.json", response_payload)
    write_text(markdown_path, render_citation_audit_markdown(title, audit, meta))

    outputs = {
        "run_dir": to_portable_path(run_dir),
        "citation_audit_json": to_portable_path(audit_json_path),
        "citation_audit_markdown": to_portable_path(markdown_path),
    }
    if args.write_vault_note:
        note_path = write_vault_note(config, title, audit_json_path, markdown_path)
        outputs["vault_note"] = to_portable_path(note_path)

    print(json.dumps(outputs, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
