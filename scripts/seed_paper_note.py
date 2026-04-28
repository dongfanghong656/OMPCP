#!/usr/bin/env python
import argparse
import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

import paper_dossiers
from path_naming import paper_attachment_slug
from path_naming import paper_short_title
from path_naming import safe_filename_component as shorten_filename_component
from path_naming import safe_slug

ACADEMIC_PAPER_FOLDER = Path("02_Literature") / "Papers"
ACADEMIC_TEMPLATE_PATH = Path("00_System") / "01_Templates" / "Literature Note.md"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def slugify(value: str) -> str:
    return safe_slug(value, max_length=72, fallback="paper")


def sanitize(value: str) -> str:
    return value.replace('"', "'")


def to_portable_path(value: str) -> str:
    return value.replace("\\", "/")


def detect_language(title: str) -> str:
    return "zh-CN" if re.search(r"[\u4e00-\u9fff]", title) else "en"


def split_authors(authors: str):
    normalized = authors.replace(" and ", ";").replace("&", ";")
    if ";" in normalized:
        parts = [part.strip() for part in normalized.split(";") if part.strip()]
    elif "," in normalized:
        parts = [part.strip() for part in normalized.split(",") if part.strip()]
    else:
        parts = [normalized.strip()] if normalized.strip() else []
    return parts


def first_author_label(authors):
    if not authors:
        return "Unknown"
    tokens = re.split(r"\s+", authors[0].strip())
    tokens = [token for token in tokens if token]
    if not tokens:
        return "Unknown"
    return safe_filename_component(tokens[-1]) or "Unknown"


def safe_filename_component(value: str) -> str:
    return shorten_filename_component(value, max_length=80, fallback="paper")


def build_short_title(title: str) -> str:
    return paper_short_title(title, max_words=6, max_length=48, fallback="paper")


def build_filename(year: str, authors, short_title: str) -> str:
    return shorten_filename_component(
        f"[{year}] {first_author_label(authors)} - {short_title}",
        max_length=72,
        fallback=f"[{year}] Paper",
    )


def build_attachment_stem(year: str, authors, title: str) -> str:
    return paper_attachment_slug(
        title,
        year=year,
        author_label=first_author_label(authors),
        max_length=56,
        fallback="paper",
    )


def build_citation_title(authors, year: str) -> str:
    if not authors:
        return f"Unknown, {year}"
    if len(authors) == 1:
        return f"{authors[0]}, {year}"
    return f"{authors[0]} et al., {year}"


def yaml_list(key: str, items):
    if not items:
        return [f"{key}: []"]
    lines = [f"{key}:"]
    for item in items:
        lines.append(f'  - "{sanitize(item)}"')
    return lines


def update_index(index_path: Path, line: str, header: str):
    index_path.parent.mkdir(parents=True, exist_ok=True)
    existing = index_path.read_text(encoding="utf-8") if index_path.exists() else header
    if line not in existing:
        if not existing.endswith("\n"):
            existing += "\n"
        existing += line + "\n"
        index_path.write_text(existing, encoding="utf-8")


def build_index_reference(note_path: Path) -> str:
    stem = note_path.stem
    if "[" in stem or "]" in stem:
        return f"[{stem}](<{note_path.name}>)"
    return f"[[{stem}]]"


def resolve_note_style(vault_root: Path, configured_paper_folder: str, requested_style: str):
    academic_dir = vault_root / ACADEMIC_PAPER_FOLDER
    has_academic_layout = (vault_root / ACADEMIC_TEMPLATE_PATH).exists() or academic_dir.exists()

    if requested_style == "academic":
        academic_dir.mkdir(parents=True, exist_ok=True)
        return "academic", academic_dir
    if requested_style == "legacy":
        legacy_dir = vault_root / configured_paper_folder
        legacy_dir.mkdir(parents=True, exist_ok=True)
        return "legacy", legacy_dir
    if has_academic_layout:
        academic_dir.mkdir(parents=True, exist_ok=True)
        return "academic", academic_dir

    legacy_dir = vault_root / configured_paper_folder
    legacy_dir.mkdir(parents=True, exist_ok=True)
    return "legacy", legacy_dir


