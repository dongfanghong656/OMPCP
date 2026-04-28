#!/usr/bin/env python
import argparse
import json
import re
from datetime import datetime
from pathlib import Path

from seed_paper_note import (
    ACADEMIC_PAPER_FOLDER,
    build_filename,
    build_index_reference,
    build_short_title,
    sanitize,
    safe_filename_component,
    split_authors,
    to_portable_path,
    update_index,
    yaml_list,
)

LEGACY_PAPER_FOLDER = Path("02_Papers")


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def split_frontmatter_and_body(text: str):
    if not text.startswith("---\n"):
        return {}, text
    parts = text.split("\n---\n", 1)
    if len(parts) != 2:
        return {}, text
    frontmatter_text = parts[0][4:]
    body = parts[1]
    return parse_frontmatter(frontmatter_text), body


def parse_frontmatter(text: str):
    data = {}
    current_list_key = None
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if not line:
            current_list_key = None
            continue
        if line.startswith("  - ") and current_list_key:
            data.setdefault(current_list_key, []).append(line[4:].strip().strip('"'))
            continue
        if ":" not in line:
            current_list_key = None
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if value == "":
            data[key] = []
            current_list_key = key
        else:
            data[key] = value.strip('"')
            current_list_key = None
    return data


def parse_sections(body: str):
    title = ""
    sections = {}
    current = None
    buffer = []
    for raw_line in body.splitlines():
        line = raw_line.rstrip()
        if line.startswith("# ") and not title:
            title = line[2:].strip()
            continue
        if line.startswith("## "):
            if current is not None:
                sections[current] = "\n".join(buffer).strip()
            current = line[3:].strip()
            buffer = []
        else:
            if current is not None:
                buffer.append(raw_line)
    if current is not None:
        sections[current] = "\n".join(buffer).strip()
    return title, sections


def first_nonempty(*values):
    for value in values:
        if value and str(value).strip():
            return str(value).strip()
    return ""


def first_paragraph(text: str):
    if not text:
        return ""
    parts = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    return parts[0] if parts else ""


def lines_from_text(text: str):
    if not text:
        return [""]
    return text.splitlines()


def bullet_block(text: str, default_line: str):
    text = text.strip()
    if not text:
        return [f"> - {default_line}"]
    lines = []
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue
        if stripped.startswith("- "):
            lines.append(f"> {stripped}")
        else:
            lines.append(f"> - {stripped}")
    return lines or [f"> - {default_line}"]


def quote_lines(text: str, fallback: str = ""):
    if not text:
        return ["> " + fallback] if fallback else [">"]
    return ["> " + line if line else ">" for line in text.splitlines()]


def detect_mojibake(text: str):
    if not text:
        return False
    markers = ["鍙", "銆", "锛", "鏈", "鐨", "绗", "璇", "杩", "浣", "妯", "€"]
    hits = sum(text.count(marker) for marker in markers)
    return hits >= 4


