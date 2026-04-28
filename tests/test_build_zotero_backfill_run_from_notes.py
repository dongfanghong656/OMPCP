import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

SCRIPT_PATH = SCRIPTS / "build_zotero_backfill_run_from_notes.py"
SPEC = importlib.util.spec_from_file_location("build_zotero_backfill_run_from_notes", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class BuildZoteroBackfillRunFromNotesTests(unittest.TestCase):
    def test_collect_candidates_reads_frontmatter_and_sync_key(self):
        temp_root = ROOT / "tmp" / "test-build-zotero-backfill-run"
        if temp_root.exists():
            for child in sorted(temp_root.rglob("*"), reverse=True):
                if child.is_file():
                    child.unlink()
                elif child.is_dir():
                    child.rmdir()
        vault_root = temp_root / "vault"
        paper_dir = vault_root / "02_Literature" / "Papers"
        paper_dir.mkdir(parents=True, exist_ok=True)
        note = paper_dir / "[2025] Example.md"
        note.write_text(
            "\n".join(
                [
                    "---",
                    'title: "Example Paper"',
                    "year: 2025",
                    'doi: "10.1234/example"',
                    'source_pdf: "C:/vault/papers/example.pdf"',
                    "authors:",
                    '  - "Alice Example"',
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

        candidates = MODULE.collect_candidates(vault_root)

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].zotero_parent_key, "ABCD1234")
        self.assertEqual(candidates[0].pdf_path, "C:/vault/papers/example.pdf")
        self.assertEqual(candidates[0].authors, ["Alice Example"])
        self.assertEqual(candidates[0].title, "Example Paper")


if __name__ == "__main__":
    unittest.main()