def build_academic_note_lines(args, note_title: str, authors, note_stem: str, source_pdf_for_note: str, copied_pdf: str):
    language = detect_language(note_title)
    title_zh = note_title if language == "zh-CN" else ""
    title_en = note_title if language != "zh-CN" else ""
    short_title = build_short_title(note_title)
    citation_key = slugify(f"{first_author_label(authors)}-{args.year}-{short_title}")
    created = datetime.now().strftime("%Y-%m-%d")
    updated = datetime.now().strftime("%Y-%m-%d %H:%M")
    css_mode = "question-mode-a" if args.question_mode == "A" else "logic-mode-b"
    export_mode = "question" if args.question_mode == "A" else "logic"

    lines = [
        "---",
        'type: "paper"',
        f'title: "{sanitize(note_title)}"',
        f'title_en: "{sanitize(title_en)}"',
        f'title_zh: "{sanitize(title_zh)}"',
        f'title_original: "{sanitize(note_title)}"',
        f'title_display: "{sanitize(title_zh or note_title)}"',
        f'short_title: "{sanitize(short_title)}"',
        f'citation_title: "{sanitize(build_citation_title(authors, args.year))}"',
        f'citation_key: "{citation_key}"',
        f'filename_title: "{sanitize(note_stem)}"',
    ]
    lines.extend(yaml_list("authors", authors))
    lines.extend(
        [
            f"year: {args.year}",
            'venue: ""',
            'doi: ""',
            'url: ""',
            'course: ""',
            'week: ""',
            'status: "to-read"',
            'reading_stage: "skim"',
            f'question_mode: "{args.question_mode}"',
            f'language: "{language}"',
        ]
    )
    lines.extend(yaml_list("tags", ["oct-paper", "deconvolution", args.source_tag]))
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
            'q2_status: "pending"',
            'q2_confidence: "low"',
            f'created: "{created}"',
            f'updated: "{updated}"',
            "cssclasses:",
            '  - "paper-note"',
            '  - "bilingual-note"',
            f'  - "{css_mode}"',
            f'source_tag: "{sanitize(args.source_tag)}"',
            f'source_pdf: "{sanitize(to_portable_path(source_pdf_for_note))}"',
            f'copied_pdf: "{sanitize(to_portable_path(copied_pdf))}"',
            f'extract_path: "{sanitize(to_portable_path(args.extract_path.strip()))}"',
            f'translated_note_path: "{sanitize(to_portable_path(args.translated_note_path.strip()))}"',
            f'translation_template_path: "{sanitize(to_portable_path(args.translation_template_path.strip()))}"',
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
            f"> short title：{short_title}",
            f"> citation title：{build_citation_title(authors, args.year)}",
            ">",
            "> 关键词拆解：",
            "> - term 1:",
            "> - term 2:",
            "> - term 3:",
            ">",
            "> 标题翻译说明：",
            "> - 直译：",
            "> - 意译：",
            "> - 为什么最终采用当前译法：",
            "",
            "> [!info]",
            f"> 作者：{', '.join(authors) if authors else 'TBD'}",
            f"> 年份：{args.year}",
            "> 期刊 / 会议：",
            "> DOI：",
            "> URL：",
            "> 课程：",
            "> Week：",
            "> 状态：to-read",
            "> 阅读阶段：skim",
            f"> 模式：{args.question_mode}",
            f"> 标签：oct-paper, deconvolution, {args.source_tag}",
            "",
            "> [!citation]",
            f"> Citation Key：{citation_key}",
            f"> Filename Title：{note_stem}",
            f"> Source Tag：{args.source_tag}",
            f"> Source PDF：{to_portable_path(source_pdf_for_note)}",
            "",
            "# 一句话总结",
            "",
            "用 1-2 句话说明这篇文章到底做了什么、为什么值得读。",
            "",
            "# 核心摘要",
            "",
            "- 研究对象：",
            "- 研究问题：",
            "- 核心主张：",
            "- 方法路径：",
            "- 结论：",
            "",
            "# 研究问题",
            "",
            "- 文章显式提出的问题：",
            "- 文章隐含想回答的问题：",
            "- 和我当前研究/课程最相关的问题：",
            "",
            "# 主要内容",
            "",
            "## Section Map",
            "",
            "| Section | 作用 | 与我最相关的点 |",
            "| --- | --- | --- |",
            "| Introduction |  |  |",
            "| Related Work |  |  |",
            "| Method |  |  |",
            "| Experiment / Evidence |  |  |",
            "| Discussion / Conclusion |  |  |",
            "",
            "# 创新点",
            "",
            "> [!innovation]",
            "> 创新点 1：",
            ">",
            "> 创新点 2：",
            ">",
            "> 创新点 3：",
            "",
            "# 最有价值的地方",
            "",
            "> [!value]",
            "> 这篇文章最值得迁移、复用或保留的内容：",
            "> - 理论：",
            "> - 方法：",
            "> - 实验设计：",
            "> - 表达方式：",
            "",
            "# 潜在局限",
            "",
            "> [!weakness]",
            "> 最值得警惕的问题：",
            "> - 证据是否足够：",
            "> - 假设是否过强：",
            "> - 泛化性是否有限：",
            "> - 是否忽略了替代解释：",
            "",
            "# 方法论说明",
            "",
            "> [!method]",
            "> 方法链路：",
            "> 1. 输入 / 数据来源：",
            "> 2. 关键处理步骤：",
            "> 3. 核心假设：",
            "> 4. 指标与评价方式：",
            "> 5. 与既有方法相比的不同：",
            "",
            "# 术语表",
            "",
            "| Term | 中文 | 文内定义 | 我的解释 | Related Note |",
            "| --- | --- | --- | --- | --- |",
            "|  |  |  |  | [[Concept - ]] |",
            "",
            "# Q1-Q10 问题系统",
            "",
        ]
    )

    questions = [
        "Q1 这篇文章试图解决什么问题？",
        "Q2 这篇文章的核心论点 / 主张是什么？",
        "Q3 作者如何定义关键概念？",
        "Q4 作者提供了哪些关键证据？",
        "Q5 作者采用了什么方法？",
        "Q6 作者如何处理可能的反驳？",
        "Q7 文章最强的论证环节是什么？",
        "Q8 文章最弱的环节或漏洞是什么？",
        "Q9 这篇文章的创新点在哪里？",
        "Q10 这篇文章对我的研究 / 课程有什么价值？",
    ]
    for index, question in enumerate(questions, start=1):
        lines.extend(
            [
                f"> [!question|q{index}] {question}",
                "> question_title:",
                "> question_note:",
                "> linked_quotes:",
                ">",
                "> short_answer:",
                "> deep_answer:",
                "> limitation_or_counterargument:",
                "",
            ]
        )

    lines.extend(
        [
            "# Q2 深答区",
            "",
            "> [!q2-focus]",
            "> Q2: 这篇文章的核心论点 / 主张是什么？",
            ">",
            "> q2_status:: pending",
            "> q2_confidence:: low",
            "> q2_source_paragraphs:: ",
            ">",
            "> 精炼回答：",
            ">",
            "> 分析回答：",
            ">",
            "> 支持摘录：",
            "> - ",
            "> - ",
            ">",
            "> 原文出处：",
            "> - [[#p01]]",
            ">",
            "> 依赖概念：",
            "> - [[Concept - ]]",
            ">",
            "> 潜在反驳：",
            ">",
            "> 我的最终判断：",
            ">",
            "> 可信度：",
            "> high / medium / low",
            "",
            "# 用户提出的问题",
            "",
            "- question_id:: UQ-01",
            "  question_text:: ",
            "  asked_by:: user",
            '  status:: open',
            "  linked_paragraphs:: ",
            "  linked_quotes:: ",
            "  tentative_answer:: ",
            "  final_answer:: ",
            "  note:: ",
            "",
            "# Logic Skeleton",
            "",
            "> [!thesis]",
            "> 作者核心主张一句话版本：",
            "",
            "> [!concept]",
            "> 关键概念及其边界：",
            "> - ",
            "",
            "> [!evidence]",
            "> 最关键证据：",
            "> - ",
            "",
            "> [!rebuttal]",
            "> 作者如何处理反驳：",
            "> - ",
            "",
            "> [!method]",
            "> 方法在论证中的角色：",
            "> - ",
            "",
            "## Pure Logic Bottom Line",
            "",
            "- 问题 -> 论点 -> 证据 -> 反驳 -> 结论：",
            "- 最强论证一条：",
            "- 最弱环节一条：",
            "",
            "# 段落级批注",
            "",
            "> [!question|q2] P03 Introduction",
            "> paragraph_id:: p03",
            "> linked_questions:: Q2, Q4",
            "> linked_user_questions:: UQ-01",
            "> section:: Introduction",
            "> paragraph_function:: ",
            "> logic_role:: ",
            "> rhetorical_move_or_weakness:: ",
            "> source_note:: para 3",
            ">",
            "> 这里写中文批注。",
            "",
            "# 原文摘录与高亮索引",
            "",
            "| paragraph_id | Original Quote | Highlight | Linked Question | Why it matters |",
            "| --- | --- | --- | --- | --- |",
            "| p01 | ==Quote here== | `==普通高亮==` | Q2 | 说明为什么重要 |",
            "| p02 | <span class=\"q2\">Quote here</span> | `span.q2` | Q2 | Q2 的关键出处 |",
            "",
            "# Related Notes",
            "",
            "- [[Concept - ]]",
            "- [[Author - ]]",
            "- [[Question - ]]",
            "",
            "# 导出信息",
            "",
            f"- export_mode:: {export_mode}",
            f"- export_template:: [[06_Exports/HTML/export-{export_mode}-mode.html]]",
            "- export_status:: draft",
            "- export_notes:: ",
            "",
        ]
    )
    return lines


