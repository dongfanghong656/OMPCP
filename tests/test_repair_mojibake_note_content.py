import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

SCRIPT_PATH = SCRIPTS / "repair_mojibake_note_content.py"
SPEC = importlib.util.spec_from_file_location("repair_mojibake_note_content", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class RepairMojibakeNoteContentTests(unittest.TestCase):
    @staticmethod
    def make_garbled(value: str) -> str:
        return value.encode("utf-8").decode("latin1")

    def test_reverse_mojibake_segment_repairs_common_chinese_case(self):
        correct = "中文测试"
        garbled = self.make_garbled(correct)
        repaired = MODULE.reverse_mojibake_segment(garbled)

        self.assertEqual(repaired, correct)

    def test_repair_text_repairs_multiple_segments(self):
        title = "基础研究"
        venue = "南京航空"
        year = "年份2010"
        text = (
            f"title: {self.make_garbled(title)}\n"
            f"> {self.make_garbled(year)}\n"
            f"> {self.make_garbled(venue)}\n"
        )

        repaired, replacements = MODULE.repair_text(text)

        self.assertIn(title, repaired)
        self.assertIn(f"> {year}", repaired)
        self.assertIn(venue, repaired)
        self.assertTrue(replacements)

    def test_looks_better_requires_lower_mojibake_score(self):
        corrected = "光学系统"
        original = self.make_garbled(corrected)
        self.assertTrue(MODULE.looks_better(original, corrected))
        self.assertFalse(MODULE.looks_better(original, original))


if __name__ == "__main__":
    unittest.main()
