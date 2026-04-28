from __future__ import annotations

from pathlib import Path
from textwrap import dedent


VAULT_ROOT = Path(
    r"C:\Users\1\OneDrive - fzu.edu.cn (1)\Attachments\OCT_Research_System\oct-research-assist\vault"
)
QUESTIONS_DIR = VAULT_ROOT / "04_Research/Questions"
CONCEPTS_DIR = VAULT_ROOT / "02_Literature/Concepts"
DASHBOARD_PATH = VAULT_ROOT / "00_System/02_Views/Questions Dashboard.md"


ZH_MAP = {
    "A-line rate": "A线速率",
    "A-scan resolution": "A-scan 分辨率",
    "Fourier domain OCT": "频域 OCT",
    "SNR advantage": "信噪比优势",
    "Wigner-Ville distribution": "Wigner-Ville 分布",
    "actuator hysteresis": "执行器迟滞",
    "artifact control": "伪影控制",
    "blind deconvolution": "盲反卷积",
    "cost-performance tradeoff": "成本性能权衡",
    "dispersion compensation": "色散补偿",
    "local PSF": "局部 PSF",
    "noise amplification": "噪声放大",
    "optical delay line": "光学延迟线",
    "practicalization": "实用化",
    "random phase modulation": "随机相位调制",
    "real-time display": "实时显示",
    "regularization": "正则化",
    "resolution uniformity": "分辨率均匀性",
    "scan linearity": "扫描线性",
    "sensitivity roll-off": "灵敏度滚降",
    "superresolution": "超分辨",
    "system baseline": "系统基线",
    "system calibration": "系统校准",
    "system complexity": "系统复杂度",
    "system integration": "系统集成",
    "task-based evaluation": "任务导向评估",
    "time-frequency reassignment": "时频重分配",
}

NAME_MAP = {
    "A-line rate": "A-line Rate",
    "A-scan resolution": "A-scan Resolution",
    "Fourier domain OCT": "Fourier-domain OCT",
    "SNR advantage": "SNR Advantage",
    "Wigner-Ville distribution": "Wigner-Ville Distribution",
    "local PSF": "Local PSF",
    "real-time display": "Real-time Display",
    "sensitivity roll-off": "Sensitivity Roll-off",
    "task-based evaluation": "Task-based Evaluation",
    "time-frequency reassignment": "Time-frequency Reassignment",
    "cost-performance tradeoff": "Cost-performance Tradeoff",
}

PENDING_BLOCK = dedent(
    """\
    ### Pending 占位问题
    > [!info]
    > 这一栏专门抓已经写进论文页、但目前仍保留为占位状态的用户问题。
    ```dataview
    TABLE WITHOUT ID
      file.link AS "文献",
      item.question_id AS "问题 ID",
      item.question_text AS "占位问题",
      item.tentative_answer AS "当前判断",
      item.note AS "说明"
    FROM "02_Literature/Papers"
    FLATTEN file.lists AS item
    WHERE item.question_id
      AND item.status = "pending"
      AND contains(item.note, "模板占位")
    SORT file.name ASC, item.question_id ASC
    ```
    """
)


def note_title(term: str) -> str:
    if term in NAME_MAP:
        return NAME_MAP[term]
    return " ".join(word.capitalize() for word in term.split())


def parse_question_files() -> dict[str, set[str]]:
    concept_papers: dict[str, set[str]] = {}
    for path in sorted(QUESTIONS_DIR.glob("Question - *.md")):
        lines = path.read_text(encoding="utf-8").splitlines()
        papers: list[str] = []
        mode = None
        for line in lines:
            if line.startswith("related_papers:"):
                mode = "papers"
                continue
            if line.startswith("related_concepts:"):
                mode = "concepts"
                continue
            if mode == "papers":
                if line.startswith("  - "):
                    papers.append(line.strip()[2:].strip().strip('"'))
                    continue
                mode = None
            if mode == "concepts":
                if line.startswith("  - "):
                    item = line.strip()[2:].strip().strip('"')
                    concept_papers.setdefault(item, set()).update(papers)
                    continue
                mode = None
    return concept_papers


