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


DEFAULT_REPORT_FOLDER_NAME = "writing-memory"
WRITING_MEMORY_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "focus_summary": {"type": "string"},
        "reusable_claims": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "claim": {"type": "string"},
                    "evidence_basis": {"type": "string"},
                    "caution": {"type": "string"},
                    "fit_sections": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["claim", "evidence_basis", "caution", "fit_sections"],
            },
        },
        "reusable_caveats": {"type": "array", "items": {"type": "string"}},
        "figure_narratives": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "artifact": {"type": "string"},
                    "caption_angle": {"type": "string"},
                    "why_it_matters": {"type": "string"},
                },
                "required": ["artifact", "caption_angle", "why_it_matters"],
            },
        },
        "reviewer_watchouts": {"type": "array", "items": {"type": "string"}},
        "terminology_preferences": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "term": {"type": "string"},
                    "preferred_usage": {"type": "string"},
                    "avoid_phrase": {"type": "string"},
                },
                "required": ["term", "preferred_usage", "avoid_phrase"],
            },
        },
        "next_writing_targets": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "focus_summary",
        "reusable_claims",
        "reusable_caveats",
        "figure_narratives",
        "reviewer_watchouts",
        "terminology_preferences",
        "next_writing_targets",
    ],
}
WRITING_MEMORY_RULES = [
    "You are extracting reusable scientific writing memory from grounded experiment-analysis artifacts.",
    "Do not invent results, citations, or figure claims.",
    "Prefer manuscript-safe claims that are honestly bounded by the provided evidence.",
    "Separate reusable claims from reusable caveats.",
    "If the evidence supports only a narrow or cautious statement, preserve that caution rather than strengthening the claim.",
    "The output should help future drafting, figure writing, and reviewer response preparation.",
]


def resolve_writing_memory_config(config: dict) -> dict:
    qa_runtime = resolve_qa_config(config)
    workflow_cfg = config.get("continuous_research", {}).get("openai", {})
    return {
        "api_key": workflow_cfg.get("api_key", "").strip() or qa_runtime["api_key"],
        "endpoint": workflow_cfg.get("base_url", "").strip() or qa_runtime["endpoint"],
        "model": workflow_cfg.get("writing_memory_model", "").strip() or qa_runtime["reason_model"],
        "reasoning_effort": workflow_cfg.get("writing_memory_reasoning_effort", "").strip()
        or qa_runtime["reason_effort"],
        "max_output_tokens": int(workflow_cfg.get("writing_memory_max_output_tokens", 5000)),
    }


def infer_title(explicit_title: str | None, analysis_json_path: Path | None, report_json_path: Path | None) -> str:
    if explicit_title and explicit_title.strip():
        return explicit_title.strip()
    if analysis_json_path and analysis_json_path.exists():
        try:
            payload = load_json(analysis_json_path)
            if payload.get("title"):
                return str(payload["title"])
        except (OSError, json.JSONDecodeError):
            pass
    if report_json_path and report_json_path.exists():
        try:
            payload = load_json(report_json_path)
            headline = payload.get("headline", "").strip()
            if headline:
                return headline[:72]
        except (OSError, json.JSONDecodeError):
            pass
    return "Writing memory"


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


def run_writing_memory(runtime_cfg: dict, payload: dict) -> tuple[dict, dict]:
    request_payload = build_request_payload(
        runtime_cfg["model"],
        runtime_cfg["reasoning_effort"],
        runtime_cfg["max_output_tokens"],
        "writing_memory_report",
        WRITING_MEMORY_SCHEMA,
        json.dumps(payload, ensure_ascii=False),
    )
    response_payload = post_openai_json(runtime_cfg["endpoint"], runtime_cfg["api_key"], request_payload)
    response_text = extract_response_text(response_payload)
    if not response_text:
        raise RuntimeError("Writing memory step did not return any text output.")
    return json.loads(response_text), response_payload


