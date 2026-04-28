#!/usr/bin/env python
import argparse
import json
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from pathlib import Path

from research_question_flow import (
    DEFAULT_QUESTION_FOLDER,
    append_text,
    attach_auto_evidence,
    build_request_payload,
    ensure_daily_note,
    extract_response_text,
    load_json,
    normalize_space,
    post_openai_json,
    read_text,
    resolve_qa_config,
    safe_filename_component,
    slugify,
    strip_frontmatter,
    timestamp_slug,
    to_portable_path,
    update_index,
    write_json,
    write_text,
)


OPENALEX_URL = "https://api.openalex.org/works"
ARXIV_URL = "http://export.arxiv.org/api/query"
DEFAULT_REPORT_FOLDER_NAME = "question-radar"
DEFAULT_DAILY_SECTION_TITLE = "Question Radar"
LOCAL_FALLBACK_MODEL = "codex-local-fallback"
DEFAULT_RECENT_NOTE_PATHS = [
    "02_Papers",
    "02_Literature/Papers",
    "03_Concepts",
    "04_Progress",
    "05_Experiments",
    "06_Writing",
    "09_Conversations",
    "10_Tasks",
    "11_Retrieval",
]
TIME_HORIZONS = {"immediate", "near_term", "strategic"}
QUESTION_RADAR_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "focus_summary": {"type": "string"},
        "candidate_questions": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "title": {"type": "string"},
                    "question": {"type": "string"},
                    "value_score": {"type": "integer", "minimum": 1, "maximum": 10},
                    "time_horizon": {"type": "string"},
                    "why_now": {"type": "string"},
                    "novelty_or_gap": {"type": "string"},
                    "required_evidence": {"type": "array", "items": {"type": "string"}},
                    "first_action": {"type": "string"},
                    "source_signals": {"type": "array", "items": {"type": "string"}},
                },
                "required": [
                    "title",
                    "question",
                    "value_score",
                    "time_horizon",
                    "why_now",
                    "novelty_or_gap",
                    "required_evidence",
                    "first_action",
                    "source_signals",
                ],
            },
        },
        "selection_advice": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["focus_summary", "candidate_questions", "selection_advice"],
}
BASE_DISCOVERY_RULES = [
    "You are mining high-value academic questions for an OCT research project.",
    "Do not answer the questions.",
    "Prefer concrete, falsifiable, research-usable questions over broad themes.",
    "A high-value question should change experimental design, evaluation burden, literature positioning, or manuscript claims.",
    "If the context is weak, say what evidence is missing instead of pretending novelty.",
    "Keep the output concise, specific, and aligned to the project's current scope.",
    "Use the same primary language as the provided context unless a technical term is better left in English.",
]
MODE_RULES = {
    "conversation": [
        "Mine questions implied by the conversation, including unresolved tensions, hidden assumptions, and promising follow-ups.",
        "Prioritize questions the user did not fully articulate but that could materially improve the research program.",
    ],
    "manual": [
        "Treat the seed text as an explicit request for candidate academic questions.",
        "Generate questions that are scoped tightly enough to be acted on in the current project.",
    ],
    "daily": [
        "Synthesize recent vault activity with the latest literature snapshot.",
        "Prefer questions that are both timely and actionable within the current research cycle.",
        "Avoid stale duplicates unless a repeated question remains unresolved and newly urgent.",
    ],
}
LOCAL_FALLBACK_QUESTION_SPECS = [
    {
        "id": "psf_drift_tolerance",
        "title": "Quantify tolerated PSF drift before gains stop transferring",
        "question": "What PSF drift or mismatch range can the current deconvolution pipeline tolerate before apparent lateral gains stop transferring across scans, field positions, or repeat sessions?",
        "value_score": 9,
        "time_horizon": "immediate",
        "why_now": "The project still needs one boundary-setting result that distinguishes stable recovery from calibration luck.",
        "novelty_or_gap": "Current notes warn about PSF mismatch and drift, but they do not yet define a measured tolerance band.",
        "required_evidence": [
            "Repeat PSF measurements across sessions or field positions",
            "A wrong-PSF or drift-versus-gain collapse curve",
            "Matched metrics for gain, background growth, and repeatability",
        ],
        "first_action": "Freeze one phantom or bead dataset and measure where gain collapses as the PSF assumption drifts away from the calibrated baseline.",
        "keywords": ["psf", "drift", "mismatch", "calibration", "kernel", "phantom", "repeatability", "repeat"],
        "focus_theme": "PSF drift tolerance",
    },
    {
        "id": "falsification_control",
        "title": "Make the first falsification experiment decisive",
        "question": "Which negative-control design most quickly falsifies the claim that observed sharpening reflects information recovery rather than artifact amplification?",
        "value_score": 8,
        "time_horizon": "near_term",
        "why_now": "A decisive falsification experiment would reduce validation ambiguity faster than another broad method branch.",
        "novelty_or_gap": "The workspace repeatedly mentions wrong-PSF and artifact controls, but the first decisive control is still not frozen.",
        "required_evidence": [
            "A deliberately mismatched PSF control",
            "Task-based metrics on the same scan pair",
            "A visual and quantitative comparison against the calibrated baseline",
        ],
        "first_action": "Define one wrong-PSF negative control and compare it against the current calibrated pipeline on the same evaluation task.",
        "keywords": ["negative control", "wrong-psf", "artifact", "falsification", "noise", "control", "repeatability"],
        "focus_theme": "falsification controls",
    },
    {
        "id": "manuscript_acceptance_gates",
        "title": "Lock manuscript-safe acceptance gates for lateral-resolution claims",
        "question": "Which explicit acceptance gates should the project lock so that a claimed lateral-resolution gain is manuscript-safe rather than only visually sharper?",
        "value_score": 8,
        "time_horizon": "immediate",
        "why_now": "Claim wording, figure choice, and experiment scope all depend on a stable acceptance board.",
        "novelty_or_gap": "The trust and validation language exists, but it has not yet been converted into pass/fail evidence gates.",
        "required_evidence": [
            "A raw-data integrity checklist for the current reconstruction path",
            "PSF provenance records and frozen solver settings",
            "Matched tables for resolution gain, artifact growth, and repeatability",
        ],
        "first_action": "Rewrite the current validation logic into a one-page acceptance matrix with pass, fail, and inconclusive states.",
        "keywords": ["manuscript", "claim", "validation", "trust", "reproducibility", "evidence", "artifact"],
        "focus_theme": "manuscript-safe validation",
    },
    {
        "id": "paper_spine",
        "title": "Decide which papers actually carry the manuscript argument",
        "question": "Which 6-8 papers must carry the main manuscript argument, and which notes should remain background-only so the evidence chain stays tight?",
        "value_score": 7,
        "time_horizon": "near_term",
        "why_now": "The literature base is growing, but the manuscript still needs a disciplined evidence spine rather than a broad reading list.",
        "novelty_or_gap": "The missing piece is no longer discovery of more papers; it is a claim-to-paper map that keeps the argument narrow and defensible.",
        "required_evidence": [
            "A shortlist of direct OCT anchor papers for the core claim",
            "A separate bucket for system or background references",
            "A section-by-section claim map linking each claim to one or two anchors",
        ],
        "first_action": "Create one manuscript evidence spine note that promotes only the highest-leverage anchors from the current progress and reading pages.",
        "keywords": ["paper", "papers", "literature", "reading", "review", "manuscript", "entry"],
        "focus_theme": "manuscript evidence spine",
    },
    {
        "id": "adaptive_escalation_gate",
        "title": "Define the promotion gate for blind or spatially varying deconvolution",
        "question": "What repeatable failure pattern must survive controls before blind or spatially varying deconvolution is promoted from background reading into the mainline?",
        "value_score": 7,
        "time_horizon": "strategic",
        "why_now": "Harder inverse methods add compute and validation burden, so they should enter only when the fixed-PSF mainline fails for evidence-based reasons.",
        "novelty_or_gap": "The project still lacks a written promotion rule connecting localized fixed-PSF failure to adaptive-method escalation.",
        "required_evidence": [
            "A residual mismatch map after the fixed-PSF baseline is tuned reasonably well",
            "Evidence that the failure persists across repeats and parameter sweeps",
            "A compute and reproducibility estimate for adaptive upgrades",
        ],
        "first_action": "Write one escalation checklist and require the fixed-PSF baseline to fail against it before adding adaptive methods to the mainline.",
        "keywords": ["blind", "spatially varying", "space variant", "adaptive", "deconvolution"],
        "focus_theme": "adaptive-method promotion",
    },
    {
        "id": "transferability_gate",
        "title": "Set the transferability gate for realistic volume data",
        "question": "What conditions must be satisfied before a realistic exported volume or ex vivo dataset becomes scientifically useful rather than just technically loadable?",
        "value_score": 6,
        "time_horizon": "near_term",
        "why_now": "Tool-level data ingress can change which datasets are practical, but it should not dilute the mainline before the scientific gate is explicit.",
        "novelty_or_gap": "The missing piece is a transferability gate that links data access to research-valid evidence instead of file loading alone.",
        "required_evidence": [
            "A statement of what signal level and metadata the imported volume preserves",
            "A compatibility check against the current evaluation pipeline",
            "A stop rule defining when transfer work should wait",
        ],
        "first_action": "Draft a one-page transferability gate before scheduling any real-volume pilot.",
        "keywords": ["transfer", "transferability", "heyex", "volume", "export", "ex vivo", "clinical", "eyepy"],
        "focus_theme": "transferability gating",
    },
    {
        "id": "generic_next_question",
        "title": "What single experiment most reduces uncertainty in the current objective?",
        "question": "Which single experiment or evidence bundle would reduce the largest uncertainty in the current research objective without widening scope prematurely?",
        "value_score": 6,
        "time_horizon": "immediate",
        "why_now": "When model-backed synthesis is unavailable, the most useful fallback is a tightly scoped next-question board rather than a broad theme list.",
        "novelty_or_gap": "The gap is prioritization: the project needs the next most decision-relevant question, not another general summary.",
        "required_evidence": [
            "A short list of current uncertainties",
            "One concrete experiment or note rewrite that would shrink the biggest one",
        ],
        "first_action": "Choose the uncertainty that would most change the next two weeks of work and frame one decisive experiment around it.",
        "keywords": [],
        "focus_theme": "next-step prioritization",
    },
]


