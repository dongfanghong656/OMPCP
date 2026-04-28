import importlib.util
import sys
import unittest
from pathlib import Path
import shutil


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

SCRIPT_PATH = SCRIPTS / "build_zotero_tag_hygiene_targets.py"
SPEC = importlib.util.spec_from_file_location("build_zotero_tag_hygiene_targets", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class BuildZoteroTagHygieneTargetsTests(unittest.TestCase):
    def test_clean_tags_removes_noise_and_preserves_order(self):
        cleaned = MODULE.clean_tags(
            [
                "oct-paper",
                "local-pdf-import",
                "discovery:google_scholar",
                "oct",
                "verification:verified_doi",
                "review",
                "oct",
            ],
            ["local-pdf-import"],
            ["discovery:", "verification:"],
        )

        self.assertEqual(cleaned, ["oct-paper", "oct", "review"])

    def test_extract_zotero_key_from_sync_block(self):
        text = (
            "---\n"
            'title: "Example"\n'
            'source_pdf: "C:/vault/paper.pdf"\n'
            "---\n\n"
            "<!-- zotero-sync:start -->\n"
            "- Zotero item: `ABCD1234` (journalArticle)\n"
            "<!-- zotero-sync:end -->\n"
        )

        self.assertEqual(MODULE.extract_zotero_key(text), "ABCD1234")
        self.assertEqual(MODULE.extract_frontmatter_pdf(text), "C:/vault/paper.pdf")

    def test_resolve_pdf_path_falls_back_to_legacy_note(self):
        temp_root = ROOT / "tmp" / "test-build-zotero-tag-hygiene-targets"
        if temp_root.exists():
            shutil.rmtree(temp_root)
        legacy_dir = temp_root / "02_Papers"
        paper_dir = temp_root / "02_Literature" / "Papers"
        legacy_dir.mkdir(parents=True, exist_ok=True)
        paper_dir.mkdir(parents=True, exist_ok=True)
        legacy_path = legacy_dir / "legacy-note.md"
        legacy_path.write_text(
            "---\n"
            'source_pdf: "C:/vault/08_Attachments/papers/example.pdf"\n'
            "---\n",
            encoding="utf-8",
        )
        migrated_text = (
            "---\n"
            'title: "Migrated"\n'
            'legacy_source_note: "[[02_Papers/legacy-note.md]]"\n'
            "---\n"
        )

        resolved = MODULE.resolve_pdf_path(paper_dir / "migrated.md", migrated_text, temp_root)

        self.assertEqual(resolved, "C:/vault/08_Attachments/papers/example.pdf")


if __name__ == "__main__":
    unittest.main()
