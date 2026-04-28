import json
import shutil
import subprocess
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "writing_memory_workflow.py"


class MockWritingMemoryHandler(BaseHTTPRequestHandler):
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


class WritingMemoryWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.test_root = ROOT / "tmp" / "test-runs"
        self.test_root.mkdir(parents=True, exist_ok=True)
        self.workspace = self.test_root / "writing-memory-workspace"
        shutil.rmtree(self.workspace, ignore_errors=True)
        self.workspace.mkdir(parents=True, exist_ok=True)

        self.vault_root = self.workspace / "vault"
        self.output_root = self.workspace / "reports"
        self.config_path = self.workspace / "config.json"
        self.analysis_json = self.workspace / "analysis.json"
        self.results_report_json = self.workspace / "results_report.json"
        self.results_report_markdown = self.workspace / "results_report.md"

        (self.vault_root / "06_Writing").mkdir(parents=True, exist_ok=True)

        self.analysis_json.write_text(
            json.dumps(
                {
                    "title": "ECM baseline",
                    "findings": [
                        {
                            "type": "ranking_leader",
                            "claim": "tukey_0p6 leads the current ranking.",
                            "evidence": "UnifiedScore=0.98",
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
                    "safe_claims": [
                        "tukey_0p6 is the strongest current candidate within this benchmark bundle."
                    ],
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        self.results_report_markdown.write_text(
            "# Results Report\n\nThe current leader should be treated as a follow-up candidate, not a universal winner.\n",
            encoding="utf-8",
        )

        MockWritingMemoryHandler.requests = []
        MockWritingMemoryHandler.response_payload = {
            "focus_summary": "Keep the manuscript centered on benchmark-bundle leadership rather than general superiority.",
            "reusable_claims": [
                {
                    "claim": "tukey_0p6 is the strongest current candidate within this benchmark bundle.",
                    "evidence_basis": "It leads the current unified ranking bundle.",
                    "caution": "This statement should not be expanded into a general OCT superiority claim.",
                    "fit_sections": ["Results", "Discussion"],
                }
            ],
            "reusable_caveats": [
                "The current ranking bundle is a follow-up selection signal, not a publication-wide proof."
            ],
            "figure_narratives": [
                {
                    "artifact": "results_report.md",
                    "caption_angle": "Highlight ranked-candidate selection without overstating generality.",
                    "why_it_matters": "This keeps figure text manuscript-safe.",
                }
            ],
            "reviewer_watchouts": ["Reviewers may ask whether the ranking transfers to real OCT evidence."],
            "terminology_preferences": [
                {
                    "term": "current best candidate",
                    "preferred_usage": "Use for evidence-bounded ranking conclusions.",
                    "avoid_phrase": "universally superior",
                }
            ],
            "next_writing_targets": ["Rewrite the abstract claim using bounded language."],
        }

        self.server = HTTPServer(("127.0.0.1", 0), MockWritingMemoryHandler)
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
                    "writing_memory_model": "gpt-5.4-writing",
                    "writing_memory_reasoning_effort": "high",
                    "writing_memory_max_output_tokens": 5000,
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

    def test_writing_memory_workflow_outputs_files_and_vault_note(self):
        stdout = self.run_cli(
            "--config",
            str(self.config_path),
            "--title",
            "ECM baseline writing memory",
            "--analysis-json",
            str(self.analysis_json),
            "--results-report-json",
            str(self.results_report_json),
            "--results-report-markdown",
            str(self.results_report_markdown),
            "--write-vault-note",
        )
        outputs = json.loads(stdout)

        self.assertTrue(Path(outputs["writing_memory_json"]).exists())
        self.assertTrue(Path(outputs["writing_memory_markdown"]).exists())
        self.assertTrue(Path(outputs["vault_note"]).exists())
        self.assertTrue(Path(outputs["run_dir"]).joinpath("writing_memory_response.json").exists())

        markdown_text = Path(outputs["writing_memory_markdown"]).read_text(encoding="utf-8")
        self.assertIn("Reusable Claims", markdown_text)
        self.assertIn("current best candidate", markdown_text)

        request_payload = MockWritingMemoryHandler.requests[-1]
        self.assertEqual(request_payload["model"], "gpt-5.4-writing")
        self.assertEqual(request_payload["reasoning"]["effort"], "high")
        self.assertEqual(request_payload["text"]["format"]["name"], "writing_memory_report")


if __name__ == "__main__":
    unittest.main()