def resolve_question_radar_config(config: dict) -> dict:
    qa_runtime = resolve_qa_config(config)
    radar_cfg = config.get("question_radar", {})
    radar_openai = radar_cfg.get("openai", {})
    qa_openai = config.get("academic_qa", {}).get("openai", {})
    retrieval_cfg = config.get("retrieval", {})

    recent_note_paths = radar_cfg.get("recent_note_paths", DEFAULT_RECENT_NOTE_PATHS)
    if not isinstance(recent_note_paths, list):
        recent_note_paths = DEFAULT_RECENT_NOTE_PATHS

    latest_sources = radar_cfg.get("latest_literature_sources", retrieval_cfg.get("sources", ["openalex", "arxiv"]))
    if not isinstance(latest_sources, list):
        latest_sources = retrieval_cfg.get("sources", ["openalex", "arxiv"])

    return {
        "api_key": radar_openai.get("api_key", "").strip() or qa_runtime["api_key"],
        "endpoint": radar_openai.get("base_url", "").strip() or qa_runtime["endpoint"],
        "model": radar_openai.get("model", "").strip()
        or qa_openai.get("discover_model", "").strip()
        or qa_runtime["reason_model"],
        "reasoning_effort": radar_openai.get("reasoning_effort", "").strip()
        or qa_openai.get("discover_reasoning_effort", "").strip()
        or qa_runtime["reason_effort"],
        "max_output_tokens": int(
            radar_openai.get("max_output_tokens", qa_openai.get("discover_max_output_tokens", 6000))
        ),
        "report_folder_name": radar_cfg.get("report_folder_name", DEFAULT_REPORT_FOLDER_NAME).strip()
        or DEFAULT_REPORT_FOLDER_NAME,
        "note_folder": radar_cfg.get("note_folder", "").strip()
        or config.get("academic_qa", {}).get("question_folder", DEFAULT_QUESTION_FOLDER),
        "max_questions": int(radar_cfg.get("max_questions", 5)),
        "lookback_days": int(radar_cfg.get("lookback_days", 1)),
        "recent_note_paths": [str(item) for item in recent_note_paths if str(item).strip()],
        "recent_note_max_files": int(radar_cfg.get("recent_note_max_files", 12)),
        "recent_note_max_chars": int(radar_cfg.get("recent_note_max_chars", 500)),
        "latest_literature_enabled": bool(radar_cfg.get("latest_literature_enabled", True)),
        "latest_literature_sources": [str(item) for item in latest_sources if str(item).strip()],
        "latest_literature_max_per_interest": int(radar_cfg.get("latest_literature_max_per_interest", 4)),
        "latest_literature_since_days": int(
            radar_cfg.get("latest_literature_since_days", retrieval_cfg.get("since_days", 7))
        ),
        "openalex_mailto": radar_cfg.get("openalex_mailto", "").strip()
        or retrieval_cfg.get("openalex_mailto", "").strip(),
        "daily_section_title": radar_cfg.get("daily_section_title", DEFAULT_DAILY_SECTION_TITLE).strip()
        or DEFAULT_DAILY_SECTION_TITLE,
        "write_daily_note": bool(radar_cfg.get("write_daily_note", True)),
        "write_vault_note": bool(radar_cfg.get("write_vault_note", True)),
        "qa_runtime": qa_runtime,
    }


