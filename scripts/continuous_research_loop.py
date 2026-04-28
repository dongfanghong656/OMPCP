#!/usr/bin/env python
import argparse
import json
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

from research_question_flow import (
    load_json,
    normalize_space,
    safe_filename_component,
    slugify,
    timestamp_slug,
    to_portable_path,
    update_index,
    write_json,
    write_text,
)


SCRIPT_DIR = Path(__file__).resolve().parent
DAILY_RESEARCH_CYCLE_SCRIPT = SCRIPT_DIR / "daily_research_cycle.py"
RESULTS_ANALYSIS_WORKFLOW_SCRIPT = SCRIPT_DIR / "results_analysis_workflow.py"
WRITING_MEMORY_WORKFLOW_SCRIPT = SCRIPT_DIR / "writing_memory_workflow.py"
SELF_REVIEW_WORKFLOW_SCRIPT = SCRIPT_DIR / "self_review_workflow.py"
DRAFT_BUILDER_WORKFLOW_SCRIPT = SCRIPT_DIR / "draft_builder_workflow.py"
REBUTTAL_SCAFFOLD_WORKFLOW_SCRIPT = SCRIPT_DIR / "rebuttal_scaffold_workflow.py"
JOURNAL_TARGETING_WORKFLOW_SCRIPT = SCRIPT_DIR / "journal_targeting_workflow.py"
RESPONSE_LETTER_WORKFLOW_SCRIPT = SCRIPT_DIR / "response_letter_workflow.py"
CITATION_AUDIT_WORKFLOW_SCRIPT = SCRIPT_DIR / "citation_audit_workflow.py"
SUBMISSION_QC_WORKFLOW_SCRIPT = SCRIPT_DIR / "submission_qc_workflow.py"
DRAFT_HEALTH_WORKFLOW_SCRIPT = SCRIPT_DIR / "draft_health_check_workflow.py"
SUBMISSION_MEMORY_WORKFLOW_SCRIPT = SCRIPT_DIR / "submission_memory_workflow.py"
DEFAULT_REPORT_FOLDER_NAME = "continuous-research"
DEFAULT_NOTE_FOLDER = "04_Progress"
STAGE_ORDER = [
    "literature_refresh",
    "question_radar",
    "question_answering",
    "experiment_analysis",
    "results_report",
    "writing_memory",
    "self_review",
    "draft_builder",
    "rebuttal_scaffold",
    "journal_targeting",
    "response_letter",
    "citation_audit",
    "submission_qc",
    "draft_health",
    "submission_memory",
]


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def resolve_loop_config(config: dict) -> dict:
    loop_cfg = config.get("continuous_research", {})
    return {
        "report_folder_name": loop_cfg.get("report_folder_name", DEFAULT_REPORT_FOLDER_NAME).strip()
        or DEFAULT_REPORT_FOLDER_NAME,
        "note_folder": loop_cfg.get("note_folder", DEFAULT_NOTE_FOLDER).strip() or DEFAULT_NOTE_FOLDER,
        "write_progress_note": bool(loop_cfg.get("write_progress_note", True)),
    }


def project_profile_summary(config: dict):
    try:
        profile = load_json(Path(config["profile_path"]))
    except OSError:
        return {}
    return {
        "updated_for": profile.get("updated_for", ""),
        "primary_objective": profile.get("primary_objective", ""),
        "evaluation_focus": profile.get("evaluation_focus", []),
        "writing_goal": profile.get("writing_goal", ""),
    }


def create_session_dir(config: dict, loop_cfg: dict, title: str, explicit_dir: str | None) -> Path:
    if explicit_dir:
        session_dir = Path(explicit_dir)
        session_dir.mkdir(parents=True, exist_ok=True)
        return session_dir

    output_root = Path(config["output_root"])
    session_dir = output_root / loop_cfg["report_folder_name"] / f"{date.today().isoformat()}-{slugify(title)}-{timestamp_slug()}"
    session_dir.mkdir(parents=True, exist_ok=True)
    return session_dir


def default_stage_manifest():
    return {
        stage: {
            "status": "pending",
            "updated_at": "",
            "summary": "",
            "artifacts": [],
        }
        for stage in STAGE_ORDER
    }


def ensure_manifest_shape(manifest: dict):
    manifest.setdefault("stages", {})
    for stage, payload in default_stage_manifest().items():
        manifest["stages"].setdefault(stage, payload)
    manifest.setdefault("recent_runs", [])
    return manifest


def note_title(title: str) -> str:
    return safe_filename_component(f"Research Loop - {title}", max_length=100)


def stage_counts(manifest: dict):
    counts = {"completed": 0, "active": 0, "pending": 0, "other": 0}
    for stage in STAGE_ORDER:
        status = manifest["stages"][stage].get("status", "pending")
        if status in counts:
            counts[status] += 1
        else:
            counts["other"] += 1
    return counts


def current_focus_stages(manifest: dict):
    active = [stage for stage in STAGE_ORDER if manifest["stages"][stage].get("status") == "active"]
    if active:
        return active
    pending = [stage for stage in STAGE_ORDER if manifest["stages"][stage].get("status") == "pending"]
    return pending[:3]


def note_lines(manifest: dict):
    counts = stage_counts(manifest)
    focus = current_focus_stages(manifest)
    lines = [
        f"# {manifest['title']}",
        "",
        f"- Session ID: `{manifest['session_id']}`",
        f"- Created: {manifest['created_at']}",
        f"- Updated: {manifest['updated_at']}",
        f"- Workspace: `{manifest['session_dir']}`",
        "",
        "## Objective",
        "",
        manifest.get("objective", "") or "No objective recorded.",
        "",
        "## Loop Snapshot",
        "",
        f"- Completed stages: {counts['completed']}",
        f"- Active stages: {counts['active']}",
        f"- Pending stages: {counts['pending']}",
        f"- Current focus: {', '.join(focus) if focus else 'All tracked stages completed.'}",
        "",
        "## Stage Status",
        "",
    ]

    for stage in STAGE_ORDER:
        payload = manifest["stages"][stage]
        lines.append(f"### {stage}")
        lines.append("")
        lines.append(f"- Status: {payload['status']}")
        lines.append(f"- Updated: {payload['updated_at'] or 'Not run yet'}")
        lines.append(f"- Summary: {payload['summary'] or 'No summary recorded.'}")
        if payload.get("artifacts"):
            lines.append("")
            lines.append("Artifacts:")
            for artifact in payload["artifacts"]:
                label = artifact.get("label", "artifact")
                path = artifact.get("path", "")
                lines.append(f"- {label}: `{path}`")
        lines.append("")

    if manifest.get("recent_runs"):
        lines.extend(["## Recent Runs", ""])
        for item in manifest["recent_runs"][:8]:
            lines.append(f"- {item['timestamp']} | {item['kind']} | {item['summary']}")
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def refresh_progress_note(config: dict, loop_cfg: dict, manifest: dict):
    if not loop_cfg["write_progress_note"]:
        return None

    vault_root = Path(config["vault_root"])
    note_folder = vault_root / Path(loop_cfg["note_folder"])
    note_folder.mkdir(parents=True, exist_ok=True)
    path = note_folder / f"{note_title(manifest['title'])}.md"
    write_text(path, note_lines(manifest))
    update_index(path.parent / "_Index.md", f"- [[{path.stem}]]", "# Progress Index\n")
    return path