def render_writing_memory_markdown(title: str, memory: dict, meta: dict):
    lines = [
        f"# Writing Memory - {title}",
        "",
        f"- Generated: {meta['generated_at']}",
        f"- Model: {meta['model']}",
        f"- Run directory: `{meta['run_dir']}`",
        "",
        "## Focus Summary",
        "",
        memory["focus_summary"],
        "",
        "## Reusable Claims",
        "",
    ]
    for item in memory.get("reusable_claims", []):
        lines.append(f"- Claim: {item['claim']}")
        lines.append(f"  Evidence basis: {item['evidence_basis']}")
        lines.append(f"  Caution: {item['caution']}")
        lines.append(f"  Fit sections: {', '.join(item.get('fit_sections', [])) or 'None recorded'}")
    if not memory.get("reusable_claims"):
        lines.append("- None recorded.")
    lines.extend(["", "## Reusable Caveats", ""])
    caveats = memory.get("reusable_caveats", [])
    lines.extend([f"- {item}" for item in caveats] or ["- None recorded."])
    lines.extend(["", "## Figure Narratives", ""])
    for item in memory.get("figure_narratives", []):
        lines.append(f"- Artifact: {item['artifact']}")
        lines.append(f"  Caption angle: {item['caption_angle']}")
        lines.append(f"  Why it matters: {item['why_it_matters']}")
    if not memory.get("figure_narratives"):
        lines.append("- None recorded.")
    lines.extend(["", "## Reviewer Watchouts", ""])
    watchouts = memory.get("reviewer_watchouts", [])
    lines.extend([f"- {item}" for item in watchouts] or ["- None recorded."])
    lines.extend(["", "## Terminology Preferences", ""])
    for item in memory.get("terminology_preferences", []):
        lines.append(f"- Term: {item['term']}")
        lines.append(f"  Preferred usage: {item['preferred_usage']}")
        lines.append(f"  Avoid phrase: {item['avoid_phrase']}")
    if not memory.get("terminology_preferences"):
        lines.append("- None recorded.")
    lines.extend(["", "## Next Writing Targets", ""])
    targets = memory.get("next_writing_targets", [])
    lines.extend([f"- {item}" for item in targets] or ["- None recorded."])
    lines.append("")
    return "\n".join(lines)


def write_vault_note(config: dict, title: str, memory_path: Path, markdown_path: Path):
    vault_root = Path(config["vault_root"])
    writing_folder = vault_root / config["obsidian"]["writing_folder"]
    writing_folder.mkdir(parents=True, exist_ok=True)
    note_path = writing_folder / f"Writing Memory - {safe_filename_component(title, max_length=80)}.md"
    lines = [
        f"# Writing Memory - {title}",
        "",
        f"- JSON: `{to_portable_path(memory_path)}`",
        f"- Markdown: `{to_portable_path(markdown_path)}`",
        "",
        "Use this note as the durable bridge between experiment-grounded conclusions and future manuscript drafting.",
        "",
    ]
    write_text(note_path, "\n".join(lines))
    return note_path


def main():
    parser = argparse.ArgumentParser(description="Extract reusable writing memory from grounded analysis artifacts.")
    parser.add_argument("--config", required=True)
    parser.add_argument("--title")
    parser.add_argument("--analysis-json")
    parser.add_argument("--results-report-json")
    parser.add_argument("--results-report-markdown")
    parser.add_argument("--output-dir")
    parser.add_argument("--write-vault-note", action="store_true")
    args = parser.parse_args()

    config = load_json(Path(args.config))
    runtime_cfg = resolve_writing_memory_config(config)
    analysis_json_path = Path(args.analysis_json) if args.analysis_json else None
    report_json_path = Path(args.results_report_json) if args.results_report_json else None
    title = infer_title(args.title, analysis_json_path, report_json_path)
    run_dir = create_run_dir(config, title, args.output_dir)

    payload = {
        "rules": WRITING_MEMORY_RULES,
        "title": title,
        "analysis": load_optional_json(args.analysis_json),
        "results_report": load_optional_json(args.results_report_json),
        "results_report_markdown": load_optional_text(args.results_report_markdown),
    }
    memory, response_payload = run_writing_memory(runtime_cfg, payload)

    meta = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "model": runtime_cfg["model"],
        "run_dir": to_portable_path(run_dir),
    }
    memory_json_path = run_dir / "writing_memory.json"
    markdown_path = run_dir / "writing_memory.md"
    write_json(memory_json_path, memory)
    write_json(run_dir / "writing_memory_response.json", response_payload)
    write_text(markdown_path, render_writing_memory_markdown(title, memory, meta))

    outputs = {
        "run_dir": to_portable_path(run_dir),
        "writing_memory_json": to_portable_path(memory_json_path),
        "writing_memory_markdown": to_portable_path(markdown_path),
    }
    if args.write_vault_note:
        note_path = write_vault_note(config, title, memory_json_path, markdown_path)
        outputs["vault_note"] = to_portable_path(note_path)

    print(json.dumps(outputs, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