def detect_seed_title(explicit_title: str, seed_text: str, fallback: str) -> str:
    if explicit_title and explicit_title.strip():
        return normalize_space(explicit_title)
    fragments = [segment.strip() for segment in seed_text.splitlines() if segment.strip()]
    if fragments:
        return normalize_space(fragments[0])[:72].rstrip()
    return fallback


def load_seed_text(inline_text: str | None, file_path: str | None, label: str) -> str:
    if inline_text:
        text = inline_text
    elif file_path:
        text = read_text(Path(file_path))
    else:
        text = ""
    cleaned = text.strip()
    if not cleaned:
        raise ValueError(f"A non-empty {label} is required.")
    return cleaned


def build_seed_snapshot(title: str, seed_text: str, evidence_files, evidence_texts):
    evidence_records = []
    for index, text in enumerate(evidence_texts or [], start=1):
        cleaned = text.strip()
        if not cleaned:
            continue
        evidence_records.append(
            {
                "source": f"inline-evidence-{index}",
                "content": cleaned,
                "evidence_role": "manual_input",
                "evidence_role_labels": ["manual_input"],
            }
        )

    for path_str in evidence_files or []:
        path = Path(path_str)
        evidence_records.append(
            {
                "source": path.name,
                "content": read_text(path).strip(),
                "evidence_role": "manual_input",
                "evidence_role_labels": ["manual_input"],
            }
        )

    return {
        "title": title,
        "raw_question": seed_text,
        "manual_evidence": evidence_records,
        "evidence": list(evidence_records),
    }


def create_run_dir(config: dict, runtime_cfg: dict, mode: str, title: str, explicit_dir: str | None) -> Path:
    if explicit_dir:
        run_dir = Path(explicit_dir)
        run_dir.mkdir(parents=True, exist_ok=True)
        return run_dir

    output_root = Path(config["output_root"])
    date_part = date.today().isoformat()
    run_dir = output_root / runtime_cfg["report_folder_name"] / f"{date_part}-{mode}-{slugify(title)}-{timestamp_slug()}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def recent_note_excerpt(note_text: str, max_chars: int) -> str:
    cleaned = normalize_space(strip_frontmatter(note_text))
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[: max_chars - 3].rstrip() + "..."


def collect_recent_note_context(config: dict, runtime_cfg: dict, lookback_days: int):
    vault_root = Path(config["vault_root"])
    cutoff = datetime.now() - timedelta(days=lookback_days)
    sections = []
    seen = set()

    for relative_path in runtime_cfg["recent_note_paths"]:
        root = vault_root / Path(relative_path)
        if not root.exists():
            continue

        note_paths = []
        if root.is_file():
            note_paths = [root]
        else:
            note_paths = [path for path in root.rglob("*.md") if path.name != "_Index.md"]

        entries = []
        for note_path in note_paths:
            key = str(note_path.resolve())
            if key in seen:
                continue
            seen.add(key)
            try:
                modified = datetime.fromtimestamp(note_path.stat().st_mtime)
                if modified < cutoff:
                    continue
                note_text = read_text(note_path)
            except OSError:
                continue

            entries.append(
                {
                    "path": to_portable_path(note_path.relative_to(vault_root)),
                    "updated_at": modified.isoformat(timespec="minutes"),
                    "excerpt": recent_note_excerpt(note_text, runtime_cfg["recent_note_max_chars"]),
                }
            )

        if not entries:
            continue

        entries.sort(key=lambda item: item["updated_at"], reverse=True)
        sections.append(
            {
                "section": relative_path,
                "entries": entries[: runtime_cfg["recent_note_max_files"]],
            }
        )

    return {
        "lookback_days": lookback_days,
        "sections": sections,
    }


