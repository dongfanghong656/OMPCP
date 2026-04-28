#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path


SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md", ".html", ".htm"}
DEFAULT_EXCLUDE_ROOTS = (
    r"C:\Users\1\OneDrive - fzu.edu.cn",
)
INCLUDE_KEYWORDS = (
    "paper",
    "papers",
    "article",
    "journal",
    "literature",
    "review",
    "reference",
    "references",
    "research",
    "thesis",
    "oct",
    "optical coherence tomography",
    "psf",
    "deconvolution",
    "speckle",
    "photoacoustic",
    "microscopy",
    "文献",
    "参考文献",
    "论文",
    "期刊",
    "综述",
    "研究",
)
NON_LITERATURE_TOKENS = (
    "license",
    "readme",
    "changelog",
    "security",
    "support",
    "grammar",
    "installer",
    "installhelp",
    "sysreq",
    "quickstart",
    "setup/",
    "/setup",
    "third-party",
    "thirdpartynotices",
    "copyright",
    "translation/zh-cn",
    "bepinex",
    "rainbow-csv",
    "debugpy",
    "jupyter",
    "python_files",
    "addons/cycles",
    "soundtrack",
    "ost",
    "cloudmusic",
    "qqmusiccache",
    "apple music",
    "bdrip",
    "subtitle",
    "_preprocessors",
    "_substitutions",
    "installer_input",
    "license_agreement",
    "version.txt",
)
EXCLUDE_TOKENS = (
    ".git",
    ".venv",
    "__pycache__",
    "node_modules",
    "site-packages",
    "appdata",
    ".cache",
    ".codex",
    ".claude",
    ".trae",
    ".gemini",
    ".marscode",
    ".qoder",
    ".vscode",
    ".conda",
    "anaconda3",
    "codex_recovery",
    "codex-data",
    "desktop_app_cache",
    "localcache",
    "logs",
    "queue",
    "schemas",
    "tmp",
    "cache",
    "$recycle.bin",
    "system volume information",
    "oct-research-assist/vault",
    "oct-research-assist/vault/09_conversations",
    "oct-research-assist/vault/08_attachments/extracted",
    "oct-research-assist/reports",
)
YEAR_PREFIX_RE = re.compile(r"^(19|20)\d{2}\b")
HAS_CJK_RE = re.compile(r"[\u4e00-\u9fff]")


@dataclass
class CandidateRecord:
    source_path: str
    relative_path: str
    root_label: str
    extension: str
    reason: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Discover additional literature-like files in OneDrive/Downloads.")
    parser.add_argument("--roots", nargs="+", required=True)
    parser.add_argument("--exclude-root", action="append", default=[])
    parser.add_argument("--exclude-source-json", action="append", default=[])
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-md", required=True)
    return parser.parse_args()


def normalize(path: str) -> str:
    return path.replace("\\", "/").lower()


def build_exclude_roots(values: list[str]) -> list[Path]:
    exclude_roots = [Path(value) for value in values]
    for raw_path in DEFAULT_EXCLUDE_ROOTS:
        path = Path(raw_path)
        if path.exists():
            exclude_roots.append(path)
    return exclude_roots


def is_excluded(path: Path, exclude_roots: list[Path]) -> bool:
    normalized = normalize(str(path))
    if any(token in normalized for token in EXCLUDE_TOKENS):
        return True
    for root in exclude_roots:
        try:
            path.relative_to(root)
            return True
        except ValueError:
            continue
    return False


def gather_files(roots: list[Path], exclude_roots: list[Path]) -> tuple[list[tuple[Path, Path, str]], Counter[str]]:
    files: list[tuple[Path, Path, str]] = []
    dir_counts: Counter[str] = Counter()
    for root in roots:
        root_label = root.name or root.drive.rstrip(":\\") or root.anchor.replace("\\", "")
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                continue
            if is_excluded(path, exclude_roots):
                continue
            rel = path.relative_to(root).as_posix()
            files.append((root, path, rel))
            dir_counts[normalize(str(path.parent))] += 1
    return files, dir_counts


def looks_like_scholarly_title(stem: str) -> bool:
    normalized = stem.replace("_", " ").replace("-", " ")
    words = [part for part in normalized.split() if part]
    if HAS_CJK_RE.search(stem):
        return len(stem) >= 8
    return len(normalized) >= 28 and len(words) >= 4


