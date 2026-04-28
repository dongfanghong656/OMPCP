import json
import shutil
import subprocess
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "draft_health_check_workflow.py"


class MockDraftHealthHandler(BaseHTTPRequestHandler):
    response_payload = {}
    requests = []

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        payload = json.loads(body.decode("utf-8"))
        self.__class__.requests.append(payload)

        response = {"output_text": json.dumps(self.__class__.response_payload, ensure_ascii=False)}
        encoded = json.dumps(response, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, format, *args):
        return


class DraftHealthCheckWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.test_root = ROOT / "tmp" / "test-runs"
        self.test_root.mkdir(parents=True, exist_ok=True)
        self.workspace = self.test_root / "draft-health-workspace"
        shutil.rmtree(self.workspace, ignore_errors=True)
        self.workspace.mkdir(parents=True, exist_ok=True)

        self.vault_root = self.workspace / "vault"
        self.output_root = self.workspace / "reports"
        self.config_path = self.workspace / "config.json"
        self.draft_file = self.workspace / "draft.md"
        self.citation_audit_json = self.workspace / "citation_audit.json"
        self.submission_qc_json = self.workspace / "submission_qc.json"
        self.journal_targeting_json = self.workspace / "journal_targeting.json"
        self.response_letter_json = self.workspace / "response_letter.json"

        (self.vault_root / "06_Writing").mkdir(parents=True, exist_ok=True)

        self.draft_file.write_text(
            "# Draft\n\nOne broad impact sentence still appears in the discussion.\n",
            encoding="utf-8",
        )
        self.citation_audit_json.write_text(
            json.dumps({"priority_repairs": ["Fix the broad impact sentence."]}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        self.submission_qc_json.write_text(
            json.dumps({"go_no_go": "Conditional go"}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        self.journal_targeting_json.write_text(
            json.dumps({"submission_checklist": ["Audit discussion tone."]}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        self.response_letter_json.write_text(
            json.dumps({"open_items": ["Keep claims bounded."]}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        MockDraftHealthHandler.requests = []
        MockDraftHealthHandler.response_payload = {
            "health_summary": "The draft is mostly stable, but one citation-backed wording debt remains.",
            "overall_status": "yellow",
            "citation_debt_items": [
                {
                    "item": "A broad discussion sentence is not yet fully evidence-bounded.",
                    "why_it_matters": "It could reopen the main overclaim risk.",
                    "source_stage": "citation_audit",
                    "repair_hint": "Tighten the wording and add a stability citation or remove the broad claim.",
                    "severity": "high",
                }
            ],
            "stability_watchpoints": ["Watch for broadening language in the discussion during future edits."],
            "recent_strengths": ["The abstract and results lead are already closer to bounded claim language."],
            "next_health_checks": ["Re-run after the next discussion edit or before submission export."],
        }

        self.server = HTTPServer(("127.0.0.1", 0), MockDraftHealthHandler)
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
                    "draft_health_model": "gpt-5.4-draft-health",
                    "draft_health_reasoning_effort": "high",
                    "draft_health_max_output_tokens": 7000,
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

    def test_draft_health_check_workflow_outputs_files_and_vault_note(self):
        stdout = self.run_cli(
            "--config",
            str(self.config_path),
            "--title",
            "Draft health snapshot",
            "--draft-file",
            str(self.draft_file),
            "--citation-audit-json",
            str(self.citation_audit_json),
            "--submission-qc-json",
            str(self.submission_qc_json),
            "--journal-targeting-json",
            str(self.journal_targeting_json),
            "--response-letter-json",
            str(self.response_letter_json),
            "--write-vault-note",
        )
        outputs = json.loads(stdout)

        self.assertTrue(Path(outputs["draft_health_json"]).exists())
        self.assertTrue(Path(outputs["draft_health_markdown"]).exists())
        self.assertTrue(Path(outputs["vault_note"]).exists())
        self.assertTrue(Path(outputs["run_dir"]).joinpath("draft_health_response.json").exists())

        markdown_text = Path(outputs["draft_health_markdown"]).read_text(encoding="utf-8")
        self.assertIn("Citation Debt Items", markdown_text)
        self.assertIn("Overall Status", markdown_text)

        request_payload = MockDraftHealthHandler.requests[-1]
        self.assertEqual(request_payload["model"], "gpt-5.4-draft-health")
        self.assertEqual(request_payload["reasoning"]["effort"], "high")
        self.assertEqual(request_payload["text"]["format"]["name"], "draft_health_report")


if __name__ == "__main__":
    unittest.main()