def fetch_json(url: str):
    with urllib.request.urlopen(url, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_text(url: str):
    with urllib.request.urlopen(url, timeout=30) as response:
        return response.read().decode("utf-8", errors="replace")


def query_openalex_latest(keyword: str, max_results: int, mailto: str, since_days: int):
    since_date = (date.today() - timedelta(days=max(0, since_days))).isoformat()
    params = {
        "search": keyword,
        "per-page": max_results,
        "sort": "publication_date:desc",
        "filter": f"from_publication_date:{since_date}",
    }
    if mailto:
        params["mailto"] = mailto
    url = OPENALEX_URL + "?" + urllib.parse.urlencode(params)
    data = fetch_json(url)
    entries = []
    for item in data.get("results", []):
        landing = item.get("primary_location", {}).get("landing_page_url", "")
        entries.append(
            {
                "title": item.get("display_name", ""),
                "year": item.get("publication_year", ""),
                "publication_date": item.get("publication_date", ""),
                "url": landing or item.get("id", ""),
                "source": "openalex",
            }
        )
    return entries


def query_arxiv_latest(keyword: str, max_results: int, since_days: int):
    params = {
        "search_query": f'all:"{keyword}"',
        "start": 0,
        "max_results": max_results,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }
    url = ARXIV_URL + "?" + urllib.parse.urlencode(params)
    xml_text = fetch_text(url)
    root = ET.fromstring(xml_text)
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    cutoff = datetime.now() - timedelta(days=max(0, since_days))
    entries = []
    for entry in root.findall("atom:entry", ns):
        published = entry.findtext("atom:published", default="", namespaces=ns) or ""
        published_dt = None
        if published:
            try:
                published_dt = datetime.fromisoformat(published.replace("Z", "+00:00")).replace(tzinfo=None)
            except ValueError:
                published_dt = None
        if published_dt and published_dt < cutoff:
            continue
        entries.append(
            {
                "title": (entry.findtext("atom:title", default="", namespaces=ns) or "").strip(),
                "year": published[:4],
                "publication_date": published[:10],
                "url": entry.findtext("atom:id", default="", namespaces=ns) or "",
                "source": "arxiv",
            }
        )
    return entries


def dedupe_literature_entries(entries, limit: int):
    ordered = []
    seen = set()
    for item in entries:
        key = item.get("url") or item.get("title", "")
        if key in seen:
            continue
        seen.add(key)
        ordered.append(item)
    ordered.sort(key=lambda item: item.get("publication_date", ""), reverse=True)
    return ordered[:limit]


def normalize_latest_literature_payload(payload):
    if isinstance(payload, dict):
        groups = []
        for interest, entries in payload.items():
            if not isinstance(entries, list):
                continue
            groups.append(
                {
                    "interest": interest,
                    "entries": [
                        {
                            "title": str(item.get("title", "")),
                            "year": str(item.get("year", "")),
                            "publication_date": str(item.get("publication_date", "")),
                            "url": str(item.get("url", "")),
                            "source": str(item.get("source", "")),
                        }
                        for item in entries
                        if isinstance(item, dict)
                    ],
                }
            )
        return groups

    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]

    return []


def fetch_latest_literature(config: dict, runtime_cfg: dict, latest_file: str | None, skip_live: bool):
    snapshot = {
        "enabled": runtime_cfg["latest_literature_enabled"] and not skip_live,
        "since_days": runtime_cfg["latest_literature_since_days"],
        "groups": [],
        "errors": [],
    }

    if latest_file:
        try:
            payload = load_json(Path(latest_file))
            snapshot["groups"].extend(normalize_latest_literature_payload(payload))
        except (OSError, json.JSONDecodeError) as exc:
            snapshot["errors"].append(f"latest-file:{exc}")

    if not snapshot["enabled"]:
        return snapshot

    try:
        profile = load_json(Path(config["profile_path"]))
    except OSError as exc:
        snapshot["errors"].append(f"profile:{exc}")
        return snapshot

    for interest in profile.get("interests", []):
        if not isinstance(interest, dict):
            continue
        keywords = [str(item).strip() for item in interest.get("keywords", []) if str(item).strip()]
        if not keywords:
            continue
        query_text = ", ".join(keywords)
        entries = []
        try:
            if "openalex" in runtime_cfg["latest_literature_sources"]:
                entries.extend(
                    query_openalex_latest(
                        query_text,
                        runtime_cfg["latest_literature_max_per_interest"],
                        runtime_cfg["openalex_mailto"],
                        runtime_cfg["latest_literature_since_days"],
                    )
                )
            if "arxiv" in runtime_cfg["latest_literature_sources"]:
                entries.extend(
                    query_arxiv_latest(
                        query_text,
                        runtime_cfg["latest_literature_max_per_interest"],
                        runtime_cfg["latest_literature_since_days"],
                    )
                )
        except (urllib.error.URLError, urllib.error.HTTPError, ET.ParseError, TimeoutError) as exc:
            snapshot["errors"].append(f"{interest.get('name', 'interest')}:{exc}")
            continue

        deduped = dedupe_literature_entries(entries, runtime_cfg["latest_literature_max_per_interest"])
        if not deduped:
            continue
        snapshot["groups"].append(
            {
                "interest": interest.get("name", "interest"),
                "query": query_text,
                "entries": deduped,
            }
        )

    return snapshot


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
        "interests": [
            {
                "name": item.get("name", ""),
                "keywords": item.get("keywords", []),
                "priority": item.get("priority", ""),
            }
            for item in profile.get("interests", [])
            if isinstance(item, dict)
        ],
    }


def normalize_time_horizon(value: str) -> str:
    cleaned = normalize_space(value).lower().replace("-", "_")
    if cleaned in TIME_HORIZONS:
        return cleaned
    return "near_term"


def _fallback_text(value) -> str:
    if isinstance(value, dict):
        return " ".join(_fallback_text(item) for item in value.values())
    if isinstance(value, list):
        return " ".join(_fallback_text(item) for item in value)
    if value is None:
        return ""
    return normalize_space(str(value))


