import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

SCRIPT_PATH = SCRIPTS / "prune_inventory_by_source_prefix.py"
SPEC = importlib.util.spec_from_file_location("prune_inventory_by_source_prefix", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class PruneInventoryBySourcePrefixTests(unittest.TestCase):
    def test_split_records_removes_matching_source_prefix(self):
        records = [
            {"source_path": r"C:\Users\1\OneDrive - fzu.edu.cn\old\a.pdf", "status": "failed", "extension": ".pdf"},
            {"source_path": r"C:\Users\1\OneDrive - fzu.edu.cn (1)\new\b.pdf", "status": "extracted", "extension": ".pdf"},
        ]

        kept, removed = MODULE.split_records(records, [MODULE.normalize_prefix(r"C:\Users\1\OneDrive - fzu.edu.cn")], [], [])

        self.assertEqual(len(removed), 1)
        self.assertEqual(len(kept), 1)
        self.assertIn("OneDrive - fzu.edu.cn\\old\\a.pdf", removed[0]["source_path"])
        self.assertIn("OneDrive - fzu.edu.cn (1)\\new\\b.pdf", kept[0]["source_path"])

    def test_split_records_removes_matching_basename_prefix(self):
        records = [
            {"source_path": r"C:\Users\1\Downloads\~$draft.docx", "status": "failed", "extension": ".docx"},
            {"source_path": r"C:\Users\1\Downloads\paper.docx", "status": "extracted", "extension": ".docx"},
        ]

        kept, removed = MODULE.split_records(records, [], [], ["~$"])

        self.assertEqual(len(removed), 1)
        self.assertEqual(len(kept), 1)
        self.assertTrue(removed[0]["source_path"].endswith(r"~$draft.docx"))
        self.assertTrue(kept[0]["source_path"].endswith(r"paper.docx"))

    def test_split_records_removes_matching_source_contains(self):
        records = [
            {"source_path": r"C:\Users\1\OneDrive - fzu.edu.cn (1)\知识库\foo\bar\哔哩哔哩_bilibili_files\a.html", "status": "failed", "extension": ".html"},
            {"source_path": r"C:\Users\1\OneDrive - fzu.edu.cn (1)\知识库\papers\paper.pdf", "status": "extracted", "extension": ".pdf"},
        ]

        kept, removed = MODULE.split_records(records, [], ["哔哩哔哩_bilibili_files"], [])

        self.assertEqual(len(removed), 1)
        self.assertEqual(len(kept), 1)
        self.assertIn("哔哩哔哩_bilibili_files", removed[0]["source_path"])


if __name__ == "__main__":
    unittest.main()