def save_manifest(session_dir: Path, manifest: dict):
    manifest["updated_at"] = now_iso()
    write_json(session_dir / "manifest.json", manifest)


def load_manifest(path: str):
    manifest_path = Path(path)
    if manifest_path.is_dir():
        manifest_path = manifest_path / "manifest.json"
    return ensure_manifest_shape(load_json(manifest_path)), manifest_path


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


def run_loop_subcommand(*args: str):
    return run_python_script(Path(__file__).resolve(), *args)


def append_recent_run(manifest: dict, kind: str, summary: str):
    manifest.setdefault("recent_runs", [])
    manifest["recent_runs"].insert(
        0,
        {
            "timestamp": now_iso(),
            "kind": kind,
            "summary": summary,
        },
    )
    manifest["recent_runs"] = manifest["recent_runs"][:12]


def set_stage_state(manifest: dict, stage: str, status: str, summary: str, artifacts):
    payload = manifest["stages"][stage]
    payload["status"] = status
    payload["updated_at"] = now_iso()
    payload["summary"] = summary
    payload["artifacts"] = artifacts


def artifact_path_for_label(manifest: dict, stage: str, label: str, fallback_stages=None) -> str:
    search_stages = [stage]
    if fallback_stages:
        search_stages.extend(fallback_stages)
    for stage_name in search_stages:
        for artifact in manifest["stages"].get(stage_name, {}).get("artifacts", []):
            if artifact.get("label") == label:
                return artifact.get("path", "")
    return ""


def init_manifest(config: dict, loop_cfg: dict, title: str, objective: str, session_dir: Path):
    session_id = f"{date.today().isoformat()}-{slugify(title)}-{timestamp_slug()}"
    manifest = {
        "session_id": session_id,
        "title": title,
        "objective": objective,
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "session_dir": to_portable_path(session_dir),
        "config_path": "",
        "profile_summary": project_profile_summary(config),
        "stages": default_stage_manifest(),
        "recent_runs": [],
    }
    return manifest


def run_init(args):
    config = load_json(Path(args.config))
    loop_cfg = resolve_loop_config(config)
    title = normalize_space(args.title)
    objective = normalize_space(args.objective) if args.objective else ""
    session_dir = create_session_dir(config, loop_cfg, title, args.output_dir)
    manifest = init_manifest(config, loop_cfg, title, objective, session_dir)
    manifest["config_path"] = to_portable_path(Path(args.config).resolve())
    note_path = refresh_progress_note(config, loop_cfg, manifest)
    save_manifest(session_dir, manifest)

    outputs = {
        "session_dir": to_portable_path(session_dir),
        "manifest": to_portable_path(session_dir / "manifest.json"),
    }
    if note_path:
        outputs["progress_note"] = to_portable_path(note_path)
    print(json.dumps(outputs, ensure_ascii=False, indent=2))


