from __future__ import annotations

from pathlib import Path
from textwrap import dedent
import re


VAULT_ROOT = Path(
    r"C:\Users\1\OneDrive - fzu.edu.cn (1)\Attachments\OCT_Research_System\oct-research-assist\vault"
)
CONCEPTS_DIR = VAULT_ROOT / "02_Literature/Concepts"
PAPERS_DIR = VAULT_ROOT / "02_Literature/Papers"
DASHBOARD_PATH = VAULT_ROOT / "00_System/02_Views/Questions Dashboard.md"


MOTIF_BLOCK = dedent(
    """\
    ### 按研究母题分组
    > [!question|q2]
    > 这里按独立问题页的 `tags` 轻量分组，方便快速看当前问题库主要集中在哪些研究母题上。
    ```dataview
    TABLE rows.file.link AS "问题页", rows.importance AS "重要性", rows.related_papers AS "相关论文"
    FROM "04_Research/Questions"
    FLATTEN tags AS motif
    WHERE type = "research-question" AND motif != "research-question"
    GROUP BY motif
    SORT key ASC
    ```
    """
)


def extract_related_papers(lines: list[str]) -> list[str]:
    papers = []
    capture = False
    for line in lines:
        if line.startswith("related_papers:"):
            capture = True
            continue
        if capture and not line.startswith("  - "):
            break
        if capture and line.startswith("  - "):
            papers.append(normalize_wikilink(line.strip()[2:].strip().strip('"')))
    return papers


def normalize_wikilink(link: str) -> str:
    link = link.strip().strip('"')
    if link.startswith("[["):
        core = link[2:].rstrip("]").strip()
        if re.match(r"^\d{4}\]", core):
            core = "[" + core
        return f"[[{core}]]"
    return link


def normalize_related_papers_block(path: Path) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    out = []
    capture = False
    for line in lines:
        if line.startswith("related_papers:"):
            capture = True
            out.append(line)
            continue
        if capture and line.startswith("  - "):
            value = normalize_wikilink(line.strip()[2:].strip().strip('"'))
            out.append(f'  - "{value}"')
            continue
        if capture and not line.startswith("  - "):
            capture = False
        out.append(line)
    path.write_text("\n".join(out) + "\n", encoding="utf-8", newline="\n")


def tokenize(term: str) -> list[str]:
    raw = re.split(r"[^A-Za-z0-9\u4e00-\u9fff\-]+", term)
    tokens = [t.lower() for t in raw if len(t) >= 3]
    return tokens


def candidate_lines(text: str) -> list[str]:
    lines = []
    started = False
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line == "---":
            continue
        if line.startswith("#"):
            started = True
            continue
        if not started:
            continue
        if re.match(r"^[A-Za-z_][A-Za-z0-9_-]*:\s*", line):
            continue
        if (
            len(line) < 20
            or "/auto/" in line
            or ".md" in line
            or line.startswith("Tags")
            or line.startswith("Attachments")
            or "Zotero note" in line
            or line in {'"oct-paper"', "'oct-paper'"}
            or (line.startswith('"') and line.endswith('"') and len(line) < 50)
        ):
            continue
        if line.startswith("> [!") or line.startswith("```"):
            continue
        if line.startswith("> "):
            line = line[2:].strip()
        if line.startswith("- "):
            line = line[2:].strip()
        if "::" in line:
            continue
        lines.append(line)
    return lines


def paper_path_from_link(link: str) -> Path | None:
    target = normalize_wikilink(link)
    if target.startswith("[[") and target.endswith("]]"):
        target = target[2:-2]
    candidate = PAPERS_DIR / f"{target}.md"
    return candidate if candidate.exists() else None


def pick_quote(term: str, text: str) -> str | None:
    tokens = tokenize(term)
    lines = candidate_lines(text)
    for line in lines:
        low = line.lower()
        if any(tok in low for tok in tokens):
            return line[:160]
    for line in lines:
        if "作者核心主张一句话版本" in line:
            return line.split("：", 1)[-1][:160]
    return lines[0][:160] if lines else None


def update_concept_note_quotes(path: Path) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    term_line = next((line for line in lines if line.startswith("term_en: ")), "")
    term = term_line.split(":", 1)[1].strip().strip('"') if term_line else path.stem.replace("Concept - ", "")
    papers = extract_related_papers(lines)
    citations = []
    for link in papers:
        paper_path = paper_path_from_link(link)
        if not paper_path:
            continue
        quote = pick_quote(term, paper_path.read_text(encoding="utf-8"))
        if not quote:
            continue
        citations.extend(
            [
                "> [!citation]",
                f"> 来源：{link}",
                f'> “{quote}”',
                "",
            ]
        )
        if len([line for line in citations if line == "> [!citation]"]) >= 2:
            break
    if not citations:
        citations = [
            "> [!citation]",
            "> 当前尚未自动抽到合适引句，后续可手动补精确摘录。",
            "",
        ]

    text = "\n".join(lines)
    marker = "# 相关引文"
    if marker in text:
        before = text.split(marker, 1)[0]
        new_text = before.rstrip() + "\n\n" + marker + "\n\n" + "\n".join(citations).rstrip() + "\n"
    else:
        new_text = text.rstrip() + "\n\n" + marker + "\n\n" + "\n".join(citations).rstrip() + "\n"
    path.write_text(new_text, encoding="utf-8", newline="\n")


def enhance_dashboard() -> None:
    text = DASHBOARD_PATH.read_text(encoding="utf-8")
    if "### 按研究母题分组" in text:
        return
    marker = "### Pending 占位问题"
    if marker in text:
        text = text.replace(marker, MOTIF_BLOCK + "\n" + marker, 1)
    else:
        text = text.rstrip() + "\n\n" + MOTIF_BLOCK + "\n"
    DASHBOARD_PATH.write_text(text, encoding="utf-8", newline="\n")


def main() -> None:
    for path in sorted((list(CONCEPTS_DIR.glob("Concept - *.md")) + list((VAULT_ROOT / "04_Research/Questions").glob("Question - *.md")))):
        normalize_related_papers_block(path)
    for path in sorted(CONCEPTS_DIR.glob("Concept - *.md")):
        if path.name == "Concept - Point Spread Function.md":
            continue
        update_concept_note_quotes(path)
        print(f"Updated concept quotes: {path}")
    enhance_dashboard()
    print(f"Enhanced dashboard motifs: {DASHBOARD_PATH}")


if __name__ == "__main__":
    main()
