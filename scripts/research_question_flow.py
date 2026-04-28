#!/usr/bin/env python
import argparse
import hashlib
import json
import os
import re
import urllib.error
import urllib.request
from datetime import date, datetime
from pathlib import Path

from secure_config import load_json


DEFAULT_QUESTION_FOLDER = "04_Research/Questions"
DEFAULT_REPORT_FOLDER_NAME = "research-question-flow"
DEFAULT_AUTO_EVIDENCE_PATHS = [
    "02_Papers",
    "02_Literature/Papers",
    "03_Concepts",
    "04_Progress",
    "05_Experiments",
    "06_Writing",
    "07_Profiles",
    "09_Conversations",
    "10_Tasks",
    "12_Zotero",
    "00_Home",
    "03_Courses",
]
ENGLISH_STOPWORDS = {
    "a",
    "an",
    "as",
    "at",
    "by",
    "do",
    "if",
    "in",
    "is",
    "it",
    "its",
    "may",
    "not",
    "of",
    "on",
    "or",
    "our",
    "the",
    "to",
    "we",
    "and",
    "for",
    "with",
    "that",
    "this",
    "from",
    "into",
    "when",
    "what",
    "how",
    "why",
    "which",
    "does",
    "would",
    "could",
    "should",
    "under",
    "have",
    "has",
    "been",
    "being",
    "were",
    "their",
    "there",
    "about",
    "because",
    "while",
    "without",
    "strict",
    "ground",
    "truth",
    "question",
    "research",
}
CJK_STOPWORDS = {
    "什么",
    "如何",
    "为什么",
    "是否",
    "能否",
    "可以",
    "应该",
    "问题",
    "研究",
    "当前",
    "需要",
    "以及",
    "如果",
    "没有",
    "一个",
    "我们",
}
CALLOUT_BONUS = {
    "thesis": 8,
    "evidence": 8,
    "q2-focus": 10,
    "question": 7,
    "weakness": 8,
    "value": 7,
    "innovation": 6,
    "method": 5,
    "rebuttal": 6,
    "concept": 5,
}
HEADING_BONUS_HINTS = {
    "why this paper matters": 6,
    "core claims": 8,
    "method and assumptions": 5,
    "weak points and open questions": 8,
    "transfer value to this project": 7,
    "evidence to verify later": 6,
    "next action": 4,
    "logic skeleton": 7,
    "q2": 9,
    "q1-q10": 6,
}
ROLE_PRIORITY = {
    "core_claim": 10,
    "strongest_evidence": 9,
    "weakness_or_risk": 8,
    "user_question_answer": 8,
    "transfer_value": 7,
    "method_assumption": 6,
    "counterargument_handling": 6,
    "novelty_signal": 5,
    "question_frame": 5,
    "general_context": 3,
}
EVIDENCE_BUCKET_ORDER = [
    "core_claim",
    "strongest_evidence",
    "weakness_or_risk",
    "user_question_answer",
    "transfer_value",
    "method_assumption",
    "counterargument_handling",
    "novelty_signal",
    "manual_input",
    "general_context",
]
EVIDENCE_BUCKET_TITLES = {
    "core_claim": "Core Claims",
    "strongest_evidence": "Strongest Evidence",
    "weakness_or_risk": "Weaknesses And Risks",
    "user_question_answer": "User Question Answers",
    "transfer_value": "Transfer Value",
    "method_assumption": "Method And Assumptions",
    "counterargument_handling": "Counterargument Handling",
    "novelty_signal": "Novelty Signals",
    "manual_input": "Manual Inputs",
    "general_context": "General Context",
}

PREPARE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "title": {"type": "string"},
        "core_question": {"type": "string"},
        "research_goal": {"type": "string"},
        "answer_type": {"type": "string"},
        "background_context": {"type": "string"},
        "known_facts": {"type": "array", "items": {"type": "string"}},
        "unknowns": {"type": "array", "items": {"type": "string"}},
        "constraints": {"type": "array", "items": {"type": "string"}},
        "assumptions_to_check": {"type": "array", "items": {"type": "string"}},
        "subquestions": {"type": "array", "items": {"type": "string"}},
        "evidence_items": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "source": {"type": "string"},
                    "snippet": {"type": "string"},
                    "why_it_matters": {"type": "string"},
                },
                "required": ["source", "snippet", "why_it_matters"],
            },
        },
        "expected_output": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "audience": {"type": "string"},
                "format": {"type": "string"},
                "must_include": {"type": "array", "items": {"type": "string"}},
                "must_avoid": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["audience", "format", "must_include", "must_avoid"],
        },
    },
    "required": [
        "title",
        "core_question",
        "research_goal",
        "answer_type",
        "background_context",
        "known_facts",
        "unknowns",
        "constraints",
        "assumptions_to_check",
        "subquestions",
        "evidence_items",
        "expected_output",
    ],
}

ANSWER_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "summary": {"type": "string"},
        "direct_answer": {"type": "string"},
        "reasoning_steps": {"type": "array", "items": {"type": "string"}},
        "evidence_chain": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "claim": {"type": "string"},
                    "support": {"type": "string"},
                    "confidence": {"type": "string"},
                },
                "required": ["claim", "support", "confidence"],
            },
        },
        "assumptions": {"type": "array", "items": {"type": "string"}},
        "counterarguments": {"type": "array", "items": {"type": "string"}},
        "uncertainties": {"type": "array", "items": {"type": "string"}},
        "next_actions": {"type": "array", "items": {"type": "string"}},
        "follow_up_questions": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "summary",
        "direct_answer",
        "reasoning_steps",
        "evidence_chain",
        "assumptions",
        "counterarguments",
        "uncertainties",
        "next_actions",
        "follow_up_questions",
    ],
}

CRITIQUE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "critique_summary": {"type": "string"},
        "overall_verdict": {"type": "string"},
        "confidence_adjustment": {"type": "string"},
        "critical_issues": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "issue": {"type": "string"},
                    "severity": {"type": "string"},
                    "why_it_matters": {"type": "string"},
                    "suggested_fix": {"type": "string"},
                },
                "required": ["issue", "severity", "why_it_matters", "suggested_fix"],
            },
        },
        "evidence_gaps": {"type": "array", "items": {"type": "string"}},
        "hidden_assumptions": {"type": "array", "items": {"type": "string"}},
        "failure_modes": {"type": "array", "items": {"type": "string"}},
        "recommended_checks": {"type": "array", "items": {"type": "string"}},
        "salvageable_strengths": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "critique_summary",
        "overall_verdict",
        "confidence_adjustment",
        "critical_issues",
        "evidence_gaps",
        "hidden_assumptions",
        "failure_modes",
        "recommended_checks",
        "salvageable_strengths",
    ],
}

PREPARE_RULES = [
    "You are preparing a complex academic question for later deep reasoning.",
    "Do not answer the question itself.",
    "Keep the output primarily in the same language as the raw question unless a technical term is better kept in English.",
    "Separate known facts from open unknowns.",
    "Extract only evidence actually present in the input evidence list.",
    "If evidence is weak, state that weakness instead of pretending certainty.",
    "Keep subquestions concrete and research-usable.",
    "When evidence entries include evidence_role or evidence_role_labels, use them as hints about how the note should be interpreted.",
    "When an evidence_brief object is present, treat it as the high-level briefing view and the raw evidence list as the inspectable backup.",
]

