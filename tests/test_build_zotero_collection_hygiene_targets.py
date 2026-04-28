import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

SCRIPT_PATH = SCRIPTS / "build_zotero_collection_hygiene_targets.py"
SPEC = importlib.util.spec_from_file_location("build_zotero_collection_hygiene_targets", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class BuildZoteroCollectionHygieneTargetsTests(unittest.TestCase):
    def test_clean_collection_paths_removes_noise_and_deduplicates(self):
        cleaned = MODULE.clean_collection_paths(
            [
                "Local PDF Imports",
                "OCT",
                "实验室论文",
                "111111111",
                "OCT",
                "OCT/Reviews",
            ],
            ["Local PDF Imports", "111111111"],
        )

        self.assertEqual(cleaned, ["OCT", "实验室论文", "OCT/Reviews"])

    def test_current_collection_paths_uses_collection_map(self):
        item = {"collections": ["AAA111", "BBB222", "AAA111"]}
        collection_map = {
            "AAA111": "OCT",
            "BBB222": "Local PDF Imports",
        }

        self.assertEqual(MODULE.current_collection_paths(item, collection_map), ["OCT", "Local PDF Imports"])

    def test_prepare_record_returns_exact_cleaned_paths(self):
        record, removed = MODULE.prepare_record(
            "ABCD1234",
            "Example Paper",
            ["实验室论文", "Local PDF Imports", "OCT", "111111111"],
            ["Local PDF Imports", "111111111"],
        )

        self.assertEqual(record.item_key, "ABCD1234")
        self.assertEqual(record.title, "Example Paper")
        self.assertEqual(record.collection_paths, ["实验室论文", "OCT"])
        self.assertEqual(removed, ["Local PDF Imports", "111111111"])


if __name__ == "__main__":
    unittest.main()