def _fallback_signal_records(mode: str, payload: dict) -> list[dict]:
    records = []
    project_profile = payload.get("project_profile", {}) or {}
    objective = _fallback_text(project_profile.get("primary_objective", ""))
    if objective:
        records.append({"label": f"Project objective: {objective}", "text": objective, "kind": "project"})
    writing_goal = _fallback_text(project_profile.get("writing_goal", ""))
    if writing_goal:
        records.append({"label": f"Writing goal: {writing_goal}", "text": writing_goal, "kind": "project"})
    evaluation_focus = _fallback_text(project_profile.get("evaluation_focus", []))
    if evaluation_focus:
        records.append({"label": f"Evaluation focus: {evaluation_focus}", "text": evaluation_focus, "kind": "project"})

    for item in project_profile.get("interests", []):
        if not isinstance(item, dict):
            continue
        name = _fallback_text(item.get("name", ""))
        if not name:
            continue
        keywords = _fallback_text(item.get("keywords", []))
        records.append({"label": f"Project interest: {name}", "text": f"{name} {keywords}", "kind": "interest"})

    if mode == "daily":
        for section in (payload.get("recent_context", {}) or {}).get("sections", []):
            for entry in section.get("entries", []):
                label = _fallback_text(entry.get("path", ""))
                text = f"{label} {_fallback_text(entry.get('excerpt', ''))}"
                if label or text.strip():
                    records.append({"label": label or section.get("section", "recent-context"), "text": text, "kind": "recent"})
        for group in (payload.get("latest_literature", {}) or {}).get("groups", []):
            interest = _fallback_text(group.get("interest", "literature"))
            for entry in group.get("entries", []):
                title = _fallback_text(entry.get("title", ""))
                pub = _fallback_text(entry.get("publication_date", "") or entry.get("year", ""))
                source = _fallback_text(entry.get("source", ""))
                label = title or interest
                text = normalize_space(f"{interest} {title} {pub} {source}")
                records.append({"label": label, "text": text, "kind": "literature"})
    else:
        title_keys = ["manual_title", "conversation_title"]
        text_keys = ["manual_prompt", "conversation_text"]
        for key in title_keys + text_keys:
            text = _fallback_text(payload.get(key, ""))
            if text:
                records.append({"label": key.replace("_", " "), "text": text, "kind": "seed"})
        for group_name in ["manual_evidence", "auto_evidence"]:
            for item in payload.get(group_name, []):
                if not isinstance(item, dict):
                    continue
                label = _fallback_text(item.get("source", group_name))
                text = _fallback_text(item.get("content", ""))
                if text:
                    records.append({"label": label, "text": text, "kind": "evidence"})
        evidence_brief = _fallback_text(payload.get("evidence_brief", {}))
        if evidence_brief:
            records.append({"label": "evidence brief", "text": evidence_brief, "kind": "evidence"})

    return records


def _fallback_match_score(corpus: str, keywords: list[str]) -> int:
    score = 0
    for keyword in keywords:
        cleaned = normalize_space(keyword).lower()
        if cleaned and cleaned in corpus:
            score += 1
    return score


def _fallback_source_signals(records: list[dict], keywords: list[str], limit: int = 3) -> list[str]:
    matched = []
    seen = set()
    for record in records:
        label = record["label"]
        if not label or label in seen:
            continue
        text = record["text"].lower()
        if any(normalize_space(keyword).lower() in text for keyword in keywords if keyword.strip()):
            matched.append(label)
            seen.add(label)
        if len(matched) >= limit:
            return matched

    for record in records:
        label = record["label"]
        if not label or label in seen:
            continue
        matched.append(label)
        seen.add(label)
        if len(matched) >= limit:
            break
    return matched


def build_local_question_radar(runtime_cfg: dict, mode: str, payload: dict, failure: Exception | None = None) -> tuple[dict, dict]:
    records = _fallback_signal_records(mode, payload)
    corpus = normalize_space(" ".join(record["text"] for record in records)).lower()

    ranked = []
    for spec in LOCAL_FALLBACK_QUESTION_SPECS:
        keywords = spec.get("keywords", [])
        score = spec["value_score"] + _fallback_match_score(corpus, keywords)
        if keywords and score == spec["value_score"]:
            continue
        ranked.append((score, spec))

    if not ranked:
        ranked.append((LOCAL_FALLBACK_QUESTION_SPECS[-1]["value_score"], LOCAL_FALLBACK_QUESTION_SPECS[-1]))

    ranked.sort(key=lambda item: (-item[0], item[1]["title"]))
    selected_specs = []
    seen_ids = set()
    for _, spec in ranked:
        if spec["id"] in seen_ids:
            continue
        seen_ids.add(spec["id"])
        selected_specs.append(spec)
        if len(selected_specs) >= max(1, runtime_cfg["max_questions"]):
            break

    questions = []
    for spec in selected_specs:
        questions.append(
            {
                "title": spec["title"],
                "question": spec["question"],
                "value_score": spec["value_score"],
                "time_horizon": normalize_time_horizon(spec["time_horizon"]),
                "why_now": spec["why_now"],
                "novelty_or_gap": spec["novelty_or_gap"],
                "required_evidence": list(spec["required_evidence"]),
                "first_action": spec["first_action"],
                "source_signals": _fallback_source_signals(records, spec.get("keywords", [])),
            }
        )

    themes = [spec["focus_theme"] for spec in selected_specs[:3]]
    if len(themes) > 1:
        theme_text = ", ".join(themes[:-1]) + f", and {themes[-1]}"
    else:
        theme_text = themes[0]
    focus_summary = (
        "This radar was generated with a local fallback because no usable OpenAI question-mining path was available. "
        f"The strongest current signals cluster around {theme_text}. "
        "The aim is to keep the research cycle actionable with concrete next-question prompts instead of blocking on credentials or transient API failures."
    )

    selection_advice = [
        f"Start with {questions[0]['title'].lower()} because it is the fastest way to reduce decision risk in the current cycle.",
    ]
    if any("blind" in item["title"].lower() or "spatially varying" in item["title"].lower() for item in questions):
        selection_advice.append(
            "Keep adaptive-method escalation behind a written promotion gate so the mainline does not widen before the fixed-PSF baseline is constrained."
        )
    if any("manuscript" in item["title"].lower() for item in questions):
        selection_advice.append(
            "Translate the highest-scoring validation question into a manuscript-safe acceptance board before expanding the reading list or method stack."
        )
    if len(selection_advice) < 3 and len(questions) > 1:
        selection_advice.append(
            f"Pair it with {questions[1]['title'].lower()} so the next experiment and the writing logic stay aligned."
        )

    failure_text = str(failure) if failure else "OpenAI path unavailable."
    response_meta = {
        "generator": LOCAL_FALLBACK_MODEL,
        "reason": "question_radar.py switched to a built-in local fallback",
        "script_failure": failure_text,
        "used_api": False,
    }
    return {
        "focus_summary": focus_summary,
        "candidate_questions": questions,
        "selection_advice": selection_advice[:3],
    }, response_meta