ANSWER_RULES = [
    "You are answering a complex academic question using the structured question pack provided.",
    "Treat the evidence items as the available evidence base and do not invent papers, experiments, or citations.",
    "Distinguish observed evidence, inference, and uncertainty.",
    "If the evidence is insufficient for a strong claim, say so explicitly.",
    "Prefer research-grade language over motivational language.",
    "Keep the answer practical for OCT and deconvolution work when relevant.",
    "When evidence entries include evidence_role or evidence_role_labels, respect those role hints when weighing the evidence.",
    "If question_pack includes an evidence_brief object, use it to understand the evidence layout before drilling into raw evidence_items.",
]

CRITIQUE_RULES = [
    "You are a skeptical academic reviewer critiquing the structured answer, not rewriting it from scratch.",
    "Use only the supplied question pack and structured answer. Do not invent citations, experiments, or external evidence.",
    "Focus on fragile reasoning, evidence gaps, hidden assumptions, and failure modes.",
    "Prefer precise, high-signal criticism over generic negativity.",
    "If part of the answer is solid, keep it in salvageable strengths instead of attacking everything.",
    "Assume the user wants a publishable and falsifiable research workflow.",
]


def write_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_text(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def append_text(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(text)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="replace")


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def sanitize(value: str) -> str:
    return str(value).replace('"', "'")


def to_portable_path(value) -> str:
    return str(value).replace("\\", "/")


def safe_filename_component(value: str, max_length: int = 80) -> str:
    value = re.sub(r'[<>:"/\\|?*]+', "", value)
    value = re.sub(r"\s+", " ", value).strip().rstrip(".")
    if not value:
        return "item"
    return value[:max_length].rstrip(" .")


def timestamp_slug() -> str:
    return datetime.now().strftime("%H%M%S%f")


def slugify(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    if normalized:
        return normalized[:64]
    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()[:10]
    return f"q-{digest}"


def shorten_title(text: str, max_chars: int = 72) -> str:
    cleaned = normalize_space(text)
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[: max_chars - 3].rstrip() + "..."


def looks_like_cjk(text: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", text))


def extract_query_keywords(text: str):
    keywords = []
    seen = set()

    for token in re.findall(r"[a-z0-9][a-z0-9\-_]{1,}", text.lower()):
        cleaned = token.strip("-_")
        if len(cleaned) < 2 or cleaned in ENGLISH_STOPWORDS:
            continue
        if cleaned not in seen:
            keywords.append(cleaned)
            seen.add(cleaned)

    for run in re.findall(r"[\u4e00-\u9fff]{2,}", text):
        if run in CJK_STOPWORDS:
            continue
        variants = [run]
        if len(run) <= 8:
            variants.extend(run[index : index + 2] for index in range(len(run) - 1))
        for token in variants:
            if len(token) < 2 or token in CJK_STOPWORDS:
                continue
            if token not in seen:
                keywords.append(token)
                seen.add(token)

    return keywords


def keyword_score(text: str, keywords):
    haystack = text.lower()
    score = 0
    matched = []
    seen = set()
    for keyword in keywords:
        probe = keyword if looks_like_cjk(keyword) else keyword.lower()
        count = haystack.count(probe)
        if count:
            score += count
            if keyword not in seen:
                matched.append(keyword)
                seen.add(keyword)
    return score, matched


def strip_frontmatter(text: str) -> str:
    if not text.startswith("---"):
        return text
    closing_index = text.find("\n---", 3)
    if closing_index == -1:
        return text
    return text[closing_index + 4 :].lstrip()


def normalize_multiline_block(text: str) -> str:
    lines = [line.strip() for line in text.splitlines()]
    cleaned = []
    pending_blank = False
    for line in lines:
        if not line:
            if cleaned:
                pending_blank = True
            continue
        if pending_blank:
            cleaned.append("")
            pending_blank = False
        cleaned.append(line)
    return "\n".join(cleaned).strip()


def heading_bonus(title: str) -> int:
    lowered = title.lower()
    for hint, bonus in HEADING_BONUS_HINTS.items():
        if hint in lowered:
            return bonus
    return 0


def role_priority(role: str) -> int:
    return ROLE_PRIORITY.get(role, 0)


def infer_callout_role(tag: str, text: str) -> str:
    lowered = text.lower()
    if tag in {"q2-focus", "thesis"}:
        return "core_claim"
    if tag == "evidence":
        return "strongest_evidence"
    if tag == "weakness":
        return "weakness_or_risk"
    if tag == "value":
        return "transfer_value"
    if tag == "innovation":
        return "novelty_signal"
    if tag == "method":
        return "method_assumption"
    if tag == "rebuttal":
        return "counterargument_handling"
    if tag == "question":
        if "q2" in lowered or "core claim" in lowered:
            return "core_claim"
        return "question_frame"
    if tag == "concept":
        return "method_assumption"
    return "general_context"


def infer_heading_role(title: str) -> str:
    lowered = title.lower()
    if "core claims" in lowered:
        return "core_claim"
    if "why this paper matters" in lowered:
        return "transfer_value"
    if "weak points" in lowered:
        return "weakness_or_risk"
    if "transfer value" in lowered:
        return "transfer_value"
    if "evidence to verify later" in lowered:
        return "strongest_evidence"
    if "method and assumptions" in lowered:
        return "method_assumption"
    if "logic skeleton" in lowered:
        return "core_claim"
    if "q1-q10" in lowered or lowered.startswith("q2"):
        return "user_question_answer"
    return "general_context"


def infer_inline_field_role(text: str) -> str:
    lowered = text.lower()
    if "question_text::" in lowered or "tentative_answer::" in lowered or "final_answer::" in lowered:
        return "user_question_answer"
    if "short_answer:" in lowered or "deep_answer:" in lowered or "q2_status::" in lowered:
        return "core_claim"
    if "paragraph_function::" in lowered or "rhetorical_move_or_weakness::" in lowered:
        return "weakness_or_risk"
    return "general_context"


def infer_table_role(text: str) -> str:
    lowered = text.lower()
    if "span.evidence" in lowered:
        return "strongest_evidence"
    if "span.q2" in lowered:
        return "core_claim"
    return "general_context"


def summarize_role_labels(roles):
    ordered = sorted(set(roles), key=lambda item: (-role_priority(item), item))
    return ordered


def shorten_text(text: str, max_chars: int) -> str:
    cleaned = normalize_space(text)
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[: max_chars - 3].rstrip() + "..."


def build_evidence_brief(snapshot: dict, max_items_per_bucket: int = 4, max_chars_per_item: int = 260):
    buckets = {role: [] for role in EVIDENCE_BUCKET_ORDER}
    source_count = 0
    seen_sources = set()

    for item in snapshot.get("evidence", []):
        source = item.get("source", "unknown")
        if source not in seen_sources:
            seen_sources.add(source)
            source_count += 1

        role_labels = summarize_role_labels(item.get("evidence_role_labels", []) or [item.get("evidence_role", "general_context")])
        if not role_labels:
            role_labels = ["general_context"]

        brief_item = {
            "source": source,
            "summary": shorten_text(item.get("content", ""), max_chars_per_item),
            "primary_role": item.get("evidence_role", role_labels[0]),
            "secondary_roles": [role for role in role_labels if role != item.get("evidence_role", role_labels[0])],
            "retrieval_reason": item.get("retrieval_reason", "manual input"),
        }

        for role in role_labels:
            bucket = buckets.setdefault(role, [])
            if len(bucket) >= max_items_per_bucket:
                continue
            bucket.append(brief_item)

    non_empty_buckets = {role: items for role, items in buckets.items() if items}
    bucket_counts = {role: len(items) for role, items in non_empty_buckets.items()}
    bucket_order = [role for role in EVIDENCE_BUCKET_ORDER if role in non_empty_buckets]

    return {
        "bucket_order": bucket_order,
        "bucket_titles": {role: EVIDENCE_BUCKET_TITLES.get(role, role) for role in bucket_order},
        "bucket_counts": bucket_counts,
        "source_count": source_count,
        "buckets": non_empty_buckets,
    }


def extract_callout_blocks(text: str):
    blocks = []
    lines = strip_frontmatter(text).splitlines()
    index = 0
    while index < len(lines):
        line = lines[index]
        if not re.match(r"^\s*>\s*\[![^\]]+\]", line):
            index += 1
            continue

        block_lines = []
        while index < len(lines) and re.match(r"^\s*>", lines[index]):
            block_lines.append(re.sub(r"^\s*>\s?", "", lines[index]).rstrip())
            index += 1

        block_text = normalize_multiline_block("\n".join(block_lines))
        if not block_text:
            continue

        match = re.match(r"\[!([^\]\|]+)", block_lines[0].strip())
        tag = match.group(1).strip().lower() if match else "callout"
        blocks.append(
            {
                "kind": "callout",
                "label": tag,
                "bonus": CALLOUT_BONUS.get(tag, 3),
                "evidence_role": infer_callout_role(tag, block_text),
                "text": block_text,
            }
        )
    return blocks


def extract_heading_sections(text: str):
    blocks = []
    lines = strip_frontmatter(text).splitlines()
    current_heading = None
    current_lines = []

    def flush():
        if not current_heading:
            return
        block_text = normalize_multiline_block("\n".join(current_lines))
        if block_text:
            blocks.append(
                {
                    "kind": "heading_section",
                    "label": current_heading,
                    "bonus": heading_bonus(current_heading),
                    "evidence_role": infer_heading_role(current_heading),
                    "text": f"{current_heading}\n{block_text}",
                }
            )

    for raw_line in lines:
        heading_match = re.match(r"^\s*#{1,6}\s+(.+?)\s*$", raw_line)
        if heading_match:
            flush()
            current_heading = heading_match.group(1).strip()
            current_lines = []
            continue
        if current_heading is not None:
            current_lines.append(raw_line.rstrip())

    flush()
    return blocks


def extract_inline_field_blocks(text: str):
    blocks = []
    lines = strip_frontmatter(text).splitlines()
    index = 0
    field_pattern = re.compile(
        r"(question_id::|question_text::|tentative_answer::|final_answer::|paragraph_function::|"
        r"rhetorical_move_or_weakness::|linked_questions::|short_answer:|deep_answer:|"
        r"limitation_or_counterargument:|q2_status::|q2_confidence::)"
    )
    while index < len(lines):
        if not field_pattern.search(lines[index]):
            index += 1
            continue

        start = index
        while start > 0 and lines[start - 1].strip().startswith("- question_id::"):
            start -= 1

        block_lines = []
        while index < len(lines):
            line = lines[index]
            stripped = line.strip()
            if block_lines and not stripped:
                break
            if block_lines and re.match(r"^\s*#{1,6}\s+", line):
                break
            if block_lines and stripped.startswith("> [!"):
                break
            if stripped:
                block_lines.append(stripped)
            index += 1

        block_text = normalize_multiline_block("\n".join(block_lines))
        if block_text:
            blocks.append(
                {
                    "kind": "inline_fields",
                    "label": "inline_fields",
                    "bonus": 6,
                    "evidence_role": infer_inline_field_role(block_text),
                    "text": block_text,
                }
            )
        else:
            index = max(index, start + 1)
    return blocks


def extract_table_signal_blocks(text: str):
    blocks = []
    for raw_line in strip_frontmatter(text).splitlines():
        stripped = raw_line.strip()
        if not stripped.startswith("|"):
            continue
        lowered = stripped.lower()
        if "span.q2" not in lowered and "span.evidence" not in lowered and "why it matters" not in lowered:
            continue
        blocks.append(
            {
                "kind": "table_signal",
                "label": "table_signal",
                "bonus": 7,
                "evidence_role": infer_table_role(stripped),
                "text": stripped,
            }
        )
    return blocks


def extract_structured_candidates(note_path: Path, text: str):
    candidates = []
    portable_path = to_portable_path(note_path)
    if "02_Literature/Papers/" in portable_path or "02_Papers/" in portable_path:
        candidates.extend(extract_callout_blocks(text))
        candidates.extend(extract_inline_field_blocks(text))
        candidates.extend(extract_table_signal_blocks(text))
        candidates.extend(extract_heading_sections(text))
    return candidates


def split_note_paragraphs(text: str):
    chunks = re.split(r"\n\s*\n", strip_frontmatter(text))
    paragraphs = []
    for chunk in chunks:
        cleaned = normalize_space(chunk)
        if not cleaned:
            continue
        if cleaned.startswith("---") and cleaned.endswith("---"):
            continue
        if cleaned.startswith("```") and cleaned.endswith("```"):
            continue
        paragraphs.append(cleaned)
    return paragraphs


def build_note_snippet(note_path: Path, text: str, keywords, max_chars: int):
    ranked = []
    for candidate in extract_structured_candidates(note_path, text):
        score, matched = keyword_score(candidate["text"], keywords)
        candidate_score = score + candidate["bonus"]
        if score <= 0 and candidate["bonus"] < 6:
            continue
        ranked.append(
            (
                candidate_score,
                matched,
                candidate["text"],
                candidate["kind"],
                candidate["label"],
                candidate.get("evidence_role", "general_context"),
            )
        )

    for paragraph in split_note_paragraphs(text):
        score, matched = keyword_score(paragraph, keywords)
        if score <= 0:
            continue
        ranked.append((score, matched, paragraph, "paragraph", "paragraph", "general_context"))

    ranked.sort(key=lambda item: item[0], reverse=True)
    selected = []
    used = 0
    matched_keywords = []
    matched_seen = set()
    block_types = []
    type_seen = set()
    role_labels = []
    role_seen = set()
    for score, matched, paragraph, kind, label, evidence_role in ranked[:8]:
        if evidence_role not in role_seen:
            role_labels.append(evidence_role)
            role_seen.add(evidence_role)

    for score, matched, paragraph, kind, label, evidence_role in ranked[:4]:
        trimmed = paragraph[:max_chars].rstrip()
        if used and used + len(trimmed) > max_chars:
            break
        selected.append(trimmed)
        used += len(trimmed)
        for item in matched:
            if item not in matched_seen:
                matched_keywords.append(item)
                matched_seen.add(item)
        block_key = f"{kind}:{label}"
        if block_key not in type_seen:
            block_types.append(block_key)
            type_seen.add(block_key)

    if not selected:
        return "", [], [], []
    snippet = "\n\n".join(selected)
    if len(snippet) > max_chars:
        snippet = snippet[: max_chars - 3].rstrip() + "..."
    return snippet, matched_keywords, block_types, summarize_role_labels(role_labels)


def update_index(index_path: Path, line: str, header: str):
    index_path.parent.mkdir(parents=True, exist_ok=True)
    existing = index_path.read_text(encoding="utf-8") if index_path.exists() else header
    if line not in existing:
        if not existing.endswith("\n"):
            existing += "\n"
        existing += line + "\n"
        index_path.write_text(existing, encoding="utf-8")


def bullet_lines(items):
    if not items:
        return ["- None recorded."]
    return [f"- {item}" for item in items]


def evidence_brief_lines(evidence_brief: dict):
    if not evidence_brief or not evidence_brief.get("bucket_order"):
        return ["- No evidence briefing buckets were assembled."]

    lines = [f"- Source count: {evidence_brief.get('source_count', 0)}"]
    for role in evidence_brief.get("bucket_order", []):
        title = evidence_brief.get("bucket_titles", {}).get(role, role)
        items = evidence_brief.get("buckets", {}).get(role, [])
        count = evidence_brief.get("bucket_counts", {}).get(role, len(items))
        lines.append(f"- {title} ({count})")
        for item in items[:2]:
            lines.append(f"  {item['source']}: {item['summary']}")
    return lines


def evidence_lines(items):
    if not items:
        return ["- No evidence items were structured."]
    lines = []
    for item in items:
        lines.append(f"- Source: {item['source']}")
        lines.append(f"  Snippet: {item['snippet']}")
        lines.append(f"  Why it matters: {item['why_it_matters']}")
    return lines


def evidence_chain_lines(items):
    if not items:
        return ["- No evidence-chain entries were returned."]
    lines = []
    for item in items:
        lines.append(f"- Claim: {item['claim']}")
        lines.append(f"  Support: {item['support']}")
        lines.append(f"  Confidence: {item['confidence']}")
    return lines


def critique_issue_lines(items):
    if not items:
        return ["- No critical issues were returned."]
    lines = []
    for item in items:
        lines.append(f"- Issue: {item['issue']}")
        lines.append(f"  Severity: {item['severity']}")
        lines.append(f"  Why it matters: {item['why_it_matters']}")
        lines.append(f"  Suggested fix: {item['suggested_fix']}")
    return lines


def detect_title(explicit_title: str, question_text: str) -> str:
    if explicit_title:
        return normalize_space(explicit_title)
    fragments = [segment.strip() for segment in re.split(r"[\n。！？?!]", question_text) if segment.strip()]
    if fragments:
        return shorten_title(fragments[0])
    return "Academic question run"


def load_input_snapshot(args) -> dict:
    question_text = ""
    if args.question:
        question_text = args.question
    elif args.question_file:
        question_text = read_text(Path(args.question_file))
    question_text = question_text.strip()
    if not question_text:
        raise ValueError("A non-empty question is required via --question or --question-file.")

    evidence_records = []
    for index, text in enumerate(args.evidence_text or [], start=1):
        cleaned = text.strip()
        if cleaned:
            evidence_records.append(
                {
                    "source": f"inline-evidence-{index}",
                    "content": cleaned,
                    "evidence_role": "manual_input",
                    "evidence_role_labels": ["manual_input"],
                }
            )

    for path_str in args.evidence_file or []:
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
        "title": detect_title(getattr(args, "title", ""), question_text),
        "raw_question": question_text,
        "manual_evidence": evidence_records,
        "evidence": list(evidence_records),
    }


def iter_auto_evidence_paths(vault_root: Path, configured_paths):
    for relative_path in configured_paths:
        root = vault_root / Path(relative_path)
        if not root.exists():
            continue
        if root.is_file():
            yield root
            continue
        for note_path in root.rglob("*.md"):
            if note_path.name == "_Index.md":
                continue
            yield note_path


def retrieve_auto_evidence(config: dict, runtime_cfg: dict, snapshot: dict):
    vault_root = Path(config["vault_root"])
    keywords = extract_query_keywords(snapshot["title"] + "\n" + snapshot["raw_question"])
    candidates = []

    for note_path in iter_auto_evidence_paths(vault_root, runtime_cfg["auto_evidence_paths"]):
        try:
            note_text = read_text(note_path)
        except OSError:
            continue

        path_score, path_matches = keyword_score(to_portable_path(note_path.relative_to(vault_root)), keywords)
        body_score, body_matches = keyword_score(note_text, keywords)
        total_score = (path_score * 3) + body_score
        if total_score < runtime_cfg["auto_evidence_min_score"]:
            continue

        snippet, snippet_matches, block_types, role_labels = build_note_snippet(
            note_path.relative_to(vault_root),
            note_text,
            keywords,
            runtime_cfg["auto_evidence_max_chars_per_note"],
        )
        if not snippet:
            continue

        matched_keywords = []
        for item in path_matches + body_matches + snippet_matches:
            if item not in matched_keywords:
                matched_keywords.append(item)

        structured_bonus = sum(2 for item in block_types if not item.startswith("paragraph:"))
        candidates.append(
            {
                "path": to_portable_path(note_path.relative_to(vault_root)),
                "score": total_score + structured_bonus,
                "matched_keywords": matched_keywords,
                "block_types": block_types,
                "evidence_role": role_labels[0] if role_labels else "general_context",
                "evidence_role_labels": role_labels,
                "snippet": snippet,
            }
        )

    candidates.sort(key=lambda item: item["score"], reverse=True)
    selected = candidates[: runtime_cfg["auto_evidence_max_notes"]]
    evidence = []
    for candidate in selected:
        keyword_label = ", ".join(candidate["matched_keywords"][:6]) or "question match"
        evidence.append(
            {
                "source": candidate["path"],
                "content": candidate["snippet"],
                "evidence_role": candidate["evidence_role"],
                "evidence_role_labels": candidate["evidence_role_labels"],
                "retrieval_reason": (
                    f"auto-evidence match on {keyword_label}; blocks: "
                    + ", ".join(candidate["block_types"][:3])
                ),
            }
        )

    return {
        "keywords": keywords,
        "selected_count": len(selected),
        "candidates": candidates[: runtime_cfg["auto_evidence_max_candidates_log"]],
        "evidence": evidence,
    }


def extract_response_text(payload: dict) -> str:
    if isinstance(payload.get("output_text"), str) and payload["output_text"].strip():
        return payload["output_text"].strip()

    pieces = []
    for output_item in payload.get("output", []):
        if not isinstance(output_item, dict):
            continue
        for content_item in output_item.get("content", []):
            if not isinstance(content_item, dict):
                continue
            if content_item.get("type") in {"output_text", "text"}:
                text = content_item.get("text", "")
                if text:
                    pieces.append(text)
    return "\n".join(pieces).strip()


def resolve_qa_config(config: dict) -> dict:
    qa_cfg = config.get("academic_qa", {})
    qa_openai = qa_cfg.get("openai", {})
    translation_openai = config.get("translation", {}).get("openai", {})
    auto_evidence_paths = qa_cfg.get("auto_evidence_paths", DEFAULT_AUTO_EVIDENCE_PATHS)
    if not isinstance(auto_evidence_paths, list):
        auto_evidence_paths = DEFAULT_AUTO_EVIDENCE_PATHS

    endpoint = (
        qa_openai.get("base_url", "").strip()
        or translation_openai.get("base_url", "").strip()
        or "https://api.openai.com/v1/responses"
    )
    api_key = (
        qa_openai.get("api_key", "").strip()
        or translation_openai.get("api_key", "").strip()
        or os.environ.get("OPENAI_API_KEY", "").strip()
    )

    return {
        "api_key": api_key,
        "endpoint": endpoint,
        "enable_critique": bool(qa_cfg.get("enable_critique", True)),
        "enable_auto_evidence": bool(qa_cfg.get("enable_auto_evidence", True)),
        "auto_evidence_paths": [str(item) for item in auto_evidence_paths if str(item).strip()],
        "auto_evidence_min_score": int(qa_cfg.get("auto_evidence_min_score", 2)),
        "auto_evidence_max_notes": int(qa_cfg.get("auto_evidence_max_notes", 6)),
        "auto_evidence_max_chars_per_note": int(qa_cfg.get("auto_evidence_max_chars_per_note", 700)),
        "auto_evidence_max_candidates_log": int(qa_cfg.get("auto_evidence_max_candidates_log", 20)),
        "extract_model": qa_openai.get("extract_model", "gpt-5-mini").strip() or "gpt-5-mini",
        "extract_effort": qa_openai.get("extract_reasoning_effort", "minimal").strip() or "minimal",
        "extract_max_output_tokens": int(qa_openai.get("extract_max_output_tokens", 4000)),
        "reason_model": qa_openai.get("reason_model", "gpt-5.4").strip() or "gpt-5.4",
        "reason_effort": qa_openai.get("reason_reasoning_effort", "high").strip() or "high",
        "reason_max_output_tokens": int(qa_openai.get("reason_max_output_tokens", 8000)),
        "critic_model": qa_openai.get("critic_model", "gpt-5.4").strip() or "gpt-5.4",
        "critic_effort": qa_openai.get("critic_reasoning_effort", "high").strip() or "high",
        "critic_max_output_tokens": int(qa_openai.get("critic_max_output_tokens", 6000)),
        "question_folder": qa_cfg.get("question_folder", DEFAULT_QUESTION_FOLDER).strip() or DEFAULT_QUESTION_FOLDER,
        "report_folder_name": qa_cfg.get("report_folder_name", DEFAULT_REPORT_FOLDER_NAME).strip()
        or DEFAULT_REPORT_FOLDER_NAME,
    }


def build_request_payload(model: str, effort: str, max_output_tokens: int, schema_name: str, schema: dict, prompt_text: str):
    payload = {
        "model": model,
        "store": False,
        "max_output_tokens": max_output_tokens,
        "input": prompt_text,
        "text": {
            "format": {
                "type": "json_schema",
                "name": schema_name,
                "strict": True,
                "schema": schema,
            }
        },
    }
    if effort:
        payload["reasoning"] = {"effort": effort}
    return payload


def post_openai_json(endpoint: str, api_key: str, payload: dict) -> dict:
    if not api_key:
        raise ValueError("OpenAI API key is not configured. Set academic_qa.openai.api_key or OPENAI_API_KEY.")

    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenAI request failed ({exc.code}): {body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"OpenAI request failed: {exc.reason}") from exc


def prepare_question_pack(config: dict, runtime_cfg: dict, run_dir: Path, snapshot: dict) -> dict:
    prompt_payload = {
        "rules": PREPARE_RULES,
        "title": snapshot["title"],
        "raw_question": snapshot["raw_question"],
        "evidence_brief": snapshot.get("evidence_brief", {}),
        "evidence": snapshot["evidence"],
    }
    prompt_text = json.dumps(prompt_payload, ensure_ascii=False)
    request_payload = build_request_payload(
        runtime_cfg["extract_model"],
        runtime_cfg["extract_effort"],
        runtime_cfg["extract_max_output_tokens"],
        "research_question_pack",
        PREPARE_SCHEMA,
        prompt_text,
    )
    response_payload = post_openai_json(runtime_cfg["endpoint"], runtime_cfg["api_key"], request_payload)
    response_text = extract_response_text(response_payload)
    if not response_text:
        raise RuntimeError("OpenAI prepare step did not return any text output.")

    question_pack = json.loads(response_text)
    question_pack["source_question"] = snapshot["raw_question"]
    question_pack["input_evidence_count"] = len(snapshot["evidence"])
    question_pack["evidence_brief"] = snapshot.get("evidence_brief", {})
    question_pack["generated_at"] = datetime.now().isoformat(timespec="seconds")
    question_pack["artifacts"] = {
        "run_dir": to_portable_path(run_dir),
        "raw_input_path": to_portable_path(run_dir / "input_snapshot.json"),
        "retrieval_candidates_path": to_portable_path(run_dir / "retrieval_candidates.json"),
        "evidence_brief_path": to_portable_path(run_dir / "evidence_brief.json"),
    }
    return question_pack


def answer_question_pack(runtime_cfg: dict, question_pack: dict) -> tuple[dict, dict]:
    prompt_payload = {
        "rules": ANSWER_RULES,
        "question_pack": question_pack,
    }
    prompt_text = json.dumps(prompt_payload, ensure_ascii=False)
    request_payload = build_request_payload(
        runtime_cfg["reason_model"],
        runtime_cfg["reason_effort"],
        runtime_cfg["reason_max_output_tokens"],
        "research_question_answer",
        ANSWER_SCHEMA,
        prompt_text,
    )
    response_payload = post_openai_json(runtime_cfg["endpoint"], runtime_cfg["api_key"], request_payload)
    response_text = extract_response_text(response_payload)
    if not response_text:
        raise RuntimeError("OpenAI answer step did not return any text output.")
    return json.loads(response_text), response_payload


def critique_question_answer(runtime_cfg: dict, question_pack: dict, answer: dict) -> tuple[dict, dict]:
    prompt_payload = {
        "rules": CRITIQUE_RULES,
        "question_pack": question_pack,
        "structured_answer": answer,
    }
    prompt_text = json.dumps(prompt_payload, ensure_ascii=False)
    request_payload = build_request_payload(
        runtime_cfg["critic_model"],
        runtime_cfg["critic_effort"],
        runtime_cfg["critic_max_output_tokens"],
        "research_question_critique",
        CRITIQUE_SCHEMA,
        prompt_text,
    )
    response_payload = post_openai_json(runtime_cfg["endpoint"], runtime_cfg["api_key"], request_payload)
    response_text = extract_response_text(response_payload)
    if not response_text:
        raise RuntimeError("OpenAI critique step did not return any text output.")
    return json.loads(response_text), response_payload


def attach_auto_evidence(config: dict, runtime_cfg: dict, snapshot: dict, skip_auto_evidence: bool):
    retrieval_debug = {
        "enabled": runtime_cfg["enable_auto_evidence"] and not skip_auto_evidence,
        "keywords": [],
        "selected_count": 0,
        "candidates": [],
    }
    snapshot["auto_evidence"] = []
    snapshot["evidence"] = list(snapshot.get("manual_evidence", []))
    if not retrieval_debug["enabled"]:
        snapshot["evidence_brief"] = build_evidence_brief(snapshot)
        return snapshot, retrieval_debug

    auto_results = retrieve_auto_evidence(config, runtime_cfg, snapshot)
    retrieval_debug.update(auto_results)
    snapshot["auto_evidence"] = auto_results["evidence"]
    snapshot["evidence"] = list(snapshot.get("manual_evidence", [])) + auto_results["evidence"]
    snapshot["evidence_brief"] = build_evidence_brief(snapshot)
    return snapshot, retrieval_debug


def render_answer_markdown(question_pack: dict, answer: dict, critique: dict | None, meta: dict) -> str:
    lines = [
        f"# {question_pack['title']}",
        "",
        f"- Generated: {meta['generated_at']}",
        f"- Extract model: {meta['extract_model']}",
        f"- Reason model: {meta['reason_model']}",
        f"- Critic model: {meta['critic_model']}",
        f"- Run directory: `{meta['run_dir']}`",
        "",
        "## Core Question",
        "",
        question_pack["core_question"],
        "",
        "## Research Goal",
        "",
        question_pack["research_goal"],
        "",
        "## Evidence Briefing",
        "",
    ]
    lines.extend(evidence_brief_lines(question_pack.get("evidence_brief", {})))
    lines.extend(
        [
            "",
            "## Summary",
            "",
            answer["summary"],
            "",
            "## Direct Answer",
            "",
            answer["direct_answer"],
            "",
            "## Background Context",
            "",
            question_pack["background_context"],
            "",
            "## Known Facts",
            "",
        ]
    )
    lines.extend(bullet_lines(question_pack["known_facts"]))
    lines.extend(
        [
            "",
            "## Unknowns",
            "",
        ]
    )
    lines.extend(bullet_lines(question_pack["unknowns"]))
    lines.extend(
        [
            "",
            "## Constraints",
            "",
        ]
    )
    lines.extend(bullet_lines(question_pack["constraints"]))
    lines.extend(
        [
            "",
            "## Assumptions To Check",
            "",
        ]
    )
    lines.extend(bullet_lines(question_pack["assumptions_to_check"]))
    lines.extend(
        [
            "",
            "## Subquestions",
            "",
        ]
    )
    lines.extend(bullet_lines(question_pack["subquestions"]))
    lines.extend(
        [
            "",
            "## Evidence Items",
            "",
        ]
    )
    lines.extend(evidence_lines(question_pack["evidence_items"]))
    lines.extend(
        [
            "",
            "## Reasoning Steps",
            "",
        ]
    )
    lines.extend(bullet_lines(answer["reasoning_steps"]))
    lines.extend(
        [
            "",
            "## Evidence Chain",
            "",
        ]
    )
    lines.extend(evidence_chain_lines(answer["evidence_chain"]))
    lines.extend(
        [
            "",
            "## Assumptions",
            "",
        ]
    )
    lines.extend(bullet_lines(answer["assumptions"]))
    lines.extend(
        [
            "",
            "## Counterarguments",
            "",
        ]
    )
    lines.extend(bullet_lines(answer["counterarguments"]))
    lines.extend(
        [
            "",
            "## Uncertainties",
            "",
        ]
    )
    lines.extend(bullet_lines(answer["uncertainties"]))
    lines.extend(
        [
            "",
            "## Next Actions",
            "",
        ]
    )
    lines.extend(bullet_lines(answer["next_actions"]))
    lines.extend(
        [
            "",
            "## Follow-up Questions",
            "",
        ]
    )
    lines.extend(bullet_lines(answer["follow_up_questions"]))
    lines.extend(
        [
            "",
            "## Expected Output Contract",
            "",
            f"- Audience: {question_pack['expected_output']['audience']}",
            f"- Format: {question_pack['expected_output']['format']}",
            "",
            "Must include:",
        ]
    )
    lines.extend(bullet_lines(question_pack["expected_output"]["must_include"]))
    lines.extend(
        [
            "",
            "Must avoid:",
        ]
    )
    lines.extend(bullet_lines(question_pack["expected_output"]["must_avoid"]))
    if critique:
        lines.extend(
            [
                "",
                "## Critique Summary",
                "",
                critique["critique_summary"],
                "",
                "## Overall Verdict",
                "",
                critique["overall_verdict"],
                "",
                "## Confidence Adjustment",
                "",
                critique["confidence_adjustment"],
                "",
                "## Critical Issues",
                "",
            ]
        )
        lines.extend(critique_issue_lines(critique["critical_issues"]))
        lines.extend(
            [
                "",
                "## Evidence Gaps",
                "",
            ]
        )
        lines.extend(bullet_lines(critique["evidence_gaps"]))
        lines.extend(
            [
                "",
                "## Hidden Assumptions",
                "",
            ]
        )
        lines.extend(bullet_lines(critique["hidden_assumptions"]))
        lines.extend(
            [
                "",
                "## Failure Modes",
                "",
            ]
        )
        lines.extend(bullet_lines(critique["failure_modes"]))
        lines.extend(
            [
                "",
                "## Recommended Checks",
                "",
            ]
        )
        lines.extend(bullet_lines(critique["recommended_checks"]))
        lines.extend(
            [
                "",
                "## Salvageable Strengths",
                "",
            ]
        )
        lines.extend(bullet_lines(critique["salvageable_strengths"]))
    return "\n".join(lines).strip() + "\n"


def render_critique_markdown(question_pack: dict, answer: dict, critique: dict, meta: dict) -> str:
    lines = [
        f"# Critique - {question_pack['title']}",
        "",
        f"- Generated: {meta['generated_at']}",
        f"- Critic model: {meta['critic_model']}",
        f"- Run directory: `{meta['run_dir']}`",
        "",
        "## Core Question",
        "",
        question_pack["core_question"],
        "",
        "## Answer Summary Under Review",
        "",
        answer["summary"],
        "",
        "## Critique Summary",
        "",
        critique["critique_summary"],
        "",
        "## Overall Verdict",
        "",
        critique["overall_verdict"],
        "",
        "## Confidence Adjustment",
        "",
        critique["confidence_adjustment"],
        "",
        "## Critical Issues",
        "",
    ]
    lines.extend(critique_issue_lines(critique["critical_issues"]))
    lines.extend(
        [
            "",
            "## Evidence Gaps",
            "",
        ]
    )
    lines.extend(bullet_lines(critique["evidence_gaps"]))
    lines.extend(
        [
            "",
            "## Hidden Assumptions",
            "",
        ]
    )
    lines.extend(bullet_lines(critique["hidden_assumptions"]))
    lines.extend(
        [
            "",
            "## Failure Modes",
            "",
        ]
    )
    lines.extend(bullet_lines(critique["failure_modes"]))
    lines.extend(
        [
            "",
            "## Recommended Checks",
            "",
        ]
    )
    lines.extend(bullet_lines(critique["recommended_checks"]))
    lines.extend(
        [
            "",
            "## Salvageable Strengths",
            "",
        ]
    )
    lines.extend(bullet_lines(critique["salvageable_strengths"]))
    return "\n".join(lines).strip() + "\n"


def ensure_daily_note(daily_path: Path):
    daily_path.parent.mkdir(parents=True, exist_ok=True)
    if not daily_path.exists():
        daily_path.write_text(
            f"# {date.today().isoformat()}\n\n## Reading\n\n## Decisions\n\n## Questions\n\n## Next actions\n",
            encoding="utf-8",
        )


def write_conversation_note(
    config: dict, runtime_cfg: dict, run_dir: Path, question_pack: dict, answer: dict, critique: dict | None
) -> Path:
    vault_root = Path(config["vault_root"])
    obs = config["obsidian"]
    today = date.today().isoformat()
    stamp = timestamp_slug()
    title = safe_filename_component(question_pack["title"], max_length=60)
    conversation_path = vault_root / obs["conversation_folder"] / f"{today}-{title}-{stamp}.md"
    daily_path = vault_root / obs["daily_folder"] / f"{today}.md"
    summary_text = "\n".join(bullet_lines(answer["next_actions"]))
    critique_summary = critique["critique_summary"] if critique else "Critique stage skipped."
    artifact_lines = [
        f"- `retrieval_candidates.json`: `{to_portable_path(run_dir / 'retrieval_candidates.json')}`",
        f"- `evidence_brief.json`: `{to_portable_path(run_dir / 'evidence_brief.json')}`",
        f"- `question_pack.json`: `{to_portable_path(run_dir / 'question_pack.json')}`",
        f"- `answer.json`: `{to_portable_path(run_dir / 'answer.json')}`",
        f"- `answer.md`: `{to_portable_path(run_dir / 'answer.md')}`",
    ]
    if critique:
        artifact_lines.extend(
            [
                f"- `critique.json`: `{to_portable_path(run_dir / 'critique.json')}`",
                f"- `critique.md`: `{to_portable_path(run_dir / 'critique.md')}`",
            ]
        )
    lines = [
        f"# {question_pack['title']}",
        "",
        f"- Date: {today}",
        f"- Time: {datetime.now().strftime('%H:%M:%S')}",
        "- Workflow: research-question-flow",
        f"- Run directory: `{to_portable_path(run_dir)}`",
        "",
        "## Core Question",
        "",
        question_pack["core_question"],
        "",
        "## Summary",
        "",
        answer["summary"],
        "",
        "## Direct Answer",
        "",
        answer["direct_answer"],
        "",
        "## Critique Summary",
        "",
        critique_summary,
        "",
        "## Next Actions",
        "",
        summary_text,
        "",
        "## Artifacts",
        "",
    ]
    lines.extend(artifact_lines)
    lines.append("")
    write_text(conversation_path, "\n".join(lines))
    ensure_daily_note(daily_path)
    append_text(daily_path, f"\n## Research question workflow update\n\n- [[{conversation_path.stem}]]\n")
    update_index(
        conversation_path.parent / "_Index.md",
        f"- [[{conversation_path.stem}]]",
        "# Conversation Index\n",
    )
    return conversation_path


def write_question_note(
    config: dict, runtime_cfg: dict, run_dir: Path, question_pack: dict, answer: dict, critique: dict | None
) -> Path:
    vault_root = Path(config["vault_root"])
    folder = vault_root / Path(runtime_cfg["question_folder"])
    folder.mkdir(parents=True, exist_ok=True)
    note_name = safe_filename_component(f"Question - {question_pack['title']}", max_length=90)
    note_path = folder / f"{note_name}.md"

    frontmatter = [
        "---",
        'type: "research-question"',
        f'question: "{sanitize(question_pack["core_question"])}"',
        "related_papers: []",
        "related_concepts: []",
        'status: "open"',
        'importance: "high"',
        "tags:",
        '  - "research-question"',
        '  - "ai-structured"',
        'cssclasses:',
        '  - "research-question-note"',
        "---",
        "",
    ]
    body = [
        "# Question Definition",
        "",
        question_pack["core_question"],
        "",
        "# Why It Matters",
        "",
        question_pack["research_goal"],
        "",
        "# Current Judgment",
        "",
        answer["summary"],
        "",
        "# Direct Answer",
        "",
        answer["direct_answer"],
        "",
        "# Critique Summary",
        "",
        critique["critique_summary"] if critique else "Critique stage skipped.",
        "",
        "# Literature And Evidence Signals",
        "",
    ]
    body.extend(evidence_lines(question_pack["evidence_items"]))
    body.extend(
        [
            "",
            "# Reviewer Pressure Test",
            "",
        ]
    )
    if critique:
        body.extend(critique_issue_lines(critique["critical_issues"]))
    else:
        body.extend(["- Critique stage skipped."])
    body.extend(
        [
            "",
            "# What Is Still Missing",
            "",
        ]
    )
    body.extend(bullet_lines(answer["uncertainties"]))
    if critique:
        body.extend(
            [
                "",
                "# Recommended Checks",
                "",
            ]
        )
        body.extend(bullet_lines(critique["recommended_checks"]))
    body.extend(
        [
            "",
            "# Next Actions",
            "",
        ]
    )
    body.extend(bullet_lines(answer["next_actions"]))
    body.extend(
        [
            "",
            "# Follow-up Questions",
            "",
        ]
    )
    body.extend(bullet_lines(answer["follow_up_questions"]))
    body.extend(
        [
            "",
            "# Run Artifacts",
            "",
            f"- `retrieval_candidates.json`: `{to_portable_path(run_dir / 'retrieval_candidates.json')}`",
            f"- `evidence_brief.json`: `{to_portable_path(run_dir / 'evidence_brief.json')}`",
            f"- `question_pack.json`: `{to_portable_path(run_dir / 'question_pack.json')}`",
            f"- `answer.json`: `{to_portable_path(run_dir / 'answer.json')}`",
            f"- `answer.md`: `{to_portable_path(run_dir / 'answer.md')}`",
        ]
    )
    if critique:
        body.extend(
            [
                f"- `critique.json`: `{to_portable_path(run_dir / 'critique.json')}`",
                f"- `critique.md`: `{to_portable_path(run_dir / 'critique.md')}`",
            ]
        )
    body.append("")
    write_text(note_path, "\n".join(frontmatter + body))
    update_index(
        note_path.parent / "_Index.md",
        f"- [[{note_path.stem}]]",
        "# Research Question Index\n",
    )
    return note_path


def create_run_dir(config: dict, runtime_cfg: dict, title: str, explicit_dir: str | None) -> Path:
    if explicit_dir:
        run_dir = Path(explicit_dir)
        run_dir.mkdir(parents=True, exist_ok=True)
        return run_dir

    output_root = Path(config["output_root"])
    date_part = date.today().isoformat()
    stamp = timestamp_slug()
    run_dir = output_root / runtime_cfg["report_folder_name"] / f"{date_part}-{slugify(title)}-{stamp}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def finalize_run(
    config: dict,
    runtime_cfg: dict,
    run_dir: Path,
    question_pack: dict,
    answer: dict,
    answer_raw_response: dict,
    critique: dict | None,
    critique_raw_response: dict | None,
    write_vault: bool,
):
    meta = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "extract_model": runtime_cfg["extract_model"],
        "reason_model": runtime_cfg["reason_model"],
        "critic_model": runtime_cfg["critic_model"] if critique else "disabled",
        "run_dir": to_portable_path(run_dir),
    }
    markdown = render_answer_markdown(question_pack, answer, critique, meta)
    write_text(run_dir / "answer.md", markdown)
    write_json(run_dir / "answer.json", answer)
    write_json(run_dir / "answer_response.json", answer_raw_response)
    if critique:
        write_text(run_dir / "critique.md", render_critique_markdown(question_pack, answer, critique, meta))
        write_json(run_dir / "critique.json", critique)
    if critique_raw_response:
        write_json(run_dir / "critique_response.json", critique_raw_response)
    write_json(run_dir / "run_meta.json", meta)

    outputs = {
        "run_dir": to_portable_path(run_dir),
        "retrieval_candidates": to_portable_path(run_dir / "retrieval_candidates.json"),
        "evidence_brief": to_portable_path(run_dir / "evidence_brief.json"),
        "question_pack": to_portable_path(run_dir / "question_pack.json"),
        "answer_json": to_portable_path(run_dir / "answer.json"),
        "answer_markdown": to_portable_path(run_dir / "answer.md"),
    }
    if critique:
        outputs["critique_json"] = to_portable_path(run_dir / "critique.json")
        outputs["critique_markdown"] = to_portable_path(run_dir / "critique.md")
    if write_vault:
        outputs["conversation_note"] = to_portable_path(
            write_conversation_note(config, runtime_cfg, run_dir, question_pack, answer, critique)
        )
        outputs["question_note"] = to_portable_path(
            write_question_note(config, runtime_cfg, run_dir, question_pack, answer, critique)
        )
    return outputs


