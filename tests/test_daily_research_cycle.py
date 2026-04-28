import json
import os
import shutil
import subprocess
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "daily_research_cycle.py"


class MockCycleRadarHandler(BaseHTTPRequestHandler):
    radar_response = {}
    requests = []

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        payload = json.loads(body.decode("utf-8"))
        self.__class__.requests.append(payload)

        response = {"output_text": json.dumps(self.__class__.radar_response, ensure_ascii=False)}
        encoded = json.dumps(response, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, format, *args):
        return


class DailyResearchCycleTests(unittest.TestCase):
    def setUp(self):
        self.test_root = Path(
            os.environ.get(
                "OCT_RESEARCH_ASSIST_TEST_ROOT",
                str(ROOT / "tmp" / "test-runs"),
            )
        )
        self.test_root.mkdir(parents=True, exist_ok=True)
        self.workspace = self.test_root / "daily-research-cycle-workspace"
        shutil.rmtree(self.workspace, ignore_errors=True)
        self.workspace.mkdir(parents=True, exist_ok=True)

        self.vault_root = self.workspace / "vault"
        self.output_root = self.workspace / "reports"
        self.config_path = self.workspace / "config.json"
        self.profile_path = self.workspace / "profile.json"
        self.latest_literature_path = self.workspace / "latest-literature.json"

        (self.vault_root / "01_Daily").mkdir(parents=True, exist_ok=True)
        (self.vault_root / "02_Literature" / "Papers").mkdir(parents=True, exist_ok=True)
        (self.vault_root / "04_Progress").mkdir(parents=True, exist_ok=True)
        (self.vault_root / "09_Conversations").mkdir(parents=True, exist_ok=True)
        (self.vault_root / "11_Retrieval").mkdir(parents=True, exist_ok=True)

        (self.vault_root / "02_Literature" / "Papers" / "[2026] Wu - OCT PSF Drift.md").write_text(
            "# OCT PSF Drift\n\nA new paper suggests calibration-aware kernels still fail once drift exceeds a measurable threshold.\n",
            encoding="utf-8",
        )
        (self.vault_root / "04_Progress" / "validation-plan.md").write_text(
            "# Validation Plan\n\nThe current bottleneck is still whether we can quantify tolerated PSF drift before making manuscript claims.\n",
            encoding="utf-8",
        )
        (self.vault_root / "09_Conversations" / "2026-03-23-notes.md").write_text(
            "# Conversation Notes\n\nThe wrong-PSF control should probably become the first decisive falsification experiment.\n",
            encoding="utf-8",
        )

        self.profile_path.write_text(
            json.dumps(
                {
                    "updated_for": "OCT deconvolution",
                    "primary_objective": "Assess deconvolution stability under realistic PSF mismatch.",
                    "evaluation_focus": ["repeatability", "artifact suppression"],
                    "writing_goal": "A cautious manuscript with strong falsification logic.",
                    "interests": [
                        {
                            "name": "Calibration-aware deconvolution",
                            "keywords": ["OCT calibration aware deconvolution", "PSF drift"],
                            "priority": 1,
                        }
                    ],
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        self.latest_literature_path.write_text(
            json.dumps(
                {
                    "Calibration-aware deconvolution": [
                        {
                            "title": "Calibration-aware spatially varying OCT deconvolution",
                            "year": "2026",
                            "publication_date": "2026-03-19",
                            "url": "https://example.com/calibration-aware-oct",
                            "source": "openalex",
                        }
                    ]
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        MockCycleRadarHandler.requests = []
        MockCycleRadarHandler.radar_response = {
            "focus_summary": "Daily context converges on PSF drift tolerance and falsification design as the two most leveraged next questions.",
            "candidate_questions": [
                {
                    "title": "Quantify PSF drift tolerance for manuscript-safe claims",
                    "question": "What PSF drift range can the current pipeline tolerate before gains stop transferring across scans?",
                    "value_score": 9,
                    "time_horizon": "immediate",
                    "why_now": "This directly controls whether the current manuscript framing is stable.",
                    "novelty_or_gap": "The vault has warnings about drift but no measured tolerance curve.",
                    "required_evidence": [
                        "Repeat-session PSF measurements",
                        "A drift-versus-gain stability curve"
                    ],
                    "first_action": "Measure PSF drift across sessions on the current phantom protocol.",
                    "source_signals": [
                        "validation-plan.md highlights the unresolved tolerance question.",
                        "A recent calibration-aware paper makes the tolerance band explicit."
                    ]
                }
            ],
            "selection_advice": [
                "Run the tolerance measurement first because it constrains both validation strategy and manuscript wording."
            ],
        }

        self.server = HTTPServer(("127.0.0.1", 0), MockCycleRadarHandler)
        self.server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.server_thread.start()

        config = {
            "profile_path": str(self.profile_path).replace("\\", "/"),
            "vault_root": str(self.vault_root).replace("\\", "/"),
            "output_root": str(self.output_root).replace("\\", "/"),
            "obsidian": {
                "daily_folder": "01_Daily",
                "paper_folder": "02_Papers",
                "concept_folder": "03_Concepts",
                "progress_folder": "04_Progress",
                "experiment_folder": "05_Experiments",
                "writing_folder": "06_Writing",
                "profile_folder": "07_Profiles",
                "attachment_folder": "08_Attachments",
                "conversation_folder": "09_Conversations",
                "task_folder": "10_Tasks",
                "retrieval_folder": "11_Retrieval",
                "zotero_folder": "12_Zotero",
            },
            "retrieval": {
                "sources": ["openalex", "arxiv"],
                "since_days": 7,
                "max_results_per_interest": 5,
                "openalex_mailto": "",
            },
            "academic_qa": {
                "enable_critique": True,
                "enable_auto_evidence": True,
                "question_folder": "04_Research/Questions",
                "auto_evidence_paths": [
                    "02_Literature/Papers",
                    "04_Progress",
                    "09_Conversations",
                ],
                "auto_evidence_min_score": 1,
                "auto_evidence_max_notes": 4,
                "auto_evidence_max_chars_per_note": 400,
                "auto_evidence_max_candidates_log": 10,
                "openai": {
                    "api_key": "test-key",
                    "base_url": f"http://127.0.0.1:{self.server.server_port}/v1/responses",
                    "reason_model": "gpt-5.4",
                    "reason_reasoning_effort": "high",
                    "reason_max_output_tokens": 8000,
                },
            },
            "question_radar": {
                "report_folder_name": "question-radar",
                "note_folder": "04_Research/Questions",
                "daily_section_title": "Question Radar",
                "max_questions": 4,
                "lookback_days": 2,
                "recent_note_paths": [
                    "02_Literature/Papers",
                    "04_Progress",
                    "09_Conversations",
                ],
                "latest_literature_enabled": True,
                "write_daily_note": True,
                "write_vault_note": True,
                "openai": {
                    "api_key": "test-key",
                    "base_url": f"http://127.0.0.1:{self.server.server_port}/v1/responses",
                    "model": "gpt-5.4",
                    "reasoning_effort": "high",
                    "max_output_tokens": 5000,
                },
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

    def test_daily_research_cycle_runs_question_radar_and_digest(self):
        stdout = self.run_cli(
            "--config",
            str(self.config_path),
            "--skip-retrieval",
            "--latest-literature-file",
            str(self.latest_literature_path),
        )

        outputs = json.loads(stdout)
        self.assertTrue(Path(outputs["summary_json"]).exists())
        self.assertTrue(Path(outputs["summary_markdown"]).exists())
        self.assertTrue(Path(outputs["question_radar_note"]).exists())
        self.assertTrue(Path(outputs["question_radar_markdown"]).exists())
        self.assertTrue(Path(outputs["daily_digest"]).exists())
        self.assertTrue(Path(outputs["daily_note"]).exists())

        summary_markdown = Path(outputs["summary_markdown"]).read_text(encoding="utf-8")
        self.assertIn("Question radar note", summary_markdown)
        self.assertIn("Daily digest report", summary_markdown)

        daily_text = Path(outputs["daily_note"]).read_text(encoding="utf-8")
        self.assertIn("## Daily Research Cycle", daily_text)
        self.assertIn("## Question Radar", daily_text)
        self.assertIn("Quantify PSF drift tolerance for manuscript-safe claims", daily_text)

        self.assertEqual(len(MockCycleRadarHandler.requests), 1)
        prompt_payload = json.loads(MockCycleRadarHandler.requests[0]["input"])
        self.assertEqual(prompt_payload["mode"], "daily")

    def test_daily_research_cycle_uses_local_radar_fallback_without_api_key(self):
        config = json.loads(self.config_path.read_text(encoding="utf-8"))
        config["academic_qa"]["openai"]["api_key"] = ""
        config["question_radar"]["openai"]["api_key"] = ""
        self.config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        MockCycleRadarHandler.requests = []

        stdout = self.run_cli(
            "--config",
            str(self.config_path),
            "--skip-retrieval",
            "--latest-literature-file",
            str(self.latest_literature_path),
        )

        outputs = json.loads(stdout)
        self.assertTrue(Path(outputs["question_radar_note"]).exists())
        self.assertTrue(Path(outputs["question_radar_markdown"]).exists())
        self.assertEqual(MockCycleRadarHandler.requests, [])

        summary_markdown = Path(outputs["summary_markdown"]).read_text(encoding="utf-8")
        self.assertIn("Question radar note", summary_markdown)
        self.assertNotIn("question_radar.py failed", summary_markdown)

        radar_run_dir = Path(outputs["question_radar_markdown"]).parent
        response_meta = json.loads((radar_run_dir / "question_radar_response.json").read_text(encoding="utf-8"))
        self.assertEqual(response_meta["generator"], "codex-local-fallback")


if __name__ == "__main__":
    unittest.main()
