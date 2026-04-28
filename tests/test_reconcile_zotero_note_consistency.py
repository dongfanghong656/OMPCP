import importlib.util
import sys
import unittest
from pathlib import Path
import shutil


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

SCRIPT_PATH = SCRIPTS / "reconcile_zotero_note_consistency.py"
SPEC = importlib.util.spec_from_file_location("reconcile_zotero_note_consistency", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class ReconcileZoteroNoteConsistencyTests(unittest.TestCase):
    def test_build_citation_key_falls_back_to_item_key_when_slug_is_too_short(self):
        citation_key = MODULE.build_citation_key(["邹恒"], "2010", "基于时域和频域的光学相干层析成像系统的研究", "4DTZS2MX")

        self.assertIn("4dtzs2mx", citation_key)
        self.assertIn("2010", citation_key)

    def test_update_template_metadata_lines_rewrites_year_specific_markers(self):
        text = "\n".join(
            [
                "> citation title：Old, 2010",
                "> 年份：2010",
                "> Citation Key：old-2010",
                "> Filename Title：[2010] Old",
            ]
        )

        updated = MODULE.update_template_metadata_lines(text, "New, 2011", "2011", "new-2011", "[2011] New")

        self.assertIn("> citation title：New, 2011", updated)
        self.assertIn("> 年份：2011", updated)
        self.assertIn("> Citation Key：new-2011", updated)
        self.assertIn("> Filename Title：[2011] New", updated)

    def test_replace_vault_note_links_updates_wikilinks_and_markdown_links(self):
        temp_root = ROOT / "tmp" / "test-reconcile-zotero-note-consistency"
        if temp_root.exists():
            shutil.rmtree(temp_root)
        vault_root = temp_root / "vault"
        notes_dir = vault_root / "02_Literature" / "Papers"
        notes_dir.mkdir(parents=True, exist_ok=True)
        target = vault_root / "00_System" / "maps.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        old_path = notes_dir / "[2010] Zhong - Example.md"
        new_path = notes_dir / "[2011] Zhong - Example.md"
        target.write_text(
            "\n".join(
                [
                    "[[02_Literature/Papers/[2010] Zhong - Example]]",
                    "[[[2010] Zhong - Example]]",
                    "- [[02_Literature/Papers/[2010] Zhong - Example|Example]]",
                    f"- [[{old_path.stem}]]",
                    f"- [idx](<{old_path.name}>)",
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        updated_count = MODULE.replace_vault_note_links(vault_root, old_path, new_path)

        self.assertEqual(updated_count, 1)
        text = target.read_text(encoding="utf-8")
        self.assertIn("[[02_Literature/Papers/[2011] Zhong - Example]]", text)
        self.assertIn("[[[2011] Zhong - Example]]", text)
        self.assertIn("[[02_Literature/Papers/[2011] Zhong - Example|Example]]", text)
        self.assertIn(f"- [[{new_path.stem}]]", text)
        self.assertIn(f"- [idx](<{new_path.name}>)", text)


if __name__ == "__main__":
    unittest.main()