def run_prepare(args):
    config = load_json(Path(args.config))
    runtime_cfg = resolve_qa_config(config)
    snapshot = load_input_snapshot(args)
    snapshot, retrieval_debug = attach_auto_evidence(config, runtime_cfg, snapshot, args.skip_auto_evidence)
    run_dir = create_run_dir(config, runtime_cfg, snapshot["title"], args.output_dir)
    write_json(run_dir / "input_snapshot.json", snapshot)
    write_json(run_dir / "retrieval_candidates.json", retrieval_debug)
    write_json(run_dir / "evidence_brief.json", snapshot.get("evidence_brief", {}))
    question_pack = prepare_question_pack(config, runtime_cfg, run_dir, snapshot)
    write_json(run_dir / "question_pack.json", question_pack)
    print(to_portable_path(run_dir / "question_pack.json"))


def run_answer(args):
    config = load_json(Path(args.config))
    runtime_cfg = resolve_qa_config(config)
    question_pack_path = Path(args.question_pack)
    run_dir = question_pack_path.parent
    question_pack = load_json(question_pack_path)
    answer, answer_raw_response = answer_question_pack(runtime_cfg, question_pack)
    critique = None
    critique_raw_response = None
    if runtime_cfg["enable_critique"] and not args.skip_critique:
        critique, critique_raw_response = critique_question_answer(runtime_cfg, question_pack, answer)
    outputs = finalize_run(
        config,
        runtime_cfg,
        run_dir,
        question_pack,
        answer,
        answer_raw_response,
        critique,
        critique_raw_response,
        not args.skip_vault_write,
    )
    print(json.dumps(outputs, ensure_ascii=False, indent=2))


