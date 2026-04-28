#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import paper_dossiers


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = PROJECT_ROOT / "config.json"
DEFAULT_OUTPUT_ROOT = Path("C:/codex-data/tmp-vault-reorg")
PAPERS_DIR = Path("02_Literature") / "Papers"

CURATED_BATCHES: dict[str, list[str]] = {
    "foundation-system-1": [
        "02_Literature/Papers/[1991] Huang - Optical coherence tomography.md",
        "02_Literature/Papers/[2003] Choma - Sensitivity advantage of swept source and.md",
        "02_Literature/Papers/[2003] de Boer - Improved signal-to-noise ratio in spectral-domain compared.md",
        "02_Literature/Papers/[2003] 吴开杰 - OCT系统实用化的研究进展.md",
        "02_Literature/Papers/[2004] Cense - Ultrahigh-resolution high-speed retinal imaging using.md",
        "02_Literature/Papers/[2004] Nassif - In vivo high-resolution video-rate spectral-domain.md",
        "02_Literature/Papers/[2005] Wojtkowski - Three-dimensional Retinal Imaging with High-Speed.md",
        "02_Literature/Papers/[2010] 邹恒 - 基于时域和频域的光学相干层析成像系统的研究.md",
        "02_Literature/Papers/[2024] Ge - Deblurring artifact-free optical cohere-7ab44c80.md",
    ],
    "foundation-system-2": [
        "02_Literature/Papers/[1996] Tearney - Rapid acquisition of in vivo biological.md",
        "02_Literature/Papers/[1997] Su - Achieving variation of the optical path.md",
        "02_Literature/Papers/[1997] Unknown - In Vivo Endoscopic Optical Biopsy with.md",
        "02_Literature/Papers/[1997] Unknown - Rapid and scalable scans at 21.md",
        "02_Literature/Papers/[1998] Szydlo - Air-turbine driven optical low-coherence reflectometry.md",
        "02_Literature/Papers/[2003] Leitgeb - Performance of Fourier domain vs. time.md",
        "02_Literature/Papers/[2003] Unknown - Delay and dispersion characteristics of a.md",
        "02_Literature/Papers/[2004] Wojtkowski - Ultrahigh-resolution high-speed Fourier domain OCT.md",
        "02_Literature/Papers/[2006] Lim - High-speed imaging of human retina in.md",
        "02_Literature/Papers/[2008] Unknown - Fourier domain optical coherence tomography using.md",
        "02_Literature/Papers/[2011] An - High speed spectral domain optical coherence.md",
        "02_Literature/Papers/[2012] Choi - Spectral domain optical coherence tomography of.md",
    ],
    "system-specialization-1": [
        "02_Literature/Papers/[2008] de Bruin - In Vivo Three-Dimensional Imaging of Neovascular.md",
        "02_Literature/Papers/[2011] Zhong - Real-time monitoring of structural vibr-124708f5.md",
        "02_Literature/Papers/[2014] Wang - Precision control of piezo-actuated opt-da1c863a.md",
        "02_Literature/Papers/[2020] Unknown - Repetitive optical coherence elastography measurements with.md",
    ]
}


@dataclass
class BridgeRecord:
    rel_path: str
    title: str
    year: str
    source_tag: str
    status: str
    message: str


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def norm(path: str | Path) -> str:
    return Path(path).as_posix()


def yaml_list(key: str, values: list[str]) -> list[str]:
    cleaned = [paper_dossiers.normalize_whitespace(value) for value in values if paper_dossiers.normalize_whitespace(value)]
    if not cleaned:
        return [f"{key}: []"]
    lines = [f"{key}:"]
    for value in cleaned:
        lines.append(f"- {json.dumps(value, ensure_ascii=False)}")
    return lines


def split_source_note(text: str) -> tuple[dict[str, Any], str]:
    return paper_dossiers.split_frontmatter(text)


def pick_title(path: Path, frontmatter: dict[str, Any], body: str) -> str:
    return paper_dossiers.pick_title(path, body, frontmatter)


