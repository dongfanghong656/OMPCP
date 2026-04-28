#!/usr/bin/env python
from __future__ import annotations

import argparse
import html
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import paper_dossiers
import translate_paper


HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
IMAGE_RE = re.compile(r"^!\[[^\]]*\]\(([^)]+)\)\s*$")
MATH_BLOCK_START_RE = re.compile(r"^\$\$\s*$")
CALLOUT_HEADER_RE = re.compile(r"^>\s*\[!([^\]]+)\]")
SENTENCE_SPLIT_RE = re.compile(r"(?<=[。！？.!?])\s+")
NON_ANCHOR_RE = re.compile(r"[^0-9A-Za-z\u4e00-\u9fff]+")
NUMBER_RE = re.compile(r"\b\d+(?:\.\d+)?(?:\s?(?:dB|mm|μm|um|nm|kHz|Hz|%|times/s))?\b", re.I)
EN_WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9/-]*")
ZH_TERM_RE = re.compile(r"[\u4e00-\u9fff]{2,20}")


def emit_json(payload: dict[str, Any]) -> None:
    sys.stdout.buffer.write((json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8"))


@dataclass(frozen=True)
class QuestionSpec:
    id: str
    short_label: str
    title: str
    color: str
    keywords: tuple[str, ...]


@dataclass
class SectionInfo:
    anchor: str
    title: str
    family: str
    level: int


@dataclass
class ContentBlock:
    kind: str
    index: int
    section: SectionInfo
    original_text: str = ""
    translated_text: str = ""
    image_src: str = ""
    original_caption: str = ""
    translated_caption: str = ""
    equation_text: str = ""
    primary_question_id: str = "Q10"
    secondary_question_ids: list[str] = field(default_factory=list)
    paragraph_function: str = ""
    logic_role: str = ""
    question_layer: str = ""


@dataclass
class DocumentPayload:
    title: str
    title_original: str
    course_info: str
    source_md: Path | None
    translated_md: Path | None
    blocks: list[ContentBlock]
    sections: list[SectionInfo]
    questions: list[QuestionSpec]


QUESTION_COLORS = {
    "Q1": "#d9a441",
    "Q2": "#d4694c",
    "Q3": "#4377d6",
    "Q4": "#2d9079",
    "Q5": "#8a56d8",
    "Q6": "#2b88b8",
    "Q7": "#d94c77",
    "Q8": "#7b8794",
    "Q9": "#df7a3d",
    "Q10": "#3a9f74",
}

QUESTION_BLUEPRINTS: dict[str, dict[str, Any]] = {
    "Q1": {
        "families": {"abstract", "introduction"},
        "cue_terms": ("problem", "challenge", "limited", "缺口", "受限", "degraded", "motivation", "背景"),
        "title_template": "“{focus}”的关键问题是什么？",
        "fallback_focus": "研究切口",
    },
    "Q2": {
        "families": {"abstract", "introduction", "discussion"},
        "cue_terms": ("we demonstrate", "we show", "propose", "enable", "提出", "证明", "结论", "claim"),
        "title_template": "作者对“{focus}”的核心主张是什么？",
        "fallback_focus": "核心主张",
    },
    "Q3": {
        "families": {"methods"},
        "cue_terms": ("approximation", "autocorrelation", "ipsf", "mtf", "theory", "定义", "原理", "model"),
        "title_template": "“{focus}”背后的理论机制是什么？",
        "fallback_focus": "理论机制",
    },
    "Q4": {
        "families": {"methods"},
        "cue_terms": ("experiment", "setup", "phantom", "offset", "a-scan", "实验", "体模", "采集", "protocol"),
        "title_template": "作者如何实现“{focus}”？",
        "fallback_focus": "方法路径",
    },
    "Q5": {
        "families": {"results"},
        "cue_terms": ("measured", "results", "improved", "critical", "测得", "结果", "提升", "increase"),
        "title_template": "哪些结果最能证明“{focus}”有效？",
        "fallback_focus": "关键结果",
    },
    "Q6": {
        "families": {"results", "discussion"},
        "cue_terms": ("validate", "validation", "compare", "control", "对照", "验证", "客观", "comparison"),
        "title_template": "“{focus}”是怎样被验证的？",
        "fallback_focus": "验证逻辑",
    },
    "Q7": {
        "families": {"abstract", "discussion"},
        "cue_terms": ("first", "opportunities", "contribution", "novel", "首次", "贡献", "意义", "advance"),
        "title_template": "“{focus}”的创新贡献在哪里？",
        "fallback_focus": "创新贡献",
    },
    "Q8": {
        "families": {"introduction", "discussion"},
        "cue_terms": ("slow", "challenging", "may", "limited", "noise", "局限", "挑战", "风险", "however"),
        "title_template": "围绕“{focus}”还存在哪些局限？",
        "fallback_focus": "局限边界",
    },
    "Q9": {
        "families": {"discussion", "introduction", "results"},
        "cue_terms": ("retina", "clinical", "adaptive optics", "ao", "flow velocity", "视网膜", "临床", "应用", "translation"),
        "title_template": "“{focus}”与更大 OCT 主线有什么关系？",
        "fallback_focus": "OCT 主线",
    },
    "Q10": {
        "families": {"discussion", "other", "references"},
        "cue_terms": ("approach", "framework", "guidance", "used", "框架", "路径", "可复用", "评价", "metric"),
        "title_template": "从“{focus}”能提炼出哪些可复用方法？",
        "fallback_focus": "复用框架",
    },
}

EN_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "been", "being", "between", "by", "for", "from", "how",
    "in", "into", "is", "it", "its", "of", "on", "or", "our", "paper", "study", "that", "the", "their",
    "this", "those", "through", "to", "using", "via", "we", "with",
}
BAD_FOCUS_STARTS = {
    "approach", "author", "demonstrate", "demonstrates", "effect", "improve", "improved", "improves", "method",
    "methods", "new", "novel", "paper", "propose", "proposed", "quantification", "result", "results",
    "separate", "separating", "show", "shows", "study", "using", "validate", "validated",
}
BAD_FOCUS_ENDS = {"approach", "beam", "method", "methods", "paper", "result", "results", "study"}
BAD_FOCUS_TRAILS = {"beam", "improved", "improves", "increased", "separate", "separating", "using", "validated"}
GENERIC_ZH_TERMS = {
    "一种", "作者", "分析", "创新", "实验", "工作", "引言", "意义", "挑战", "方法", "结果", "背景", "论文", "讨论",
    "证明", "贡献", "结论", "问题", "路径", "验证", "评价", "本文", "研究", "设计", "过程", "系统",
}


def question_lookup(questions: list[QuestionSpec]) -> dict[str, QuestionSpec]:
    return {question.id: question for question in questions}


def normalize_whitespace(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def slugify_anchor(text: str) -> str:
    slug = NON_ANCHOR_RE.sub("-", normalize_whitespace(text)).strip("-").lower()
    return slug or "section"


def section_family(title: str) -> str:
    lowered = normalize_whitespace(title).lower()
    if any(token in lowered for token in ("abstract", "摘要")):
        return "abstract"
    if any(token in lowered for token in ("introduction", "引言", "背景")):
        return "introduction"
    if any(token in lowered for token in ("theoretical", "principle", "method", "methods", "原理", "方法", "理论")):
        return "methods"
    if any(token in lowered for token in ("result", "results", "experiment", "实验", "结果")):
        return "results"
    if any(token in lowered for token in ("discussion", "结论", "conclusion", "讨论")):
        return "discussion"
    if any(token in lowered for token in ("reference", "参考文献")):
        return "references"
    return "other"


def first_sentence(text: str, limit: int = 160) -> str:
    cleaned = normalize_whitespace(text)
    if not cleaned:
        return ""
    parts = SENTENCE_SPLIT_RE.split(cleaned)
    sentence = parts[0] if parts else cleaned
    if len(sentence) <= limit:
        return sentence
    return sentence[: limit - 1].rstrip() + "…"


def sentences(text: str, count: int = 2) -> str:
    cleaned = normalize_whitespace(text)
    if not cleaned:
        return ""
    parts = [part for part in SENTENCE_SPLIT_RE.split(cleaned) if part]
    chosen = " ".join(parts[:count]) if parts else cleaned
    if len(chosen) <= 220:
        return chosen
    return chosen[:219].rstrip() + "…"


def block_search_text(block: ContentBlock) -> str:
    return normalize_whitespace(
        " ".join(
            [
                block.original_text,
                block.translated_text,
                block.original_caption,
                block.translated_caption,
                block.equation_text,
            ]
        )
    )


def add_unique(values: list[str], seen: set[str], candidate: str) -> None:
    clean = normalize_whitespace(candidate).strip("\"'“”‘’.,;:()[]{}")
    if not clean:
        return
    key = clean.casefold()
    if key in seen:
        return
    seen.add(key)
    values.append(clean)


def extract_focus_candidates(text: str, *, limit: int = 12, prefer_short: bool = False) -> list[str]:
    normalized = normalize_whitespace(text)
    if not normalized:
        return []

    candidates: list[str] = []
    seen: set[str] = set()
    segments = [segment for segment in re.split(r"[|:;/()\[\]{}]+", normalized) if normalize_whitespace(segment)]
    segments.append(normalized)

    for segment in segments:
        clean_segment = normalize_whitespace(segment)
        if not clean_segment:
            continue

        for match in ZH_TERM_RE.findall(clean_segment):
            if 2 <= len(match) <= 16 and match not in GENERIC_ZH_TERMS:
                add_unique(candidates, seen, match)
                if len(candidates) >= limit:
                    return candidates

        words = [word for word in EN_WORD_RE.findall(clean_segment) if word.lower() not in EN_STOPWORDS]
        ngram_order = (2, 3) if prefer_short else (3, 2)
        for n in ngram_order:
            if len(words) < n:
                continue
            for index in range(len(words) - n + 1):
                phrase = " ".join(words[index : index + n])
                add_unique(candidates, seen, phrase)
                if len(candidates) >= limit:
                    return candidates

        for word in words:
            if len(word) >= 4 or word.isupper():
                add_unique(candidates, seen, word)
                if len(candidates) >= limit:
                    return candidates

    return candidates


def focus_candidate_score(candidate: str, title_focuses: list[str]) -> int:
    score = 0
    lowered = candidate.casefold()
    words = [word.lower() for word in EN_WORD_RE.findall(candidate)]
    title_words = {
        word.lower()
        for focus in title_focuses
        for word in EN_WORD_RE.findall(focus)
        if word.lower() not in EN_STOPWORDS
    }

    if re.search(r"[\u4e00-\u9fff]", candidate):
        score += min(len(candidate), 10)
        if candidate in GENERIC_ZH_TERMS:
            score -= 4
    elif words:
        score += len(words) * 2
        overlap = len(set(words) & title_words)
        score += overlap * 3
        if words[0] in BAD_FOCUS_STARTS:
            score -= 4
        if words[-1] in BAD_FOCUS_ENDS:
            score -= 2
        if any(word.isupper() for word in EN_WORD_RE.findall(candidate)):
            score += 1

    if any(focus.casefold() == lowered for focus in title_focuses):
        score += 4
    return score


def sanitize_focus_phrase(candidate: str) -> str:
    phrase = normalize_whitespace(candidate)
    if not phrase:
        return phrase
    if re.search(r"[\u4e00-\u9fff]", phrase):
        return phrase[:18]

    words = EN_WORD_RE.findall(phrase)
    while len(words) > 1 and words[0].lower() in BAD_FOCUS_STARTS:
        words = words[1:]
    while len(words) > 1 and words[-1].lower() in BAD_FOCUS_ENDS:
        words = words[:-1]
    while len(words) > 1 and words[-1].lower() in BAD_FOCUS_TRAILS:
        words = words[:-1]
    if len(words) > 4:
        words = words[:4]
    return " ".join(words) if words else phrase


def choose_focus_phrase(
    question_id: str,
    *,
    anchor_text: str,
    title_focuses: list[str],
    section_title: str,
) -> str:
    blueprint = QUESTION_BLUEPRINTS[question_id]
    anchor_candidates = extract_focus_candidates(anchor_text)
    section_candidates = extract_focus_candidates(section_title, limit=4)

    if anchor_candidates:
        best_anchor = max(anchor_candidates, key=lambda value: focus_candidate_score(value, title_focuses))
        if focus_candidate_score(best_anchor, title_focuses) >= 8:
            focus = best_anchor
        else:
            combined = [*section_candidates, *title_focuses, *anchor_candidates]
            ordered = sorted(
                enumerate(combined),
                key=lambda item: (-focus_candidate_score(item[1], title_focuses), item[0]),
            )
            focus = combined[ordered[0][0]]
    else:
        combined = [*section_candidates, *title_focuses]
        if combined:
            ordered = sorted(
                enumerate(combined),
                key=lambda item: (-focus_candidate_score(item[1], title_focuses), item[0]),
            )
            focus = combined[ordered[0][0]]
        else:
            focus = blueprint["fallback_focus"]

    return sanitize_focus_phrase(focus)


def build_question_keywords(question_id: str, focus: str, anchor_text: str, title_focuses: list[str]) -> tuple[str, ...]:
    candidates = []
    seen: set[str] = set()
    for value in [focus, *extract_focus_candidates(anchor_text, limit=8), *title_focuses]:
        add_unique(candidates, seen, value)
        if len(candidates) >= 6:
            break
    if not candidates:
        for cue_term in QUESTION_BLUEPRINTS[question_id]["cue_terms"][:4]:
            add_unique(candidates, seen, cue_term)
    return tuple(candidates[:6])


def select_anchor_block(blocks: list[ContentBlock], question_id: str) -> ContentBlock | None:
    blueprint = QUESTION_BLUEPRINTS[question_id]
    preferred_families = blueprint["families"]
    cue_terms = [term.lower() for term in blueprint["cue_terms"]]
    best_block: ContentBlock | None = None
    best_score = -10**9

    for position, block in enumerate(blocks):
        text = block_search_text(block)
        if not text:
            continue
        lower = text.lower()
        score = 0
        if block.section.family in preferred_families:
            score += 6
        if block.kind == "equation" and question_id == "Q3":
            score += 4
        if block.kind == "image" and question_id in {"Q5", "Q6"}:
            score += 2
        if question_id in {"Q1", "Q2"} and position < 5:
            score += 2
        if question_id in {"Q7", "Q8", "Q9", "Q10"} and block.section.family == "discussion":
            score += 2
        if question_id in {"Q5", "Q6"} and NUMBER_RE.search(text):
            score += 3
        score += sum(1 for cue_term in cue_terms if cue_term in lower)
        if score > best_score:
            best_score = score
            best_block = block

    return best_block


def generate_questions(
    *,
    title: str,
    title_original: str,
    blocks: list[ContentBlock],
    sections: list[SectionInfo],
) -> list[QuestionSpec]:
    title_focuses = extract_focus_candidates(
        " | ".join(filter(None, [title, title_original])),
        limit=8,
        prefer_short=True,
    )
    if not title_focuses:
        title_focuses = [title_original or title or "论文主题"]

    generated: list[QuestionSpec] = []
    for question_id, blueprint in QUESTION_BLUEPRINTS.items():
        anchor_block = select_anchor_block(blocks, question_id)
        if anchor_block is not None and anchor_block.kind == "equation":
            anchor_text = anchor_block.section.title
        else:
            anchor_text = block_search_text(anchor_block) if anchor_block is not None else " ".join(title_focuses)
        section_title = anchor_block.section.title if anchor_block is not None else (sections[0].title if sections else "")
        focus = choose_focus_phrase(
            question_id,
            anchor_text=anchor_text,
            title_focuses=title_focuses,
            section_title=section_title,
        )
        generated.append(
            QuestionSpec(
                question_id,
                question_id,
                blueprint["title_template"].format(focus=focus),
                QUESTION_COLORS[question_id],
                build_question_keywords(question_id, focus, anchor_text, title_focuses),
            )
        )

    return generated


def highlighted_html(text: str, question_ids: list[str], lookup: dict[str, QuestionSpec]) -> str:
    clean = normalize_whitespace(text)
    if not clean:
        return ""

    spans: list[tuple[int, int, str]] = []
    for question_id in question_ids[:2]:
        question = lookup[question_id]
        for keyword in question.keywords:
            pattern = re.compile(re.escape(keyword), re.I)
            match = pattern.search(clean)
            if match:
                spans.append((match.start(), match.end(), question_id))
                break

    if not spans:
        number_match = NUMBER_RE.search(clean)
        if number_match:
            spans.append((number_match.start(), number_match.end(), question_ids[0]))
        else:
            words = clean.split()
            fallback = " ".join(words[: min(9, len(words))])
            end = len(fallback)
            spans.append((0, end, question_ids[0]))

    spans = sorted(spans, key=lambda item: item[0])
    merged: list[tuple[int, int, str]] = []
    last_end = -1
    for start, end, question_id in spans:
        if start < last_end:
            continue
        merged.append((start, end, question_id))
        last_end = end

    pieces: list[str] = []
    cursor = 0
    for start, end, question_id in merged:
        pieces.append(html.escape(clean[cursor:start]))
        pieces.append(
            f'<mark class="mark {question_id.lower()}">{html.escape(clean[start:end])}</mark>'
        )
        cursor = end
    pieces.append(html.escape(clean[cursor:]))
    return "".join(pieces)


def load_translations(template_path: Path) -> dict[str, str]:
    payload = json.loads(template_path.read_text(encoding="utf-8-sig"))
    translations: dict[str, str] = {}
    for block in payload.get("blocks", []):
        block_id = normalize_whitespace(block.get("id"))
        translation = normalize_whitespace(block.get("translation"))
        if block_id and translation:
            translations[block_id] = translation
    return translations


def build_document_from_template(
    *,
    source_md: Path,
    template_path: Path,
    title: str,
    title_original: str,
    course_info: str,
) -> DocumentPayload:
    parsed_blocks = translate_paper.parse_markdown_blocks(source_md)
    translate_paper.collect_translatable_items(title_original or title, parsed_blocks)
    translations = load_translations(template_path)

    overview = SectionInfo(anchor="section-overview", title="Overview", family="other", level=1)
    current_section = overview
    sections: list[SectionInfo] = []
    content_blocks: list[ContentBlock] = []
    paragraph_index = 1

    for block in parsed_blocks:
        if block.get("skip_render"):
            continue
        kind = block["kind"]

        if kind == "heading":
            translated_heading = translations.get(block["id"], block["text"])
            level = int(block.get("level", 1))
            current_section = SectionInfo(
                anchor=f"section-{slugify_anchor(translated_heading)}",
                title=translated_heading,
                family=section_family(translated_heading),
                level=level,
            )
            sections.append(current_section)
            continue

        if kind == "paragraph":
            content_blocks.append(
                ContentBlock(
                    kind="paragraph",
                    index=paragraph_index,
                    section=current_section,
                    original_text=block["text"],
                    translated_text=translations.get(block["id"], block["text"]),
                )
            )
            paragraph_index += 1
            continue

        if kind == "equation":
            content_blocks.append(
                ContentBlock(
                    kind="equation",
                    index=paragraph_index,
                    section=current_section,
                    equation_text=block["text"],
                    translated_text="公式块保留原样，用于支持该节的理论关系与量化推导。",
                )
            )
            paragraph_index += 1
            continue

        if kind == "image":
            translated_caption = " ".join(
                translations.get(caption_block["id"], caption_block["text"])
                for caption_block in block.get("caption_blocks", [])
                if normalize_whitespace(caption_block.get("text"))
            )
            original_caption = " ".join(
                normalize_whitespace(caption_block.get("text"))
                for caption_block in block.get("caption_blocks", [])
                if normalize_whitespace(caption_block.get("text"))
            )
            content_blocks.append(
                ContentBlock(
                    kind="image",
                    index=paragraph_index,
                    section=current_section,
                    image_src=block.get("image_path", ""),
                    original_caption=original_caption,
                    translated_caption=translated_caption,
                    translated_text=translated_caption or "图像块保留原样，主要承担证据呈现功能。",
                )
            )
            paragraph_index += 1

    return finalize_document(
        title=title,
        title_original=title_original,
        course_info=course_info,
        source_md=source_md,
        translated_md=None,
        blocks=content_blocks,
        sections=sections,
    )


def build_document_from_translated_markdown(
    *,
    translated_md: Path,
    title: str = "",
    title_original: str = "",
    course_info: str,
    source_md: Path | None = None,
) -> DocumentPayload:
    frontmatter, body = paper_dossiers.split_frontmatter(
        translated_md.read_text(encoding="utf-8", errors="replace")
    )
    resolved_title = normalize_whitespace(title) or normalize_whitespace(frontmatter.get("title")) or translated_md.stem
    resolved_original_title = (
        normalize_whitespace(title_original)
        or normalize_whitespace(frontmatter.get("paper_title_original"))
        or normalize_whitespace(frontmatter.get("title_original"))
        or resolved_title
    )

    lines = body.splitlines()
    overview = SectionInfo(anchor="section-overview", title="Overview", family="other", level=1)
    current_section = overview
    sections: list[SectionInfo] = []
    content_blocks: list[ContentBlock] = []
    paragraph_index = 1
    pending_block: ContentBlock | None = None
    i = 0

    while i < len(lines):
        raw = lines[i].rstrip()
        stripped = raw.strip()

        if not stripped:
            i += 1
            continue

        heading_match = HEADING_RE.match(stripped)
        if heading_match:
            heading_text = normalize_whitespace(heading_match.group(2))
            if heading_text and heading_text != resolved_title:
                current_section = SectionInfo(
                    anchor=f"section-{slugify_anchor(heading_text)}",
                    title=heading_text,
                    family=section_family(heading_text),
                    level=len(heading_match.group(1)),
                )
                sections.append(current_section)
            pending_block = None
            i += 1
            continue

        if stripped.startswith("> [!quote]- Original"):
            original_lines: list[str] = []
            i += 1
            while i < len(lines) and lines[i].startswith(">"):
                original_line = lines[i][1:].lstrip()
                if original_line and not original_line.startswith("[!"):
                    original_lines.append(original_line)
                i += 1
            if pending_block is not None:
                text_value = normalize_whitespace(" ".join(original_lines))
                if pending_block.kind == "image":
                    pending_block.original_caption = text_value
                else:
                    pending_block.original_text = text_value
            continue

        callout_match = CALLOUT_HEADER_RE.match(stripped)
        if callout_match:
            i += 1
            while i < len(lines) and lines[i].startswith(">"):
                i += 1
            pending_block = None
            continue

        image_match = IMAGE_RE.match(stripped)
        if image_match:
            image_src = image_match.group(1)
            translated_caption = ""
            j = i + 1
            if j < len(lines):
                maybe_caption = lines[j].strip()
                if maybe_caption.startswith("_") and maybe_caption.endswith("_"):
                    translated_caption = maybe_caption.strip("_").strip()
                    i = j
            block = ContentBlock(
                kind="image",
                index=paragraph_index,
                section=current_section,
                image_src=image_src,
                translated_caption=translated_caption,
                translated_text=translated_caption or "图像块保留原样，主要承担证据呈现功能。",
            )
            content_blocks.append(block)
            pending_block = block
            paragraph_index += 1
            i += 1
            continue

        if MATH_BLOCK_START_RE.match(stripped):
            equation_lines = [stripped]
            i += 1
            while i < len(lines):
                equation_lines.append(lines[i].rstrip())
                if MATH_BLOCK_START_RE.match(lines[i].strip()):
                    i += 1
                    break
                i += 1
            content_blocks.append(
                ContentBlock(
                    kind="equation",
                    index=paragraph_index,
                    section=current_section,
                    equation_text="\n".join(equation_lines),
                    translated_text="公式块保留原样，用于支持该节的理论关系与量化推导。",
                )
            )
            pending_block = None
            paragraph_index += 1
            continue

        paragraph_lines = [stripped]
        i += 1
        while i < len(lines):
            probe = lines[i].strip()
            if not probe:
                break
            if HEADING_RE.match(probe) or IMAGE_RE.match(probe) or probe.startswith("> [!quote]- Original"):
                break
            if CALLOUT_HEADER_RE.match(probe) or MATH_BLOCK_START_RE.match(probe):
                break
            paragraph_lines.append(probe)
            i += 1

        paragraph_text = normalize_whitespace(" ".join(paragraph_lines))
        block = ContentBlock(
            kind="paragraph",
            index=paragraph_index,
            section=current_section,
            translated_text=paragraph_text,
        )
        content_blocks.append(block)
        pending_block = block
        paragraph_index += 1

    resolved_source_md = source_md
    if resolved_source_md is None:
        source_text = normalize_whitespace(frontmatter.get("source_extract") or frontmatter.get("source_md"))
        if source_text:
            resolved_source_md = Path(source_text.replace("\\", "/"))

    return finalize_document(
        title=resolved_title,
        title_original=resolved_original_title,
        course_info=course_info,
        source_md=resolved_source_md,
        translated_md=translated_md,
        blocks=content_blocks,
        sections=sections,
    )


def finalize_document(
    *,
    title: str,
    title_original: str,
    course_info: str,
    source_md: Path | None,
    translated_md: Path | None,
    blocks: list[ContentBlock],
    sections: list[SectionInfo],
) -> DocumentPayload:
    if not sections:
        sections = [SectionInfo(anchor="section-body", title="正文", family="other", level=2)]
        for block in blocks:
            block.section = sections[0]

    questions = generate_questions(
        title=title,
        title_original=title_original,
        blocks=blocks,
        sections=sections,
    )
    assign_question_annotations(blocks, questions)

    return DocumentPayload(
        title=title,
        title_original=title_original,
        course_info=course_info,
        source_md=source_md,
        translated_md=translated_md,
        blocks=blocks,
        sections=sections,
        questions=questions,
    )


def assign_question_annotations(blocks: list[ContentBlock], questions: list[QuestionSpec]) -> None:
    for block in blocks:
        primary, secondary = choose_questions(block, questions)
        block.primary_question_id = primary
        block.secondary_question_ids = secondary
        block.paragraph_function = infer_paragraph_function(block)
        block.logic_role = infer_logic_role(block)
        secondary_text = "、".join(secondary[:2]) if secondary else "无次级映射"
        block.question_layer = f"直接回答 {primary}，并与 {secondary_text} 形成互证。"


def choose_questions(block: ContentBlock, questions: list[QuestionSpec]) -> tuple[str, list[str]]:
    scores = {question.id: 0 for question in questions}
    family = block.section.family
    text = normalize_whitespace(
        f"{block.original_text} {block.translated_text} {block.original_caption} {block.translated_caption}"
    ).lower()

    family_boosts = {
        "abstract": {"Q1": 2, "Q2": 3, "Q5": 2, "Q7": 1},
        "introduction": {"Q1": 3, "Q2": 1, "Q8": 1, "Q9": 1},
        "methods": {"Q3": 3, "Q4": 3, "Q6": 1},
        "results": {"Q5": 3, "Q6": 2, "Q4": 1},
        "discussion": {"Q7": 2, "Q8": 2, "Q9": 2, "Q10": 2, "Q2": 1},
        "references": {"Q10": 2, "Q8": 1},
        "other": {"Q10": 1},
    }
    for question_id, boost in family_boosts.get(family, family_boosts["other"]).items():
        scores[question_id] += boost

    if block.kind == "equation":
        scores["Q3"] += 3
        scores["Q4"] += 1
    if block.kind == "image":
        scores["Q5"] += 2
        scores["Q6"] += 1

    for question in questions:
        for keyword in [*question.keywords, *QUESTION_BLUEPRINTS[question.id]["cue_terms"]]:
            if keyword.lower() in text:
                scores[question.id] += 1

    if NUMBER_RE.search(text):
        scores["Q5"] += 1
        scores["Q6"] += 1
    if any(token in text for token in ("however", "but", "challenge", "risk", "although", "however,")):
        scores["Q8"] += 1
    if any(token in text for token in ("we demonstrate", "we show", "本文提出", "本文展示")):
        scores["Q2"] += 2
        scores["Q7"] += 1

    ordered = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    primary = ordered[0][0]
    secondary = [question_id for question_id, score in ordered[1:] if score > 0][:2]
    return primary, secondary


def infer_paragraph_function(block: ContentBlock) -> str:
    family = block.section.family
    text = normalize_whitespace(block.translated_text or block.original_text or block.translated_caption)
    lower = text.lower()
    if block.kind == "equation":
        return "把文字主张压缩成可计算的数学关系，供后文量化与验证。"
    if block.kind == "image":
        return "把前文论证落实到图像证据或图注说明，承担直观展示功能。"
    if family == "abstract":
        return "用最短篇幅交代问题、方法、结果和意义，是全文的压缩预告。"
    if family == "introduction":
        if any(token in lower for token in ("however", "limited", "受限", "challenge", "缺失")):
            return "指出现有路线的不足，逼出本文必须回答的关键缺口。"
        return "搭建研究背景，说明为什么这个问题值得单独研究。"
    if family == "methods":
        return "定义变量、系统结构或实验路径，让核心主张有可执行载体。"
    if family == "results":
        return "给出实测现象或定量结果，把方法有效性转成证据。"
    if family == "discussion":
        return "把局部结果外推到更广的解释、应用或边界判断。"
    if family == "references":
        return "该段属于参考文献信息，用于交代证据来源与前序文献链。"
    return "补充正文中的定义、证据或上下文，使论证更加完整。"


def infer_logic_role(block: ContentBlock) -> str:
    family = block.section.family
    text = normalize_whitespace(block.translated_text or block.original_text or block.translated_caption)
    lower = text.lower()
    if block.kind == "equation":
        return "先把物理对象形式化，再为后文的参数估计、图像解释和定量比较提供统一坐标系。"
    if block.kind == "image":
        return "图像证据把抽象主张落到可见差异上，帮助读者判断趋势是否真实而非口头描述。"
    if family == "introduction" and any(token in lower for token in ("however", "limited", "受限", "challenge", "缺失")):
        return "先承认既有成像手段的价值，再指出它们在当前问题上仍有不可绕开的盲区。"
    if family == "methods":
        return "把主张拆成可测变量和可复现实验步骤，减少“只是概念宣称”的空间。"
    if family == "results":
        return "通过数字、对照或曲线把“能做到”升级成“已经被看到并可量化”。"
    if family == "discussion":
        return "把结果与更广泛的研究语境连接起来，同时交代其外推时应注意的边界条件。"
    if family == "references":
        return "这一段不直接承载作者新结论，但决定读者能否追溯其理论与实验来源。"
    return "这段更多承担承上启下作用，把前文问题与后文结论串成连续推理。"


def resolve_from_paper_note(note_path: Path) -> dict[str, Any]:
    frontmatter, _body = paper_dossiers.split_frontmatter(
        note_path.read_text(encoding="utf-8", errors="replace")
    )
    payload = {
        "title": normalize_whitespace(
            frontmatter.get("title_display")
            or frontmatter.get("title_zh")
            or frontmatter.get("title")
            or note_path.stem
        ),
        "title_original": normalize_whitespace(
            frontmatter.get("title_original")
            or frontmatter.get("title_en")
            or frontmatter.get("title")
            or note_path.stem
        ),
        "source_md": normalize_whitespace(frontmatter.get("extract_path")),
        "translated_md": normalize_whitespace(frontmatter.get("translated_note_path")),
        "translation_template": normalize_whitespace(frontmatter.get("translation_template_path")),
    }
    return payload


def worksheet_cards(document: DocumentPayload) -> list[dict[str, str]]:
    limitation_pool = [
        block for block in document.blocks if block.primary_question_id == "Q8" and block.kind == "paragraph"
    ]
    general_limit = first_sentence(limitation_pool[0].translated_text) if limitation_pool else "当前版本主要受现有抽取质量、噪声控制与外推边界约束。"
    cards: list[dict[str, str]] = []

    for question in document.questions:
        matched = [
            block
            for block in document.blocks
            if block.primary_question_id == question.id or question.id in block.secondary_question_ids
        ]
        core_source = matched[0].translated_text if matched else ""
        evidence_source = next(
            (
                block.translated_text
                for block in matched
                if block.section.family in {"results", "methods", "discussion"}
            ),
            core_source,
        )
        cards.append(
            {
                "id": question.id,
                "title": question.title,
                "color": question.color,
                "core_argument": first_sentence(core_source) or f"这篇论文围绕“{question.title}”给出了一条相对清晰的回答路径。",
                "key_evidence": sentences(evidence_source) or "核心证据主要来自作者在对应章节给出的定义、对照和定量结果。",
                "limitation": general_limit if question.id != "Q8" else first_sentence(core_source) or general_limit,
            }
        )
    return cards


def section_nav(document: DocumentPayload) -> list[SectionInfo]:
    deduped: list[SectionInfo] = []
    seen: set[str] = set()
    for section in document.sections:
        if section.anchor in seen:
            continue
        seen.add(section.anchor)
        deduped.append(section)
    return deduped


def render_content_rows(document: DocumentPayload) -> str:
    rows: list[str] = []
    current_anchor = ""
    lookup = question_lookup(document.questions)

    for block in document.blocks:
        if block.section.anchor != current_anchor:
            current_anchor = block.section.anchor
            rows.append(
                "\n".join(
                    [
                        f'<section id="{html.escape(block.section.anchor)}" class="section-divider">',
                        f'  <div class="section-pill">{html.escape(block.section.title)}</div>',
                        "</section>",
                    ]
                )
            )

        question_ids = [block.primary_question_id] + block.secondary_question_ids
        question = lookup[block.primary_question_id]
        source_body = render_source_block(block, question_ids, lookup)
        annotation_body = render_annotation_block(block, question)
        rows.append(
            "\n".join(
                [
                    '<div class="content-row">',
                    source_body,
                    annotation_body,
                    "</div>",
                ]
            )
        )

    return "\n".join(rows)


def render_source_block(
    block: ContentBlock,
    question_ids: list[str],
    lookup: dict[str, QuestionSpec],
) -> str:
    if block.kind == "equation":
        body = f"<pre class=\"equation-block\">{html.escape(block.equation_text)}</pre>"
    elif block.kind == "image":
        caption = block.original_caption or block.translated_caption
        caption_html = (
            f'<p class="source-caption">{highlighted_html(caption, question_ids, lookup)}</p>' if caption else ""
        )
        body = (
            f'<img class="source-image" src="{html.escape(block.image_src)}" alt="Figure {block.index}">'
            f"{caption_html}"
        )
    else:
        source_text = block.original_text or block.translated_text
        body = f'<p class="source-text">{highlighted_html(source_text, question_ids, lookup)}</p>'

    question_tags = " ".join(
        f'<span class="mini-chip {question_id.lower()}">{html.escape(question_id)}</span>'
        for question_id in question_ids
    )
    return "\n".join(
        [
            '<article class="source-card">',
            f'  <div class="block-meta"><span class="block-id">P{block.index:02d}</span><div class="mini-chip-row">{question_tags}</div></div>',
            f"  {body}",
            "</article>",
        ]
    )


def render_annotation_block(block: ContentBlock, question: QuestionSpec) -> str:
    chinese_summary = (
        sentences(block.translated_text)
        if block.kind != "equation"
        else "这条公式用于压缩表达该段的数学关系，右侧解释其在全文中的角色。"
    )
    if block.kind == "image":
        chinese_summary = sentences(block.translated_caption or block.translated_text or block.original_caption) or "该图主要承担结果展示与图证功能。"

    secondary_text = "、".join(block.secondary_question_ids) if block.secondary_question_ids else "无"
    return "\n".join(
        [
            f'<aside class="annotation-card {question.id.lower()}">',
            '  <div class="annotation-head">',
            f'    <span class="question-badge {question.id.lower()}">{html.escape(question.id)} {html.escape(question.title)}</span>',
            f'    <span class="section-tag">{html.escape(block.section.title)}</span>',
            "  </div>",
            f'  <p><strong>中文对应：</strong>{html.escape(chinese_summary)}</p>',
            f'  <p><strong>段落功能：</strong>{html.escape(block.paragraph_function)}</p>',
            f'  <p><strong>论证逻辑：</strong>{html.escape(block.logic_role)}</p>',
            f'  <p><strong>答题定位：</strong>{html.escape(block.question_layer)} 次级关联：{html.escape(secondary_text)}</p>',
            "</aside>",
        ]
    )


def render_question_legend(document: DocumentPayload) -> str:
    chips = []
    for question in document.questions:
        chips.append(
            f'<span class="legend-chip {question.id.lower()}"><strong>{html.escape(question.id)}</strong> {html.escape(question.title)}</span>'
        )
    return "\n".join(chips)


def render_section_nav(document: DocumentPayload) -> str:
    links = []
    for section in section_nav(document):
        links.append(
            f'<a href="#{html.escape(section.anchor)}" class="section-link">{html.escape(section.title)}</a>'
        )
    return "\n".join(links)


def render_worksheet(document: DocumentPayload) -> str:
    cards = []
    for card in worksheet_cards(document):
        cards.append(
            "\n".join(
                [
                    f'<article class="worksheet-card {card["id"].lower()}">',
                    f'  <div class="worksheet-head"><span class="question-badge {card["id"].lower()}">{html.escape(card["id"])}</span><h3>{html.escape(card["title"])}</h3></div>',
                    f'  <p><strong>核心论点：</strong>{html.escape(card["core_argument"])}</p>',
                    f'  <p><strong>关键证据：</strong>{html.escape(card["key_evidence"])}</p>',
                    f'  <p><strong>潜在反驳 / 局限：</strong>{html.escape(card["limitation"])}</p>',
                    "</article>",
                ]
            )
        )
    return "\n".join(cards)


def render_html(document: DocumentPayload) -> str:
    legend = render_question_legend(document)
    nav = render_section_nav(document)
    rows = render_content_rows(document)
    worksheet = render_worksheet(document)

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(document.title)} | 双栏批注阅读版</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=Lora:wght@400;500;600;700&display=swap" rel="stylesheet">
  <style>
    :root {{
      --navy: #102b45;
      --navy-soft: #173c61;
      --paper: #f7f1e7;
      --ink: #243341;
      --muted: #5a6874;
      --border: rgba(16, 43, 69, 0.12);
      --surface: rgba(255, 255, 255, 0.76);
      --shadow: 0 18px 42px rgba(16, 43, 69, 0.10);
      --q1: #d9a441;
      --q2: #d4694c;
      --q3: #4377d6;
      --q4: #2d9079;
      --q5: #8a56d8;
      --q6: #2b88b8;
      --q7: #d94c77;
      --q8: #7b8794;
      --q9: #df7a3d;
      --q10: #3a9f74;
    }}
    * {{ box-sizing: border-box; }}
    html {{ scroll-behavior: smooth; }}
    body {{
      margin: 0;
      color: var(--ink);
      background:
        radial-gradient(circle at top left, rgba(255, 255, 255, 0.65), transparent 40%),
        linear-gradient(180deg, #fbf7ee 0%, var(--paper) 100%);
      font-family: "IBM Plex Sans", "Segoe UI", sans-serif;
      line-height: 1.72;
    }}
    .page {{
      width: min(1440px, calc(100vw - 32px));
      margin: 0 auto;
      padding: 18px 0 48px;
    }}
    .topbar {{
      position: sticky;
      top: 0;
      z-index: 20;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      padding: 14px 18px;
      background: rgba(16, 43, 69, 0.95);
      color: #f8fbfd;
      border-radius: 18px;
      box-shadow: 0 18px 38px rgba(8, 24, 38, 0.22);
      backdrop-filter: blur(10px);
    }}
    .brand {{
      font-weight: 700;
      letter-spacing: 0.03em;
    }}
    .course-info {{
      color: rgba(248, 251, 253, 0.84);
      font-size: 0.94rem;
      text-align: right;
    }}
    .hero,
    .legend,
    .section-nav,
    .worksheet-shell {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 22px;
      box-shadow: var(--shadow);
    }}
    .hero {{
      margin-top: 18px;
      padding: 26px 28px 22px;
    }}
    .hero h1 {{
      margin: 0;
      color: var(--navy);
      font-size: clamp(2rem, 4vw, 3rem);
      line-height: 1.15;
    }}
    .hero .subtitle {{
      margin-top: 10px;
      color: var(--muted);
      font-family: "Lora", "STSong", serif;
      font-size: 1.1rem;
    }}
    .hero .meta {{
      margin-top: 14px;
      color: var(--muted);
      font-size: 0.96rem;
    }}
    .legend {{
      margin-top: 16px;
      padding: 16px 18px;
    }}
    .legend-title {{
      font-weight: 700;
      color: var(--navy);
      margin-bottom: 10px;
    }}
    .legend-grid {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
    }}
    .legend-chip,
    .question-badge,
    .mini-chip {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      border-radius: 999px;
      border: 1px solid rgba(16, 43, 69, 0.08);
      font-size: 0.80rem;
      font-weight: 700;
    }}
    .legend-chip {{
      padding: 0.34rem 0.8rem;
      color: #102b45;
      background: rgba(255, 255, 255, 0.8);
    }}
    .section-nav {{
      position: sticky;
      top: 76px;
      z-index: 16;
      margin-top: 16px;
      padding: 12px 14px;
    }}
    .section-links {{
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
    }}
    .section-link {{
      text-decoration: none;
      color: var(--navy-soft);
      font-weight: 600;
      padding: 0.32rem 0.72rem;
      border-radius: 999px;
      background: rgba(16, 43, 69, 0.05);
    }}
    .content {{
      margin-top: 18px;
    }}
    .section-divider {{
      margin: 28px 0 12px;
    }}
    .section-pill {{
      display: inline-flex;
      align-items: center;
      padding: 0.48rem 0.9rem;
      border-radius: 999px;
      background: rgba(16, 43, 69, 0.9);
      color: #f8fbfd;
      font-weight: 700;
      box-shadow: 0 10px 26px rgba(16, 43, 69, 0.14);
    }}
    .content-row {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
      gap: 18px;
      margin-bottom: 16px;
    }}
    .source-card,
    .annotation-card {{
      background: rgba(255, 255, 255, 0.78);
      border: 1px solid var(--border);
      border-radius: 20px;
      box-shadow: var(--shadow);
      padding: 18px 18px 16px;
      min-width: 0;
    }}
    .source-card {{
      font-family: "Lora", "STSong", serif;
    }}
    .block-meta,
    .annotation-head,
    .worksheet-head {{
      display: flex;
      justify-content: space-between;
      gap: 10px;
      align-items: flex-start;
      flex-wrap: wrap;
      margin-bottom: 12px;
    }}
    .block-id {{
      font-weight: 700;
      color: var(--navy);
    }}
    .mini-chip-row {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }}
    .mini-chip {{
      padding: 0.18rem 0.62rem;
      background: rgba(16, 43, 69, 0.05);
      color: var(--navy-soft);
    }}
    .question-badge {{
      padding: 0.24rem 0.7rem;
      color: white;
    }}
    .section-tag {{
      color: var(--muted);
      font-size: 0.86rem;
      font-weight: 600;
    }}
    .source-text,
    .source-caption {{
      margin: 0;
      font-size: 1.03rem;
      line-height: 1.88;
    }}
    .source-image {{
      display: block;
      width: 100%;
      border-radius: 14px;
      border: 1px solid rgba(16, 43, 69, 0.10);
      background: #fff;
    }}
    .equation-block {{
      margin: 0;
      padding: 14px;
      overflow-x: auto;
      background: rgba(16, 43, 69, 0.04);
      border-radius: 14px;
      border: 1px solid rgba(16, 43, 69, 0.08);
      font-family: "IBM Plex Sans", "Segoe UI", sans-serif;
      white-space: pre-wrap;
    }}
    .annotation-card {{
      border-left: 6px solid var(--q10);
      background: linear-gradient(180deg, rgba(255, 255, 255, 0.90), rgba(250, 251, 252, 0.84));
    }}
    .annotation-card p {{
      margin: 0 0 10px;
    }}
    .annotation-card p:last-child {{
      margin-bottom: 0;
    }}
    .mark {{
      padding: 0.06em 0.22em;
      border-radius: 0.38em;
      color: #102b45;
      box-decoration-break: clone;
      -webkit-box-decoration-break: clone;
    }}
    .worksheet-shell {{
      margin-top: 28px;
      padding: 22px;
    }}
    .worksheet-shell h2 {{
      margin: 0 0 12px;
      color: var(--navy);
    }}
    .worksheet-grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 16px;
    }}
    .worksheet-card {{
      background: rgba(255, 255, 255, 0.84);
      border: 1px solid var(--border);
      border-left: 6px solid var(--q10);
      border-radius: 18px;
      box-shadow: var(--shadow);
      padding: 16px 18px;
    }}
    .worksheet-card h3 {{
      margin: 0;
      color: var(--navy);
      font-size: 1rem;
    }}
    .worksheet-card p {{
      margin: 0 0 10px;
    }}
    .worksheet-card p:last-child {{
      margin-bottom: 0;
    }}
    .q1, .mark.q1 {{ background: rgba(217, 164, 65, 0.26); border-left-color: var(--q1); }}
    .q2, .mark.q2 {{ background: rgba(212, 105, 76, 0.22); border-left-color: var(--q2); }}
    .q3, .mark.q3 {{ background: rgba(67, 119, 214, 0.18); border-left-color: var(--q3); }}
    .q4, .mark.q4 {{ background: rgba(45, 144, 121, 0.18); border-left-color: var(--q4); }}
    .q5, .mark.q5 {{ background: rgba(138, 86, 216, 0.18); border-left-color: var(--q5); }}
    .q6, .mark.q6 {{ background: rgba(43, 136, 184, 0.18); border-left-color: var(--q6); }}
    .q7, .mark.q7 {{ background: rgba(217, 76, 119, 0.18); border-left-color: var(--q7); }}
    .q8, .mark.q8 {{ background: rgba(123, 135, 148, 0.18); border-left-color: var(--q8); }}
    .q9, .mark.q9 {{ background: rgba(223, 122, 61, 0.18); border-left-color: var(--q9); }}
    .q10, .mark.q10 {{ background: rgba(58, 159, 116, 0.18); border-left-color: var(--q10); }}
    .annotation-card.q1, .worksheet-card.q1 {{ border-left-color: var(--q1); }}
    .annotation-card.q2, .worksheet-card.q2 {{ border-left-color: var(--q2); }}
    .annotation-card.q3, .worksheet-card.q3 {{ border-left-color: var(--q3); }}
    .annotation-card.q4, .worksheet-card.q4 {{ border-left-color: var(--q4); }}
    .annotation-card.q5, .worksheet-card.q5 {{ border-left-color: var(--q5); }}
    .annotation-card.q6, .worksheet-card.q6 {{ border-left-color: var(--q6); }}
    .annotation-card.q7, .worksheet-card.q7 {{ border-left-color: var(--q7); }}
    .annotation-card.q8, .worksheet-card.q8 {{ border-left-color: var(--q8); }}
    .annotation-card.q9, .worksheet-card.q9 {{ border-left-color: var(--q9); }}
    .annotation-card.q10, .worksheet-card.q10 {{ border-left-color: var(--q10); }}
    .question-badge.q1 {{ background: var(--q1); }}
    .question-badge.q2 {{ background: var(--q2); }}
    .question-badge.q3 {{ background: var(--q3); }}
    .question-badge.q4 {{ background: var(--q4); }}
    .question-badge.q5 {{ background: var(--q5); }}
    .question-badge.q6 {{ background: var(--q6); }}
    .question-badge.q7 {{ background: var(--q7); }}
    .question-badge.q8 {{ background: var(--q8); }}
    .question-badge.q9 {{ background: var(--q9); }}
    .question-badge.q10 {{ background: var(--q10); }}
    .legend-chip.q1, .mini-chip.q1 {{ background: rgba(217, 164, 65, 0.18); }}
    .legend-chip.q2, .mini-chip.q2 {{ background: rgba(212, 105, 76, 0.18); }}
    .legend-chip.q3, .mini-chip.q3 {{ background: rgba(67, 119, 214, 0.15); }}
    .legend-chip.q4, .mini-chip.q4 {{ background: rgba(45, 144, 121, 0.15); }}
    .legend-chip.q5, .mini-chip.q5 {{ background: rgba(138, 86, 216, 0.15); }}
    .legend-chip.q6, .mini-chip.q6 {{ background: rgba(43, 136, 184, 0.15); }}
    .legend-chip.q7, .mini-chip.q7 {{ background: rgba(217, 76, 119, 0.15); }}
    .legend-chip.q8, .mini-chip.q8 {{ background: rgba(123, 135, 148, 0.15); }}
    .legend-chip.q9, .mini-chip.q9 {{ background: rgba(223, 122, 61, 0.15); }}
    .legend-chip.q10, .mini-chip.q10 {{ background: rgba(58, 159, 116, 0.15); }}
    @media (max-width: 1024px) {{
      .content-row,
      .worksheet-grid {{
        grid-template-columns: 1fr;
      }}
      .section-nav {{
        top: 68px;
      }}
      .course-info {{
        text-align: left;
      }}
    }}
  </style>
