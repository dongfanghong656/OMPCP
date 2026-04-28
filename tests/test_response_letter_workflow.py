import json
import shutil
import subprocess
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "response_letter_workflow.py"


class MockResponseLetterHandler(BaseHTTPRequestHandler):
    response_payload = {}
    requests = []

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        payload = json.loads(body.decode("utf-8"))
        self.__class__.requests.append(payload)

        round_label = payload.get("input", "")
        response_payload = dict(self.__class__.response_payload)
        if "\"round_label\": \"round-2\"" in round_label:
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


class ResponseLetterWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.test_root = ROOT / "tmp" / "test-runs"
        self.test_root.mkdir(parents=True, exist_ok=True)
        self.workspace = self.test_root / "response-letter-workspace"
        shutil.rmtree(self.workspace, ignore_errors=True)
        self.workspace.mkdir(parents=True, exist_ok=True)

        self.vault_root = self.workspace / "vault"
        self.output_root = self.workspace / "reports"
        self.config_path = self.workspace / "config.json"
        self.review_comments_file = self.workspace / "review-comments.md"
        self.current_changes_file = self.workspace / "current-changes.md"
        self.rebuttal_scaffold_json = self.workspace / "rebuttal_scaffold.json"
        self.journal_targeting_json = self.workspace / "journal_targeting.json"
        self.draft_builder_json = self.workspace / "draft_builder.json"
        self.draft_file = self.workspace / "draft.md"

        (self.vault_root / "06_Writing").mkdir(parents=True, exist_ok=True)

        self.review_comments_file.write_text(
            "# Reviewer Comments\n\n1. The manuscript appears to overstate general superiority.\n",
            encoding="utf-8",
        )
        self.current_changes_file.write_text(
            "# Changes\n\nWe rewrote the abstract to use bounded benchmark language.\n",
            encoding="utf-8",
        )
        self.rebuttal_scaffold_json.write_text(
            json.dumps({"review_risk_summary": "Overclaim risk is central."}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        self.journal_targeting_json.write_text(
            json.dumps({"submission_checklist": ["Tighten the abstract claim."]}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        self.draft_builder_json.write_text(
            json.dumps({"claim_rewrites": [{"safe_rewrite": "bounded benchmark language"}]}, ensure_ascii=False, indent=2)
            + "\n",
            encoding="utf-8",
        )
        self.draft_file.write_text(
            "# Draft\n\nWe now describe the method as the strongest current candidate within the benchmark bundle.\n",
            encoding="utf-8",
        )

        MockResponseLetterHandler.requests = []
        MockResponseLetterHandler.response_payload = {
            "round_label": "round-1",
            "response_strategy_summary": "Acknowledge the wording problem and point to the revised bounded claim.",
            "tracked_points": [
                {
                    "reviewer_point": "The manuscript overstates general superiority.",
                    "response_text": "We revised the wording to reflect a bounded benchmark-bundle conclusion.",
                    "manuscript_change": "Abstract and Results opening rewritten.",
                    "evidence_anchor": "draft_builder.json + rebuttal_scaffold.json",
                    "status": "drafted",
                }
            ],
            "tone_guardrails": ["Thank the reviewer and concede the original wording was too broad."],
            "open_items": ["Keep future rounds aligned with the same bounded language."],
            "next_round_preparation": ["Track whether reviewers continue to ask for broader transfer evidence."],
        }

        self.server = HTTPServer(("127.0.0.1", 0), MockResponseLetterHandler)
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
                    "response_letter_model": "gpt-5.4-response-letter",
                    "response_letter_reasoning_effort": "high",
                    "response_letter_max_output_tokens": 7000,
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

    def test_response_letter_workflow_tracks_multiple_rounds(self):
        common_args = (
            "--config",
            str(self.config_path),
            "--title",
            "Reviewer response prep",
            "--review-comments-file",
            str(self.review_comments_file),
            "--current-changes-file",
            str(self.current_changes_file),
            "--rebuttal-scaffold-json",
            str(self.rebuttal_scaffold_json),
            "--journal-targeting-json",
            str(self.journal_targeting_json),
            "--draft-builder-json",
            str(self.draft_builder_json),
            "--draft-file",
            str(self.draft_file),
            "--write-vault-note",
        )

        stdout_round_1 = self.run_cli(*common_args, "--round-label", "round-1")
        outputs_round_1 = json.loads(stdout_round_1)
        self.assertTrue(Path(outputs_round_1["response_letter_json"]).exists())
        self.assertTrue(Path(outputs_round_1["tracker_index_json"]).exists())

        stdout_round_2 = self.run_cli(*common_args, "--round-label", "round-2")
        outputs_round_2 = json.loads(stdout_round_2)
        self.assertTrue(Path(outputs_round_2["response_letter_markdown"]).exists())
        self.assertTrue(Path(outputs_round_2["vault_note"]).exists())

        tracker_index = json.loads(Path(outputs_round_2["tracker_index_json"]).read_text(encoding="utf-8"))
        self.assertEqual(len(tracker_index["rounds"]), 2)
        self.assertEqual(tracker_index["rounds"][0]["round_label"], "round-2")
        self.assertEqual(tracker_index["rounds"][1]["round_label"], "round-1")

        request_payload = MockResponseLetterHandler.requests[-1]
        self.assertEqual(request_payload["model"], "gpt-5.4-response-letter")
        self.assertEqual(request_payload["reasoning"]["effort"], "high")
        self.assertEqual(request_payload["text"]["format"]["name"], "response_letter_report")


if __name__ == "__main__":
    unittest.main()