def write_concept_note(term: str, papers: set[str]) -> None:
    title = note_title(term)
    path = CONCEPTS_DIR / f"Concept - {title}.md"
    if path.name == "Concept - Point Spread Function.md":
        return
    zh = ZH_MAP.get(term, term)
    definition = f"{zh} 概念卡，当前由问题页中的 related_concepts 反向整理生成，后续可补更精确的定义和引文。"
    related_papers_lines = [f'  - "{paper}"' for paper in sorted(papers)] or ["  []"]
    appear_lines = [f"- {paper}" for paper in sorted(papers)] or ["- 待补"]
    content_lines = [
        "---",
        "type: concept",
        f'term: "{title}"',
        f'term_en: "{term}"',
        f'term_zh: "{zh}"',
        f'definition: "{definition}"',
        "related_papers:",
        *related_papers_lines,
        "related_authors: []",
        "debates:",
        '  - "这张概念卡目前仍需补充更具体的作者差异与定义边界"',
        'my_note: "先保证问题页可以链接到概念卡，后续再逐步补厚。"',
        "tags:",
        "  - concept",
        "  - oct",
        "cssclasses:",
        "  - concept-note",
        "---",
        "",
        "# 定义",
        "",
        definition,
        "",
        "# 在哪些论文中出现",
        "",
        *appear_lines,
        "",
        "# 不同作者如何使用",
        "",
        "这张概念卡目前主要由问题页反向整理，后续可继续细化。",
        "",
        "# 争议点",
        "",
        "- 不同论文里对这个概念的评价口径可能并不一致。",
        "",
        "# 与我研究的关系",
        "",
        "它帮助我把研究问题、系统边界和方法判断连接起来。",
        "",
        "# 相关引文",
        "",
        "> [!concept]",
        "> 当前为最小可用概念卡，后续可补精确引文。",
        "",
    ]
    content = "\n".join(content_lines)
    path.write_text(content, encoding="utf-8", newline="\n")


def update_related_concepts(path: Path) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    out: list[str] = []
    capture = False
    for line in lines:
        if line.startswith("related_concepts:"):
            capture = True
            out.append(line)
            continue
        if capture and (line.startswith("status:") or line.startswith("importance:")):
            capture = False
            out.append(line)
            continue
        if capture and line.startswith("  - "):
            item = line.strip()[2:].strip().strip('"')
            if item.startswith("[[Concept - "):
                out.append(line)
            else:
                out.append(f'  - "[[Concept - {note_title(item)}]]"')
            continue
        if not capture:
            out.append(line)
    path.write_text("\n".join(out) + "\n", encoding="utf-8", newline="\n")


def enhance_dashboard() -> None:
    text = DASHBOARD_PATH.read_text(encoding="utf-8")
    if "### Pending 占位问题" in text:
        return
    marker = "### 所有 Q2 尚未完成的论文"
    if marker in text:
        text = text.replace(marker, PENDING_BLOCK + "\n" + marker, 1)
    else:
        text = text.rstrip() + "\n\n" + PENDING_BLOCK + "\n"
    DASHBOARD_PATH.write_text(text, encoding="utf-8", newline="\n")


def normalize_generated_concept_notes() -> None:
    for path in CONCEPTS_DIR.glob("Concept - *.md"):
        if path.name == "Concept - Point Spread Function.md":
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        if not lines or not lines[0].startswith("        "):
            continue
        fixed = []
        for line in lines:
            if line.startswith("        "):
                fixed.append(line[8:])
            else:
                fixed.append(line)
        path.write_text("\n".join(fixed) + "\n", encoding="utf-8", newline="\n")


def main() -> None:
    CONCEPTS_DIR.mkdir(parents=True, exist_ok=True)
    concept_papers = parse_question_files()
    for concept, papers in concept_papers.items():
        if concept.startswith("[[Concept - "):
            continue
        write_concept_note(concept, papers)
    normalize_generated_concept_notes()
    for path in sorted(QUESTIONS_DIR.glob("Question - *.md")):
        update_related_concepts(path)
        print(f"Updated question note: {path}")
    enhance_dashboard()
    print(f"Enhanced dashboard: {DASHBOARD_PATH}")


if __name__ == "__main__":
    main()
