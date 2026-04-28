import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

SCRIPT_PATH = SCRIPTS / "rescue_onedrive_failed_extracts.py"
SPEC = importlib.util.spec_from_file_location("rescue_onedrive_failed_extracts", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class RescueOneDriveFailedExtractsTests(unittest.TestCase):
    def test_should_retry_targeted_source_even_for_generic_failure(self):
        record = {
            "status": "failed",
            "source_path": r"C:\Users\1\OneDrive - fzu.edu.cn (1)\FBSGXCG\文献总结.docx",
            "message": "File is not a zip file",
        }

        self.assertTrue(MODULE.should_retry(record, "文献总结.docx"))

    def test_should_not_retry_non_onedrive_generic_failure_without_target(self):
        record = {
            "status": "failed",
            "source_path": r"C:\Users\1\OneDrive - fzu.edu.cn (1)\FBSGXCG\文献总结.docx",
            "message": "File is not a zip file",
        }

        self.assertFalse(MODULE.should_retry(record, ""))


if __name__ == "__main__":
    unittest.main()
