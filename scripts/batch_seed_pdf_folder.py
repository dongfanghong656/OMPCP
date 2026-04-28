#!/usr/bin/env python
import argparse
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import seed_paper_note

try:
    from pypdf import PdfReader  # type: ignore[import-not-found]
except ModuleNotFoundError:
    PdfReader = None


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def safe_stem(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("_") or "paper"


def looks_placeholder_title(value: str) -> bool:
    text = normalize_space(value)
    if not text:
        return True
    lowered = text.lower()
    if lowered.startswith("title:") or lowered.startswith("pii:"):
        return True
    if re.fullmatch(r"[a-z]+\d{4}", lowered):
        return True
    if len(text) < 8:
        return True
    return False


def guess_title_from_filename(path: Path) -> str:
    title = path.stem
    title = re.sub(r"^\[\d+\]\s*", "", title)
    title = title.replace("_", " ")
    title = re.sub(r"\s+", " ", title).strip(" -")
    return title


def extract_page_texts(pdf_path: Path):
    reader_cls = PdfReader
    if reader_cls is None:
        raise ModuleNotFoundError(
            "pypdf is required for PDF text extraction in batch_seed_pdf_folder.py. "
            "Install it in the active Python interpreter before running this extraction path."
        )
    reader = reader_cls(str(pdf_path))
    page_texts = []
    for page in reader.pages:
        page_texts.append(page.extract_text() or "")
    return reader, page_texts


def title_line_score(line: str) -> int:
    line = normalize_space(line)
    if not line:
        return -999
    lowered = line.lower()
    bad_prefixes = (
        "abstract",
        "introduction",
        "department",
        "school of",
        "university",
        "received",
        "accepted",
        "keywords",
        "key words",
        "doi",
        "www.",
        "http",
        "email",
    )
    if any(lowered.startswith(prefix) for prefix in bad_prefixes):
        return -999
    if "researchgate.net" in lowered or "see discussions, stats, and author profiles" in lowered:
        return -999
    if "@" in line:
        return -999
    if re.search(r"\b(vol\.?|no\.?|issue|pages?)\b", lowered):
        return -200
    if re.search(r"^\d+$", line):
        return -999
    if len(line) < 20 or len(line) > 220:
        return -200
    if re.search(r"[A-Za-z\u4e00-\u9fff]", line) is None:
        return -999
    score = len(line)
    if ":" in line:
        score += 8
    if line.count(",") <= 2:
        score += 5
    if re.search(r"\b(optical|coherence|tomography|interferometry|imaging|spectral|swept)\b", lowered):
        score += 20
    if line[0].isupper():
        score += 5
    return score


def guess_title_from_text(file_title: str, page_texts):
    filename_guess = guess_title_from_filename(Path(file_title))
    if page_texts:
        lines = []
        for raw in page_texts[0].splitlines()[:40]:
            line = normalize_space(raw)
            if line:
                lines.append(line)

        best = ""
        best_score = -999
        for idx, line in enumerate(lines):
            combined = line
            if idx + 1 < len(lines):
                nxt = lines[idx + 1]
                if len(combined) + len(nxt) < 220 and not re.search(
                    r"\b(university|department|school|institute|abstract|received|accepted)\b",
                    nxt.lower(),
                ):
                    combined = normalize_space(f"{line} {nxt}")
            for candidate in {line, combined}:
                score = title_line_score(candidate)
                if score > best_score:
                    best = candidate
                    best_score = score
        if best_score > 30:
            return best
    return filename_guess


def guess_year(path: Path, meta_title: str, page_texts, metadata):
    candidates = [
        str(metadata.get("/CreationDate") or ""),
        str(metadata.get("/ModDate") or ""),
        meta_title,
        guess_title_from_filename(path),
        page_texts[0] if page_texts else "",
    ]
    for item in candidates:
        match = re.search(r"(19|20)\d{2}", item)
        if match:
            return match.group(0)
    return "1900"


def clean_authors(value: str) -> str:
    text = normalize_space(value)
    text = re.sub(r"[*0-9]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip(" ,;")
    return text


def guess_authors(meta_author: str, page_texts, title: str) -> str:
    meta_author = clean_authors(meta_author)
    if meta_author:
        return meta_author

    if not page_texts:
        return ""

    title_key = normalize_space(title).lower()
    lines = [normalize_space(line) for line in page_texts[0].splitlines()[:45] if normalize_space(line)]
    for idx, line in enumerate(lines):
        if title_key and title_key in line.lower():
            for probe in lines[idx + 1 : idx + 6]:
                lowered = probe.lower()
                if any(
                    token in lowered
                    for token in ("abstract", "department", "university", "school", "institute", "@")
                ):
                    break
                if len(probe) < 4 or len(probe) > 180:
                    continue
                if re.search(r"[A-Za-z]", probe) is None:
                    continue
                if probe.count(",") >= 1 or " and " in lowered:
                    return clean_authors(probe)
    return ""


def write_pypdf_extract(vault_root: Path, pdf_path: Path, title: str, page_texts):
    extract_root = vault_root / "08_Attachments" / "extracted" / safe_stem(pdf_path.stem)
    extract_root.mkdir(parents=True, exist_ok=True)
    extract_path = extract_root / "pypdf-extract.md"
    lines = [f"# {title}", "", f"- Source PDF: `{pdf_path.as_posix()}`", ""]
    for idx, text in enumerate(page_texts, start=1):
        lines.append(f"## Page {idx}")
        lines.append("")
        lines.append(text.strip())
        lines.append("")
    extract_path.write_text("\n".join(lines), encoding="utf-8")
    return extract_path


def write_metadata_only_extract(vault_root: Path, pdf_path: Path, title: str, reason: str):
    extract_root = vault_root / "08_Attachments" / "extracted" / safe_stem(pdf_path.stem)
    extract_root.mkdir(parents=True, exist_ok=True)
    extract_path = extract_root / "metadata-only-extract.md"
    lines = [
        f"# {title}",
        "",
        f"- Source PDF: `{pdf_path.as_posix()}`",
        f"- Extraction status: metadata-only",
        f"- Reason: {reason}",
        "",
        "PDF text extraction was skipped. The source PDF was still copied into the vault, and the paper note was seeded from metadata overrides.",
        "",
    ]
    extract_path.write_text("\n".join(lines), encoding="utf-8")
    return extract_path


def determine_note_path(config: dict, title: str, year: str, authors: str, note_style_arg: str):
    vault_root = Path(config["vault_root"])
    obs = config["obsidian"]
    note_style, paper_dir = seed_paper_note.resolve_note_style(vault_root, obs["paper_folder"], note_style_arg)
    if note_style == "academic":
        author_parts = seed_paper_note.split_authors(authors)
        note_stem = seed_paper_note.build_filename(year, author_parts, seed_paper_note.build_short_title(title))
    else:
        note_stem = seed_paper_note.slugify(f"{year}-{title}")
    return paper_dir / f"{note_stem}.md"


def load_overrides(path: Path | None):
    if not path:
        return {}
    payload = load_json(path)
    if isinstance(payload, list):
        return {item["file"]: item for item in payload if isinstance(item, dict) and item.get("file")}
    if isinstance(payload, dict):
        return payload
    return {}


def build_seed_command(
    script_dir: Path,
    config_path: Path,
    pdf_path: Path,
    title: str,
    year: str,
    authors: str,
    source_tag: str,
    extract_path: Path,
    note_style: str,
):
    cmd = [
        sys.executable,
        str(script_dir / "seed_paper_note.py"),
        "--config",
        str(config_path),
        "--pdf-path",
        str(pdf_path),
        "--title",
        title,
        "--year",
        year,
        "--source-tag",
        source_tag,
        "--extract-path",
        str(extract_path),
        "--copy-pdf",
        "--note-style",
        note_style,
    ]
    if authors:
        cmd.extend(["--authors", authors])
    return cmd


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--folder", required=True)
    parser.add_argument("--source-tag", default="local-folder-pypdf")
    parser.add_argument("--manifest-out", default="")
    parser.add_argument("--overrides-json", default="")
    parser.add_argument("--max-files", type=int, default=0)
    parser.add_argument("--skip-existing", action="store_true")
    parser.add_argument("--note-style", choices=["auto", "legacy", "academic"], default="auto")
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    config_path = Path(args.config).resolve()
    config = load_json(config_path)
    vault_root = Path(config["vault_root"])
    folder = Path(args.folder).resolve()
    overrides = load_overrides(Path(args.overrides_json).resolve() if args.overrides_json else None)

    pdf_paths = sorted(folder.glob("*.pdf"))
    if args.max_files > 0:
        pdf_paths = pdf_paths[: args.max_files]

    results = []
    for pdf_path in pdf_paths:
        override = overrides.get(pdf_path.name, {})
        if override.get("skip"):
            results.append(
                {
                    "file": pdf_path.name,
                    "status": "skipped",
                    "reason": override.get("reason", "skip requested"),
                }
            )
            continue

        row = {"file": pdf_path.name, "pdf_path": str(pdf_path)}
        try:
            if PdfReader is None and override.get("title") and override.get("year"):
                page_texts = []
                title = normalize_space(override.get("title") or guess_title_from_filename(pdf_path))
                year = normalize_space(override.get("year") or "1900")
                authors = normalize_space(override.get("authors") or "")
                extract_path = write_metadata_only_extract(
                    vault_root,
                    pdf_path,
                    title,
                    "pypdf is not installed in the active Python interpreter",
                )
            else:
                try:
                    reader, page_texts = extract_page_texts(pdf_path)
                    metadata = reader.metadata or {}
                    meta_title = normalize_space(str(metadata.get("/Title") or ""))
                    title = override.get("title") or (
                        meta_title if not looks_placeholder_title(meta_title) else guess_title_from_text(pdf_path.name, page_texts)
                    )
                    title = normalize_space(title)
                    year = override.get("year") or guess_year(pdf_path, title, page_texts, metadata)
                    authors = override.get("authors") or guess_authors(str(metadata.get("/Author") or ""), page_texts, title)
                    authors = normalize_space(authors)
                    extract_path = write_pypdf_extract(vault_root, pdf_path, title, page_texts)
                except Exception as extract_exc:
                    if not (override.get("title") and override.get("year")):
                        raise
                    page_texts = []
                    title = normalize_space(override.get("title") or guess_title_from_filename(pdf_path))
                    year = normalize_space(override.get("year") or "1900")
                    authors = normalize_space(override.get("authors") or "")
                    extract_path = write_metadata_only_extract(
                        vault_root,
                        pdf_path,
                        title,
                        f"PDF text extraction failed: {extract_exc}",
                    )
            note_path = determine_note_path(config, title, year, authors, args.note_style)

            row.update(
                {
                    "title": title,
                    "year": year,
                    "authors": authors,
                    "extract_path": str(extract_path),
                    "note_path": str(note_path),
                    "pages": len(page_texts),
                    "text_extraction": "metadata-only" if PdfReader is None else "pypdf",
                }
            )

            if args.skip_existing and note_path.exists():
                row["status"] = "skipped-existing"
                results.append(row)
                continue

            cmd = build_seed_command(
                script_dir,
                config_path,
                pdf_path,
                title,
                year,
                authors,
                args.source_tag,
                extract_path,
                args.note_style,
            )
            completed = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
            row["seed_stdout"] = completed.stdout.strip()
            row["seed_stderr"] = completed.stderr.strip()
            row["status"] = "ok" if completed.returncode == 0 else "seed-failed"
        except Exception as exc:
            row["status"] = "error"
            row["error"] = str(exc)

        results.append(row)

    manifest_path = Path(args.manifest_out).resolve() if args.manifest_out else (
        Path(config["output_root"]) / f"{datetime.now():%Y-%m-%d}_batch_seed_{safe_stem(folder.name)}.json"
    )
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(str(manifest_path))


if __name__ == "__main__":
    main()
