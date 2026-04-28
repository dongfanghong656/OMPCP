import json
import shutil
import subprocess
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "citation_audit_workflow.py"


class MockCitationAuditHandler(BaseHTTPRequestHandler):
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


class CitationAuditWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.test_root = ROOT / "tmp" / "test-runs"
        self.test_root.mkdir(parents=True, exist_ok=True)
        self.workspace = self.test_root / "citation-audit-workspace"
        shutil.rmtree(self.workspace, ignore_errors=True)
        self.workspace.mkdir(parents=True, exist_ok=True)

        self.vault_root = self.workspace / "vault"
        self.output_root = self.workspace / "reports"
        self.config_path = self.workspace / "config.json"
        self.draft_file = self.workspace / "draft.md"
        self.journal_targeting_json = self.workspace / "journal_targeting.json"
        self.response_letter_json = self.workspace / "response_letter.json"
        self.references_file = self.workspace / "references.md"

        (self.vault_root / "06_Writing").mkdir(parents=True, exist_ok=True)

        self.draft_file.write_text(
            "# Draft\n\nWe suggest the benchmark result should transfer broadly to OCT applications.\n",
            encoding="utf-8",
        )
        self.journal_targeting_json.write_text(
            json.dumps({"journal_fit_summary": "Keep translational claims conservative."}, ensure_ascii=False, indent=2)
            + "\n",
            encoding="utf-8",
        )
        self.response_letter_json.write_text(
            json.dumps({"response_strategy_summary": "Tighten broad wording."}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        self.references_file.write_text(
            "# References\n\n- OCT stability paper\n- OCT repeatability paper\n",
            encoding="utf-8",
        )

        MockCitationAuditHandler.requests = []
        MockCitationAuditHandler.response_payload = {
            "citation_risk_summary": "The main citation risk is unsupported broad transfer wording.",
            "reference_basis_note": "The audit uses the draft and the provided lightweight reference notes.",
            "claim_audits": [
                {
                    "claim_or_sentence": "The benchmark result should transfer broadly to OCT applications.",
                    "risk": "The claim extends beyond the visible evidence base.",
                    "citation_action": "Narrow the statement or add stronger validation-oriented references.",
                    "evidence_or_reference_needed": "Transferability and repeatability literature",
                    "severity": "high",
                }
            ],
            "reference_completeness_checks": ["Check that broad-impact sentences cite both method and validation literature."],
            "safe_keep_areas": ["The bounded benchmark result itself is relatively safe."],
            "priority_repairs": ["Rewrite the transferability sentence in the opening paragraph."],
            "final_citation_targets": ["Add one repeatability citation near the main conclusion boundary."],
        }

        self.server = HTTPServer(("127.0.0.1", 0), MockCitationAuditHandler)
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
                    "citation_audit_model": "gpt-5.4-citation",
                    "citation_audit_reasoning_effort": "high",
                    "citation_audit_max_output_tokens": 7000,
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

    def test_citation_audit_workflow_outputs_files_and_vault_note(self):
        stdout = self.run_cli(
            "--config",
            str(self.config_path),
            "--title",
            "Citation sweep",
            "--draft-file",
            str(self.draft_file),
            "--journal-targeting-json",
            str(self.journal_targeting_json),
            "--response-letter-json",
            str(self.response_letter_json),
            "--references-file",
            str(self.references_file),
            "--write-vault-note",
        )
        outputs = json.loads(stdout)

        self.assertTrue(Path(outputs["citation_audit_json"]).exists())
        self.assertTrue(Path(outputs["citation_audit_markdown"]).exists())
        self.assertTrue(Path(outputs["vault_note"]).exists())
        self.assertTrue(Path(outputs["run_dir"]).joinpath("citation_audit_response.json").exists())

        markdown_text = Path(outputs["citation_audit_markdown"]).read_text(encoding="utf-8")
        self.assertIn("Claim Audits", markdown_text)
        self.assertIn("Citation action", markdown_text)

        request_payload = MockCitationAuditHandler.requests[-1]
        self.assertEqual(request_payload["model"], "gpt-5.4-citation")
        self.assertEqual(request_payload["reasoning"]["effort"], "high")
        self.assertEqual(request_payload["text"]["format"]["name"], "citation_audit_report")


if __name__ == "__main__":
    unittest.main()
