import json
import shutil
import subprocess
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "submission_qc_workflow.py"


class MockSubmissionQcHandler(BaseHTTPRequestHandler):
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


class SubmissionQcWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.test_root = ROOT / "tmp" / "test-runs"
        self.test_root.mkdir(parents=True, exist_ok=True)
        self.workspace = self.test_root / "submission-qc-workspace"
        shutil.rmtree(self.workspace, ignore_errors=True)
        self.workspace.mkdir(parents=True, exist_ok=True)

        self.vault_root = self.workspace / "vault"
        self.output_root = self.workspace / "reports"
        self.config_path = self.workspace / "config.json"
        self.draft_file = self.workspace / "draft.md"
        self.citation_audit_json = self.workspace / "citation_audit.json"
        self.journal_targeting_json = self.workspace / "journal_targeting.json"
        self.response_letter_json = self.workspace / "response_letter.json"

        (self.vault_root / "06_Writing").mkdir(parents=True, exist_ok=True)

        self.draft_file.write_text(
            "# Draft\n\nThe manuscript is nearly ready, but one broad-impact sentence remains.\n",
            encoding="utf-8",
        )
        self.citation_audit_json.write_text(
            json.dumps({"priority_repairs": ["Fix the broad-impact sentence."]}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        self.journal_targeting_json.write_text(
            json.dumps({"submission_checklist": ["Audit the abstract for broad wording."]}, ensure_ascii=False, indent=2)
            + "\n",
            encoding="utf-8",
        )
        self.response_letter_json.write_text(
            json.dumps({"open_items": ["Keep the final claim bounded."]}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        MockSubmissionQcHandler.requests = []
        MockSubmissionQcHandler.response_payload = {
            "readiness_summary": "The package is close, but one last wording-and-citation sweep is still needed.",
            "go_no_go": "Conditional go after the final repair pass.",
            "critical_blocks": [
                {
                    "blocker": "Residual broad-impact wording remains in the draft.",
                    "why_it_blocks": "It could reintroduce the main claim-evidence mismatch at submission time.",
                    "repair_direction": "Tighten the final sentence and recheck the abstract.",
                    "severity": "high",
                }
            ],
            "final_polish_actions": ["Do a final wording and citation sweep in abstract and discussion."],
            "pre_submission_checklist": ["Confirm all broad claims are either narrowed or explicitly supported."],
            "safe_to_submit_signals": ["The main revision logic is already aligned across review artifacts."],
            "next_actions": ["Repair the last broad sentence, then export the submission package."],
        }

        self.server = HTTPServer(("127.0.0.1", 0), MockSubmissionQcHandler)
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
                    "submission_qc_model": "gpt-5.4-submission-qc",
                    "submission_qc_reasoning_effort": "high",
                    "submission_qc_max_output_tokens": 7000,
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

    def test_submission_qc_workflow_outputs_files_and_vault_note(self):
        stdout = self.run_cli(
            "--config",
            str(self.config_path),
            "--title",
            "Final submission gate",
            "--draft-file",
            str(self.draft_file),
            "--citation-audit-json",
            str(self.citation_audit_json),
            "--journal-targeting-json",
            str(self.journal_targeting_json),
            "--response-letter-json",
            str(self.response_letter_json),
            "--write-vault-note",
        )
        outputs = json.loads(stdout)

        self.assertTrue(Path(outputs["submission_qc_json"]).exists())
        self.assertTrue(Path(outputs["submission_qc_markdown"]).exists())
        self.assertTrue(Path(outputs["vault_note"]).exists())
        self.assertTrue(Path(outputs["run_dir"]).joinpath("submission_qc_response.json").exists())

        markdown_text = Path(outputs["submission_qc_markdown"]).read_text(encoding="utf-8")
        self.assertIn("Go No Go", markdown_text)
        self.assertIn("Critical Blocks", markdown_text)

        request_payload = MockSubmissionQcHandler.requests[-1]
        self.assertEqual(request_payload["model"], "gpt-5.4-submission-qc")
        self.assertEqual(request_payload["reasoning"]["effort"], "high")
        self.assertEqual(request_payload["text"]["format"]["name"], "submission_qc_report")


if __name__ == "__main__":
    unittest.main()
