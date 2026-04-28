import importlib.util
import sys
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

SCRIPT_PATH = SCRIPTS / "zotero_to_vault.py"
SPEC = importlib.util.spec_from_file_location("zotero_to_vault", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class ZoteroToVaultTests(unittest.TestCase):
    def test_upsert_sync_block_inserts_after_frontmatter(self):
        original = "---\ntitle: \"Example\"\n---\n\n# Heading\n"
        updated = MODULE.upsert_sync_block(original, "BLOCK")

        self.assertIn("---\n\nBLOCK", updated)
        self.assertTrue(updated.index("BLOCK") < updated.index("# Heading"))

    def test_upsert_sync_block_replaces_existing_block(self):
        original = (
            "---\ntitle: \"Example\"\n---\n\n"
            "<!-- zotero-sync:start -->\nold\n<!-- zotero-sync:end -->\n\n# Heading\n"
        )
        updated = MODULE.upsert_sync_block(original, "NEWBLOCK")

        self.assertIn("NEWBLOCK", updated)
        self.assertNotIn("old", updated)
        self.assertEqual(updated.count("NEWBLOCK"), 1)

    def test_find_paper_note_prefers_doi_then_pdf(self):
        index = MODULE.PaperNoteIndex(
            by_doi={"10.1234/example": Path("doi.md")},
            by_pdf_path={"c:/tmp/paper.pdf": Path("pdf.md")},
        )
        candidate = MODULE.local_pdf.LocalPdfImportCandidate(
            pdf_path="C:/tmp/paper.pdf",
            doi="10.1234/example",
            title="Example Paper",
        )

        self.assertEqual(MODULE.find_paper_note(candidate, index), Path("doi.md"))

    def test_write_zotero_note_and_index(self):
        temp_root = ROOT / "tmp" / "test-zotero-to-vault"
        if temp_root.exists():
            for child in sorted(temp_root.rglob("*"), reverse=True):
                if child.is_file():
                    child.unlink()
                elif child.is_dir():
                    child.rmdir()
        temp_root.mkdir(parents=True, exist_ok=True)

        vault_root = temp_root / "vault"
        backfill_dir = vault_root / "12_Zotero" / MODULE.BACKFILL_FOLDER
        backfill_dir.mkdir(parents=True, exist_ok=True)
        paper_note = vault_root / "02_Literature" / "Papers" / "[2025] Example.md"
        paper_note.parent.mkdir(parents=True, exist_ok=True)
        paper_note.write_text("# Example\n", encoding="utf-8")

        config = {
            "vault_root": str(vault_root),
            "obsidian": {
                "paper_folder": "02_Papers",
                "zotero_folder": "12_Zotero",
            },
        }
        item_data = {
            "key": "ABCD1234",
            "title": "Example OCT Paper",
            "itemType": "journalArticle",
            "date": "2025-01-01",
            "DOI": "10.1234/example",
            "url": "https://example.com/paper",
            "tags": [{"tag": "oct"}, {"tag": "deconvolution"}],
            "creators": [{"firstName": "Alice", "lastName": "Example"}],
            "collections": ["COLL1"],
        }
        attachments = [{"contentType": "application/pdf", "filename": "paper.pdf"}]
        note_path = MODULE.write_zotero_note(config, item_data, attachments, paper_note, ["OCT/Deconvolution"])

        self.assertTrue(note_path.exists())
        content = note_path.read_text(encoding="utf-8")
        self.assertIn("ABCD1234", content)
        self.assertIn("[[02_Literature/Papers/[2025] Example]]", content)
        self.assertIn("OCT/Deconvolution", content)

    def test_write_zotero_note_removes_duplicate_backfills_for_same_item(self):
        temp_root = ROOT / "tmp" / "test-zotero-to-vault-duplicates"
        if temp_root.exists():
            for child in sorted(temp_root.rglob("*"), reverse=True):
                if child.is_file():
                    child.unlink()
                elif child.is_dir():
                    child.rmdir()
        vault_root = temp_root / "vault"
        backfill_dir = vault_root / "12_Zotero" / MODULE.BACKFILL_FOLDER
        backfill_dir.mkdir(parents=True, exist_ok=True)
        stale = backfill_dir / "[2007] ABCD1234 - stale.md"
        stale.write_text(
            "\n".join(
                [
                    "---",
                    'zotero_key: "ABCD1234"',
                    'year: "2007"',
                    "---",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        paper_note = vault_root / "02_Literature" / "Papers" / "[2025] Example.md"
        paper_note.parent.mkdir(parents=True, exist_ok=True)
        paper_note.write_text("# Example\n", encoding="utf-8")

        config = {
            "vault_root": str(vault_root),
            "obsidian": {
                "paper_folder": "02_Papers",
                "zotero_folder": "12_Zotero",
            },
        }
        item_data = {
            "key": "ABCD1234",
            "title": "Example OCT Paper",
            "itemType": "journalArticle",
            "date": "2025-01-01",
            "creators": [{"firstName": "Alice", "lastName": "Example"}],
        }

        note_path = MODULE.write_zotero_note(config, item_data, [], paper_note, [])

        self.assertTrue(note_path.exists())
        self.assertFalse(stale.exists())

    def test_build_fallback_item_data_uses_candidate_metadata(self):
        candidate = MODULE.local_pdf.LocalPdfImportCandidate(
            pdf_path=str(ROOT / "tmp" / "fallback-paper.pdf"),
            title="Fallback Paper",
            authors=["Alice Example"],
            year="2025",
            doi="10.1234/fallback",
            url="https://example.com/fallback",
            zotero_parent_key="FALLBACK1",
            tags=["local-pdf-import", "oct"],
            collection_keys=["COLL123"],
        )
        Path(candidate.pdf_path).parent.mkdir(parents=True, exist_ok=True)
        Path(candidate.pdf_path).write_bytes(b"%PDF-1.4")

        item_data, attachments = MODULE.build_fallback_item_data(candidate, {"zotero": {"default_tags": ["oct-research-assist"]}})

        self.assertEqual(item_data["key"], "FALLBACK1")
        self.assertEqual(item_data["DOI"], "10.1234/fallback")
        self.assertEqual([tag["tag"] for tag in item_data["tags"]], ["oct-research-assist", "local-pdf-import", "oct"])
        self.assertEqual(attachments[0]["filename"], "fallback-paper.pdf")

    def test_fetch_remote_collection_path_map_resolves_nested_paths(self):
        payload = [
            {"data": {"key": "ROOT1", "name": "OCT", "parentCollection": ""}},
            {"data": {"key": "CHILD1", "name": "Deconvolution", "parentCollection": "ROOT1"}},
            {"data": {"key": "CHILD2", "name": "Blind", "parentCollection": "CHILD1"}},
        ]
        with mock.patch.object(MODULE.local_pdf, "http_json", side_effect=[(payload, {}), ([], {})]):
            mapping = MODULE.fetch_remote_collection_path_map({"zotero": {"api_key": "x", "library_id": "1", "library_type": "user"}})

        self.assertEqual(mapping["ROOT1"], "OCT")
        self.assertEqual(mapping["CHILD1"], "OCT/Deconvolution")
        self.assertEqual(mapping["CHILD2"], "OCT/Deconvolution/Blind")

    def test_load_paper_note_index_reads_zotero_key_from_sync_block(self):
        temp_root = ROOT / "tmp" / "test-zotero-to-vault-index"
        if temp_root.exists():
            for child in sorted(temp_root.rglob("*"), reverse=True):
                if child.is_file():
                    child.unlink()
                elif child.is_dir():
                    child.rmdir()
        paper_dir = temp_root / "vault" / "02_Literature" / "Papers"
        paper_dir.mkdir(parents=True, exist_ok=True)
        note_path = paper_dir / "[2025] Example.md"
        note_path.write_text(
            "\n".join(
                [
                    "---",
                    'title: "Example Paper"',
                    'source_pdf: "C:/vault/08_Attachments/papers/example.pdf"',
                    "---",
                    "",
                    "<!-- zotero-sync:start -->",
                    "- Zotero item: `ABCD1234` (journalArticle)",
                    "<!-- zotero-sync:end -->",
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        index = MODULE.load_paper_note_index(
            {
                "vault_root": str(temp_root / "vault"),
                "obsidian": {"paper_folder": "02_Papers"},
            }
        )

        self.assertEqual(index.by_zotero_key["ABCD1234"], note_path)

    def test_collect_candidates_from_paper_notes_uses_sync_block_keys(self):
        temp_root = ROOT / "tmp" / "test-zotero-to-vault-scan"
        if temp_root.exists():
            for child in sorted(temp_root.rglob("*"), reverse=True):
                if child.is_file():
                    child.unlink()
                elif child.is_dir():
                    child.rmdir()
        paper_dir = temp_root / "vault" / "02_Literature" / "Papers"
        paper_dir.mkdir(parents=True, exist_ok=True)
        note_path = paper_dir / "[2025] Example.md"
        note_path.write_text(
            "\n".join(
                [
                    "---",
                    'title: "Example Paper"',
                    'year: "2025"',
                    'doi: "10.1234/example"',
                    'source_pdf: "C:/vault/08_Attachments/papers/example.pdf"',
                    "---",
                    "",
                    "<!-- zotero-sync:start -->",
                    "- Zotero item: `ABCD1234` (journalArticle)",
                    "<!-- zotero-sync:end -->",
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        candidates = MODULE.collect_candidates_from_paper_notes(
            {
                "vault_root": str(temp_root / "vault"),
                "obsidian": {"paper_folder": "02_Papers"},
            }
        )

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].zotero_parent_key, "ABCD1234")
        self.assertEqual(candidates[0].title, "Example Paper")
        self.assertEqual(candidates[0].doi, "10.1234/example")
        self.assertTrue(candidates[0].already_in_zotero)


if __name__ == "__main__":
    unittest.main()
