import importlib.util
import sys
import unittest


from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

SCRIPT_PATH = SCRIPTS / "sync_paper_note_frontmatter_from_zotero.py"
SPEC = importlib.util.spec_from_file_location("sync_paper_note_frontmatter_from_zotero", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class SyncPaperNoteFrontmatterFromZoteroTests(unittest.TestCase):
    def test_remote_metadata_extracts_common_fields(self):
        item_data = {
            "itemType": "journalArticle",
            "publicationTitle": "Optics Letters",
            "DOI": "10.1234/example",
            "url": "https://example.com",
            "creators": [{"firstName": "Alice", "lastName": "Example"}],
        }

        metadata = MODULE.remote_metadata(item_data)

        self.assertEqual(metadata["venue"], "Optics Letters")
        self.assertEqual(metadata["doi"], "10.1234/example")
        self.assertEqual(metadata["url"], "https://example.com")
        self.assertEqual(metadata["authors"], ["Alice Example"])
        self.assertEqual(metadata["publication_type"], "期刊论文")

    def test_maybe_update_scalar_respects_overwrite_flag(self):
        frontmatter = {"venue": ""}
        changed = MODULE.maybe_update_scalar(frontmatter, "venue", "Optics Letters", overwrite=False)
        self.assertTrue(changed)
        self.assertEqual(frontmatter["venue"], "Optics Letters")

        unchanged = MODULE.maybe_update_scalar(frontmatter, "venue", "Different Venue", overwrite=False)
        self.assertFalse(unchanged)
        self.assertEqual(frontmatter["venue"], "Optics Letters")

    def test_maybe_update_authors_updates_related_authors(self):
        frontmatter = {"authors": [], "related_authors": []}
        changed = MODULE.maybe_update_authors(frontmatter, ["Alice Example", "Bob Example"], overwrite=False)

        self.assertTrue(changed)
        self.assertEqual(frontmatter["authors"], ["Alice Example", "Bob Example"])
        self.assertEqual(frontmatter["related_authors"], ["Alice Example", "Bob Example"])

    def test_update_info_block_lines_rewrites_fields(self):
        text = "\n".join(
            [
                "> 作者：TBD",
                "> 年份：2024",
                "> 期刊 / 会议：TBD",
                "> DOI：TBD",
                "> URL：TBD",
            ]
        )

        updated = MODULE.update_info_block_lines(
            text,
            ["Alice Example"],
            "期刊论文",
            "Optics Letters",
            "10.1234/example",
            "https://example.com",
        )

        self.assertIn("> 作者：Alice Example", updated)
        self.assertIn("> 文献类型：期刊论文", updated)
        self.assertIn("> 期刊 / 会议：Optics Letters", updated)
        self.assertIn("> DOI：10.1234/example", updated)
        self.assertIn("> URL：https://example.com", updated)

    def test_publication_type_from_note_prefers_remote_then_heuristics(self):
        text = "## Zotero Sync\n- Zotero item: `ABC123` (preprint)"
        self.assertEqual(MODULE.publication_type_from_note({}, text, "学位论文"), "学位论文")
        self.assertEqual(MODULE.publication_type_from_note({}, text, ""), "预印本")
        self.assertEqual(
            MODULE.publication_type_from_note({"venue": "南京航空航天大学"}, "", ""),
            "学位论文",
        )


if __name__ == "__main__":
    unittest.main()
