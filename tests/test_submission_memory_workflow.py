import json
import shutil
import subprocess
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "submission_memory_workflow.py"


class MockSubmissionMemoryHandler(BaseHTTPRequestHandler):
    response_payload = {}
    requests = []

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        payload = json.loads(body.decode("utf-8"))
        self.__class__.requests.append(payload)

        response_payload = dict(self.__class__.response_payload)
        input_text = payload.get("input", "")
        if "\"round_label\": \"round-2\"" in input_text:
            response_payload["round_label"] = "round-2"
        response = {"output_text": json.dumps(response_payload, ensure_ascii=False)}
        encoded = json.dumps(response, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, format, *args):
        return


class SubmissionMemoryWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.test_root = ROOT / "tmp" / "test-runs"
        self.test_root.mkdir(parents=True, exist_ok=True)
        self.workspace = self.test_root / "submission-memory-workspace"
        shutil.rmtree(self.workspace, ignore_errors=True)
        self.workspace.mkdir(parents=True, exist_ok=True)

        self.vault_root = self.workspace / "vault"
        self.output_root = self.workspace / "reports"
        self.config_path = self.workspace / "config.json"
        self.draft_health_json = self.workspace / "draft_health.json"
        self.submission_qc_json = self.workspace / "submission_qc.json"
        self.citation_audit_json = self.workspace / "citation_audit.json"
        self.response_letter_json = self.workspace / "response_letter.json"
        self.journal_targeting_json = self.workspace / "journal_targeting.json"
        self.draft_file = self.workspace / "draft.md"

        (self.vault_root / "06_Writing").mkdir(parents=True, exist_ok=True)

        self.draft_health_json.write_text(
            json.dumps({"overall_status": "yellow"}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        self.submission_qc_json.write_text(
            json.dumps({"go_no_go": "Conditional go"}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        self.citation_audit_json.write_text(
            json.dumps({"priority_repairs": ["Fix one broad sentence."]}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        self.response_letter_json.write_text(
            json.dumps({"round_label": "round-1"}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        self.journal_targeting_json.write_text(
            json.dumps({"journal_fit_summary": "Methods-forward venue."}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        self.draft_file.write_text(
            "# Draft\n\nThe paper currently keeps most claims bounded.\n",
            encoding="utf-8",
        )

        MockSubmissionMemoryHandler.requests = []
        MockSubmissionMemoryHandler.response_payload = {
            "memory_summary": "This venue rewards careful limitation language and fast response to overclaim risk.",
            "venue_name": "Biomedical Optics Express",
            "round_label": "round-1",
            "durable_lessons": ["Lead with bounded validation claims before broader impact language."],
            "venue_specific_rules": ["Keep reproducibility and limitation language visible early."],
            "recurring_debts": ["Broad wording tends to reappear in discussion edits."],
            "next_round_memory": ["Recheck discussion tone after every major rewrite."],
        }

        self.server = HTTPServer(("127.0.0.1", 0), MockSubmissionMemoryHandler)
        self.server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.server_thread.start()

        config = {
            "vault_root": str(self.vault_root).replace("\\", "/"),
            "output_root": str(self.output_root).replace("\\", "/"),
            "obsidian": {
                "writing_folder": "06_Writing",
            },
            "continuous_research": {
                "openai": {
                    "api_key": "test-key",
                    "base_url": f"http://127.0.0.1:{self.server.server_port}/v1/responses",
                    "submission_memory_model": "gpt-5.4-submission-memory",
                    "submission_memory_reasoning_effort": "high",
                    "submission_memory_max_output_tokens": 7000,
                }
            },
        }
        self.config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.server_thread.join(timeout=5)
        shutil.rmtree(self.workspace, ignore_errors=True)

    def run_cli(self, *args: str) -> str:
        completed = subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            raise AssertionError(
                "CLI failed with return code "
                f"{completed.returncode}\nSTDOUT:\n{completed.stdout}\nSTDERR:\n{completed.stderr}"
            )
        return completed.stdout.strip()

    def test_submission_memory_workflow_updates_registry_across_rounds(self):
        common_args = (
            "--config",
            str(self.config_path),
            "--venue-name",
            "Biomedical Optics Express",
            "--draft-health-json",
            str(self.draft_health_json),
            "--submission-qc-json",
            str(self.submission_qc_json),
            "--citation-audit-json",
            str(self.citation_audit_json),
            "--response-letter-json",
            str(self.response_letter_json),
            "--journal-targeting-json",
            str(self.journal_targeting_json),
            "--draft-file",
            str(self.draft_file),
        )

        round_1 = json.loads(self.run_cli(*common_args, "--round-label", "round-1"))
        round_2 = json.loads(self.run_cli(*common_args, "--round-label", "round-2"))

        self.assertTrue(Path(round_1["submission_memory_note"]).exists())
        self.assertTrue(Path(round_2["submission_memory_json"]).exists())
        registry = json.loads(Path(round_2["submission_memory_registry"]).read_text(encoding="utf-8"))
        self.assertEqual(len(registry["entries"]), 2)
        self.assertEqual(registry["entries"][0]["round_label"], "round-2")
        self.assertEqual(registry["entries"][1]["round_label"], "round-1")

        request_payload = MockSubmissionMemoryHandler.requests[-1]
        self.assertEqual(request_payload["model"], "gpt-5.4-submission-memory")
        self.assertEqual(request_payload["reasoning"]["effort"], "high")
        self.assertEqual(request_payload["text"]["format"]["name"], "submission_memory_report")


if __name__ == "__main__":
    unittest.main()