def run_full(args):
    config = load_json(Path(args.config))
    runtime_cfg = resolve_qa_config(config)
    snapshot = load_input_snapshot(args)
    snapshot, retrieval_debug = attach_auto_evidence(config, runtime_cfg, snapshot, args.skip_auto_evidence)
    run_dir = create_run_dir(config, runtime_cfg, snapshot["title"], args.output_dir)
    write_json(run_dir / "input_snapshot.json", snapshot)
    write_json(run_dir / "retrieval_candidates.json", retrieval_debug)
    write_json(run_dir / "evidence_brief.json", snapshot.get("evidence_brief", {}))
    question_pack = prepare_question_pack(config, runtime_cfg, run_dir, snapshot)
    write_json(run_dir / "question_pack.json", question_pack)
    answer, answer_raw_response = answer_question_pack(runtime_cfg, question_pack)
    critique = None
    critique_raw_response = None
    if runtime_cfg["enable_critique"] and not args.skip_critique:
        critique, critique_raw_response = critique_question_answer(runtime_cfg, question_pack, answer)
    outputs = finalize_run(
        config,
        runtime_cfg,
        run_dir,
        question_pack,
        answer,
        answer_raw_response,
        critique,
        critique_raw_response,
        not args.skip_vault_write,
    )
    print(json.dumps(outputs, ensure_ascii=False, indent=2))