def build_legacy_note_lines(args, note_title: str, source_pdf_for_note: str, copied_pdf: str):
    lines = [
        "---",
        f'title: "{sanitize(note_title)}"',
        f"year: {args.year}",
        f"source_tag: {args.source_tag}",
        f'authors: "{sanitize(args.authors)}"',
        f'source_pdf: "{sanitize(to_portable_path(source_pdf_for_note))}"',
        f'copied_pdf: "{sanitize(to_portable_path(copied_pdf))}"',
        f'extract_path: "{sanitize(to_portable_path(args.extract_path.strip()))}"',
        f'translated_note_path: "{sanitize(to_portable_path(args.translated_note_path.strip()))}"',
        f'translation_template_path: "{sanitize(to_portable_path(args.translation_template_path.strip()))}"',
        f'updated_at: "{datetime.now().isoformat(timespec="seconds")}"',
        "tags:",
        "  - oct-paper",
        "  - deconvolution",
        "---",
        "",
        f"# {note_title}",
        "",
        "## Citation",
        "",
        f"- Year: {args.year}",
        f"- Authors: {args.authors or 'TBD'}",
        f"- Source tag: {args.source_tag}",
        "",
        "## Why this paper matters",
        "",
        "## Core claims",
        "",
        "## Method and assumptions",
        "",
        "## Weak points and open questions",
        "",
        "## Transfer value to this project",
        "",
        "## Evidence to verify later",
        "",
        "## Next action",
        "",
    ]
    if args.extract_path.strip():
        lines.extend(["## Extraction", "", f"- Extracted text folder: `{to_portable_path(args.extract_path.strip())}`", ""])

    if args.translated_note_path.strip() or args.translation_template_path.strip():
        lines.extend(["## Translation", ""])
        if args.translated_note_path.strip():
            lines.append(f"- Translated note: `{to_portable_path(args.translated_note_path.strip())}`")
        if args.translation_template_path.strip():
            lines.append(
                f"- Manual translation template: `{to_portable_path(args.translation_template_path.strip())}`"
            )
        lines.append("")

    return lines


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--pdf-path", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--year", required=True)
    parser.add_argument("--authors", default="")
    parser.add_argument("--source-tag", default="local-pdf")
    parser.add_argument("--extract-path", default="")
    parser.add_argument("--translated-note-path", default="")
    parser.add_argument("--translation-template-path", default="")
    parser.add_argument("--copy-pdf", action="store_true")
    parser.add_argument("--note-style", choices=["auto", "legacy", "academic"], default="auto")
    parser.add_argument("--question-mode", choices=["A", "B"], default="A")
    args = parser.parse_args()

    config = load_json(Path(args.config))
    vault_root = Path(config["vault_root"])
    obs = config["obsidian"]
    note_style, paper_dir = resolve_note_style(vault_root, obs["paper_folder"], args.note_style)

    attachment_dir = vault_root / obs["attachment_folder"] / "papers"
    attachment_dir.mkdir(parents=True, exist_ok=True)

    title = args.title.strip()
    authors = split_authors(args.authors)

    if note_style == "academic":
        note_stem = build_filename(args.year, authors, build_short_title(title))
    else:
        note_stem = slugify(f"{args.year}-{title}")
    note_path = paper_dir / f"{note_stem}.md"

    source_pdf = Path(args.pdf_path)
    copied_pdf = ""
    if args.copy_pdf and source_pdf.exists():
        copied_target_name = build_attachment_stem(args.year, authors, title) + source_pdf.suffix.lower()
        copied_target = attachment_dir / copied_target_name
        if not copied_target.exists():
            shutil.copy2(source_pdf, copied_target)
        copied_pdf = str(copied_target)
    source_pdf_for_note = copied_pdf or str(source_pdf)

    if note_style == "academic":
        note_lines = build_academic_note_lines(args, title, authors, note_stem, source_pdf_for_note, copied_pdf)
        index_header = "# Literature Paper Index\n\n"
    else:
        note_lines = build_legacy_note_lines(args, title, source_pdf_for_note, copied_pdf)
        index_header = "# Paper Index\n\n"

    note_path.write_text("\n".join(note_lines), encoding="utf-8")
    note_reference = build_index_reference(note_path)
    update_index(paper_dir / "_Index.md", f"- {note_reference} | {args.year} | {args.source_tag}", index_header)
    try:
        paper_dossiers.sync_dossiers(config)
    except Exception as exc:
        print(f"Warning: paper dossier sync failed: {exc}", file=sys.stderr)
    print(str(note_path))


if __name__ == "__main__":
    main()