def migrated_note_lines(frontmatter, sections, note_title: str, authors, new_stem: str, legacy_path: Path):
    year = str(frontmatter.get("year", "")).strip()
    source_tag = frontmatter.get("source_tag", "legacy-note")
    source_pdf = frontmatter.get("source_pdf", "")
    copied_pdf = frontmatter.get("copied_pdf", "")
    extract_path = frontmatter.get("extract_path", "")
    updated_at = frontmatter.get("updated_at", "")
    tags = frontmatter.get("tags", [])
    if not isinstance(tags, list):
        tags = [tags] if tags else []

    research_question = sections.get("Research Question", "")
    method_summary = sections.get("Method Summary", "")
    main_contribution = sections.get("Main Contribution", "")
    assumptions = sections.get("Assumptions and Boundaries", "")
    weak_points = sections.get("Weak Points and Controversies", "")
    transfer_value = sections.get("Transfer Value to This Project", "")
    case_example = sections.get("Case Example", "")
    links = sections.get("Links and Evidence", "")
    next_action = sections.get("Next Action", "")
    extraction = sections.get("Extraction", "")

    legacy_warning = detect_mojibake(
        "\n".join(
            [
                research_question,
                method_summary,
                main_contribution,
                assumptions,
                weak_points,
                transfer_value,
                case_example,
            ]
        )
    )
    title_zh = note_title if re.search(r"[\u4e00-\u9fff]", note_title) else ""
    title_en = note_title if not title_zh else ""
    citation_title = f"{authors[0]} et al., {year}" if len(authors) > 1 else f"{authors[0]}, {year}" if authors else f"Unknown, {year}"
    citation_key = re.sub(r"[^a-z0-9]+", "-", f"{authors[0] if authors else 'unknown'}-{year}-{build_short_title(note_title)}".lower()).strip("-")
    updated_display = updated_at.replace("T", " ") if updated_at else datetime.now().strftime("%Y-%m-%d %H:%M")
    one_sentence = first_nonempty(first_paragraph(main_contribution), first_paragraph(research_question), "旧笔记已迁移到新模板，等待补完 Q2 深答与段落级批注。")

    lines = [
        "---",
        'type: "paper"',
        f'title: "{sanitize(note_title)}"',
        f'title_en: "{sanitize(title_en)}"',
        f'title_zh: "{sanitize(title_zh)}"',
        f'title_original: "{sanitize(note_title)}"',
        f'title_display: "{sanitize(title_zh or note_title)}"',
        f'title_legacy_slug: "{sanitize(legacy_path.stem)}"',
        f'short_title: "{sanitize(build_short_title(note_title))}"',
        f'citation_title: "{sanitize(citation_title)}"',
        f'citation_key: "{sanitize(citation_key)}"',
        f'filename_title: "{sanitize(new_stem)}"',
    ]
    lines.extend(yaml_list("authors", authors))
    lines.extend(
        [
            f"year: {year}" if year else "year:",
            'venue: ""',
            'doi: ""',
            'url: ""',
            'course: ""',
            'week: ""',
            'status: "annotated"',
            'reading_stage: "synthesis"',
            'question_mode: "A"',
            'language: "zh-CN"',
        ]
    )
    merged_tags = ["oct-paper", "migrated-legacy-note"] + [tag for tag in tags if tag]
    deduped_tags = []
    for tag in merged_tags:
        if tag not in deduped_tags:
            deduped_tags.append(tag)
    lines.extend(yaml_list("tags", deduped_tags))
    lines.extend(
        [
            "topics: []",
            "concepts: []",
        ]
    )
    lines.extend(yaml_list("related_authors", authors))
    lines.extend(
        [
            'priority: "medium"',
            "rating:",
            'q2_status: "draft"',
            'q2_confidence: "medium"',
            f'created: "{year}-01-01"' if year else f'created: "{datetime.now().strftime("%Y-%m-%d")}"',
            f'updated: "{sanitize(updated_display)}"',
            "cssclasses:",
            '  - "paper-note"',
            '  - "bilingual-note"',
            '  - "question-mode-a"',
            f'source_tag: "{sanitize(source_tag)}"',
            f'source_pdf: "{sanitize(to_portable_path(source_pdf))}"',
            f'copied_pdf: "{sanitize(to_portable_path(copied_pdf))}"',
            f'extract_path: "{sanitize(to_portable_path(extract_path))}"',
            'translated_note_path: ""',
            'translation_template_path: ""',
            f'legacy_source_note: "[[{legacy_path.as_posix()}]]"',
            'migration_status: "migrated-from-legacy-note"',
            f'legacy_mojibake_detected: {"true" if legacy_warning else "false"}',
            "---",
            "",
            f"# {title_zh or '中文标题待补'}",
            "",
            f"## {title_en or note_title}",
            "",
            "> [!translation]",
            f"> 原始标题：{note_title}",
            f"> 英文标题：{title_en or note_title}",
            f"> 中文标题：{title_zh}",
            f"> short title：{build_short_title(note_title)}",
            f"> citation title：{citation_title}",
            ">",
            "> 关键词拆解：",
            "> - 旧资料迁移后待补",
            ">",
            "> 标题翻译说明：",
            "> - 直译：",
            "> - 意译：",
            "> - 为什么最终采用当前译法：",
            "",
            "> [!info]",
            f"> 作者：{', '.join(authors) if authors else 'TBD'}",
            f"> 年份：{year}",
            "> 期刊 / 会议：",
            "> DOI：",
            "> URL：",
            "> 课程：",
            "> Week：",
            "> 状态：annotated",
            "> 阅读阶段：synthesis",
            "> 模式：A / migrated",
            f"> 标签：{', '.join(deduped_tags)}",
            "",
            "> [!citation]",
            f"> Citation Key：{citation_key}",
            f"> Legacy Source Note：[[{legacy_path.as_posix()}]]",
            f"> Source Tag：{source_tag}",
            f"> Source PDF：{to_portable_path(source_pdf)}",
            "",
            "# 一句话总结",
            "",
            one_sentence,
            "",
            "# 核心摘要",
            "",
        ]
    )
    for line in lines_from_text(first_nonempty(method_summary, main_contribution, "旧摘要待补。")):
        lines.append(f"- {line}" if line else "-")
    lines.extend(
        [
            "",
            "# 研究问题",
            "",
        ]
    )
    lines.extend(lines_from_text(first_nonempty(research_question, "旧资料中没有显式写出研究问题，需要回到原文补全。")))
    lines.extend(
        [
            "",
            "# 主要内容",
            "",
        ]
    )
    lines.extend(lines_from_text(first_nonempty(method_summary, "旧资料中没有完整方法总结，需要补充。")))
    if case_example:
        lines.extend(["", "## Legacy Case Example", ""])
        lines.extend(lines_from_text(case_example))
    lines.extend(["", "# 创新点", "", "> [!innovation]"])
    lines.extend(quote_lines(first_nonempty(main_contribution, "旧资料没有明确写出创新点，建议重读摘要与结论补全。")))
    lines.extend(["", "# 最有价值的地方", "", "> [!value]"])
    lines.extend(quote_lines(first_nonempty(transfer_value, "旧资料没有明确写出迁移价值。")))
    lines.extend(["", "# 潜在局限", "", "> [!weakness]"])
    lines.extend(quote_lines(first_nonempty(assumptions, weak_points, "旧资料没有完整局限分析。")))
    if weak_points and weak_points != assumptions:
        lines.extend([">", "> 争议与薄弱环节："])
        lines.extend(quote_lines(weak_points))
    lines.extend(["", "# 方法论说明", "", "> [!method]"])
    lines.extend(quote_lines(first_nonempty(method_summary, "旧资料没有明确写出方法链路。")))
    lines.extend(
        [
            "",
            "# 术语表",
            "",
            "| Term | 中文 | 文内定义 | 我的解释 | Related Note |",
            "| --- | --- | --- | --- | --- |",
            "|  |  |  |  | [[Concept - ]] |",
            "",
            "# Q1-Q10 问题系统",
            "",
            "> [!question|q1] Q1 这篇文章试图解决什么问题？",
            "> question_title: 研究问题",
            "> question_note: 由旧笔记迁移",
            "> linked_quotes: [[#Legacy Source Snapshot]]",
            ">",
            f"> short_answer: {first_nonempty(first_paragraph(research_question), '待补')}",
            f"> deep_answer: {first_nonempty(research_question, '待补')}",
            "> limitation_or_counterargument: 待补",
            "",
            "> [!question|q2] Q2 这篇文章的核心论点 / 主张是什么？",
            "> question_title: 核心主张",
            "> question_note: 由旧笔记迁移",
            "> linked_quotes: [[#Q2 深答区]]",
            ">",
            f"> short_answer: {first_nonempty(first_paragraph(main_contribution), '待补')}",
            f"> deep_answer: {first_nonempty(main_contribution, '待补')}",
            f"> limitation_or_counterargument: {first_nonempty(first_paragraph(weak_points), '待补')}",
            "",
            "> [!question|q3] Q3 作者如何定义关键概念？",
            "> question_title: 概念定义",
            "> question_note: 旧笔记未结构化记录",
            "> linked_quotes:",
            ">",
            "> short_answer:",
            "> deep_answer:",
            "> limitation_or_counterargument:",
            "",
            "> [!question|q4] Q4 作者提供了哪些关键证据？",
            "> question_title: 关键证据",
            "> question_note: 暂从旧资料链接区继承",
            "> linked_quotes: [[#Legacy Links and Evidence]]",
            ">",
            "> short_answer:",
            "> deep_answer:",
            "> limitation_or_counterargument:",
            "",
            "> [!question|q5] Q5 作者采用了什么方法？",
            "> question_title: 方法路径",
            "> question_note: 由旧笔记迁移",
            "> linked_quotes: [[#方法论说明]]",
            ">",
            f"> short_answer: {first_nonempty(first_paragraph(method_summary), '待补')}",
            f"> deep_answer: {first_nonempty(method_summary, '待补')}",
            "> limitation_or_counterargument:",
            "",
            "> [!question|q6] Q6 作者如何处理可能的反驳？",
            "> question_title: 反驳处理",
            "> question_note: 旧笔记未单独拆出",
            "> linked_quotes:",
            ">",
            "> short_answer:",
            "> deep_answer:",
            "> limitation_or_counterargument:",
            "",
            "> [!question|q7] Q7 文章最强的论证环节是什么？",
            "> question_title: 最强论证",
            "> question_note: 迁移后待补",
            "> linked_quotes:",
            ">",
            "> short_answer:",
            "> deep_answer:",
            "> limitation_or_counterargument:",
            "",
            "> [!question|q8] Q8 文章最弱的环节或漏洞是什么？",
            "> question_title: 论证薄弱处",
            "> question_note: 由旧笔记迁移",
            "> linked_quotes: [[#潜在局限]]",
            ">",
            f"> short_answer: {first_nonempty(first_paragraph(weak_points), first_paragraph(assumptions), '待补')}",
            f"> deep_answer: {first_nonempty(weak_points, assumptions, '待补')}",
            "> limitation_or_counterargument:",
            "",
            "> [!question|q9] Q9 这篇文章的创新点在哪里？",
            "> question_title: 创新性判断",
            "> question_note: 由旧笔记迁移",
            "> linked_quotes: [[#创新点]]",
            ">",
            f"> short_answer: {first_nonempty(first_paragraph(main_contribution), '待补')}",
            f"> deep_answer: {first_nonempty(main_contribution, '待补')}",
            "> limitation_or_counterargument:",
            "",
            "> [!question|q10] Q10 这篇文章对我的研究 / 课程有什么价值？",
            "> question_title: 迁移价值",
            "> question_note: 由旧笔记迁移",
            "> linked_quotes: [[#最有价值的地方]]",
            ">",
            f"> short_answer: {first_nonempty(first_paragraph(transfer_value), '待补')}",
            f"> deep_answer: {first_nonempty(transfer_value, '待补')}",
            "> limitation_or_counterargument:",
            "",
            "# Q2 深答区",
            "",
            "> [!q2-focus]",
            "> Q2: 这篇文章的核心论点 / 主张是什么？",
            ">",
            "> q2_status:: draft",
            f"> q2_confidence:: {'low' if legacy_warning else 'medium'}",
            "> q2_source_paragraphs:: legacy-note",
            ">",
            "> 精炼回答：",
            f"> {first_nonempty(first_paragraph(main_contribution), '待补')}",
            ">",
            "> 分析回答：",
        ]
    )
    lines.extend(quote_lines(first_nonempty(main_contribution, "待补")))
    lines.extend(
        [
            ">",
            "> 支持摘录：",
        ]
    )
    lines.extend(bullet_block(links, "旧笔记没有直接摘录原文，需要回到原文补充。"))
    lines.extend(
        [
            ">",
            "> 原文出处：",
            "> - [[#Legacy Source Snapshot]]",
            ">",
            "> 依赖概念：",
            "> - [[Concept - ]]",
            ">",
            "> 潜在反驳：",
        ]
    )
    lines.extend(quote_lines(first_nonempty(weak_points, assumptions, "待补")))
    lines.extend(
        [
            ">",
            "> 我的最终判断：",
            f"> {first_nonempty(first_paragraph(transfer_value), '迁移完成后待补个人判断。')}",
            ">",
            "> 可信度：",
            f"> {'low' if legacy_warning else 'medium'}",
            "",
            "# 用户提出的问题",
            "",
            "- question_id:: UQ-01",
            "  question_text:: ",
            "  asked_by:: user",
            "  status:: open",
            "  linked_paragraphs:: legacy-note",
            "  linked_quotes:: [[#Legacy Source Snapshot]]",
            "  tentative_answer:: ",
            "  final_answer:: ",
            "  note:: 由旧资料迁移后待补。",
            "",
            "# Logic Skeleton",
            "",
            "> [!thesis]",
            f"> 作者核心主张一句话版本：{first_nonempty(first_paragraph(main_contribution), '待补')}",
            "",
            "> [!concept]",
            "> 关键概念及其边界：",
            "> - 迁移后待补",
            "",
            "> [!evidence]",
            "> 最关键证据：",
        ]
    )
    lines.extend(bullet_block(links, "旧笔记主要保留了链接，尚未拆出证据摘录。"))
    lines.extend(
        [
            "",
            "> [!rebuttal]",
            "> 作者如何处理反驳：",
        ]
    )
    lines.extend(bullet_block(weak_points, "迁移后待补"))
    lines.extend(
        [
            "",
            "> [!method]",
            "> 方法在论证中的角色：",
        ]
    )
    lines.extend(bullet_block(method_summary, "迁移后待补"))
    lines.extend(
        [
            "",
            "## Pure Logic Bottom Line",
            "",
            f"- 问题 -> 论点 -> 证据 -> 反驳 -> 结论：{first_nonempty(first_paragraph(research_question), '待补')} -> {first_nonempty(first_paragraph(main_contribution), '待补')} -> 待补 -> {first_nonempty(first_paragraph(weak_points), '待补')} -> 待补",
            f"- 最强论证一条：{first_nonempty(first_paragraph(main_contribution), '待补')}",
            f"- 最弱环节一条：{first_nonempty(first_paragraph(weak_points), first_paragraph(assumptions), '待补')}",
            "",
            "# 段落级批注",
            "",
            "> [!question|q2] Legacy Note Migration",
            "> paragraph_id:: legacy-note",
            "> linked_questions:: Q1, Q2, Q5, Q8, Q10",
            "> linked_user_questions:: UQ-01",
            "> section:: Legacy Paper Note",
            "> paragraph_function:: 旧模板迁移入口",
            "> logic_role:: 旧分析摘要",
            f"> rhetorical_move_or_weakness:: {'检测到旧笔记存在编码异常，建议回原文核对。' if legacy_warning else '可继续补段落级批注。'}",
            "> source_note:: legacy note",
            ">",
            "> 这篇笔记由旧 `02_Papers` 结构迁移而来，原笔记内容保留在下方 `Legacy Source Snapshot`。",
            "",
            "# 原文摘录与高亮索引",
            "",
            "| paragraph_id | Original Quote | Highlight | Linked Question | Why it matters |",
            "| --- | --- | --- | --- | --- |",
            "| legacy-note | Legacy content retained below | `legacy` | Q1, Q2, Q5, Q8, Q10 | 迁移后待回原文补强 |",
            "",
            "# Related Notes",
            "",
            f"- [[{legacy_path.as_posix()}]]",
        ]
    )
    if links:
        for raw_line in links.splitlines():
            stripped = raw_line.strip()
            if stripped:
                lines.append(f"- {stripped}")
    lines.extend(
        [
            "",
            "# 导出信息",
            "",
            "- export_mode:: question",
            "- export_template:: [[06_Exports/HTML/export-question-mode.html]]",
            "- export_status:: draft",
            "- export_notes:: This note was migrated from a legacy OCT paper note.",
            "",
            "# Legacy Links and Evidence",
            "",
        ]
    )
    lines.extend(lines_from_text(first_nonempty(links, "旧笔记没有保留单独的 links and evidence。")))
    if extraction:
        lines.extend(["", "## Legacy Extraction", ""])
        lines.extend(lines_from_text(extraction))
    if next_action:
        lines.extend(["", "## Legacy Next Action", ""])
        lines.extend(lines_from_text(next_action))
    lines.extend(["", "# Legacy Source Snapshot", ""])
    for section_name in [
        "Research Question",
        "Method Summary",
        "Main Contribution",
        "Assumptions and Boundaries",
        "Weak Points and Controversies",
        "Transfer Value to This Project",
        "Case Example",
        "Links and Evidence",
        "Next Action",
        "Extraction",
    ]:
        section_text = sections.get(section_name, "")
        if section_text:
            lines.extend([f"## {section_name}", ""])
            lines.extend(lines_from_text(section_text))
            lines.append("")
    return lines


