import json
import shutil
import subprocess
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "rebuttal_scaffold_workflow.py"


class MockRebuttalScaffoldHandler(BaseHTTPRequestHandler):
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


class RebuttalScaffoldWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.test_root = ROOT / "tmp" / "test-runs"
        self.test_root.mkdir(parents=True, exist_ok=True)
        self.workspace = self.test_root / "rebuttal-scaffold-workspace"
        shutil.rmtree(self.workspace, ignore_errors=True)
        self.workspace.mkdir(parents=True, exist_ok=True)

        self.vault_root = self.workspace / "vault"
        self.output_root = self.workspace / "reports"
        self.config_path = self.workspace / "config.json"
        self.self_review_json = self.workspace / "self_review.json"
        self.writing_memory_json = self.workspace / "writing_memory.json"
        self.results_report_json = self.workspace / "results_report.json"
        self.draft_file = self.workspace / "draft.md"

        (self.vault_root / "06_Writing").mkdir(parents=True, exist_ok=True)

        self.self_review_json.write_text(
            json.dumps(
                {
                    "review_summary": "The draft overstates generality.",
                    "overclaim_risks": ["Universal superiority is too strong."],
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        self.writing_memory_json.write_text(
            json.dumps(
                {
                    "reviewer_watchouts": ["Reviewers may ask about transferability."],
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        self.results_report_json.write_text(
            json.dumps(
                {
                    "unsupported_claims": ["The benchmark alone proves general superiority."],
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        self.draft_file.write_text(
            "# Draft\n\nWe currently call the method universally superior.\n",
            encoding="utf-8",
        )

        MockRebuttalScaffoldHandler.requests = []
        MockRebuttalScaffoldHandler.response_payload = {
            "review_risk_summary": "The central reviewer risk is overclaiming beyond the benchmark bundle.",
            "likely_reviewer_concerns": [
                {
                    "concern": "The manuscript appears to overstate general superiority.",
                    "why_it_is_likely": "Both the self-review and results report flag unsupported generality.",
                    "evidence_backed_response": "We revised the wording to reflect a bounded benchmark-bundle conclusion.",
                    "concession_if_needed": "We agree that broader transfer validation remains future work.",
                    "follow_up_action": "Tighten the wording in Results and Discussion.",
                }
            ],
            "manuscript_changes_to_preempt": ["Replace universal wording with bounded language."],
            "response_letter_phrases": ["We thank the reviewer for highlighting this claim-evidence alignment issue."],
            "high_priority_evidence_requests": ["Real-OCT transfer validation."],
            "next_rebuttal_targets": ["Prepare one reusable reply on transferability limits."],
        }

        self.server = HTTPServer(("127.0.0.1", 0), MockRebuttalScaffoldHandler)
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
                    "rebuttal_scaffold_model": "gpt-5.4-rebuttal",
                    "rebuttal_scaffold_reasoning_effort": "high",
                    "rebuttal_scaffold_max_output_tokens": 7000,
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

    def test_rebuttal_scaffold_workflow_outputs_files_and_vault_note(self):
        stdout = self.run_cli(
            "--config",
            str(self.config_path),
            "--title",
            "Reviewer response prep",
            "--self-review-json",
            str(self.self_review_json),
            "--writing-memory-json",
            str(self.writing_memory_json),
            "--results-report-json",
            str(self.results_report_json),
            "--draft-file",
            str(self.draft_file),
            "--write-vault-note",
        )
        outputs = json.loads(stdout)

        self.assertTrue(Path(outputs["rebuttal_scaffold_json"]).exists())
        self.assertTrue(Path(outputs["rebuttal_scaffold_markdown"]).exists())
        self.assertTrue(Path(outputs["vault_note"]).exists())
        self.assertTrue(Path(outputs["run_dir"]).joinpath("rebuttal_scaffold_response.json").exists())

        markdown_text = Path(outputs["rebuttal_scaffold_markdown"]).read_text(encoding="utf-8")
        self.assertIn("Likely Reviewer Concerns", markdown_text)
        self.assertIn("overstate general superiority", markdown_text)

        request_payload = MockRebuttalScaffoldHandler.requests[-1]
        self.assertEqual(request_payload["model"], "gpt-5.4-rebuttal")
        self.assertEqual(request_payload["reasoning"]["effort"], "high")
        self.assertEqual(request_payload["text"]["format"]["name"], "rebuttal_scaffold_report")


if __name__ == "__main__":
    unittest.main()