def discover_question_radar(runtime_cfg: dict, mode: str, payload: dict) -> tuple[dict, dict]:
    prompt_payload = {
        "rules": BASE_DISCOVERY_RULES + MODE_RULES[mode],
        "mode": mode,
        "max_questions": runtime_cfg["max_questions"],
        "payload": payload,
    }
    request_payload = build_request_payload(
        runtime_cfg["model"],
        runtime_cfg["reasoning_effort"],
        runtime_cfg["max_output_tokens"],
        "question_radar_report",
        QUESTION_RADAR_SCHEMA,
        json.dumps(prompt_payload, ensure_ascii=False),
    )
    if not runtime_cfg["api_key"]:
        return build_local_question_radar(
            runtime_cfg,
            mode,
            payload,
            ValueError("OpenAI API key is not configured. Set academic_qa.openai.api_key or OPENAI_API_KEY."),
        )
    try:
        response_payload = post_openai_json(runtime_cfg["endpoint"], runtime_cfg["api_key"], request_payload)
        response_text = extract_response_text(response_payload)
        if not response_text:
            raise RuntimeError("Question radar step did not return any text output.")

        radar = json.loads(response_text)
        for item in radar.get("candidate_questions", []):
            item["time_horizon"] = normalize_time_horizon(item.get("time_horizon", "near_term"))
        return radar, response_payload
    except (RuntimeError, ValueError, json.JSONDecodeError) as exc:
        return build_local_question_radar(runtime_cfg, mode, payload, exc)


def render_question_radar_markdown(mode: str, title: str, radar: dict, meta: dict, context: dict) -> str:
    lines = [
        f"# Question Radar - {title}",
        "",
        f"- Mode: {mode}",
        f"- Generated: {meta['generated_at']}",
        f"- Model: {meta['model']}",
        f"- Run directory: `{meta['run_dir']}`",
        "",
        "## Focus Summary",
        "",
        radar["focus_summary"],
        "",
        "## Candidate Questions",
        "",
    ]

    for index, item in enumerate(radar.get("candidate_questions", []), start=1):
        lines.extend(
            [
                f"### {index}. {item['title']}",
                "",
                item["question"],
                "",
                f"- Value score: {item['value_score']}/10",
                f"- Time horizon: {item['time_horizon']}",
                f"- Why now: {item['why_now']}",
                f"- Novelty or gap: {item['novelty_or_gap']}",
                f"- First action: {item['first_action']}",
                "",
                "Required evidence:",
            ]
        )
        required = item.get("required_evidence", [])
        if required:
            lines.extend([f"- {entry}" for entry in required])
        else:
            lines.append("- None recorded.")
        lines.extend(["", "Source signals:"])
        signals = item.get("source_signals", [])
        if signals:
            lines.extend([f"- {entry}" for entry in signals])
        else:
            lines.append("- None recorded.")
        lines.append("")

    lines.extend(["## Selection Advice", ""])
    advice = radar.get("selection_advice", [])
    if advice:
        lines.extend([f"- {entry}" for entry in advice])
    else:
        lines.append("- None recorded.")

    if context.get("recent_context", {}).get("sections"):
        lines.extend(["", "## Recent Vault Context", ""])
        for section in context["recent_context"]["sections"]:
            lines.append(f"### {section['section']}")
            lines.append("")
            for entry in section.get("entries", []):
                lines.append(f"- {entry['path']} | {entry['updated_at']}")
            lines.append("")

    if context.get("latest_literature", {}).get("groups"):
        lines.extend(["## Latest Literature Signals", ""])
        for group in context["latest_literature"]["groups"]:
            lines.append(f"### {group['interest']}")
            lines.append("")
            for entry in group.get("entries", []):
                pub = entry.get("publication_date") or entry.get("year", "")
                lines.append(f"- {entry['title']} | {pub} | {entry['source']} | {entry['url']}")
            lines.append("")

    if context.get("latest_literature", {}).get("errors"):
        lines.extend(["## Literature Fetch Notes", ""])
        lines.extend([f"- {entry}" for entry in context["latest_literature"]["errors"]])
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def radar_note_name(mode: str, title: str) -> str:
    return safe_filename_component(f"Question Radar - {mode.capitalize()} - {title}", max_length=110)


