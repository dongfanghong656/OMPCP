import json
import shutil
import subprocess
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "draft_builder_workflow.py"


class MockDraftBuilderHandler(BaseHTTPRequestHandler):
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


class DraftBuilderWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.test_root = ROOT / "tmp" / "test-runs"
        self.test_root.mkdir(parents=True, exist_ok=True)
        self.workspace = self.test_root / "draft-builder-workspace"
        shutil.rmtree(self.workspace, ignore_errors=True)
        self.workspace.mkdir(parents=True, exist_ok=True)

        self.vault_root = self.workspace / "vault"
        self.output_root = self.workspace / "reports"
        self.config_path = self.workspace / "config.json"
        self.analysis_json = self.workspace / "analysis.json"
        self.results_report_json = self.workspace / "results_report.json"
        self.writing_memory_json = self.workspace / "writing_memory.json"
        self.self_review_json = self.workspace / "self_review.json"
        self.outline_file = self.workspace / "outline.md"

        (self.vault_root / "06_Writing").mkdir(parents=True, exist_ok=True)

        self.analysis_json.write_text(
            json.dumps({"title": "ECM baseline"}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        self.results_report_json.write_text(
            json.dumps(
                {
                    "headline": "tukey_0p6 is the current best candidate under this benchmark bundle.",
                    "safe_claims": ["Use bounded benchmark language."],
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
                    "focus_summary": "Use manuscript-safe bounded language.",
                    "terminology_preferences": [
                        {
                            "term": "current best candidate",
                            "preferred_usage": "Use for bounded benchmark claims.",
                            "avoid_phrase": "universally superior",
                        }
                    ],
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        self.self_review_json.write_text(
            json.dumps(
                {
                    "review_summary": "Tighten the lead claim.",
                    "overclaim_risks": ["Universal superiority wording is too strong."],
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        self.outline_file.write_text(
            "# Outline\n\n## Results\n## Discussion\n",
            encoding="utf-8",
        )

        MockDraftBuilderHandler.requests = []
        MockDraftBuilderHandler.response_payload = {
            "positioning_summary": "Frame the paper around bounded candidate selection.",
            "claim_rewrites": [
                {
                    "unsafe_claim": "The top window is universally superior.",
                    "safe_rewrite": "The top window is the strongest current candidate within this benchmark bundle.",
                    "why_safer": "The rewrite matches the evidence boundary.",
                }
            ],
            "section_blocks": [
                {
                    "section": "Results",
                    "goal": "Report the bounded ranking outcome.",
                    "paragraph_text": "Within the present benchmark bundle, tukey_0p6 emerged as the strongest current candidate.",
                    "evidence_anchor": "results_report.json",
                    "carryover_caution": "Do not generalize beyond the benchmark bundle.",
                }
            ],
            "figure_callouts": [
                {
                    "figure_or_artifact": "results_report.md",
                    "narrative_role": "Anchor the bounded ranking result.",
                    "safe_caption_hook": "Current benchmark-bundle leader used for follow-up validation.",
                }
            ],
            "next_section_targets": ["Draft the discussion boundary paragraph."],
        }

        self.server = HTTPServer(("127.0.0.1", 0), MockDraftBuilderHandler)
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
                    "draft_builder_model": "gpt-5.4-draft-builder",
                    "draft_builder_reasoning_effort": "high",
                    "draft_builder_max_output_tokens": 7000,
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

    def test_draft_builder_workflow_outputs_files_and_vault_note(self):
        stdout = self.run_cli(
            "--config",
            str(self.config_path),
            "--title",
            "ECM manuscript blocks",
            "--analysis-json",
            str(self.analysis_json),
            "--results-report-json",
            str(self.results_report_json),
            "--writing-memory-json",
            str(self.writing_memory_json),
            "--self-review-json",
            str(self.self_review_json),
            "--outline-file",
            str(self.outline_file),
            "--write-vault-note",
        )
        outputs = json.loads(stdout)

        self.assertTrue(Path(outputs["draft_builder_json"]).exists())
        self.assertTrue(Path(outputs["draft_builder_markdown"]).exists())
        self.assertTrue(Path(outputs["vault_note"]).exists())
        self.assertTrue(Path(outputs["run_dir"]).joinpath("draft_builder_response.json").exists())

        markdown_text = Path(outputs["draft_builder_markdown"]).read_text(encoding="utf-8")
        self.assertIn("Claim Rewrites", markdown_text)
        self.assertIn("benchmark bundle", markdown_text)

        request_payload = MockDraftBuilderHandler.requests[-1]
        self.assertEqual(request_payload["model"], "gpt-5.4-draft-builder")
        self.assertEqual(request_payload["reasoning"]["effort"], "high")
        self.assertEqual(request_payload["text"]["format"]["name"], "draft_builder_report")


if __name__ == "__main__":
    unittest.main()
