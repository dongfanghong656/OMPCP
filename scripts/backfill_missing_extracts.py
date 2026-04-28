#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

import batch_seed_pdf_folder as batch_seed
import paper_dossiers
from path_naming import paper_attachment_slug, safe_slug


@dataclass
class BackfillRecord:
    paper_path: str
    title: str
    status: str = "pending"
    message: str = ""
    old_extract_path: str = ""
    new_extract_path: str = ""
    pdf_path: str = ""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Repair missing extract_path links for paper notes.")
    parser.add_argument("--config", required=True)
    parser.add_argument("--output-root", default="")
    parser.add_argument("--run-label", default="obsidian-extract-backfill")
    parser.add_argument("--write", action="store_true")
    return parser.parse_args()


def resolve_output_root(config: dict[str, Any], output_root: str) -> Path:
    return Path(output_root) if output_root else Path(config["output_root"])


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    return paper_dossiers.split_frontmatter(text)


def dump_frontmatter(data: dict[str, Any]) -> str:
    return "---\n" + yaml.safe_dump(data, sort_keys=False, allow_unicode=True).strip() + "\n---\n"


def note_title(frontmatter: dict[str, Any], note_path: Path) -> str:
    for key in ("title_display", "title", "title_en", "title_zh", "citation_title"):
        value = paper_dossiers.normalize_whitespace(frontmatter.get(key))
        if value:
            return value
    return note_path.stem


def paper_note_paths(config: dict[str, Any]) -> list[Path]:
    vault_root = Path(config["vault_root"])
    paper_dir = paper_dossiers.paper_note_directory(vault_root, config)
    return [path for path in sorted(paper_dir.glob("*.md")) if not path.name.startswith("_")]


def raw_to_path(vault_root: Path, raw_value: Any) -> Path | None:
    raw = paper_dossiers.normalize_whitespace(raw_value)
    if not raw:
        return None

    parsed_wikilink = paper_dossiers.parse_wikilink_target(raw)
    if parsed_wikilink:
        return (vault_root / Path(parsed_wikilink)).resolve()

    portable = raw.replace("\\", "/")
    candidate = Path(portable)
    if candidate.is_absolute():
        return candidate.resolve()

    relative = portable.lstrip("./")
    if not relative:
        return None
    return (vault_root / Path(relative)).resolve()


def resolve_existing_path(vault_root: Path, raw_value: Any) -> Path | None:
    candidate = raw_to_path(vault_root, raw_value)
    if candidate is None or not candidate.exists():
        return None
    return candidate


def choose_extract_candidate(candidates: list[Path], preferred: Path | None = None) -> Path | None:
    if not candidates:
        return None

    def score(path: Path) -> tuple[int, int, int, str]:
        preferred_match = int(preferred is not None and path.name == preferred.name)
        pypdf_match = int(path.name.lower() == "pypdf-extract.md")
        same_stem = int(preferred is not None and path.stem == preferred.stem)
        size = path.stat().st_size if path.exists() else 0
        return (preferred_match, pypdf_match, same_stem, size, path.name.lower())

    return sorted(candidates, key=score, reverse=True)[0]


def find_existing_extract(vault_root: Path, raw_extract_path: Any) -> Path | None:
    target = raw_to_path(vault_root, raw_extract_path)
    if target is not None and target.exists():
        return target
    if target is None:
        return None
    parent = target.parent
    if not parent.exists():
        return None
    md_candidates = [path for path in sorted(parent.glob("*.md")) if path.is_file()]
    return choose_extract_candidate(md_candidates, preferred=target)


def resolve_pdf_path(vault_root: Path, frontmatter: dict[str, Any]) -> Path | None:
    for key in ("copied_pdf", "source_pdf"):
        candidate = resolve_existing_path(vault_root, frontmatter.get(key))
        if candidate is not None and candidate.suffix.lower() == ".pdf":
            return candidate
    return None