def run_status(args):
    manifest, manifest_path = load_manifest(args.manifest)
    summary = {
        "session_id": manifest["session_id"],
        "title": manifest["title"],
        "updated_at": manifest["updated_at"],
        "session_dir": manifest["session_dir"],
        "stages": {
            stage: {
                "status": manifest["stages"][stage]["status"],
                "updated_at": manifest["stages"][stage]["updated_at"],
                "summary": manifest["stages"][stage]["summary"],
            }
            for stage in STAGE_ORDER
        },
        "manifest": to_portable_path(manifest_path),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def run_daily(args):
    manifest, manifest_path = load_manifest(args.manifest)
    config = load_json(Path(manifest["config_path"]))
    loop_cfg = resolve_loop_config(config)
    session_dir = manifest_path.parent

    cycle_args = ["--config", manifest["config_path"]]
    if args.skip_retrieval:
        cycle_args.append("--skip-retrieval")
    if args.skip_question_radar:
        cycle_args.append("--skip-question-radar")
    if args.skip_digest:
        cycle_args.append("--skip-digest")
    if args.latest_literature_file:
        cycle_args.extend(["--latest-literature-file", args.latest_literature_file])

    cycle_stdout = run_python_script(DAILY_RESEARCH_CYCLE_SCRIPT, *cycle_args)
    cycle_outputs = json.loads(cycle_stdout)

    if cycle_outputs.get("retrieval_markdown") or cycle_outputs.get("retrieval_json"):
        artifacts = []
        if cycle_outputs.get("retrieval_markdown"):
            artifacts.append({"label": "retrieval_markdown", "path": cycle_outputs["retrieval_markdown"]})
        if cycle_outputs.get("retrieval_json"):
            artifacts.append({"label": "retrieval_json", "path": cycle_outputs["retrieval_json"]})
        set_stage_state(manifest, "literature_refresh", "completed", "Daily literature refresh recorded.", artifacts)

    if cycle_outputs.get("question_radar_note") or cycle_outputs.get("question_radar_markdown"):
        artifacts = []
        if cycle_outputs.get("question_radar_note"):
            artifacts.append({"label": "question_radar_note", "path": cycle_outputs["question_radar_note"]})
        if cycle_outputs.get("question_radar_markdown"):
            artifacts.append({"label": "question_radar_markdown", "path": cycle_outputs["question_radar_markdown"]})
        set_stage_state(manifest, "question_radar", "completed", "Daily question radar updated.", artifacts)

    if cycle_outputs.get("daily_digest"):
        artifacts = [{"label": "daily_digest", "path": cycle_outputs["daily_digest"]}]
        set_stage_state(manifest, "results_report", "active", "Daily digest available for decision review.", artifacts)

    append_recent_run(
        manifest,
        "daily_cycle",
        "Ran daily literature/question/digest cycle.",
    )
    note_path = refresh_progress_note(config, loop_cfg, manifest)
    save_manifest(session_dir, manifest)

    outputs = {
        "manifest": to_portable_path(session_dir / "manifest.json"),
        "cycle_outputs": cycle_outputs,
    }
    if note_path:
        outputs["progress_note"] = to_portable_path(note_path)
    print(json.dumps(outputs, ensure_ascii=False, indent=2))


def run_link_artifact(args):
    manifest, manifest_path = load_manifest(args.manifest)
    config = load_json(Path(manifest["config_path"]))
    loop_cfg = resolve_loop_config(config)
    session_dir = manifest_path.parent

    if args.stage not in STAGE_ORDER:
        raise ValueError(f"Unsupported stage: {args.stage}")

    artifact = {
        "label": args.label or Path(args.path).name,
        "path": to_portable_path(Path(args.path)),
    }
    set_stage_state(
        manifest,
        args.stage,
        args.status,
        args.summary or f"Linked artifact for {args.stage}.",
        [artifact],
    )
    append_recent_run(manifest, f"link:{args.stage}", artifact["label"])
    note_path = refresh_progress_note(config, loop_cfg, manifest)
    save_manifest(session_dir, manifest)

    outputs = {
        "manifest": to_portable_path(session_dir / "manifest.json"),
    }
    if note_path:
        outputs["progress_note"] = to_portable_path(note_path)
    print(json.dumps(outputs, ensure_ascii=False, indent=2))


def run_results_analysis(args):
    manifest, manifest_path = load_manifest(args.manifest)
    config = load_json(Path(manifest["config_path"]))
    loop_cfg = resolve_loop_config(config)
    session_dir = manifest_path.parent

    analysis_args = [
        "--config",
        manifest["config_path"],
        "--experiment-dir",
        args.experiment_dir,
    ]
    if args.title:
        analysis_args.extend(["--title", args.title])
    if args.write_progress_note:
        analysis_args.append("--write-progress-note")

    workflow_stdout = run_python_script(RESULTS_ANALYSIS_WORKFLOW_SCRIPT, *analysis_args)
    workflow_outputs = json.loads(workflow_stdout)

    analysis_artifacts = []
    if workflow_outputs.get("analysis_json"):
        analysis_artifacts.append({"label": "analysis_json", "path": workflow_outputs["analysis_json"]})
    if workflow_outputs.get("results_report_json"):
        analysis_artifacts.append({"label": "results_report_json", "path": workflow_outputs["results_report_json"]})
    set_stage_state(
        manifest,
        "experiment_analysis",
        "completed",
        "Structured post-experiment analysis package generated.",
        analysis_artifacts,
    )

    report_artifacts = []
    if workflow_outputs.get("results_report_json"):
        report_artifacts.append({"label": "results_report_json", "path": workflow_outputs["results_report_json"]})
    if workflow_outputs.get("results_report_markdown"):
        report_artifacts.append(
            {"label": "results_report_markdown", "path": workflow_outputs["results_report_markdown"]}
        )
    if workflow_outputs.get("progress_note"):
        report_artifacts.append({"label": "results_progress_note", "path": workflow_outputs["progress_note"]})
    set_stage_state(
        manifest,
        "results_report",
        "completed",
        "Decision-oriented results report generated.",
        report_artifacts,
    )

    append_recent_run(
        manifest,
        "results_analysis",
        f"Analyzed experiment bundle at {to_portable_path(Path(args.experiment_dir))}",
    )
    note_path = refresh_progress_note(config, loop_cfg, manifest)
    save_manifest(session_dir, manifest)

    outputs = {
        "manifest": to_portable_path(session_dir / "manifest.json"),
        "analysis_outputs": workflow_outputs,
    }
    if note_path:
        outputs["progress_note"] = to_portable_path(note_path)
    print(json.dumps(outputs, ensure_ascii=False, indent=2))


def run_writing_memory(args):
    manifest, manifest_path = load_manifest(args.manifest)
    config = load_json(Path(manifest["config_path"]))
    loop_cfg = resolve_loop_config(config)
    session_dir = manifest_path.parent

    analysis_json = args.analysis_json or artifact_path_for_label(manifest, "experiment_analysis", "analysis_json")
    results_report_json = args.results_report_json or artifact_path_for_label(
        manifest, "results_report", "results_report_json", fallback_stages=["experiment_analysis"]
    )
    results_report_markdown = artifact_path_for_label(manifest, "results_report", "results_report_markdown")

    workflow_args = ["--config", manifest["config_path"]]
    if analysis_json:
        workflow_args.extend(["--analysis-json", analysis_json])
    if results_report_json:
        workflow_args.extend(["--results-report-json", results_report_json])
    if results_report_markdown:
        workflow_args.extend(["--results-report-markdown", results_report_markdown])
    if args.title:
        workflow_args.extend(["--title", args.title])
    if args.write_vault_note:
        workflow_args.append("--write-vault-note")

    workflow_stdout = run_python_script(WRITING_MEMORY_WORKFLOW_SCRIPT, *workflow_args)
    workflow_outputs = json.loads(workflow_stdout)

    artifacts = []
    if workflow_outputs.get("writing_memory_json"):
        artifacts.append({"label": "writing_memory_json", "path": workflow_outputs["writing_memory_json"]})
    if workflow_outputs.get("writing_memory_markdown"):
        artifacts.append({"label": "writing_memory_markdown", "path": workflow_outputs["writing_memory_markdown"]})
    if workflow_outputs.get("vault_note"):
        artifacts.append({"label": "writing_memory_note", "path": workflow_outputs["vault_note"]})
    set_stage_state(
        manifest,
        "writing_memory",
        "completed",
        "Reusable writing memory extracted from grounded analysis artifacts.",
        artifacts,
    )
    append_recent_run(manifest, "writing_memory", "Updated reusable writing memory.")
    note_path = refresh_progress_note(config, loop_cfg, manifest)
    save_manifest(session_dir, manifest)

    outputs = {
        "manifest": to_portable_path(session_dir / "manifest.json"),
        "writing_memory_outputs": workflow_outputs,
    }
    if note_path:
        outputs["progress_note"] = to_portable_path(note_path)
    print(json.dumps(outputs, ensure_ascii=False, indent=2))


def run_self_review(args):
    manifest, manifest_path = load_manifest(args.manifest)
    config = load_json(Path(manifest["config_path"]))
    loop_cfg = resolve_loop_config(config)
    session_dir = manifest_path.parent

    workflow_args = [
        "--config",
        manifest["config_path"],
        "--draft-file",
        args.draft_file,
    ]
    analysis_json = args.analysis_json or artifact_path_for_label(manifest, "experiment_analysis", "analysis_json")
    results_report_json = args.results_report_json or artifact_path_for_label(
        manifest, "results_report", "results_report_json", fallback_stages=["experiment_analysis"]
    )
    writing_memory_json = args.writing_memory_json or artifact_path_for_label(
        manifest, "writing_memory", "writing_memory_json"
    )
    if analysis_json:
        workflow_args.extend(["--analysis-json", analysis_json])
    if results_report_json:
        workflow_args.extend(["--results-report-json", results_report_json])
    if writing_memory_json:
        workflow_args.extend(["--writing-memory-json", writing_memory_json])
    if args.title:
        workflow_args.extend(["--title", args.title])
    if args.write_vault_note:
        workflow_args.append("--write-vault-note")

    workflow_stdout = run_python_script(SELF_REVIEW_WORKFLOW_SCRIPT, *workflow_args)
    workflow_outputs = json.loads(workflow_stdout)

    artifacts = []
    if workflow_outputs.get("self_review_json"):
        artifacts.append({"label": "self_review_json", "path": workflow_outputs["self_review_json"]})
    if workflow_outputs.get("self_review_markdown"):
        artifacts.append({"label": "self_review_markdown", "path": workflow_outputs["self_review_markdown"]})
    if workflow_outputs.get("vault_note"):
        artifacts.append({"label": "self_review_note", "path": workflow_outputs["vault_note"]})
    set_stage_state(
        manifest,
        "self_review",
        "completed",
        "Evidence-constrained self review completed for the supplied draft.",
        artifacts,
    )
    append_recent_run(manifest, "self_review", f"Reviewed draft {to_portable_path(Path(args.draft_file))}")
    note_path = refresh_progress_note(config, loop_cfg, manifest)
    save_manifest(session_dir, manifest)

    outputs = {
        "manifest": to_portable_path(session_dir / "manifest.json"),
        "self_review_outputs": workflow_outputs,
    }
    if note_path:
        outputs["progress_note"] = to_portable_path(note_path)
    print(json.dumps(outputs, ensure_ascii=False, indent=2))


def run_draft_builder(args):
    manifest, manifest_path = load_manifest(args.manifest)
    config = load_json(Path(manifest["config_path"]))
    loop_cfg = resolve_loop_config(config)
    session_dir = manifest_path.parent

    workflow_args = ["--config", manifest["config_path"]]
    analysis_json = args.analysis_json or artifact_path_for_label(manifest, "experiment_analysis", "analysis_json")
    results_report_json = args.results_report_json or artifact_path_for_label(
        manifest, "results_report", "results_report_json", fallback_stages=["experiment_analysis"]
    )
    writing_memory_json = args.writing_memory_json or artifact_path_for_label(
        manifest, "writing_memory", "writing_memory_json"
    )
    self_review_json = args.self_review_json or artifact_path_for_label(manifest, "self_review", "self_review_json")
    if analysis_json:
        workflow_args.extend(["--analysis-json", analysis_json])
    if results_report_json:
        workflow_args.extend(["--results-report-json", results_report_json])
    if writing_memory_json:
        workflow_args.extend(["--writing-memory-json", writing_memory_json])
    if self_review_json:
        workflow_args.extend(["--self-review-json", self_review_json])
    if args.outline_file:
        workflow_args.extend(["--outline-file", args.outline_file])
    if args.title:
        workflow_args.extend(["--title", args.title])
    if args.write_vault_note:
        workflow_args.append("--write-vault-note")

    workflow_stdout = run_python_script(DRAFT_BUILDER_WORKFLOW_SCRIPT, *workflow_args)
    workflow_outputs = json.loads(workflow_stdout)

    artifacts = []
    if workflow_outputs.get("draft_builder_json"):
        artifacts.append({"label": "draft_builder_json", "path": workflow_outputs["draft_builder_json"]})
    if workflow_outputs.get("draft_builder_markdown"):
        artifacts.append({"label": "draft_builder_markdown", "path": workflow_outputs["draft_builder_markdown"]})
    if workflow_outputs.get("vault_note"):
        artifacts.append({"label": "draft_builder_note", "path": workflow_outputs["vault_note"]})
    set_stage_state(
        manifest,
        "draft_builder",
        "completed",
        "Section-aware manuscript building blocks generated from grounded artifacts.",
        artifacts,
    )
    append_recent_run(manifest, "draft_builder", "Updated grounded draft building blocks.")
    note_path = refresh_progress_note(config, loop_cfg, manifest)
    save_manifest(session_dir, manifest)

    outputs = {
        "manifest": to_portable_path(session_dir / "manifest.json"),
        "draft_builder_outputs": workflow_outputs,
    }
    if note_path:
        outputs["progress_note"] = to_portable_path(note_path)
    print(json.dumps(outputs, ensure_ascii=False, indent=2))


def run_rebuttal_scaffold(args):
    manifest, manifest_path = load_manifest(args.manifest)
    config = load_json(Path(manifest["config_path"]))
    loop_cfg = resolve_loop_config(config)
    session_dir = manifest_path.parent

    workflow_args = ["--config", manifest["config_path"]]
    self_review_json = args.self_review_json or artifact_path_for_label(manifest, "self_review", "self_review_json")
    writing_memory_json = args.writing_memory_json or artifact_path_for_label(
        manifest, "writing_memory", "writing_memory_json"
    )
    results_report_json = args.results_report_json or artifact_path_for_label(
        manifest, "results_report", "results_report_json", fallback_stages=["experiment_analysis"]
    )
    if self_review_json:
        workflow_args.extend(["--self-review-json", self_review_json])
    if writing_memory_json:
        workflow_args.extend(["--writing-memory-json", writing_memory_json])
    if results_report_json:
        workflow_args.extend(["--results-report-json", results_report_json])
    if args.draft_file:
        workflow_args.extend(["--draft-file", args.draft_file])
    if args.title:
        workflow_args.extend(["--title", args.title])
    if args.write_vault_note:
        workflow_args.append("--write-vault-note")

    workflow_stdout = run_python_script(REBUTTAL_SCAFFOLD_WORKFLOW_SCRIPT, *workflow_args)
    workflow_outputs = json.loads(workflow_stdout)

    artifacts = []
    if workflow_outputs.get("rebuttal_scaffold_json"):
        artifacts.append(
            {"label": "rebuttal_scaffold_json", "path": workflow_outputs["rebuttal_scaffold_json"]}
        )
    if workflow_outputs.get("rebuttal_scaffold_markdown"):
        artifacts.append(
            {"label": "rebuttal_scaffold_markdown", "path": workflow_outputs["rebuttal_scaffold_markdown"]}
        )
    if workflow_outputs.get("vault_note"):
        artifacts.append({"label": "rebuttal_scaffold_note", "path": workflow_outputs["vault_note"]})
    set_stage_state(
        manifest,
        "rebuttal_scaffold",
        "completed",
        "Reviewer-response scaffold generated from grounded review artifacts.",
        artifacts,
    )
    append_recent_run(manifest, "rebuttal_scaffold", "Prepared reviewer-response scaffold.")
    note_path = refresh_progress_note(config, loop_cfg, manifest)
    save_manifest(session_dir, manifest)

    outputs = {
        "manifest": to_portable_path(session_dir / "manifest.json"),
        "rebuttal_scaffold_outputs": workflow_outputs,
    }
    if note_path:
        outputs["progress_note"] = to_portable_path(note_path)
    print(json.dumps(outputs, ensure_ascii=False, indent=2))


def run_journal_targeting(args):
    manifest, manifest_path = load_manifest(args.manifest)
    config = load_json(Path(manifest["config_path"]))
    loop_cfg = resolve_loop_config(config)
    session_dir = manifest_path.parent

    workflow_args = ["--config", manifest["config_path"]]
    draft_builder_json = args.draft_builder_json or artifact_path_for_label(
        manifest, "draft_builder", "draft_builder_json"
    )
    self_review_json = args.self_review_json or artifact_path_for_label(manifest, "self_review", "self_review_json")
    rebuttal_scaffold_json = args.rebuttal_scaffold_json or artifact_path_for_label(
        manifest, "rebuttal_scaffold", "rebuttal_scaffold_json"
    )
    if args.journal_name:
        workflow_args.extend(["--journal-name", args.journal_name])
    if args.journal_notes_file:
        workflow_args.extend(["--journal-notes-file", args.journal_notes_file])
    if draft_builder_json:
        workflow_args.extend(["--draft-builder-json", draft_builder_json])
    if self_review_json:
        workflow_args.extend(["--self-review-json", self_review_json])
    if rebuttal_scaffold_json:
        workflow_args.extend(["--rebuttal-scaffold-json", rebuttal_scaffold_json])
    if args.draft_file:
        workflow_args.extend(["--draft-file", args.draft_file])
    if args.title:
        workflow_args.extend(["--title", args.title])
    if args.write_vault_note:
        workflow_args.append("--write-vault-note")

    workflow_stdout = run_python_script(JOURNAL_TARGETING_WORKFLOW_SCRIPT, *workflow_args)
    workflow_outputs = json.loads(workflow_stdout)

    artifacts = []
    if workflow_outputs.get("journal_targeting_json"):
        artifacts.append({"label": "journal_targeting_json", "path": workflow_outputs["journal_targeting_json"]})
    if workflow_outputs.get("journal_targeting_markdown"):
        artifacts.append(
            {"label": "journal_targeting_markdown", "path": workflow_outputs["journal_targeting_markdown"]}
        )
    if workflow_outputs.get("vault_note"):
        artifacts.append({"label": "journal_targeting_note", "path": workflow_outputs["vault_note"]})
    set_stage_state(
        manifest,
        "journal_targeting",
        "completed",
        "Journal-fit adaptation rules and submission checklist generated.",
        artifacts,
    )
    append_recent_run(manifest, "journal_targeting", "Updated target-journal adaptation rules.")
    note_path = refresh_progress_note(config, loop_cfg, manifest)
    save_manifest(session_dir, manifest)

    outputs = {
        "manifest": to_portable_path(session_dir / "manifest.json"),
        "journal_targeting_outputs": workflow_outputs,
    }
    if note_path:
        outputs["progress_note"] = to_portable_path(note_path)
    print(json.dumps(outputs, ensure_ascii=False, indent=2))


def run_response_letter(args):
    manifest, manifest_path = load_manifest(args.manifest)
    config = load_json(Path(manifest["config_path"]))
    loop_cfg = resolve_loop_config(config)
    session_dir = manifest_path.parent

    workflow_args = ["--config", manifest["config_path"]]
    rebuttal_scaffold_json = args.rebuttal_scaffold_json or artifact_path_for_label(
        manifest, "rebuttal_scaffold", "rebuttal_scaffold_json"
    )
    journal_targeting_json = args.journal_targeting_json or artifact_path_for_label(
        manifest, "journal_targeting", "journal_targeting_json"
    )
    draft_builder_json = args.draft_builder_json or artifact_path_for_label(
        manifest, "draft_builder", "draft_builder_json"
    )
    if args.round_label:
        workflow_args.extend(["--round-label", args.round_label])
    if args.review_comments_file:
        workflow_args.extend(["--review-comments-file", args.review_comments_file])
    if args.current_changes_file:
        workflow_args.extend(["--current-changes-file", args.current_changes_file])
    if rebuttal_scaffold_json:
        workflow_args.extend(["--rebuttal-scaffold-json", rebuttal_scaffold_json])
    if journal_targeting_json:
        workflow_args.extend(["--journal-targeting-json", journal_targeting_json])
    if draft_builder_json:
        workflow_args.extend(["--draft-builder-json", draft_builder_json])
    if args.draft_file:
        workflow_args.extend(["--draft-file", args.draft_file])
    if args.tracker_dir:
        workflow_args.extend(["--tracker-dir", args.tracker_dir])
    if args.title:
        workflow_args.extend(["--title", args.title])
    if args.write_vault_note:
        workflow_args.append("--write-vault-note")

    workflow_stdout = run_python_script(RESPONSE_LETTER_WORKFLOW_SCRIPT, *workflow_args)
    workflow_outputs = json.loads(workflow_stdout)

    artifacts = []
    if workflow_outputs.get("response_letter_json"):
        artifacts.append({"label": "response_letter_json", "path": workflow_outputs["response_letter_json"]})
    if workflow_outputs.get("response_letter_markdown"):
        artifacts.append(
            {"label": "response_letter_markdown", "path": workflow_outputs["response_letter_markdown"]}
        )
    if workflow_outputs.get("tracker_index_json"):
        artifacts.append({"label": "response_tracker_json", "path": workflow_outputs["tracker_index_json"]})
    if workflow_outputs.get("tracker_markdown"):
        artifacts.append({"label": "response_tracker_markdown", "path": workflow_outputs["tracker_markdown"]})
    if workflow_outputs.get("vault_note"):
        artifacts.append({"label": "response_letter_note", "path": workflow_outputs["vault_note"]})
    set_stage_state(
        manifest,
        "response_letter",
        "completed",
        "Versioned response-letter package generated and tracked.",
        artifacts,
    )
    append_recent_run(
        manifest,
        "response_letter",
        f"Updated response-letter package for {args.round_label or 'round-1'}.",
    )
    note_path = refresh_progress_note(config, loop_cfg, manifest)
    save_manifest(session_dir, manifest)

    outputs = {
        "manifest": to_portable_path(session_dir / "manifest.json"),
        "response_letter_outputs": workflow_outputs,
    }
    if note_path:
        outputs["progress_note"] = to_portable_path(note_path)
    print(json.dumps(outputs, ensure_ascii=False, indent=2))


def run_citation_audit(args):
    manifest, manifest_path = load_manifest(args.manifest)
    config = load_json(Path(manifest["config_path"]))
    loop_cfg = resolve_loop_config(config)
    session_dir = manifest_path.parent

    workflow_args = ["--config", manifest["config_path"]]
    journal_targeting_json = args.journal_targeting_json or artifact_path_for_label(
        manifest, "journal_targeting", "journal_targeting_json"
    )
    response_letter_json = args.response_letter_json or artifact_path_for_label(
        manifest, "response_letter", "response_letter_json"
    )
    if args.draft_file:
        workflow_args.extend(["--draft-file", args.draft_file])
    if journal_targeting_json:
        workflow_args.extend(["--journal-targeting-json", journal_targeting_json])
    if response_letter_json:
        workflow_args.extend(["--response-letter-json", response_letter_json])
    if args.references_file:
        workflow_args.extend(["--references-file", args.references_file])
    if args.title:
        workflow_args.extend(["--title", args.title])
    if args.write_vault_note:
        workflow_args.append("--write-vault-note")

    workflow_stdout = run_python_script(CITATION_AUDIT_WORKFLOW_SCRIPT, *workflow_args)
    workflow_outputs = json.loads(workflow_stdout)

    artifacts = []
    if workflow_outputs.get("citation_audit_json"):
        artifacts.append({"label": "citation_audit_json", "path": workflow_outputs["citation_audit_json"]})
    if workflow_outputs.get("citation_audit_markdown"):
        artifacts.append({"label": "citation_audit_markdown", "path": workflow_outputs["citation_audit_markdown"]})
    if workflow_outputs.get("vault_note"):
        artifacts.append({"label": "citation_audit_note", "path": workflow_outputs["vault_note"]})
    set_stage_state(
        manifest,
        "citation_audit",
        "completed",
        "Citation and evidence-linking audit generated for the current draft package.",
        artifacts,
    )
    append_recent_run(manifest, "citation_audit", "Updated citation-risk audit.")
    note_path = refresh_progress_note(config, loop_cfg, manifest)
    save_manifest(session_dir, manifest)

    outputs = {
        "manifest": to_portable_path(session_dir / "manifest.json"),
        "citation_audit_outputs": workflow_outputs,
    }
    if note_path:
        outputs["progress_note"] = to_portable_path(note_path)
    print(json.dumps(outputs, ensure_ascii=False, indent=2))


def run_submission_qc(args):
    manifest, manifest_path = load_manifest(args.manifest)
    config = load_json(Path(manifest["config_path"]))
    loop_cfg = resolve_loop_config(config)
    session_dir = manifest_path.parent

    workflow_args = ["--config", manifest["config_path"]]
    citation_audit_json = args.citation_audit_json or artifact_path_for_label(
        manifest, "citation_audit", "citation_audit_json"
    )
    journal_targeting_json = args.journal_targeting_json or artifact_path_for_label(
        manifest, "journal_targeting", "journal_targeting_json"
    )
    response_letter_json = args.response_letter_json or artifact_path_for_label(
        manifest, "response_letter", "response_letter_json"
    )
    if args.draft_file:
        workflow_args.extend(["--draft-file", args.draft_file])
    if citation_audit_json:
        workflow_args.extend(["--citation-audit-json", citation_audit_json])
    if journal_targeting_json:
        workflow_args.extend(["--journal-targeting-json", journal_targeting_json])
    if response_letter_json:
        workflow_args.extend(["--response-letter-json", response_letter_json])
    if args.title:
        workflow_args.extend(["--title", args.title])
    if args.write_vault_note:
        workflow_args.append("--write-vault-note")

    workflow_stdout = run_python_script(SUBMISSION_QC_WORKFLOW_SCRIPT, *workflow_args)
    workflow_outputs = json.loads(workflow_stdout)

    artifacts = []
    if workflow_outputs.get("submission_qc_json"):
        artifacts.append({"label": "submission_qc_json", "path": workflow_outputs["submission_qc_json"]})
    if workflow_outputs.get("submission_qc_markdown"):
        artifacts.append({"label": "submission_qc_markdown", "path": workflow_outputs["submission_qc_markdown"]})
    if workflow_outputs.get("vault_note"):
        artifacts.append({"label": "submission_qc_note", "path": workflow_outputs["vault_note"]})
    set_stage_state(
        manifest,
        "submission_qc",
        "completed",
        "Final polish and pre-submission QC package generated.",
        artifacts,
    )
    append_recent_run(manifest, "submission_qc", "Updated final go/no-go submission check.")
    note_path = refresh_progress_note(config, loop_cfg, manifest)
    save_manifest(session_dir, manifest)

    outputs = {
        "manifest": to_portable_path(session_dir / "manifest.json"),
        "submission_qc_outputs": workflow_outputs,
    }
    if note_path:
        outputs["progress_note"] = to_portable_path(note_path)
    print(json.dumps(outputs, ensure_ascii=False, indent=2))


def run_draft_health(args):
    manifest, manifest_path = load_manifest(args.manifest)
    config = load_json(Path(manifest["config_path"]))
    loop_cfg = resolve_loop_config(config)
    session_dir = manifest_path.parent

    workflow_args = ["--config", manifest["config_path"]]
    citation_audit_json = args.citation_audit_json or artifact_path_for_label(
        manifest, "citation_audit", "citation_audit_json"
    )
    submission_qc_json = args.submission_qc_json or artifact_path_for_label(
        manifest, "submission_qc", "submission_qc_json"
    )
    journal_targeting_json = args.journal_targeting_json or artifact_path_for_label(
        manifest, "journal_targeting", "journal_targeting_json"
    )
    response_letter_json = args.response_letter_json or artifact_path_for_label(
        manifest, "response_letter", "response_letter_json"
    )
    if args.draft_file:
        workflow_args.extend(["--draft-file", args.draft_file])
    if citation_audit_json:
        workflow_args.extend(["--citation-audit-json", citation_audit_json])
    if submission_qc_json:
        workflow_args.extend(["--submission-qc-json", submission_qc_json])
    if journal_targeting_json:
        workflow_args.extend(["--journal-targeting-json", journal_targeting_json])
    if response_letter_json:
        workflow_args.extend(["--response-letter-json", response_letter_json])
    if args.title:
        workflow_args.extend(["--title", args.title])
    if args.write_vault_note:
        workflow_args.append("--write-vault-note")

    workflow_stdout = run_python_script(DRAFT_HEALTH_WORKFLOW_SCRIPT, *workflow_args)
    workflow_outputs = json.loads(workflow_stdout)

    artifacts = []
    if workflow_outputs.get("draft_health_json"):
        artifacts.append({"label": "draft_health_json", "path": workflow_outputs["draft_health_json"]})
    if workflow_outputs.get("draft_health_markdown"):
        artifacts.append({"label": "draft_health_markdown", "path": workflow_outputs["draft_health_markdown"]})
    if workflow_outputs.get("vault_note"):
        artifacts.append({"label": "draft_health_note", "path": workflow_outputs["vault_note"]})
    set_stage_state(
        manifest,
        "draft_health",
        "completed",
        "Recurring draft health check generated from the latest submission artifacts.",
        artifacts,
    )
    append_recent_run(manifest, "draft_health", "Updated recurring draft health snapshot.")
    note_path = refresh_progress_note(config, loop_cfg, manifest)
    save_manifest(session_dir, manifest)

    outputs = {
        "manifest": to_portable_path(session_dir / "manifest.json"),
        "draft_health_outputs": workflow_outputs,
    }
    if note_path:
        outputs["progress_note"] = to_portable_path(note_path)
    print(json.dumps(outputs, ensure_ascii=False, indent=2))


def run_submission_memory(args):
    manifest, manifest_path = load_manifest(args.manifest)
    config = load_json(Path(manifest["config_path"]))
    loop_cfg = resolve_loop_config(config)
    session_dir = manifest_path.parent

    workflow_args = ["--config", manifest["config_path"]]
    draft_health_json = args.draft_health_json or artifact_path_for_label(manifest, "draft_health", "draft_health_json")
    submission_qc_json = args.submission_qc_json or artifact_path_for_label(
        manifest, "submission_qc", "submission_qc_json"
    )
    citation_audit_json = args.citation_audit_json or artifact_path_for_label(
        manifest, "citation_audit", "citation_audit_json"
    )
    response_letter_json = args.response_letter_json or artifact_path_for_label(
        manifest, "response_letter", "response_letter_json"
    )
    journal_targeting_json = args.journal_targeting_json or artifact_path_for_label(
        manifest, "journal_targeting", "journal_targeting_json"
    )
    if args.venue_name:
        workflow_args.extend(["--venue-name", args.venue_name])
    if args.round_label:
        workflow_args.extend(["--round-label", args.round_label])
    if draft_health_json:
        workflow_args.extend(["--draft-health-json", draft_health_json])
    if submission_qc_json:
        workflow_args.extend(["--submission-qc-json", submission_qc_json])
    if citation_audit_json:
        workflow_args.extend(["--citation-audit-json", citation_audit_json])
    if response_letter_json:
        workflow_args.extend(["--response-letter-json", response_letter_json])
    if journal_targeting_json:
        workflow_args.extend(["--journal-targeting-json", journal_targeting_json])
    if args.draft_file:
        workflow_args.extend(["--draft-file", args.draft_file])
    if args.title:
        workflow_args.extend(["--title", args.title])

    workflow_stdout = run_python_script(SUBMISSION_MEMORY_WORKFLOW_SCRIPT, *workflow_args)
    workflow_outputs = json.loads(workflow_stdout)

    artifacts = []
    if workflow_outputs.get("submission_memory_json"):
        artifacts.append({"label": "submission_memory_json", "path": workflow_outputs["submission_memory_json"]})
    if workflow_outputs.get("submission_memory_note"):
        artifacts.append({"label": "submission_memory_note", "path": workflow_outputs["submission_memory_note"]})
    if workflow_outputs.get("submission_memory_registry"):
        artifacts.append(
            {"label": "submission_memory_registry", "path": workflow_outputs["submission_memory_registry"]}
        )
    set_stage_state(
        manifest,
        "submission_memory",
        "completed",
        "Durable submission memory updated for the current venue and revision round.",
        artifacts,
    )
    append_recent_run(
        manifest,
        "submission_memory",
        f"Updated submission memory for {args.venue_name or 'unspecified venue'} {args.round_label or 'round-1'}.",
    )
    note_path = refresh_progress_note(config, loop_cfg, manifest)
    save_manifest(session_dir, manifest)

    outputs = {
        "manifest": to_portable_path(session_dir / "manifest.json"),
        "submission_memory_outputs": workflow_outputs,
    }
    if note_path:
        outputs["progress_note"] = to_portable_path(note_path)
    print(json.dumps(outputs, ensure_ascii=False, indent=2))


def step_title(prefix: str | None, default_title: str):
    if prefix and prefix.strip():
        return f"{prefix.strip()} - {default_title}"
    return default_title


def run_paper_finishing(args):
    manifest, manifest_path = load_manifest(args.manifest)
    draft_file = args.draft_file
    if not draft_file:
        raise ValueError("run-paper-finishing requires --draft-file so the late-stage writing chain can run.")

    write_flag = ["--write-vault-note"] if args.write_vault_notes else []
    bundle_outputs = {}

    writing_args = [
        "run-writing-memory",
        "--manifest",
        str(manifest_path),
        "--title",
        step_title(args.title_prefix, "Writing Memory"),
        *write_flag,
    ]
    bundle_outputs["writing_memory"] = json.loads(run_loop_subcommand(*writing_args))

    review_args = [
        "run-self-review",
        "--manifest",
        str(manifest_path),
        "--draft-file",
        draft_file,
        "--title",
        step_title(args.title_prefix, "Self Review"),
        *write_flag,
    ]
    bundle_outputs["self_review"] = json.loads(run_loop_subcommand(*review_args))

    draft_builder_args = [
        "run-draft-builder",
        "--manifest",
        str(manifest_path),
        "--title",
        step_title(args.title_prefix, "Draft Builder"),
        *write_flag,
    ]
    if args.outline_file:
        draft_builder_args.extend(["--outline-file", args.outline_file])
    bundle_outputs["draft_builder"] = json.loads(run_loop_subcommand(*draft_builder_args))

    rebuttal_args = [
        "run-rebuttal-scaffold",
        "--manifest",
        str(manifest_path),
        "--draft-file",
        draft_file,
        "--title",
        step_title(args.title_prefix, "Rebuttal Scaffold"),
        *write_flag,
    ]
    bundle_outputs["rebuttal_scaffold"] = json.loads(run_loop_subcommand(*rebuttal_args))

    journal_args = [
        "run-journal-targeting",
        "--manifest",
        str(manifest_path),
        "--draft-file",
        draft_file,
        "--title",
        step_title(args.title_prefix, "Journal Targeting"),
        *write_flag,
    ]
    if args.journal_name:
        journal_args.extend(["--journal-name", args.journal_name])
    if args.journal_notes_file:
        journal_args.extend(["--journal-notes-file", args.journal_notes_file])
    bundle_outputs["journal_targeting"] = json.loads(run_loop_subcommand(*journal_args))

    response_args = [
        "run-response-letter",
        "--manifest",
        str(manifest_path),
        "--round-label",
        args.round_label or "round-1",
        "--draft-file",
        draft_file,
        "--title",
        step_title(args.title_prefix, "Response Letter"),
        *write_flag,
    ]
    if args.review_comments_file:
        response_args.extend(["--review-comments-file", args.review_comments_file])
    if args.current_changes_file:
        response_args.extend(["--current-changes-file", args.current_changes_file])
    bundle_outputs["response_letter"] = json.loads(run_loop_subcommand(*response_args))

    citation_args = [
        "run-citation-audit",
        "--manifest",
        str(manifest_path),
        "--draft-file",
        draft_file,
        "--title",
        step_title(args.title_prefix, "Citation Audit"),
        *write_flag,
    ]
    if args.references_file:
        citation_args.extend(["--references-file", args.references_file])
    bundle_outputs["citation_audit"] = json.loads(run_loop_subcommand(*citation_args))

    qc_args = [
        "run-submission-qc",
        "--manifest",
        str(manifest_path),
        "--draft-file",
        draft_file,
        "--title",
        step_title(args.title_prefix, "Submission QC"),
        *write_flag,
    ]
    bundle_outputs["submission_qc"] = json.loads(run_loop_subcommand(*qc_args))

    health_args = [
        "run-draft-health",
        "--manifest",
        str(manifest_path),
        "--draft-file",
        draft_file,
        "--title",
        step_title(args.title_prefix, "Draft Health"),
        *write_flag,
    ]
    bundle_outputs["draft_health"] = json.loads(run_loop_subcommand(*health_args))

    memory_args = [
        "run-submission-memory",
        "--manifest",
        str(manifest_path),
        "--round-label",
        args.round_label or "round-1",
        "--draft-file",
        draft_file,
        "--title",
        step_title(args.title_prefix, "Submission Memory"),
    ]
    venue_name = args.venue_name or args.journal_name
    if venue_name:
        memory_args.extend(["--venue-name", venue_name])
    bundle_outputs["submission_memory"] = json.loads(run_loop_subcommand(*memory_args))

    refreshed_manifest, refreshed_manifest_path = load_manifest(str(manifest_path))
    outputs = {
        "manifest": to_portable_path(refreshed_manifest_path),
        "bundle_outputs": bundle_outputs,
        "completed_stages": [
            stage for stage in STAGE_ORDER if refreshed_manifest["stages"][stage].get("status") == "completed"
        ],
    }
    print(json.dumps(outputs, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Maintain a manifest-driven continuous OCT research loop.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Create a new continuous research session.")
    init_parser.add_argument("--config", required=True)
    init_parser.add_argument("--title", required=True)
    init_parser.add_argument("--objective")
    init_parser.add_argument("--output-dir")
    init_parser.set_defaults(func=run_init)

    status_parser = subparsers.add_parser("status", help="Show the current manifest state.")
    status_parser.add_argument("--manifest", required=True)
    status_parser.set_defaults(func=run_status)

    daily_parser = subparsers.add_parser("run-daily", help="Run the daily research cycle and attach it to the manifest.")
    daily_parser.add_argument("--manifest", required=True)
    daily_parser.add_argument("--skip-retrieval", action="store_true")
    daily_parser.add_argument("--skip-question-radar", action="store_true")
    daily_parser.add_argument("--skip-digest", action="store_true")
    daily_parser.add_argument("--latest-literature-file")
    daily_parser.set_defaults(func=run_daily)

    link_parser = subparsers.add_parser("link-artifact", help="Attach a manual or external artifact to a stage.")
    link_parser.add_argument("--manifest", required=True)
    link_parser.add_argument("--stage", required=True)
    link_parser.add_argument("--path", required=True)
    link_parser.add_argument("--label")
    link_parser.add_argument("--summary")
    link_parser.add_argument("--status", default="completed")
    link_parser.set_defaults(func=run_link_artifact)

    analysis_parser = subparsers.add_parser(
        "run-results-analysis",
        help="Generate strict analysis and a decision report from experiment artifacts, then attach them to the manifest.",
    )
    analysis_parser.add_argument("--manifest", required=True)
    analysis_parser.add_argument("--experiment-dir", required=True)
    analysis_parser.add_argument("--title")
    analysis_parser.add_argument("--write-progress-note", action="store_true")
    analysis_parser.set_defaults(func=run_results_analysis)

    writing_parser = subparsers.add_parser(
        "run-writing-memory",
        help="Extract reusable writing memory from the latest grounded analysis artifacts.",
    )
    writing_parser.add_argument("--manifest", required=True)
    writing_parser.add_argument("--analysis-json")
    writing_parser.add_argument("--results-report-json")
    writing_parser.add_argument("--title")
    writing_parser.add_argument("--write-vault-note", action="store_true")
    writing_parser.set_defaults(func=run_writing_memory)

    review_parser = subparsers.add_parser(
        "run-self-review",
        help="Run an evidence-constrained self review on a draft using the latest manifest artifacts.",
    )
    review_parser.add_argument("--manifest", required=True)
    review_parser.add_argument("--draft-file", required=True)
    review_parser.add_argument("--analysis-json")
    review_parser.add_argument("--results-report-json")
    review_parser.add_argument("--writing-memory-json")
    review_parser.add_argument("--title")
    review_parser.add_argument("--write-vault-note", action="store_true")
    review_parser.set_defaults(func=run_self_review)

    draft_parser = subparsers.add_parser(
        "run-draft-builder",
        help="Build section-aware manuscript blocks from grounded results, writing memory, and self-review outputs.",
    )
    draft_parser.add_argument("--manifest", required=True)
    draft_parser.add_argument("--analysis-json")
    draft_parser.add_argument("--results-report-json")
    draft_parser.add_argument("--writing-memory-json")
    draft_parser.add_argument("--self-review-json")
    draft_parser.add_argument("--outline-file")
    draft_parser.add_argument("--title")
    draft_parser.add_argument("--write-vault-note", action="store_true")
    draft_parser.set_defaults(func=run_draft_builder)

    rebuttal_parser = subparsers.add_parser(
        "run-rebuttal-scaffold",
        help="Build a reviewer-response scaffold from self-review and grounded report artifacts.",
    )
    rebuttal_parser.add_argument("--manifest", required=True)
    rebuttal_parser.add_argument("--self-review-json")
    rebuttal_parser.add_argument("--writing-memory-json")
    rebuttal_parser.add_argument("--results-report-json")
    rebuttal_parser.add_argument("--draft-file")
    rebuttal_parser.add_argument("--title")
    rebuttal_parser.add_argument("--write-vault-note", action="store_true")
    rebuttal_parser.set_defaults(func=run_rebuttal_scaffold)

    journal_parser = subparsers.add_parser(
        "run-journal-targeting",
        help="Adapt grounded manuscript artifacts toward a target journal or submission venue.",
    )
    journal_parser.add_argument("--manifest", required=True)
    journal_parser.add_argument("--journal-name")
    journal_parser.add_argument("--journal-notes-file")
    journal_parser.add_argument("--draft-builder-json")
    journal_parser.add_argument("--self-review-json")
    journal_parser.add_argument("--rebuttal-scaffold-json")
    journal_parser.add_argument("--draft-file")
    journal_parser.add_argument("--title")
    journal_parser.add_argument("--write-vault-note", action="store_true")
    journal_parser.set_defaults(func=run_journal_targeting)

    response_parser = subparsers.add_parser(
        "run-response-letter",
        help="Build a versioned response-letter package from grounded revision artifacts.",
    )
    response_parser.add_argument("--manifest", required=True)
    response_parser.add_argument("--round-label", default="round-1")
    response_parser.add_argument("--review-comments-file")
    response_parser.add_argument("--current-changes-file")
    response_parser.add_argument("--rebuttal-scaffold-json")
    response_parser.add_argument("--journal-targeting-json")
    response_parser.add_argument("--draft-builder-json")
    response_parser.add_argument("--draft-file")
    response_parser.add_argument("--tracker-dir")
    response_parser.add_argument("--title")
    response_parser.add_argument("--write-vault-note", action="store_true")
    response_parser.set_defaults(func=run_response_letter)

    citation_parser = subparsers.add_parser(
        "run-citation-audit",
        help="Audit the current draft package for citation and evidence-linking risk.",
    )
    citation_parser.add_argument("--manifest", required=True)
    citation_parser.add_argument("--draft-file")
    citation_parser.add_argument("--journal-targeting-json")
    citation_parser.add_argument("--response-letter-json")
    citation_parser.add_argument("--references-file")
    citation_parser.add_argument("--title")
    citation_parser.add_argument("--write-vault-note", action="store_true")
    citation_parser.set_defaults(func=run_citation_audit)

    qc_parser = subparsers.add_parser(
        "run-submission-qc",
        help="Run final polish and pre-submission QC on the current manuscript package.",
    )
    qc_parser.add_argument("--manifest", required=True)
    qc_parser.add_argument("--draft-file")
    qc_parser.add_argument("--citation-audit-json")
    qc_parser.add_argument("--journal-targeting-json")
    qc_parser.add_argument("--response-letter-json")
    qc_parser.add_argument("--title")
    qc_parser.add_argument("--write-vault-note", action="store_true")
    qc_parser.set_defaults(func=run_submission_qc)

    health_parser = subparsers.add_parser(
        "run-draft-health",
        help="Run a recurring health check on the current draft and latest submission artifacts.",
    )
    health_parser.add_argument("--manifest", required=True)
    health_parser.add_argument("--draft-file")
    health_parser.add_argument("--citation-audit-json")
    health_parser.add_argument("--submission-qc-json")
    health_parser.add_argument("--journal-targeting-json")
    health_parser.add_argument("--response-letter-json")
    health_parser.add_argument("--title")
    health_parser.add_argument("--write-vault-note", action="store_true")
    health_parser.set_defaults(func=run_draft_health)

    memory_parser = subparsers.add_parser(
        "run-submission-memory",
        help="Write durable submission memory by venue and revision round.",
    )
    memory_parser.add_argument("--manifest", required=True)
    memory_parser.add_argument("--venue-name")
    memory_parser.add_argument("--round-label", default="round-1")
    memory_parser.add_argument("--draft-health-json")
    memory_parser.add_argument("--submission-qc-json")
    memory_parser.add_argument("--citation-audit-json")
    memory_parser.add_argument("--response-letter-json")
    memory_parser.add_argument("--journal-targeting-json")
    memory_parser.add_argument("--draft-file")
    memory_parser.add_argument("--title")
    memory_parser.set_defaults(func=run_submission_memory)

    paper_parser = subparsers.add_parser(
        "run-paper-finishing",
        help="Run the late-stage paper-finishing chain from writing memory through submission memory in one command.",
    )
    paper_parser.add_argument("--manifest", required=True)
    paper_parser.add_argument("--draft-file", required=True)
    paper_parser.add_argument("--outline-file")
    paper_parser.add_argument("--journal-name")
    paper_parser.add_argument("--journal-notes-file")
    paper_parser.add_argument("--review-comments-file")
    paper_parser.add_argument("--current-changes-file")
    paper_parser.add_argument("--references-file")
    paper_parser.add_argument("--venue-name")
    paper_parser.add_argument("--round-label", default="round-1")
    paper_parser.add_argument("--title-prefix")
    paper_parser.add_argument("--write-vault-notes", action="store_true")
    paper_parser.set_defaults(func=run_paper_finishing)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