def add_input_arguments(parser):
    parser.add_argument("--config", required=True)
    parser.add_argument("--title", help="Optional short title for the research question run.")
    parser.add_argument("--question", help="Raw academic question text.")
    parser.add_argument("--question-file", help="Path to a text or markdown file containing the raw question.")
    parser.add_argument(
        "--evidence-file",
        action="append",
        default=[],
        help="Path to a text or markdown file that should be treated as evidence input. Repeat for multiple files.",
    )
    parser.add_argument(
        "--evidence-text",
        action="append",
        default=[],
        help="Inline evidence text. Repeat for multiple snippets.",
    )
    parser.add_argument("--output-dir", help="Optional explicit run directory.")
    parser.add_argument("--skip-auto-evidence", action="store_true")


def main():
    parser = argparse.ArgumentParser(description="Structure and answer complex academic questions with the Responses API.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare_parser = subparsers.add_parser("prepare", help="Create a structured question pack from raw inputs.")
    add_input_arguments(prepare_parser)
    prepare_parser.set_defaults(func=run_prepare)

    answer_parser = subparsers.add_parser("answer", help="Answer an existing question pack and write reports.")
    answer_parser.add_argument("--config", required=True)
    answer_parser.add_argument("--question-pack", required=True)
    answer_parser.add_argument("--skip-vault-write", action="store_true")
    answer_parser.add_argument("--skip-critique", action="store_true")
    answer_parser.set_defaults(func=run_answer)

    run_parser = subparsers.add_parser("run", help="Prepare a question pack, answer it, and write outputs.")
    add_input_arguments(run_parser)
    run_parser.add_argument("--skip-vault-write", action="store_true")
    run_parser.add_argument("--skip-critique", action="store_true")
    run_parser.set_defaults(func=run_full)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