def resolve_zotero_storage_pdf(config: dict[str, Any], frontmatter: dict[str, Any]) -> Path | None:
    sqlite_path_raw = paper_dossiers.normalize_whitespace(config.get("zotero", {}).get("sqlite_path", ""))
    zotero_key = paper_dossiers.normalize_whitespace(frontmatter.get("zotero_key"))
    if not sqlite_path_raw or not zotero_key:
        return None
    sqlite_path = Path(sqlite_path_raw)
    if not sqlite_path.exists():
        return None
    storage_root = sqlite_path.parent / "storage"
    if not storage_root.exists():
        return None

    with sqlite3.connect(str(sqlite_path)) as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT child.key, ia.contentType
            FROM items parent
            JOIN itemAttachments ia ON ia.parentItemID = parent.itemID
            JOIN items child ON child.itemID = ia.itemID
            WHERE parent.key = ?
            """,
            (zotero_key,),
        )
        for attachment_key, content_type in cursor.fetchall():
            if str(content_type or "").lower() != "application/pdf":
                continue
            attachment_dir = storage_root / str(attachment_key)
            if not attachment_dir.exists():
                continue
            pdf_candidates = sorted(attachment_dir.glob("*.pdf"))
            if pdf_candidates:
                return pdf_candidates[0]
    return None


def ensure_pdf_in_vault(config: dict[str, Any], frontmatter: dict[str, Any], *, write: bool) -> Path | None:
    vault_root = Path(config["vault_root"])
    existing = resolve_pdf_path(vault_root, frontmatter)
    if existing is not None:
        return existing

    zotero_pdf = resolve_zotero_storage_pdf(config, frontmatter)
    if zotero_pdf is None:
        return None

    title = note_title(frontmatter, Path(frontmatter.get("filename_title", "paper")))
    year = paper_dossiers.normalize_whitespace(frontmatter.get("year"))
    authors = paper_dossiers.coerce_list(frontmatter.get("authors"))
    author_label = authors[0].split()[-1] if authors else ""
    target_name = paper_attachment_slug(title, year=year, author_label=author_label, fallback="paper") + ".pdf"
    target = vault_root / "08_Attachments" / "papers" / target_name
    if write:
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            shutil.copy2(zotero_pdf, target)
        portable = paper_dossiers.to_portable_path(target)
        frontmatter["source_pdf"] = portable
        frontmatter["copied_pdf"] = portable
    return target


def create_extract_from_pdf(vault_root: Path, pdf_path: Path, title: str) -> Path:
    _, page_texts = batch_seed.extract_page_texts(pdf_path)
    return batch_seed.write_pypdf_extract(vault_root, pdf_path, title, page_texts)


def planned_extract_path(vault_root: Path, pdf_path: Path) -> Path:
    return vault_root / "08_Attachments" / "extracted" / batch_seed.safe_stem(pdf_path.stem) / "pypdf-extract.md"


def update_extract_path(note_path: Path, frontmatter: dict[str, Any], body: str, extract_path: Path) -> None:
    frontmatter["extract_path"] = paper_dossiers.to_portable_path(extract_path)
    if "updated" in frontmatter:
        frontmatter["updated"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    rendered = dump_frontmatter(frontmatter) + body.lstrip("\n")
    note_path.write_text(rendered if rendered.endswith("\n") else rendered + "\n", encoding="utf-8")


def backfill_missing_extracts(
    config: dict[str, Any],
    *,
    write: bool = False,
    sync_dossiers_after_write: bool = True,
) -> tuple[list[BackfillRecord], list[str]]:
    vault_root = Path(config["vault_root"])
    records: list[BackfillRecord] = []

    for note_path in paper_note_paths(config):
        try:
            text = note_path.read_text(encoding="utf-8", errors="replace")
            frontmatter, body = parse_frontmatter(text)
            if paper_dossiers.is_synthetic_example_note(frontmatter):
                records.append(
                    BackfillRecord(
                        paper_path=str(note_path),
                        title=note_title(frontmatter, note_path),
                        status="skipped",
                        message="Synthetic example note is excluded from paper-source backfill.",
                    )
                )
                continue
            title = note_title(frontmatter, note_path)
            raw_extract_path = frontmatter.get("extract_path", "")
            existing_extract = resolve_existing_path(vault_root, raw_extract_path)
            if existing_extract is not None:
                records.append(
                    BackfillRecord(
                        paper_path=str(note_path),
                        title=title,
                        status="unchanged",
                        message="extract_path is already valid.",
                        old_extract_path=paper_dossiers.normalize_whitespace(raw_extract_path),
                        new_extract_path=paper_dossiers.to_portable_path(existing_extract),
                    )
                )
                continue

            relink_candidate = find_existing_extract(vault_root, raw_extract_path)
            pdf_path = ensure_pdf_in_vault(config, frontmatter, write=write)
            record = BackfillRecord(
                paper_path=str(note_path),
                title=title,
                old_extract_path=paper_dossiers.normalize_whitespace(raw_extract_path),
                pdf_path=paper_dossiers.to_portable_path(pdf_path) if pdf_path else "",
            )

            if relink_candidate is not None:
                record.status = "relinked" if write else "planned-relink"
                record.message = "Found an existing markdown extract near the broken extract_path."
                record.new_extract_path = paper_dossiers.to_portable_path(relink_candidate)
                if write:
                    update_extract_path(note_path, frontmatter, body, relink_candidate)
                records.append(record)
                continue

            if pdf_path is None:
                record.status = "skipped"
                record.message = "No usable PDF was found for extract backfill."
                records.append(record)
                continue

            generated_extract = create_extract_from_pdf(vault_root, pdf_path, title) if write else planned_extract_path(
                vault_root,
                pdf_path,
            )
            record.status = "generated" if write else "planned-generate"
            record.message = "Generated a fresh pypdf extract from an available PDF."
            record.new_extract_path = paper_dossiers.to_portable_path(generated_extract)
            if write:
                update_extract_path(note_path, frontmatter, body, generated_extract)
            records.append(record)
        except Exception as exc:
            records.append(
                BackfillRecord(
                    paper_path=str(note_path),
                    title=note_path.stem,
                    status="failed",
                    message=str(exc),
                )
            )

    written_dossiers: list[str] = []
    changed = [record for record in records if record.status in {"relinked", "generated"}]
    if write and changed and sync_dossiers_after_write:
        written_dossiers = paper_dossiers.sync_dossiers(config)
    return records, written_dossiers


def write_run_report(path: Path, run_id: str, records: list[BackfillRecord], written_dossiers: list[str]) -> None:
    changed_statuses = {"relinked", "generated"}
    lines = [
        "# Missing Extract Backfill",
        "",
        f"- Run ID: `{run_id}`",
        f"- Generated: `{datetime.now().isoformat(timespec='seconds')}`",
        f"- Checked: {len(records)}",
        f"- Relinked: {sum(1 for record in records if record.status in {'relinked', 'planned-relink'})}",
        f"- Generated: {sum(1 for record in records if record.status in {'generated', 'planned-generate'})}",
        f"- Skipped: {sum(1 for record in records if record.status == 'skipped')}",
        f"- Unchanged: {sum(1 for record in records if record.status == 'unchanged')}",
        f"- Failed: {sum(1 for record in records if record.status == 'failed')}",
        f"- Dossier files refreshed: {len(written_dossiers)}",
        "",
        "## Updated Notes",
        "",
    ]
    for record in records:
        marker = "updated" if record.status in changed_statuses else record.status
        lines.append(f"- {record.title} | {marker}")
        if record.old_extract_path:
            lines.append(f"  - Old extract: `{record.old_extract_path}`")
        if record.new_extract_path:
            lines.append(f"  - New extract: `{record.new_extract_path}`")
        if record.pdf_path:
            lines.append(f"  - PDF: `{record.pdf_path}`")
        if record.message:
            lines.append(f"  - Note: {record.message}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    config = paper_dossiers.load_json(Path(args.config))
    output_root = resolve_output_root(config, args.output_root)
    run_id = f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{safe_slug(args.run_label)}"
    run_dir = output_root / "vault-reorg" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    records, written_dossiers = backfill_missing_extracts(
        config,
        write=args.write,
        sync_dossiers_after_write=True,
    )

    payload = {
        "run_id": run_id,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "records": [asdict(record) for record in records],
        "written_dossiers": written_dossiers,
    }
    (run_dir / "run.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_run_report(run_dir / "run.md", run_id, records, written_dossiers)
    print(str(run_dir / "run.md"))


if __name__ == "__main__":
    main()
