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


DEFAULT_REPORT_FOLDER_NAME = "draft-builder"
DRAFT_BUILDER_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "positioning_summary": {"type": "string"},
        "claim_rewrites": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "unsafe_claim": {"type": "string"},
                    "safe_rewrite": {"type": "string"},
                    "why_safer": {"type": "string"},
                },
                "required": ["unsafe_claim", "safe_rewrite", "why_safer"],
            },
        },
        "section_blocks": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "section": {"type": "string"},
                    "goal": {"type": "string"},
                    "paragraph_text": {"type": "string"},
                    "evidence_anchor": {"type": "string"},
                    "carryover_caution": {"type": "string"},
                },
                "required": ["section", "goal", "paragraph_text", "evidence_anchor", "carryover_caution"],
            },
        },
        "figure_callouts": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "figure_or_artifact": {"type": "string"},
                    "narrative_role": {"type": "string"},
                    "safe_caption_hook": {"type": "string"},
                },
                "required": ["figure_or_artifact", "narrative_role", "safe_caption_hook"],
            },
        },
        "next_section_targets": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "positioning_summary",
        "claim_rewrites",
        "section_blocks",
        "figure_callouts",
        "next_section_targets",
    ],
}
DRAFT_BUILDER_RULES = [
    "You are turning grounded analysis artifacts into manuscript-building blocks.",
    "Do not invent results, citations, numerical claims, or journal requirements.",
    "Write in a manuscript-usable style, but stay bounded by the provided evidence.",
    "Prefer section-ready paragraph blocks over vague advice.",
    "Use the self-review findings to rewrite risky claims into safer, publication-ready language.",
]


def resolve_draft_builder_config(config: dict) -> dict:
    qa_runtime = resolve_qa_config(config)
    workflow_cfg = config.get("continuous_research", {}).get("openai", {})
    return {
        "api_key": workflow_cfg.get("api_key", "").strip() or qa_runtime["api_key"],
        "endpoint": workflow_cfg.get("base_url", "").strip() or qa_runtime["endpoint"],
        "model": workflow_cfg.get("draft_builder_model", "").strip() or qa_runtime["reason_model"],
        "reasoning_effort": workflow_cfg.get("draft_builder_reasoning_effort", "").strip()
        or qa_runtime["reason_effort"],
        "max_output_tokens": int(workflow_cfg.get("draft_builder_max_output_tokens", 7000)),
    }


def infer_title(
    explicit_title: str | None,
    results_report_json_path: Path | None,
    self_review_json_path: Path | None,
) -> str:
    if explicit_title and explicit_title.strip():
        return explicit_title.strip()
    for candidate in [results_report_json_path, self_review_json_path]:
        if candidate and candidate.exists():
            try:
                payload = load_json(candidate)
            except (OSError, json.JSONDecodeError):
                continue
            headline = payload.get("headline", "").strip()
            if headline:
                return headline[:72]
    return "Draft builder"


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


def run_draft_builder(runtime_cfg: dict, payload: dict) -> tuple[dict, dict]:
    request_payload = build_request_payload(
        runtime_cfg["model"],
        runtime_cfg["reasoning_effort"],
        runtime_cfg["max_output_tokens"],
        "draft_builder_report",
        DRAFT_BUILDER_SCHEMA,
        json.dumps(payload, ensure_ascii=False),
    )
    response_payload = post_openai_json(runtime_cfg["endpoint"], runtime_cfg["api_key"], request_payload)
    response_text = extract_response_text(response_payload)
    if not response_text:
        raise RuntimeError("Draft builder step did not return any text output.")
    return json.loads(response_text), response_payload


