import importlib.util
import sys
import unittest
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

SCRIPT_PATH = SCRIPTS / "extract_local_literature_corpus.py"
SPEC = importlib.util.spec_from_file_location("extract_local_literature_corpus", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class ExtractLocalLiteratureCorpusTests(unittest.TestCase):
    def test_describe_windows_placeholder_attributes(self):
        names = MODULE.describe_windows_file_attributes(
            MODULE.FILE_ATTRIBUTE_ARCHIVE | MODULE.FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS | MODULE.FILE_ATTRIBUTE_UNPINNED
        )
        self.assertIn("archive", names)
        self.assertIn("recall_on_data_access", names)
        self.assertIn("unpinned", names)

    def test_pdf_with_html_payload_falls_back_to_html_extractor(self):
        test_root = ROOT / "tmp" / f"test-extract-local-literature-{uuid.uuid4().hex}"
        try:
            fake_pdf = test_root / "masquerading.pdf"
            fake_pdf.parent.mkdir(parents=True, exist_ok=True)
            fake_pdf.write_text(
                "\n".join(
                    [
                        "<!DOCTYPE html>",
                        "<html>",
                        "<body>",
                        "<h1>Test Article</h1>",
                        "<p>This paper describes a fast OCT imaging method.</p>",
                        "</body>",
                        "</html>",
                    ]
                ),
                encoding="utf-8",
            )

            body, extractor, page_count = MODULE.extract_source(fake_pdf)

            self.assertTrue(extractor.startswith("pdf-html:"))
            self.assertEqual(page_count, 0)
            self.assertIn("Test Article", body)
            self.assertIn("fast OCT imaging method", body)
        finally:
            if test_root.exists():
                for path in sorted(test_root.rglob("*"), reverse=True):
                    if path.is_file():
                        path.unlink()
                    else:
                        path.rmdir()


if __name__ == "__main__":
    unittest.main()
