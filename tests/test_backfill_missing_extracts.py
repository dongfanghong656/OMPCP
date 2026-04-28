import importlib.util
import sqlite3
import sys
import time
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

SCRIPT_PATH = SCRIPTS / "backfill_missing_extracts.py"
SPEC = importlib.util.spec_from_file_location("backfill_missing_extracts", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def write_file(root: Path, rel_path: str, content: bytes | str) -> Path:
    path = root / Path(rel_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, bytes):
        path.write_bytes(content)
    else:
        path.write_text(content, encoding="utf-8")
    return path


def read_frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    frontmatter, _ = MODULE.parse_frontmatter(text)
    return frontmatter


class BackfillMissingExtractsTests(unittest.TestCase):
    def test_relinks_to_existing_markdown_near_broken_extract_path(self):
        test_root = ROOT / "tmp" / f"test-backfill-extracts-{uuid.uuid4().hex}"
        try:
            vault_root = test_root / "vault"
            existing_extract = write_file(
                vault_root,
                "08_Attachments/extracted/example-paper/paper-abc123.md",
                "# Existing extract\n",
            )
            note_path = write_file(
                vault_root,
                "02_Literature/Papers/[2024] Example - Existing Extract.md",
                "\n".join(
                    [
                        "---",
                        'title: "Existing Extract Example"',
                        f'extract_path: "{(vault_root / "08_Attachments/extracted/example-paper/missing.md").as_posix()}"',
                        "---",
                        "",
                        "# Existing Extract Example",
                        "",
                    ]
                ),
            )
            config = {"vault_root": str(vault_root), "obsidian": {"paper_folder": "02_Papers"}}

            records, written = MODULE.backfill_missing_extracts(
                config,
                write=True,
                sync_dossiers_after_write=False,
            )

            self.assertEqual(len(records), 1)
            self.assertEqual(records[0].status, "relinked")
            self.assertEqual(records[0].new_extract_path, existing_extract.as_posix())
            self.assertEqual(written, [])
            self.assertEqual(read_frontmatter(note_path)["extract_path"], existing_extract.as_posix())
        finally:
            if test_root.exists():
                for path in sorted(test_root.rglob("*"), reverse=True):
                    if path.is_file():
                        try:
                            path.unlink()
                        except PermissionError:
                            time.sleep(0.2)
                            try:
                                path.unlink()
                            except PermissionError:
                                continue
                    else:
                        try:
                            path.rmdir()
                        except OSError:
                            continue

    def test_generates_extract_from_pdf_when_no_existing_markdown_is_available(self):
        test_root = ROOT / "tmp" / f"test-backfill-extracts-{uuid.uuid4().hex}"
        original_generator = MODULE.create_extract_from_pdf
        try:
            vault_root = test_root / "vault"
            pdf_path = write_file(vault_root, "08_Attachments/papers/example.pdf", b"%PDF-1.4\n")
            note_path = write_file(
                vault_root,
                "02_Literature/Papers/[2024] Example - Generate Extract.md",
                "\n".join(
                    [
                        "---",
                        'title: "Generate Extract Example"',
                        'extract_path: ""',
                        f'copied_pdf: "{pdf_path.as_posix()}"',
                        "---",
                        "",
                        "# Generate Extract Example",
                        "",
                    ]
                ),
            )

            def fake_generator(vault_root_arg: Path, pdf_path_arg: Path, title: str) -> Path:
                self.assertEqual(pdf_path_arg, pdf_path)
                generated = vault_root_arg / "08_Attachments" / "extracted" / "example" / "pypdf-extract.md"
                generated.parent.mkdir(parents=True, exist_ok=True)
                generated.write_text(f"# {title}\n", encoding="utf-8")
                return generated

            MODULE.create_extract_from_pdf = fake_generator
            config = {"vault_root": str(vault_root), "obsidian": {"paper_folder": "02_Papers"}}

            records, written = MODULE.backfill_missing_extracts(
                config,
                write=True,
                sync_dossiers_after_write=False,
            )

            self.assertEqual(len(records), 1)
            self.assertEqual(records[0].status, "generated")
            self.assertTrue(Path(records[0].new_extract_path).exists())
            self.assertEqual(written, [])
            self.assertEqual(
                read_frontmatter(note_path)["extract_path"],
                (vault_root / "08_Attachments/extracted/example/pypdf-extract.md").as_posix(),
            )
        finally:
            MODULE.create_extract_from_pdf = original_generator
            if test_root.exists():
                for path in sorted(test_root.rglob("*"), reverse=True):
                    if path.is_file():
                        path.unlink()
                    else:
                        path.rmdir()

    def test_dry_run_plans_generation_without_creating_extract_file(self):
        test_root = ROOT / "tmp" / f"test-backfill-extracts-{uuid.uuid4().hex}"
        original_generator = MODULE.create_extract_from_pdf
        try:
            vault_root = test_root / "vault"
            pdf_path = write_file(vault_root, "08_Attachments/papers/example.pdf", b"%PDF-1.4\n")
            write_file(
                vault_root,
                "02_Literature/Papers/[2024] Example - Dry Run.md",
                "\n".join(
                    [
                        "---",
                        'title: "Dry Run Example"',
                        'extract_path: ""',
                        f'copied_pdf: "{pdf_path.as_posix()}"',
                        "---",
                        "",
                        "# Dry Run Example",
                        "",
                    ]
                ),
            )

            def should_not_run(*args, **kwargs):
                raise AssertionError("create_extract_from_pdf should not run during dry-run")

            MODULE.create_extract_from_pdf = should_not_run
            config = {"vault_root": str(vault_root), "obsidian": {"paper_folder": "02_Papers"}}

            records, _ = MODULE.backfill_missing_extracts(
                config,
                write=False,
                sync_dossiers_after_write=False,
            )

            self.assertEqual(len(records), 1)
            self.assertEqual(records[0].status, "planned-generate")
            self.assertFalse((vault_root / "08_Attachments/extracted/example/pypdf-extract.md").exists())
        finally:
            MODULE.create_extract_from_pdf = original_generator
            if test_root.exists():
                for path in sorted(test_root.rglob("*"), reverse=True):
                    if path.is_file():
                        path.unlink()
                    else:
                        path.rmdir()

    def test_ensure_pdf_in_vault_copies_from_zotero_storage(self):
        test_root = ROOT / "tmp" / f"test-backfill-extracts-{uuid.uuid4().hex}"
        try:
            vault_root = test_root / "vault"
            zotero_root = test_root / "zotero"
            storage_dir = zotero_root / "storage" / "ATTACH01"
            storage_dir.mkdir(parents=True, exist_ok=True)
            source_pdf = storage_dir / "paper.pdf"
            source_pdf.write_bytes(b"%PDF-1.4\n")

            sqlite_path = zotero_root / "zotero.sqlite"
            conn = sqlite3.connect(sqlite_path)
            cur = conn.cursor()
            cur.execute("CREATE TABLE items (itemID INTEGER PRIMARY KEY, key TEXT)")
            cur.execute(
                "CREATE TABLE itemAttachments (itemID INTEGER PRIMARY KEY, parentItemID INT, linkMode INT, contentType TEXT, path TEXT)"
            )
            cur.execute("INSERT INTO items (itemID, key) VALUES (1, 'PARENT01')")
            cur.execute("INSERT INTO items (itemID, key) VALUES (2, 'ATTACH01')")
            cur.execute(
                "INSERT INTO itemAttachments (itemID, parentItemID, linkMode, contentType, path) VALUES (2, 1, 0, 'application/pdf', 'storage:paper.pdf')"
            )
            conn.commit()
            conn.close()

            frontmatter = {
                "title": "Zotero PDF Example",
                "year": "2024",
                "authors": ["Jane Example"],
                "zotero_key": "PARENT01",
            }
            config = {
                "vault_root": str(vault_root),
                "obsidian": {"paper_folder": "02_Papers"},
                "zotero": {"sqlite_path": str(sqlite_path)},
            }

            copied = MODULE.ensure_pdf_in_vault(config, frontmatter, write=True)

            self.assertIsNotNone(copied)
            self.assertTrue(copied.exists())
            self.assertTrue(str(copied).startswith(str(vault_root)))
            self.assertEqual(frontmatter["source_pdf"], copied.as_posix())
            self.assertEqual(frontmatter["copied_pdf"], copied.as_posix())
        finally:
            if test_root.exists():
                for path in sorted(test_root.rglob("*"), reverse=True):
                    if path.is_file():
                        try:
                            path.unlink()
                        except PermissionError:
                            time.sleep(0.2)
                            try:
                                path.unlink()
                            except PermissionError:
                                continue
                    else:
                        try:
                            path.rmdir()
                        except OSError:
                            continue


if __name__ == "__main__":
    unittest.main()