def render_draft_builder_markdown(title: str, draft_builder: dict, meta: dict):
    lines = [
        f"# Draft Builder - {title}",
        "",
        f"- Generated: {meta['generated_at']}",
        f"- Model: {meta['model']}",
        f"- Run directory: `{meta['run_dir']}`",
        "",
        "## Positioning Summary",
        "",
        draft_builder["positioning_summary"],
        "",
        "## Claim Rewrites",
        "",
    ]
    for item in draft_builder.get("claim_rewrites", []):
        lines.append(f"- Unsafe claim: {item['unsafe_claim']}")
        lines.append(f"  Safe rewrite: {item['safe_rewrite']}")
        lines.append(f"  Why safer: {item['why_safer']}")
    if not draft_builder.get("claim_rewrites"):
        lines.append("- None recorded.")
    lines.extend(["", "## Section Blocks", ""])
    for item in draft_builder.get("section_blocks", []):
        lines.append(f"### {item['section']}")
        lines.append("")
        lines.append(f"- Goal: {item['goal']}")
        lines.append(f"- Evidence anchor: {item['evidence_anchor']}")
        lines.append(f"- Carryover caution: {item['carryover_caution']}")
        lines.append("")
        lines.append(item["paragraph_text"])
        lines.append("")
    if not draft_builder.get("section_blocks"):
        lines.append("- None recorded.")
        lines.append("")
    lines.extend(["## Figure Callouts", ""])
    for item in draft_builder.get("figure_callouts", []):
        lines.append(f"- Figure or artifact: {item['figure_or_artifact']}")
        lines.append(f"  Narrative role: {item['narrative_role']}")
        lines.append(f"  Safe caption hook: {item['safe_caption_hook']}")
    if not draft_builder.get("figure_callouts"):
        lines.append("- None recorded.")
    lines.extend(["", "## Next Section Targets", ""])
    targets = draft_builder.get("next_section_targets", [])
    lines.extend([f"- {item}" for item in targets] or ["- None recorded."])
    lines.append("")
    return "\n".join(lines)


def write_vault_note(config: dict, title: str, draft_builder_path: Path, markdown_path: Path):
    vault_root = Path(config["vault_root"])
    writing_folder = vault_root / config["obsidian"]["writing_folder"]
    writing_folder.mkdir(parents=True, exist_ok=True)
    note_path = writing_folder / f"Draft Builder - {safe_filename_component(title, max_length=80)}.md"
    lines = [
        f"# Draft Builder - {title}",
        "",
        f"- JSON: `{to_portable_path(draft_builder_path)}`",
        f"- Markdown: `{to_portable_path(markdown_path)}`",
        "",
        "Use this note as the bridge from grounded results into section-ready manuscript blocks.",
        "",
    ]
    write_text(note_path, "\n".join(lines))
    return note_path


def main():
    parser = argparse.ArgumentParser(description="Turn grounded analysis artifacts into section-aware manuscript building blocks.")
    parser.add_argument("--config", required=True)
    parser.add_argument("--title")
    parser.add_argument("--analysis-json")
    parser.add_argument("--results-report-json")
    parser.add_argument("--writing-memory-json")
    parser.add_argument("--self-review-json")
    parser.add_argument("--outline-file")
    parser.add_argument("--output-dir")
    parser.add_argument("--write-vault-note", action="store_true")
    args = parser.parse_args()

    config = load_json(Path(args.config))
    runtime_cfg = resolve_draft_builder_config(config)
    title = infer_title(
        args.title,
        Path(args.results_report_json) if args.results_report_json else None,
        Path(args.self_review_json) if args.self_review_json else None,
    )
    run_dir = create_run_dir(config, title, args.output_dir)

    payload = {
        "rules": DRAFT_BUILDER_RULES,
        "title": title,
        "analysis": load_optional_json(args.analysis_json),
        "results_report": load_optional_json(args.results_report_json),
        "writing_memory": load_optional_json(args.writing_memory_json),
        "self_review": load_optional_json(args.self_review_json),
        "outline_text": load_optional_text(args.outline_file),
    }
    draft_builder, response_payload = run_draft_builder(runtime_cfg, payload)

    meta = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "model": runtime_cfg["model"],
        "run_dir": to_portable_path(run_dir),
    }
    draft_builder_json_path = run_dir / "draft_builder.json"
    markdown_path = run_dir / "draft_builder.md"
    write_json(draft_builder_json_path, draft_builder)
    write_json(run_dir / "draft_builder_response.json", response_payload)
    write_text(markdown_path, render_draft_builder_markdown(title, draft_builder, meta))

    outputs = {
        "run_dir": to_portable_path(run_dir),
        "draft_builder_json": to_portable_path(draft_builder_json_path),
        "draft_builder_markdown": to_portable_path(markdown_path),
    }
    if args.write_vault_note:
        note_path = write_vault_note(config, title, draft_builder_json_path, markdown_path)
        outputs["vault_note"] = to_portable_path(note_path)

    print(json.dumps(outputs, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