def read_legacy_source_reference(path: Path):
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return ""
    match = re.search(r'^legacy_source_note:\s*"\[\[(.+?)\]\]"', text, re.MULTILINE)
    return match.group(1) if match else ""


def deterministic_target_path(target_dir: Path, base_stem: str, legacy_path: Path):
    primary = target_dir / f"{base_stem}.md"
    if not primary.exists():
        return primary

    existing_legacy = read_legacy_source_reference(primary)
    if existing_legacy == legacy_path.as_posix():
        return primary

    fallback_suffix = legacy_path.stem
    if "-" in fallback_suffix:
        fallback_suffix = fallback_suffix.split("-", 1)[1]
    fallback_stem = safe_filename_component(f"{base_stem} -- {fallback_suffix}")[:180]
    fallback = target_dir / f"{fallback_stem}.md"
    if not fallback.exists():
        return fallback

    existing_legacy = read_legacy_source_reference(fallback)
    if existing_legacy == legacy_path.as_posix():
        return fallback

    return target_dir / f"{safe_filename_component(fallback_stem + ' -- migrated')[:190]}.md"


def migrate_one_note(vault_root: Path, legacy_path: Path, overwrite: bool):
    frontmatter, body = split_frontmatter_and_body(legacy_path.read_text(encoding="utf-8-sig"))
    body_title, sections = parse_sections(body)
    note_title = first_nonempty(frontmatter.get("title"), body_title, legacy_path.stem)
    authors = split_authors(frontmatter.get("authors", ""))
    new_stem = build_filename(str(frontmatter.get("year", "")).strip() or "Unknown", authors, build_short_title(note_title))
    target_dir = vault_root / ACADEMIC_PAPER_FOLDER
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = deterministic_target_path(target_dir, new_stem, legacy_path.relative_to(vault_root))
    if target_path.exists() and not overwrite:
        return None, "exists"
    lines = migrated_note_lines(frontmatter, sections, note_title, authors, new_stem, legacy_path.relative_to(vault_root))
    target_path.write_text("\n".join(lines), encoding="utf-8")
    update_index(
        target_dir / "_Index.md",
        f"- {build_index_reference(target_path)} | {frontmatter.get('year', '')} | migrated-from-legacy",
        "# Literature Paper Index\n\n",
    )
    return target_path, "migrated"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    config = load_json(Path(args.config))
    vault_root = Path(config["vault_root"])
    legacy_dir = vault_root / LEGACY_PAPER_FOLDER
    migrated = []
    skipped = []

    for legacy_path in sorted(legacy_dir.glob("*.md")):
        if legacy_path.name.startswith("_"):
            continue
        target_path, status = migrate_one_note(vault_root, legacy_path, args.overwrite)
        if status == "migrated" and target_path:
            migrated.append(str(target_path))
        else:
            skipped.append(legacy_path.name)

    print(json.dumps({"migrated": migrated, "skipped": skipped}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
