import json
import shutil
import subprocess
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "journal_targeting_workflow.py"


class MockJournalTargetingHandler(BaseHTTPRequestHandler):
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


class JournalTargetingWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.test_root = ROOT / "tmp" / "test-runs"
        self.test_root.mkdir(parents=True, exist_ok=True)
        self.workspace = self.test_root / "journal-targeting-workspace"
        shutil.rmtree(self.workspace, ignore_errors=True)
        self.workspace.mkdir(parents=True, exist_ok=True)

        self.vault_root = self.workspace / "vault"
        self.output_root = self.workspace / "reports"
        self.config_path = self.workspace / "config.json"
        self.journal_notes_file = self.workspace / "journal-notes.md"
        self.draft_builder_json = self.workspace / "draft_builder.json"
        self.self_review_json = self.workspace / "self_review.json"
        self.rebuttal_scaffold_json = self.workspace / "rebuttal_scaffold.json"
        self.draft_file = self.workspace / "draft.md"

        (self.vault_root / "06_Writing").mkdir(parents=True, exist_ok=True)

        self.journal_notes_file.write_text(
            "# Journal Notes\n\nMethods-heavy venue with strong emphasis on limitations and reproducibility.\n",
            encoding="utf-8",
        )
        self.draft_builder_json.write_text(
            json.dumps({"positioning_summary": "Bound the claim to the benchmark bundle."}, ensure_ascii=False, indent=2)
            + "\n",
            encoding="utf-8",
        )
        self.self_review_json.write_text(
            json.dumps({"review_summary": "Move caution earlier."}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        self.rebuttal_scaffold_json.write_text(
            json.dumps({"review_risk_summary": "Main risk is overclaiming."}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        self.draft_file.write_text(
            "# Draft\n\nWe currently lead with the benchmark result and mention limitations later.\n",
            encoding="utf-8",
        )

        MockJournalTargetingHandler.requests = []
        MockJournalTargetingHandler.response_payload = {
            "journal_fit_summary": "The paper fits if it foregrounds reproducibility and limitations.",
            "journal_basis_note": "Advice is grounded in the provided journal notes rather than inferred house style.",
            "adaptation_rules": [
                {
                    "section_or_element": "Abstract",
                    "keep": "Bounded benchmark conclusion.",
                    "adapt_for_journal": "State the validation boundary earlier.",
                    "risk_if_unchanged": "The claim may read as too broad for a methods-heavy venue.",
                }
            ],
            "citation_actions": [
                {
                    "claim_area": "Transferability framing",
                    "citation_need": "Add prior validation-focused OCT references.",
                    "evidence_type_needed": "Methods and stability literature",
                    "priority": "high",
                }
            ],
            "presentation_priorities": ["Move reproducibility logic ahead of broad impact framing."],
            "submission_checklist": ["Audit the abstract for residual universal wording."],
            "next_journal_targets": ["Prepare a short cover-letter angle around reproducibility and caution."],
        }

        self.server = HTTPServer(("127.0.0.1", 0), MockJournalTargetingHandler)
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
                    "journal_targeting_model": "gpt-5.4-journal",
                    "journal_targeting_reasoning_effort": "high",
                    "journal_targeting_max_output_tokens": 7000,
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

    def test_journal_targeting_workflow_outputs_files_and_vault_note(self):
        stdout = self.run_cli(
            "--config",
            str(self.config_path),
            "--title",
            "Target journal prep",
            "--journal-name",
            "Biomedical Optics Express",
            "--journal-notes-file",
            str(self.journal_notes_file),
            "--draft-builder-json",
            str(self.draft_builder_json),
            "--self-review-json",
            str(self.self_review_json),
            "--rebuttal-scaffold-json",
            str(self.rebuttal_scaffold_json),
            "--draft-file",
            str(self.draft_file),
            "--write-vault-note",
        )
        outputs = json.loads(stdout)

        self.assertTrue(Path(outputs["journal_targeting_json"]).exists())
        self.assertTrue(Path(outputs["journal_targeting_markdown"]).exists())
        self.assertTrue(Path(outputs["vault_note"]).exists())
        self.assertTrue(Path(outputs["run_dir"]).joinpath("journal_targeting_response.json").exists())

        markdown_text = Path(outputs["journal_targeting_markdown"]).read_text(encoding="utf-8")
        self.assertIn("Adaptation Rules", markdown_text)
        self.assertIn("Citation Actions", markdown_text)

        request_payload = MockJournalTargetingHandler.requests[-1]
        self.assertEqual(request_payload["model"], "gpt-5.4-journal")
        self.assertEqual(request_payload["reasoning"]["effort"], "high")
        self.assertEqual(request_payload["text"]["format"]["name"], "journal_targeting_report")


if __name__ == "__main__":
    unittest.main()
