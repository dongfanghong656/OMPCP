import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


PATH_NAMING = load_module("path_naming", SCRIPTS / "path_naming.py")
SEED = load_module("seed_paper_note", SCRIPTS / "seed_paper_note.py")
TRANSLATE = load_module("translate_paper", SCRIPTS / "translate_paper.py")

LONG_TITLE = (
    "Enhanced A-scan spatial resolution in spectral domain OCT exploiting the "
    "Wigner-Ville distribution with extremely long validation naming pressure"
)
SCREENSHOT_TITLE = (
    "Superresolving artifact-free optical coherence tomography with "
    "deconvolution-random phase modulation"
)


class PathNamingTests(unittest.TestCase):
    def test_safe_slug_shortens_long_values_with_hash_suffix(self):
        slug = PATH_NAMING.safe_slug(LONG_TITLE, max_length=40, fallback="paper")

        self.assertLessEqual(len(slug), 40)
        self.assertRegex(slug, r"^[a-z0-9-]+$")
        self.assertRegex(slug, r".+-[0-9a-f]{8}$")

    def test_seed_paper_note_compacts_note_and_copy_names(self):
        short_title = SEED.build_short_title(LONG_TITLE)
        note_name = SEED.build_filename("2025", ["ExampleAuthor"], short_title)
        copied_pdf_name = SEED.build_attachment_stem("2025", ["ExampleAuthor"], LONG_TITLE) + ".pdf"

        self.assertLessEqual(len(short_title), 48)
        self.assertLessEqual(len(note_name), 72)
        self.assertLessEqual(len(copied_pdf_name), 60)

    def test_translate_output_dir_uses_compact_leaf_name(self):
        config = {
            "vault_root": "C:/Users/1/OneDrive - fzu.edu.cn (1)/Attachments/OCT_Research_System/oct-research-assist/vault",
            "obsidian": {"attachment_folder": "08_Attachments"},
            "translation": {"render": {}},
        }

        output_dir = TRANSLATE.build_output_dir(config, LONG_TITLE, "2025")

        self.assertLessEqual(len(output_dir.name), 32)

    def test_simulated_onedrive_extract_path_stays_under_260_chars(self):
        extract_root = Path(
            "C:/Users/1/OneDrive - fzu.edu.cn (1)/Attachments/OCT_Research_System/"
            "oct-research-assist/vault/08_Attachments/extracted"
        )
        extract_leaf = PATH_NAMING.paper_slug(LONG_TITLE, year="2025", max_length=32, fallback="paper")
        mineru_leaf = PATH_NAMING.paper_artifact_label(LONG_TITLE, year="2025", prefix="paper")
        simulated_path = extract_root / extract_leaf / mineru_leaf / "auto" / f"{mineru_leaf}.md"

        self.assertLess(len(str(simulated_path)), 260)
        self.assertEqual(str(simulated_path).lower().count("enhanced-a-scan"), 1)

    def test_span_pdf_path_only_keeps_title_once(self):
        extract_root = Path(
            "C:/Users/1/OneDrive - fzu.edu.cn (1)/Attachments/OCT_Research_System/"
            "oct-research-assist/vault/08_Attachments/extracted"
        )
        extract_leaf = PATH_NAMING.paper_slug(SCREENSHOT_TITLE, year="2022", max_length=32, fallback="paper")
        mineru_leaf = PATH_NAMING.paper_artifact_label(SCREENSHOT_TITLE, year="2022", prefix="paper")
        simulated_path = extract_root / extract_leaf / mineru_leaf / "auto" / f"{mineru_leaf}_span.pdf"

        self.assertLess(len(str(simulated_path)), 260)
        self.assertEqual(str(simulated_path).lower().count("superresolving"), 1)

    def test_copied_pdf_name_uses_short_attachment_stem(self):
        copied_pdf_name = SEED.build_attachment_stem("2022", ["Example Author"], SCREENSHOT_TITLE) + ".pdf"

        self.assertLessEqual(len(copied_pdf_name), 60)
        self.assertRegex(copied_pdf_name, r"^[a-z0-9-]+\.pdf$")


if __name__ == "__main__":
    unittest.main()