</head>
<body>
  <div class="page">
    <div class="topbar">
      <div class="brand">论文双栏批注阅读版</div>
      <div class="course-info">{html.escape(document.title)} | {html.escape(document.course_info)}</div>
    </div>

    <section class="hero">
      <h1>{html.escape(document.title)}</h1>
      <div class="subtitle">{html.escape(document.title_original)}</div>
      <div class="meta">课程 / 周次：{html.escape(document.course_info)}</div>
    </section>

    <section class="legend">
      <div class="legend-title">颜色图例</div>
      <div class="legend-grid">
        {legend}
      </div>
    </section>

    <section class="section-nav">
      <div class="section-links">
        {nav}
      </div>
    </section>

    <main class="content">
      {rows}
    </main>

    <section class="worksheet-shell" id="worksheet-index">
      <h2>Worksheet 答题索引</h2>
      <div class="worksheet-grid">
        {worksheet}
      </div>
    </section>
  </div>
</body>
</html>
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a dual-column annotated paper HTML file.")
    parser.add_argument("--paper-note", default="", help="Optional paper note path for resolving extract/template paths.")
    parser.add_argument("--source-md", default="")
    parser.add_argument("--translated-md", default="")
    parser.add_argument("--translation-template", default="")
    parser.add_argument("--paper-title", default="")
    parser.add_argument("--paper-title-original", default="")
    parser.add_argument("--course-info", default="OCT 文献精读自动整理")
    parser.add_argument("--output-html", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    source_md = Path(args.source_md) if args.source_md else None
    translated_md = Path(args.translated_md) if args.translated_md else None
    translation_template = Path(args.translation_template) if args.translation_template else None
    paper_title = normalize_whitespace(args.paper_title)
    paper_title_original = normalize_whitespace(args.paper_title_original)

    if args.paper_note:
        resolved = resolve_from_paper_note(Path(args.paper_note))
        paper_title = paper_title or resolved["title"]
        paper_title_original = paper_title_original or resolved["title_original"]
        if source_md is None and resolved["source_md"]:
            source_md = Path(resolved["source_md"].replace("\\", "/"))
        if translated_md is None and resolved["translated_md"]:
            translated_md = Path(resolved["translated_md"].replace("\\", "/"))
        if translation_template is None and resolved["translation_template"]:
            translation_template = Path(resolved["translation_template"].replace("\\", "/"))

    if source_md is not None and translation_template is not None and source_md.exists() and translation_template.exists():
        document = build_document_from_template(
            source_md=source_md,
            template_path=translation_template,
            title=paper_title or paper_title_original or source_md.stem,
            title_original=paper_title_original or paper_title or source_md.stem,
            course_info=args.course_info,
        )
    elif translated_md is not None and translated_md.exists():
        document = build_document_from_translated_markdown(
            translated_md=translated_md,
            title=paper_title,
            title_original=paper_title_original,
            course_info=args.course_info,
            source_md=source_md,
        )
    else:
        raise FileNotFoundError("Need either a valid --source-md with --translation-template, or a valid --translated-md.")

    output_html = Path(args.output_html)
    output_html.parent.mkdir(parents=True, exist_ok=True)
    output_html.write_text(render_html(document), encoding="utf-8")

    result = {
        "status": "built",
        "output_html": str(output_html),
        "title": document.title,
        "title_original": document.title_original,
        "block_count": len(document.blocks),
        "section_count": len(document.sections),
    }
    emit_json(result)


if __name__ == "__main__":
    main()