def load_excluded_source_paths(paths: list[Path]) -> set[str]:
    excluded: set[str] = set()
    for path in paths:
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
        except Exception:
            continue
        if isinstance(payload, dict):
            if isinstance(payload.get("records"), list):
                items = payload["records"]
            else:
                items = []
        elif isinstance(payload, list):
            items = payload
        else:
            items = []
        for item in items:
            if not isinstance(item, dict):
                continue
            source_path = str(item.get("source_path", "")).strip()
            if source_path:
                excluded.add(normalize(source_path))
    return excluded


def candidate_reason(path: Path, rel: str, dense_dir_count: int) -> str:
    rel_lower = normalize(rel)
    name_lower = path.name.lower()
    if any(token in rel_lower for token in NON_LITERATURE_TOKENS):
        return ""
    if any(keyword in rel_lower for keyword in INCLUDE_KEYWORDS):
        return "keyword-path"
    if YEAR_PREFIX_RE.match(path.stem):
        return "year-prefix"
    if path.suffix.lower() in {".pdf", ".docx"} and looks_like_scholarly_title(path.stem):
        return "title-like"
    parent_lower = normalize(str(path.parent))
    if path.suffix.lower() == ".pdf" and dense_dir_count >= 3 and any(keyword in parent_lower for keyword in INCLUDE_KEYWORDS):
        return "pdf-dense-folder"
    if path.suffix.lower() in {".md", ".txt", ".html", ".htm"} and any(
        token in name_lower for token in ("paper", "article", "thesis", "review", "reference", "research", "论文", "综述", "文献")
    ):
        return "scholarly-text-name"
    if any(token in name_lower for token in ("oct", "psf", "deconvolution", "review", "optical coherence tomography", "thesis")):
        return "scholarly-name"
    return ""


def render_markdown(summary: dict[str, object], records: list[CandidateRecord]) -> str:
    lines = [
        "# 额外文献候选清单",
        "",
        f"- 生成时间：`{summary['generated_at']}`",
        f"- 候选总数：`{summary['candidate_total']}`",
        "",
        "## 根目录统计",
        "",
    ]
    for root_label, count in summary["by_root"].items():
        lines.append(f"- {root_label}: {count}")
    lines.extend(["", "## 扩展名统计", ""])
    for extension, count in summary["by_extension"].items():
        lines.append(f"- {extension}: {count}")
    lines.extend(["", "## 明细", ""])
    for record in records:
        lines.append(f"- [{record.root_label}] {record.relative_path} | {record.extension} | {record.reason}")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    roots = [Path(value) for value in args.roots]
    exclude_roots = build_exclude_roots(args.exclude_root)
    excluded_source_paths = load_excluded_source_paths([Path(value) for value in args.exclude_source_json])

    files, dir_counts = gather_files(roots, exclude_roots)

    records: list[CandidateRecord] = []
    by_root: Counter[str] = Counter()
    by_extension: Counter[str] = Counter()
    seen_paths: set[str] = set()

    for root, path, rel in files:
        reason = candidate_reason(path, rel, dir_counts[normalize(str(path.parent))])
        if not reason:
            continue
        source_path = str(path)
        if normalize(source_path) in excluded_source_paths:
            continue
        if source_path in seen_paths:
            continue
        seen_paths.add(source_path)
        root_label = root.name
        record = CandidateRecord(
            source_path=source_path,
            relative_path=f"{root_label}/{rel}",
            root_label=root_label,
            extension=path.suffix.lower(),
            reason=reason,
        )
        records.append(record)
        by_root[root_label] += 1
        by_extension[record.extension] += 1

    records.sort(key=lambda item: (item.root_label.lower(), item.relative_path.lower()))
    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "candidate_total": len(records),
        "by_root": dict(sorted(by_root.items())),
        "by_extension": dict(sorted(by_extension.items())),
    }

    output_json = Path(args.output_json)
    output_md = Path(args.output_md)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps([asdict(record) for record in records], ensure_ascii=False, indent=2), encoding="utf-8")
    output_md.write_text(render_markdown(summary, records), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
