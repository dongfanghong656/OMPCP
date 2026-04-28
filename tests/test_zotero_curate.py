import importlib.util
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

SCRIPT_PATH = SCRIPTS / "zotero_curate.py"
SPEC = importlib.util.spec_from_file_location("zotero_curate", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class ZoteroCurateTests(unittest.TestCase):
    def test_load_targets_supports_defaults_and_aliases(self):
        payload = {
            "defaults": {
                "tags": ["oct-paper", "oct"],
                "collections": ["OCT", "OCT/Deconvolution"],
                "preserve_existing_tags": True,
            },
            "items": [
                {
                    "zotero_key": "ABCD1234",
                    "paper_title": "Example Paper",
                    "remove_tags": ["draft"],
                }
            ],
        }
        temp_dir = ROOT / "tmp" / "test-zotero-curate"
        temp_dir.mkdir(parents=True, exist_ok=True)
        path = temp_dir / "curation.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        targets = MODULE.load_targets(path)

        self.assertEqual(len(targets), 1)
        self.assertEqual(targets[0].item_key, "ABCD1234")
        self.assertEqual(targets[0].title, "Example Paper")
        self.assertEqual(targets[0].add_tags, ["oct-paper", "oct"])
        self.assertEqual(targets[0].add_collection_paths, ["OCT", "OCT/Deconvolution"])
        self.assertEqual(targets[0].remove_tags, ["draft"])
        self.assertEqual(targets[0].remove_tag_prefixes, [])
        self.assertTrue(targets[0].preserve_existing_tags)

    def test_merge_tags_reorders_and_preserves_extras(self):
        target = MODULE.CurationTarget(
            item_key="ITEM1",
            add_tags=["oct-paper", "oct", "deconvolution", "superresolution"],
            preserve_existing_tags=True,
        )
        merged = MODULE.merge_tags(
            ["deconvolution", "local-pdf-import", "oct-paper", "superresolution"],
            target,
        )

        self.assertEqual(
            merged,
            ["oct-paper", "oct", "deconvolution", "superresolution", "local-pdf-import"],
        )

    def test_merge_tags_drops_prefixed_noise_tags(self):
        target = MODULE.CurationTarget(
            item_key="ITEM1",
            add_tags=["oct-paper", "oct", "deconvolution"],
            remove_tag_prefixes=["discovery:", "verification:"],
            remove_tags=["local-pdf-import"],
            preserve_existing_tags=True,
        )

        merged = MODULE.merge_tags(
            [
                "discovery:google_scholar",
                "verification:verified_doi",
                "local-pdf-import",
                "oct-paper",
                "review",
            ],
            target,
        )

        self.assertEqual(merged, ["oct-paper", "oct", "deconvolution", "review"])

    def test_merge_collection_keys_reorders_and_preserves_extras(self):
        target = MODULE.CurationTarget(
            item_key="ITEM1",
            add_collection_paths=["OCT", "OCT/Deconvolution"],
            remove_collection_paths=["OCT/Legacy"],
            preserve_existing_collections=True,
        )
        context = MODULE.CollectionContext(
            cache=MODULE.local_pdf.ZoteroLocalIndex(),
            path_by_key={
                "ROOT": "OCT",
                "CHILD": "OCT/Deconvolution",
                "DUPE": "OCT/Deconvolution",
                "EXTRA1": "111111111",
                "EXTRA2": "OCT/Legacy",
            },
            key_by_path={
                "OCT": "ROOT",
                "OCT/Deconvolution": "CHILD",
                "111111111": "EXTRA1",
                "OCT/Legacy": "EXTRA2",
            },
        )

        merged = MODULE.merge_collection_keys(["DUPE", "EXTRA2", "EXTRA1"], ["ROOT", "CHILD"], target, context)

        self.assertEqual(merged, ["ROOT", "CHILD", "EXTRA1"])


if __name__ == "__main__":
    unittest.main()
