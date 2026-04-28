import importlib.util
import json
import sys
import types
import unittest
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

SCRIPT_PATH = SCRIPTS / "batch_build_unmatched_local_translated_papers.py"
if "pypdf" not in sys.modules:
    pypdf_stub = types.ModuleType("pypdf")
    pypdf_stub.PdfReader = object
    sys.modules["pypdf"] = pypdf_stub
SPEC = importlib.util.spec_from_file_location("batch_build_unmatched_local_translated_papers", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class BatchBuildUnmatchedLocalTranslatedPapersTests(unittest.TestCase):
    def test_only_missing_filters_existing_outputs_before_batch_selection(self):
        test_root = ROOT / "tmp" / f"test-batch-build-unmatched-{uuid.uuid4().hex}"
        queue_path = test_root / "queue.json"
        output_root = test_root / "out"
        report_path = test_root / "report.json"
        original_argv = sys.argv[:]
        original_build_for_record = MODULE.build_for_record

        try:
            output_root.mkdir(parents=True, exist_ok=True)
            queue_records = [
                {
                    "display_title": "Paper One",
                    "year_guess": "2020",
                    "score": 20,
                    "corpus": "demo",
                    "extract_path": "C:/demo/extract-1.md",
                    "source_path": "C:/demo/paper-1.pdf",
                    "relative_path": "demo/paper-1.pdf",
                },
                {
                    "display_title": "Paper Two",
                    "year_guess": "2021",
                    "score": 19,
                    "corpus": "demo",
                    "extract_path": "C:/demo/extract-2.md",
                    "source_path": "C:/demo/paper-2.pdf",
                    "relative_path": "demo/paper-2.pdf",
                },
                {
                    "display_title": "Paper Three",
                    "year_guess": "2022",
                    "score": 18,
                    "corpus": "demo",
                    "extract_path": "C:/demo/extract-3.md",
                    "source_path": "C:/demo/paper-3.pdf",
                    "relative_path": "demo/paper-3.pdf",
                },
            ]
            queue_path.parent.mkdir(parents=True, exist_ok=True)
            queue_path.write_text(
                json.dumps({"records": queue_records}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            target_dir, translated_path, metadata_path = MODULE.resolve_output_paths(output_root, "Paper One", "2020")
            target_dir.mkdir(parents=True, exist_ok=True)
            translated_path.write_text("# existing", encoding="utf-8")
            metadata_path.write_text("{}", encoding="utf-8")

            def fake_build_for_record(**kwargs):
                record = kwargs["record"]
                return MODULE.QueueTranslationRecord(
                    queue_rank=int(record.get("_queue_rank", 0)),
                    corpus=str(record.get("corpus", "")),
                    title=MODULE.extract_title(record),
                    year=MODULE.infer_year(record),
                    score=int(record.get("score", 0)),
                    status="built",
                    extract_path=str(record.get("extract_path", "")),
                    source_path=str(record.get("source_path", "")),
                    relative_path=str(record.get("relative_path", "")),
                    normalized_extract_path="",
                    translated_note_path="",
                    translation_template_path="",
                    metadata_path="",
                    message="ok",
                )

            MODULE.build_for_record = fake_build_for_record
            sys.argv = [
                str(SCRIPT_PATH),
                "--queue-json",
                str(queue_path),
                "--output-root",
                str(output_root),
                "--report-out",
                str(report_path),
                "--limit",
                "2",
                "--only-missing",
            ]
            MODULE.main()

            payload = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["summary"]["eligible_total"], 3)
            self.assertEqual(payload["summary"]["filtered_total"], 2)
            self.assertEqual(payload["summary"]["candidate_total"], 2)
            self.assertTrue(payload["summary"]["only_missing"])

            records = payload["records"]
            self.assertEqual([item["title"] for item in records], ["Paper Two", "Paper Three"])
            self.assertEqual([item["queue_rank"] for item in records], [2, 3])
        finally:
            MODULE.build_for_record = original_build_for_record
            sys.argv = original_argv
            if test_root.exists():
                for path in sorted(test_root.rglob("*"), reverse=True):
                    if path.is_file():
                        path.unlink()
                    else:
                        path.rmdir()


if __name__ == "__main__":
    unittest.main()
