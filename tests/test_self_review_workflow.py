import json
import shutil
import subprocess
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "self_review_workflow.py"


class MockSelfReviewHandler(BaseHTTPRequestHandler):
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


class SelfReviewWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.test_root = ROOT / "tmp" / "test-runs"
        self.test_root.mkdir(parents=True, exist_ok=True)
        self.workspace = self.test_root / "self-review-workspace"
        shutil.rmtree(self.workspace, ignore_errors=True)
        self.workspace.mkdir(parents=True, exist_ok=True)

        self.vault_root = self.workspace / "vault"
        self.output_root = self.workspace / "reports"
        self.config_path = self.workspace / "config.json"
        self.draft_file = self.workspace / "draft.md"
        self.analysis_json = self.workspace / "analysis.json"
        self.results_report_json = self.workspace / "results_report.json"
        self.writing_memory_json = self.workspace / "writing_memory.json"

        (self.vault_root / "06_Writing").mkdir(parents=True, exist_ok=True)

        self.draft_file.write_text(
            "# Draft\n\nWe claim the current leader is universally superior across OCT conditions.\n",
            encoding="utf-8",
        )
        self.analysis_json.write_text(
            json.dumps(
                {
                    "title": "ECM baseline",
                    "findings": [
                        {
                            "type": "ranking_span",
                            "claim": "The ranking separates best and worst candidates within this bundle.",
                            "evidence": "Best=tukey_0p6, Worst=hann",
                        }
                    ],
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
                    "headline": "tukey_0p6 is the current best candidate under this benchmark bundle.",
                    "unsupported_claims": [
                        "This benchmark alone proves general superiority across all OCT conditions."
                    ],
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
                    "terminology_preferences": [
                        {
                            "term": "current best candidate",
                            "preferred_usage": "Use for bounded benchmark conclusions.",
                            "avoid_phrase": "universally superior",
                        }
                    ]
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        MockSelfReviewHandler.requests = []
        MockSelfReviewHandler.response_payload = {
            "review_summary": "The draft overstates what the benchmark bundle can support.",
            "overall_readiness": "Needs revision before it is manuscript-safe.",
            "claim_alignment_issues": [
                {
                    "claim_or_section": "Opening claim",
                    "issue": "The draft implies universal superiority.",
                    "severity": "high",
                    "evidence_gap": "The evidence only supports a bounded benchmark-bundle statement.",
                    "revision_direction": "Replace the claim with a current best-candidate formulation.",
                }
            ],
            "overclaim_risks": ["The wording implies general OCT transferability that is not shown."],
            "missing_controls_or_evidence": ["Cross-condition validation is still missing."],
            "wording_risks": ["Avoid 'universally superior'."],
            "salvageable_strengths": ["The draft is already centered on the current ranking leader."],
            "revision_actions": ["Rewrite the opening paragraph with evidence-bounded language."],
        }

        self.server = HTTPServer(("127.0.0.1", 0), MockSelfReviewHandler)
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
                    "self_review_model": "gpt-5.4-self-review",
                    "self_review_reasoning_effort": "high",
                    "self_review_max_output_tokens": 6000,
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

    def test_self_review_workflow_outputs_files_and_vault_note(self):
        stdout = self.run_cli(
            "--config",
            str(self.config_path),
            "--draft-file",
            str(self.draft_file),
            "--title",
            "ECM draft review",
            "--analysis-json",
            str(self.analysis_json),
            "--results-report-json",
            str(self.results_report_json),
            "--writing-memory-json",
            str(self.writing_memory_json),
            "--write-vault-note",
        )
        outputs = json.loads(stdout)

        self.assertTrue(Path(outputs["self_review_json"]).exists())
        self.assertTrue(Path(outputs["self_review_markdown"]).exists())
        self.assertTrue(Path(outputs["vault_note"]).exists())
        self.assertTrue(Path(outputs["run_dir"]).joinpath("self_review_response.json").exists())

        markdown_text = Path(outputs["self_review_markdown"]).read_text(encoding="utf-8")
        self.assertIn("Claim Alignment Issues", markdown_text)
        self.assertIn("universally superior", markdown_text)

        request_payload = MockSelfReviewHandler.requests[-1]
        self.assertEqual(request_payload["model"], "gpt-5.4-self-review")
        self.assertEqual(request_payload["reasoning"]["effort"], "high")
        self.assertEqual(request_payload["text"]["format"]["name"], "self_review_report")


if __name__ == "__main__":
    unittest.main()