def write_question_radar_note(config: dict, runtime_cfg: dict, run_dir: Path, mode: str, title: str, radar: dict) -> Path:
    vault_root = Path(config["vault_root"])
    folder = vault_root / Path(runtime_cfg["note_folder"])
    folder.mkdir(parents=True, exist_ok=True)
    note_path = folder / f"{radar_note_name(mode, title)}.md"

    lines = [
        "---",
        'type: "question-radar"',
        f'mode: "{mode}"',
        f'generated: "{datetime.now().isoformat(timespec="seconds")}"',
        "---",
        "",
        f"# Question Radar - {title}",
        "",
        "## Focus Summary",
        "",
        radar["focus_summary"],
        "",
        "## Candidate Questions",
        "",
    ]

    for index, item in enumerate(radar.get("candidate_questions", []), start=1):
        lines.extend(
            [
                f"### {index}. {item['title']}",
                "",
                item["question"],
                "",
                f"- Value score: {item['value_score']}/10",
                f"- Time horizon: {item['time_horizon']}",
                f"- Why now: {item['why_now']}",
                f"- Novelty or gap: {item['novelty_or_gap']}",
                f"- First action: {item['first_action']}",
                "",
                "Required evidence:",
            ]
        )
        required = item.get("required_evidence", [])
        if required:
            lines.extend([f"- {entry}" for entry in required])
        else:
            lines.append("- None recorded.")
        lines.extend(["", "Source signals:"])
        signals = item.get("source_signals", [])
        if signals:
            lines.extend([f"- {entry}" for entry in signals])
        else:
            lines.append("- None recorded.")
        lines.append("")

    lines.extend(["## Selection Advice", ""])
    advice = radar.get("selection_advice", [])
    if advice:
        lines.extend([f"- {entry}" for entry in advice])
    else:
        lines.append("- None recorded.")
    lines.extend(
        [
            "",
            "## Artifacts",
            "",
            f"- `question_radar.json`: `{to_portable_path(run_dir / 'question_radar.json')}`",
            f"- `question_radar.md`: `{to_portable_path(run_dir / 'question_radar.md')}`",
            f"- `context_snapshot.json`: `{to_portable_path(run_dir / 'context_snapshot.json')}`",
            f"- `question_radar_response.json`: `{to_portable_path(run_dir / 'question_radar_response.json')}`",
        ]
    )
    write_text(note_path, "\n".join(lines) + "\n")
    update_index(note_path.parent / "_Index.md", f"- [[{note_path.stem}]]", "# Research Question Index\n")
    return note_path


def append_question_radar_to_daily(config: dict, runtime_cfg: dict, radar_note_path: Path | None, radar: dict) -> Path:
    vault_root = Path(config["vault_root"])
    daily_path = vault_root / config["obsidian"]["daily_folder"] / f"{date.today().isoformat()}.md"
    ensure_daily_note(daily_path)

    lines = [f"\n## {runtime_cfg['daily_section_title']}\n"]
    if radar_note_path:
        lines.append(f"\n- [[{radar_note_path.stem}]]")
    for item in radar.get("candidate_questions", [])[:3]:
        lines.append(f"- [{item['value_score']}/10] {item['title']}")
    lines.append("")
    append_text(daily_path, "\n".join(lines))
    return daily_path


def build_manual_or_conversation_context(
    config: dict,
    radar_runtime: dict,
    seed_title: str,
    seed_text: str,
    evidence_files,
    evidence_texts,
    skip_auto_evidence: bool,
):
    snapshot = build_seed_snapshot(seed_title, seed_text, evidence_files, evidence_texts)
    qa_runtime = radar_runtime["qa_runtime"]
    snapshot, retrieval_debug = attach_auto_evidence(config, qa_runtime, snapshot, skip_auto_evidence)
    return {
        "seed_title": seed_title,
        "seed_text": seed_text,
        "manual_evidence": snapshot.get("manual_evidence", []),
        "auto_evidence": snapshot.get("auto_evidence", []),
        "evidence_brief": snapshot.get("evidence_brief", {}),
        "retrieval_debug": retrieval_debug,
    }


def build_daily_context(config: dict, radar_runtime: dict, latest_file: str | None, skip_live_literature: bool):
    return {
        "project_profile": project_profile_summary(config),
        "recent_context": collect_recent_note_context(config, radar_runtime, radar_runtime["lookback_days"]),
        "latest_literature": fetch_latest_literature(config, radar_runtime, latest_file, skip_live_literature),
    }


def finalize_question_radar_run(
    config: dict,
    radar_runtime: dict,
    run_dir: Path,
    mode: str,
    title: str,
    radar: dict,
    radar_raw_response: dict,
    context: dict,
    write_vault_note_flag: bool,
    write_daily_note_flag: bool,
):
    model_name = radar_raw_response.get("generator") or radar_raw_response.get("generator_model") or radar_runtime["model"]
    meta = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "model": model_name,
        "run_dir": to_portable_path(run_dir),
    }
    if radar_raw_response.get("reason"):
        meta["generation_note"] = str(radar_raw_response["reason"])
    postprocess_warnings = []
    write_json(run_dir / "context_snapshot.json", context)
    write_json(run_dir / "question_radar.json", radar)
    markdown = render_question_radar_markdown(mode, title, radar, meta, context)
    write_text(run_dir / "question_radar.md", markdown)

    outputs = {
        "run_dir": to_portable_path(run_dir),
        "question_radar_json": to_portable_path(run_dir / "question_radar.json"),
        "question_radar_markdown": to_portable_path(run_dir / "question_radar.md"),
        "context_snapshot": to_portable_path(run_dir / "context_snapshot.json"),
    }

    radar_note_path = None
    if write_vault_note_flag:
        try:
            radar_note_path = write_question_radar_note(config, radar_runtime, run_dir, mode, title, radar)
            outputs["question_radar_note"] = to_portable_path(radar_note_path)
        except OSError as exc:
            postprocess_warnings.append(f"vault-note-write:{exc}")

    if write_daily_note_flag:
        try:
            daily_path = append_question_radar_to_daily(config, radar_runtime, radar_note_path, radar)
            outputs["daily_note"] = to_portable_path(daily_path)
        except OSError as exc:
            postprocess_warnings.append(f"daily-note-write:{exc}")

    if postprocess_warnings:
        radar_raw_response["postprocess_warnings"] = postprocess_warnings
        outputs["postprocess_warnings"] = postprocess_warnings

    write_json(run_dir / "question_radar_response.json", radar_raw_response)
    write_json(run_dir / "run_meta.json", meta)

    return outputs