def first_nonempty(frontmatter: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = paper_dossiers.normalize_whitespace(frontmatter.get(key))
        if value:
            return value
    return ""


def extract_authors(frontmatter: dict[str, Any]) -> list[str]:
    return paper_dossiers.coerce_list(frontmatter.get("authors"))


def bridge_tags(frontmatter: dict[str, Any]) -> list[str]:
    tags = paper_dossiers.coerce_list(frontmatter.get("tags"))
    if "workspace-bridge" not in tags:
        tags.append("workspace-bridge")
    return tags


def portable(value: str) -> str:
    return paper_dossiers.to_portable_path(value) if value else ""


def filename_core_key(path: Path) -> str:
    stem = path.stem
    stem = re.sub(r"^\[\d{4}\]\s+.+?\s+-\s+", "", stem)
    return paper_dossiers.canonicalize_title(stem)


def build_bridge_note(
    *,
    rel_path: str,
    source_path: Path,
    frontmatter: dict[str, Any],
    body: str,
) -> str:
    title = pick_title(source_path, frontmatter, body)
    title_en = first_nonempty(frontmatter, "title_en")
    title_zh = first_nonempty(frontmatter, "title_zh")
    title_display = first_nonempty(frontmatter, "title_display", "title_zh", "title", "title_en") or title
    year = first_nonempty(frontmatter, "year")
    venue = first_nonempty(frontmatter, "venue")
    doi = paper_dossiers.normalize_doi(frontmatter.get("doi"))
    status = first_nonempty(frontmatter, "status") or "to-read"
    reading_stage = first_nonempty(frontmatter, "reading_stage") or "skim"
    language = first_nonempty(frontmatter, "language") or ("zh-CN" if any("\u4e00" <= ch <= "\u9fff" for ch in title_display) else "en")
    source_pdf = portable(first_nonempty(frontmatter, "source_pdf", "copied_pdf"))
    extract_path = portable(first_nonempty(frontmatter, "extract_path"))
    translated_note_path = portable(first_nonempty(frontmatter, "translated_note_path"))
    authors = extract_authors(frontmatter)
    tags = bridge_tags(frontmatter)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    lines = [
        "---",
        'type: "paper"',
        f"title: {json.dumps(title, ensure_ascii=False)}",
        f"title_en: {json.dumps(title_en, ensure_ascii=False)}",
        f"title_zh: {json.dumps(title_zh, ensure_ascii=False)}",
        f"title_display: {json.dumps(title_display, ensure_ascii=False)}",
    ]
    lines.extend(yaml_list("authors", authors))
    lines.extend(
        [
            f"year: {json.dumps(year, ensure_ascii=False)}",
            f"venue: {json.dumps(venue, ensure_ascii=False)}",
            f"doi: {json.dumps(doi, ensure_ascii=False)}",
            f"status: {json.dumps(status, ensure_ascii=False)}",
            f"reading_stage: {json.dumps(reading_stage, ensure_ascii=False)}",
            f"language: {json.dumps(language, ensure_ascii=False)}",
        ]
    )
    lines.extend(yaml_list("tags", tags))
    lines.extend(
        [
            'source_tag: "workspace-bridge"',
            f"source_note_path: {json.dumps(portable(source_path), ensure_ascii=False)}",
            f"source_pdf: {json.dumps(source_pdf, ensure_ascii=False)}",
            f"extract_path: {json.dumps(extract_path, ensure_ascii=False)}",
            f"translated_note_path: {json.dumps(translated_note_path, ensure_ascii=False)}",
            f"bridge_created: {json.dumps(now, ensure_ascii=False)}",
            "---",
            "",
            f"# {title_display}",
            "",
            "这是一篇 workspace bridge 笔记，用来把当前缺失在 workspace 里的关键论文重新接回阅读、检索和进展入口。完整长笔记仍保存在 `source_note_path` 指向的 source vault。",
            "",
            "## 当前用途",
            "",
            "- 作为读者入口和研究主线里的稳定落点",
            "- 保留最关键的元数据、PDF、抽取和译文路径",
            "- 避免入口继续跳到当前 workspace 缺失的单篇论文目录",
            "",
            "## 快速进入",
            "",
            f"- 原始长笔记：`{portable(source_path)}`",
        ]
    )
    if source_pdf:
        lines.append(f"- PDF：`{source_pdf}`")
    if extract_path:
        lines.append(f"- 抽取：`{extract_path}`")
    if translated_note_path:
        lines.append(f"- 译文：`{translated_note_path}`")
    lines.extend(
        [
            "- 文献索引：[[02_Literature/Papers/_Index|文献论文索引]]",
            "- 阅读入口：[[13_阅读区/02_文献阅读区/文献阅读起步入口|文献阅读起步入口]]",
            "- 检索入口：[[13_阅读区/09_项目进展与管理/检索与文献管理总览|检索与文献管理总览]]",
            "",
            "## 当前判断",
            "",
            "这篇桥接笔记的任务不是替代原始长笔记，而是先把论文重新接回当前 workspace 的导航层，确保你能从主线入口、检索入口和论文索引里稳定找到它。",
            "",
        ]
    )
    return "\n".join(lines)


def index_reference(rel_path: str) -> str:
    path = Path(rel_path)
    return f"[{path.stem}](<{path.name}>)"


def note_summary_from_text(path: Path, text: str) -> tuple[str, str, str]:
    frontmatter, body = split_source_note(text)
    title = pick_title(path, frontmatter, body)
    year = first_nonempty(frontmatter, "year")
    source_tag = first_nonempty(frontmatter, "source_tag") or "workspace-bridge"
    return title, year, source_tag


def is_real_paper_note(frontmatter: dict[str, Any]) -> bool:
    return not paper_dossiers.is_synthetic_example_note(frontmatter)


def collect_existing_paper_state(workspace_vault_root: Path) -> tuple[list[tuple[str, str, str, str]], set[str], set[str], set[str]]:
    summaries: list[tuple[str, str, str, str]] = []
    title_keys: set[str] = set()
    doi_keys: set[str] = set()
    filename_keys: set[str] = set()
    paper_dir = workspace_vault_root / PAPERS_DIR
    for note_path in sorted(paper_dir.glob("*.md")):
        if note_path.name == "_Index.md":
            continue
        try:
            text = note_path.read_text(encoding="utf-8-sig")
        except OSError:
            continue
        frontmatter, body = split_source_note(text)
        if not is_real_paper_note(frontmatter):
            continue
        title = pick_title(note_path, frontmatter, body)
        year = first_nonempty(frontmatter, "year")
        source_tag = first_nonempty(frontmatter, "source_tag") or "workspace-bridge"
        summaries.append((note_path.name, title, year, source_tag))
        title_key = paper_dossiers.canonicalize_title(title)
        doi_key = paper_dossiers.normalize_doi(frontmatter.get("doi"))
        filename_key = filename_core_key(note_path)
        if title_key:
            title_keys.add(title_key)
        if doi_key:
            doi_keys.add(doi_key)
        if filename_key:
            filename_keys.add(filename_key)
    return summaries, title_keys, doi_keys, filename_keys


def build_papers_index(existing: list[tuple[str, str, str, str]], added: list[tuple[str, str, str, str]]) -> str:
    merged: dict[str, tuple[str, str, str]] = {}
    for filename, title, year, source_tag in existing + added:
        merged[filename] = (title, year, source_tag)
    lines = ["# Literature Paper Index", ""]
    rows = sorted(
        merged.items(),
        key=lambda item: (
            item[1][1] or "9999",
            item[1][0].lower(),
            item[0].lower(),
        ),
    )
    for filename, (title, year, source_tag) in rows:
        rel_path = norm(PAPERS_DIR / filename)
        lines.append(f"- {index_reference(rel_path)} | {year or 'unknown'} | {source_tag or 'workspace-bridge'}")
    lines.append("")
    return "\n".join(lines)


def generate_bundle(
    *,
    source_vault_root: Path,
    workspace_vault_root: Path,
    output_root: Path,
    run_label: str,
    batch_name: str,
) -> Path:
    rel_paths = CURATED_BATCHES[batch_name]
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = output_root / "vault-reorg" / f"{timestamp}-{run_label}"
    bundle_root = run_dir / "bundle"
    bundle_root.mkdir(parents=True, exist_ok=True)

    existing_summaries, existing_title_keys, existing_doi_keys, existing_filename_keys = collect_existing_paper_state(
        workspace_vault_root
    )
    records: list[BridgeRecord] = []
    added_summaries: list[tuple[str, str, str, str]] = []
    added_title_keys: set[str] = set()
    added_doi_keys: set[str] = set()
    added_filename_keys: set[str] = set()

    for rel_path in rel_paths:
        source_path = source_vault_root / rel_path
        workspace_path = workspace_vault_root / rel_path
        if workspace_path.exists():
            records.append(
                BridgeRecord(
                    rel_path=rel_path,
                    title=Path(rel_path).stem,
                    year="",
                    source_tag="workspace-existing",
                    status="skipped",
                    message="Already exists in workspace.",
                )
            )
            continue
        if not source_path.exists():
            records.append(
                BridgeRecord(
                    rel_path=rel_path,
                    title=Path(rel_path).stem,
                    year="",
                    source_tag="missing-source",
                    status="missing-source",
                    message="Source note does not exist in source vault.",
                )
            )
            continue
        source_text = source_path.read_text(encoding="utf-8-sig")
        frontmatter, body = split_source_note(source_text)
        if not is_real_paper_note(frontmatter):
            records.append(
                BridgeRecord(
                    rel_path=rel_path,
                    title=Path(rel_path).stem,
                    year=first_nonempty(frontmatter, "year"),
                    source_tag="synthetic-example",
                    status="skipped",
                    message="Source note is a synthetic/example paper note and was excluded.",
                )
            )
            continue
        title = pick_title(source_path, frontmatter, body)
        year = first_nonempty(frontmatter, "year")
        title_key = paper_dossiers.canonicalize_title(title)
        doi_key = paper_dossiers.normalize_doi(frontmatter.get("doi"))
        filename_key = filename_core_key(source_path)
        if (
            (doi_key and doi_key in existing_doi_keys)
            or (title_key and title_key in existing_title_keys)
            or (filename_key and filename_key in existing_filename_keys)
        ):
            records.append(
                BridgeRecord(
                    rel_path=rel_path,
                    title=title,
                    year=year,
                    source_tag="duplicate-existing",
                    status="skipped",
                    message="A matching paper already exists in workspace by DOI, title, or filename core.",
                )
            )
            continue
        if (
            (doi_key and doi_key in added_doi_keys)
            or (title_key and title_key in added_title_keys)
            or (filename_key and filename_key in added_filename_keys)
        ):
            records.append(
                BridgeRecord(
                    rel_path=rel_path,
                    title=title,
                    year=year,
                    source_tag="duplicate-batch",
                    status="skipped",
                    message="A matching paper was already bridged earlier in this batch.",
                )
            )
            continue
        bridge_text = build_bridge_note(
            rel_path=rel_path,
            source_path=source_path,
            frontmatter=frontmatter,
            body=body,
        )
        target_path = bundle_root / rel_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(bridge_text, encoding="utf-8")
        added_summaries.append((Path(rel_path).name, title, year, "workspace-bridge"))
        if title_key:
            added_title_keys.add(title_key)
        if doi_key:
            added_doi_keys.add(doi_key)
        if filename_key:
            added_filename_keys.add(filename_key)
        records.append(
            BridgeRecord(
                rel_path=rel_path,
                title=title,
                year=year,
                source_tag="workspace-bridge",
                status="bridged",
                message="Bridge note written into bundle.",
            )
        )

    papers_index = build_papers_index(existing_summaries, added_summaries)
    index_path = bundle_root / PAPERS_DIR / "_Index.md"
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(papers_index, encoding="utf-8")

    report_lines = [
        f"# {run_label}",
        "",
        f"- batch: `{batch_name}`",
        f"- source_vault_root: `{paper_dossiers.to_portable_path(source_vault_root)}`",
        f"- workspace_vault_root: `{paper_dossiers.to_portable_path(workspace_vault_root)}`",
        f"- bundle_root: `{paper_dossiers.to_portable_path(bundle_root)}`",
        "",
        "## Records",
        "",
    ]
    for record in records:
        report_lines.append(
            f"- `{record.status}` | `{record.year or 'unknown'}` | `{record.rel_path}` | {record.message}"
        )
    report_lines.append("")
    (run_dir / "run.md").write_text("\n".join(report_lines), encoding="utf-8")
    (run_dir / "manifest.json").write_text(
        json.dumps(
            {
                "run_label": run_label,
                "batch": batch_name,
                "records": [record.__dict__ for record in records],
                "bundle_root": paper_dossiers.to_portable_path(bundle_root),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return run_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a workspace paper-bridge bundle for missing key paper notes.")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument(
        "--workspace-vault-root",
        default=str(PROJECT_ROOT / "vault"),
        help="Workspace vault root to compare against and target for bundle layout.",
    )
    parser.add_argument(
        "--output-root",
        default=str(DEFAULT_OUTPUT_ROOT),
        help="Root directory for generated run artifacts.",
    )
    parser.add_argument("--run-label", default="workspace-paper-bridge-batch")
    parser.add_argument("--batch", default="foundation-system-1", choices=sorted(CURATED_BATCHES))
    args = parser.parse_args()

    config = load_json(Path(args.config))
    source_vault_root = Path(config["vault_root"])
    workspace_vault_root = Path(args.workspace_vault_root)
    output_root = Path(args.output_root)
    run_dir = generate_bundle(
        source_vault_root=source_vault_root,
        workspace_vault_root=workspace_vault_root,
        output_root=output_root,
        run_label=args.run_label,
        batch_name=args.batch,
    )
    print(run_dir)


if __name__ == "__main__":
    main()