def run_conversation(args):
    config = load_json(Path(args.config))
    radar_runtime = resolve_question_radar_config(config)
    conversation_text = load_seed_text(args.conversation, args.conversation_file, "conversation text")
    title = detect_seed_title(args.title, conversation_text, "Conversation radar")
    context = build_manual_or_conversation_context(
        config,
        radar_runtime,
        title,
        conversation_text,
        args.evidence_file,
        args.evidence_text,
        args.skip_auto_evidence,
    )
    payload = {
        "project_profile": project_profile_summary(config),
        "conversation_title": title,
        "conversation_text": conversation_text,
        "manual_evidence": context["manual_evidence"],
        "auto_evidence": context["auto_evidence"],
        "evidence_brief": context["evidence_brief"],
    }
    run_dir = create_run_dir(config, radar_runtime, "conversation", title, args.output_dir)
    radar, radar_raw_response = discover_question_radar(radar_runtime, "conversation", payload)
    outputs = finalize_question_radar_run(
        config,
        radar_runtime,
        run_dir,
        "conversation",
        title,
        radar,
        radar_raw_response,
        context,
        not args.skip_vault_write and radar_runtime["write_vault_note"],
        args.write_daily_note,
    )
    print(json.dumps(outputs, ensure_ascii=False, indent=2))


def run_manual(args):
    config = load_json(Path(args.config))
    radar_runtime = resolve_question_radar_config(config)
    prompt_text = load_seed_text(args.prompt, args.prompt_file, "manual prompt")
    title = detect_seed_title(args.title, prompt_text, "Manual radar")
    context = build_manual_or_conversation_context(
        config,
        radar_runtime,
        title,
        prompt_text,
        args.evidence_file,
        args.evidence_text,
        args.skip_auto_evidence,
    )
    payload = {
        "project_profile": project_profile_summary(config),
        "manual_title": title,
        "manual_prompt": prompt_text,
        "manual_evidence": context["manual_evidence"],
        "auto_evidence": context["auto_evidence"],
        "evidence_brief": context["evidence_brief"],
    }
    run_dir = create_run_dir(config, radar_runtime, "manual", title, args.output_dir)
    radar, radar_raw_response = discover_question_radar(radar_runtime, "manual", payload)
    outputs = finalize_question_radar_run(
        config,
        radar_runtime,
        run_dir,
        "manual",
        title,
        radar,
        radar_raw_response,
        context,
        not args.skip_vault_write and radar_runtime["write_vault_note"],
        args.write_daily_note,
    )
    print(json.dumps(outputs, ensure_ascii=False, indent=2))


def run_daily(args):
    config = load_json(Path(args.config))
    radar_runtime = resolve_question_radar_config(config)
    title = args.title.strip() if args.title else f"Daily radar {date.today().isoformat()}"
    context = build_daily_context(config, radar_runtime, args.latest_literature_file, args.skip_live_literature)
    payload = {
        "project_profile": context["project_profile"],
        "recent_context": context["recent_context"],
        "latest_literature": context["latest_literature"],
    }
    run_dir = create_run_dir(config, radar_runtime, "daily", title, args.output_dir)
    radar, radar_raw_response = discover_question_radar(radar_runtime, "daily", payload)
    outputs = finalize_question_radar_run(
        config,
        radar_runtime,
        run_dir,
        "daily",
        title,
        radar,
        radar_raw_response,
        context,
        not args.skip_vault_write and radar_runtime["write_vault_note"],
        (not args.skip_daily_note_write) and radar_runtime["write_daily_note"],
    )
    print(json.dumps(outputs, ensure_ascii=False, indent=2))


def add_shared_context_arguments(parser):
    parser.add_argument("--config", required=True)
    parser.add_argument("--title", help="Optional short title for the radar run.")
    parser.add_argument("--output-dir", help="Optional explicit run directory.")
    parser.add_argument("--skip-vault-write", action="store_true")
    parser.add_argument("--write-daily-note", action="store_true")


def add_manual_context_arguments(parser):
    add_shared_context_arguments(parser)
    parser.add_argument("--evidence-file", action="append", default=[])
    parser.add_argument("--evidence-text", action="append", default=[])
    parser.add_argument("--skip-auto-evidence", action="store_true")


def main():
    parser = argparse.ArgumentParser(description="Mine high-value academic questions from conversations, prompts, or daily context.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    conversation_parser = subparsers.add_parser("conversation", help="Mine candidate research questions from a conversation.")
    add_manual_context_arguments(conversation_parser)
    conversation_parser.add_argument("--conversation")
    conversation_parser.add_argument("--conversation-file")
    conversation_parser.set_defaults(func=run_conversation)

    manual_parser = subparsers.add_parser("manual", help="Generate candidate academic questions from manual input.")
    add_manual_context_arguments(manual_parser)
    manual_parser.add_argument("--prompt")
    manual_parser.add_argument("--prompt-file")
    manual_parser.set_defaults(func=run_manual)

    daily_parser = subparsers.add_parser("daily", help="Generate daily high-value questions from recent notes and latest literature.")
    add_shared_context_arguments(daily_parser)
    daily_parser.add_argument("--latest-literature-file")
    daily_parser.add_argument("--skip-live-literature", action="store_true")
    daily_parser.add_argument("--skip-daily-note-write", action="store_true")
    daily_parser.set_defaults(func=run_daily)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
