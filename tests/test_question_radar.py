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
SCRIPT = ROOT / "scripts" / "question_radar.py"


class MockRadarHandler(BaseHTTPRequestHandler):
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


class QuestionRadarTests(unittest.TestCase):
    def setUp(self):
        self.test_root = Path(
            os.environ.get(
                "OCT_RESEARCH_ASSIST_TEST_ROOT",
                str(ROOT / "tmp" / "test-runs"),
            )
        )
        self.test_root.mkdir(parents=True, exist_ok=True)
        self.workspace = self.test_root / "question-radar-workspace"
        shutil.rmtree(self.workspace, ignore_errors=True)
        self.workspace.mkdir(parents=True, exist_ok=True)

        self.vault_root = self.workspace / "vault"
        self.output_root = self.workspace / "reports"
        self.config_path = self.workspace / "config.json"
        self.profile_path = self.workspace / "profile.json"
        self.latest_literature_path = self.workspace / "latest-literature.json"

        (self.vault_root / "01_Daily").mkdir(parents=True, exist_ok=True)
        (self.vault_root / "02_Literature" / "Papers").mkdir(parents=True, exist_ok=True)
        (self.vault_root / "03_Concepts").mkdir(parents=True, exist_ok=True)
        (self.vault_root / "04_Progress").mkdir(parents=True, exist_ok=True)
        (self.vault_root / "09_Conversations").mkdir(parents=True, exist_ok=True)
        (self.vault_root / "11_Retrieval").mkdir(parents=True, exist_ok=True)

        (self.vault_root / "02_Literature" / "Papers" / "[2026] Li - Calibration Aware OCT.md").write_text(
            "---\n"
            'title: "Calibration Aware OCT"\n'
            "---\n\n"
            "> [!q2-focus]\n"
            "> Calibrated kernels remain useful only when PSF drift stays within a measurable tolerance band.\n\n"
            "> [!evidence]\n"
            "> The paper compares deliberate PSF mismatch and shows stability degrades before visual sharpness obviously collapses.\n",
            encoding="utf-8",
        )
        (self.vault_root / "03_Concepts" / "Concept - Negative Controls.md").write_text(
            "# Negative Controls\n\nWrong-PSF controls are currently the fastest way to separate information recovery from artifact amplification.\n",
            encoding="utf-8",
        )
        (self.vault_root / "04_Progress" / "manuscript-risk.md").write_text(
            "# Manuscript Risk\n\nWe still cannot state how much PSF drift the current pipeline tolerates before claims stop transferring across scans.\n",
            encoding="utf-8",
        )
        (self.vault_root / "09_Conversations" / "2026-03-23-psf-discussion.md").write_text(
            "# Discussion\n\nWe keep circling back to PSF mismatch, repeatability, and whether the wrong-PSF negative control should be the first decisive experiment.\n",
            encoding="utf-8",
        )
        (self.vault_root / "11_Retrieval" / "2026-03-23-retrieval.md").write_text(
            "# Retrieval Snapshot\n\nA new adaptive-kernel paper suggests calibration-aware deconvolution needs explicit tolerance analysis.\n",
            encoding="utf-8",
        )

        self.profile_path.write_text(
            json.dumps(
                {
                    "updated_for": "OCT deconvolution and lateral-resolution research",
                    "primary_objective": "Assess whether physically grounded deconvolution improves lateral resolution without unacceptable artifacts.",
                    "evaluation_focus": ["lateral resolution", "artifact suppression", "repeatability"],
                    "writing_goal": "A cautious SCI manuscript with strong falsification logic.",
                    "interests": [
                        {
                            "name": "Blind and spatially varying deconvolution",
                            "keywords": ["blind deconvolution OCT", "space variant PSF"],
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
                    "Blind and spatially varying deconvolution": [
                        {
                            "title": "Calibration-aware spatially varying OCT deconvolution",
                            "year": "2026",
                            "publication_date": "2026-03-19",
                            "url": "https://example.com/calibration-aware-oct",
                            "source": "openalex",
                        },
                        {
                            "title": "Mismatch-sensitive kernel adaptation for OCT",
                            "year": "2026",
                            "publication_date": "2026-03-18",
                            "url": "https://arxiv.org/abs/2603.12345",
                            "source": "arxiv",
                        },
                    ]
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        MockRadarHandler.requests = []
        MockRadarHandler.radar_response = {
            "focus_summary": "Current context points to a narrow but high-leverage question set around PSF tolerance, falsification strategy, and manuscript-grade validation.",
            "candidate_questions": [
                {
                    "title": "Quantify tolerated PSF drift before gains stop transferring",
                    "question": "How much field and session PSF drift can the current deconvolution pipeline tolerate before apparent lateral gains stop transferring across scans?",
                    "value_score": 9,
                    "time_horizon": "immediate",
                    "why_now": "This determines whether the main manuscript claim is stable or only local to a narrow calibration window.",
                    "novelty_or_gap": "Current notes warn about PSF mismatch, but no note quantifies the tolerated drift band.",
                    "required_evidence": [
                        "Repeat PSF measurements across field positions and sessions",
                        "A wrong-PSF negative-control curve"
                    ],
                    "first_action": "Run a phantom PSF sweep across field position and a repeat session, then fit the gain collapse point.",
                    "source_signals": [
                        "04_Progress/manuscript-risk.md flags transferability risk.",
                        "Calibration-aware spatially varying OCT deconvolution argues for measurable tolerance bands."
                    ]
                },
                {
                    "title": "Make the first falsification experiment decisive",
                    "question": "Which negative-control design most quickly falsifies the claim that observed sharpening reflects information recovery rather than artifact amplification?",
                    "value_score": 8,
                    "time_horizon": "near_term",
                    "why_now": "A decisive falsification experiment would compress the current validation backlog.",
                    "novelty_or_gap": "The team references wrong-PSF controls repeatedly but has not locked the exact test design.",
                    "required_evidence": [
                        "A deliberately mismatched PSF control",
                        "Task-based metrics on the same scan pair"
                    ],
                    "first_action": "Define one wrong-PSF control and compare it against the calibrated pipeline on the current phantom task.",
                    "source_signals": [
                        "Concept - Negative Controls.md pushes wrong-PSF controls.",
                        "Conversation notes keep returning to falsification-first logic."
                    ]
                }
            ],
            "selection_advice": [
                "Start with the PSF drift tolerance question because it can invalidate or stabilize the main manuscript framing fastest."
            ],
        }

        self.server = HTTPServer(("127.0.0.1", 0), MockRadarHandler)
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
                    "03_Concepts",
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
                    "11_Retrieval",
                ],
                "recent_note_max_files": 5,
                "recent_note_max_chars": 320,
                "latest_literature_enabled": True,
                "latest_literature_max_per_interest": 3,
                "latest_literature_since_days": 7,
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

    def test_manual_mode_generates_question_radar_note(self):
        stdout = self.run_cli(
            "manual",
            "--config",
            str(self.config_path),
            "--title",
            "PSF mismatch pressure points",
            "--prompt",
            "I want a small set of high-value questions about PSF mismatch, repeatability, and manuscript-grade validation.",
            "--evidence-text",
            "We still need a decisive experiment before writing strong claims.",
        )

        outputs = json.loads(stdout)
        run_dir = Path(outputs["run_dir"])
        self.assertTrue((run_dir / "question_radar.json").exists())
        self.assertTrue((run_dir / "question_radar.md").exists())
        self.assertTrue((run_dir / "context_snapshot.json").exists())
        self.assertTrue(Path(outputs["question_radar_note"]).exists())

        context_snapshot = json.loads((run_dir / "context_snapshot.json").read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(context_snapshot["auto_evidence"]), 1)
        self.assertIn("evidence_brief", context_snapshot)

        radar_markdown = (run_dir / "question_radar.md").read_text(encoding="utf-8")
        self.assertIn("## Candidate Questions", radar_markdown)
        self.assertIn("Quantify tolerated PSF drift before gains stop transferring", radar_markdown)

        prompt_payload = json.loads(MockRadarHandler.requests[0]["input"])
        self.assertEqual(prompt_payload["mode"], "manual")
        self.assertEqual(MockRadarHandler.requests[0]["model"], "gpt-5.4")

    def test_conversation_mode_can_append_daily_note(self):
        stdout = self.run_cli(
            "conversation",
            "--config",
            str(self.config_path),
            "--title",
            "Conversation on validation logic",
            "--conversation",
            "User: We keep worrying about PSF mismatch and no-ground-truth validation.\nAssistant: The wrong-PSF control may be the fastest falsification test.",
            "--write-daily-note",
        )

        outputs = json.loads(stdout)
        daily_path = Path(outputs["daily_note"])
        self.assertTrue(daily_path.exists())
        daily_text = daily_path.read_text(encoding="utf-8")
        self.assertIn("## Question Radar", daily_text)
        self.assertIn("Quantify tolerated PSF drift before gains stop transferring", daily_text)

        prompt_payload = json.loads(MockRadarHandler.requests[0]["input"])
        self.assertEqual(prompt_payload["mode"], "conversation")
        self.assertIn("conversation_text", prompt_payload["payload"])

    def test_daily_mode_uses_recent_context_and_latest_literature(self):
        stdout = self.run_cli(
            "daily",
            "--config",
            str(self.config_path),
            "--title",
            "Daily radar",
            "--latest-literature-file",
            str(self.latest_literature_path),
            "--skip-live-literature",
        )

        outputs = json.loads(stdout)
        run_dir = Path(outputs["run_dir"])
        self.assertTrue((run_dir / "question_radar.json").exists())
        self.assertTrue((run_dir / "question_radar.md").exists())
        self.assertTrue((run_dir / "context_snapshot.json").exists())
        self.assertTrue(Path(outputs["question_radar_note"]).exists())
        self.assertTrue(Path(outputs["daily_note"]).exists())

        context_snapshot = json.loads((run_dir / "context_snapshot.json").read_text(encoding="utf-8"))
        sections = context_snapshot["recent_context"]["sections"]
        self.assertTrue(any(section["section"] == "04_Progress" for section in sections))
        literature_groups = context_snapshot["latest_literature"]["groups"]
        self.assertEqual(literature_groups[0]["interest"], "Blind and spatially varying deconvolution")

        radar_markdown = (run_dir / "question_radar.md").read_text(encoding="utf-8")
        self.assertIn("## Latest Literature Signals", radar_markdown)
        self.assertIn("Calibration-aware spatially varying OCT deconvolution", radar_markdown)

        prompt_payload = json.loads(MockRadarHandler.requests[0]["input"])
        self.assertEqual(prompt_payload["mode"], "daily")
        self.assertIn("latest_literature", prompt_payload["payload"])

    def test_daily_mode_falls_back_locally_when_api_key_missing(self):
        config = json.loads(self.config_path.read_text(encoding="utf-8"))
        config["academic_qa"]["openai"]["api_key"] = ""
        config["question_radar"]["openai"]["api_key"] = ""
        self.config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        MockRadarHandler.requests = []

        stdout = self.run_cli(
            "daily",
            "--config",
            str(self.config_path),
            "--title",
            "Daily radar fallback",
            "--latest-literature-file",
            str(self.latest_literature_path),
            "--skip-live-literature",
        )

        outputs = json.loads(stdout)
        run_dir = Path(outputs["run_dir"])
        self.assertTrue((run_dir / "question_radar.json").exists())
        self.assertTrue((run_dir / "question_radar.md").exists())
        self.assertEqual(MockRadarHandler.requests, [])

        run_meta = json.loads((run_dir / "run_meta.json").read_text(encoding="utf-8"))
        self.assertEqual(run_meta["model"], "codex-local-fallback")

        response_meta = json.loads((run_dir / "question_radar_response.json").read_text(encoding="utf-8"))
        self.assertEqual(response_meta["generator"], "codex-local-fallback")
        self.assertIn("OpenAI API key is not configured", response_meta["script_failure"])

        radar = json.loads((run_dir / "question_radar.json").read_text(encoding="utf-8"))
        titles = [item["title"] for item in radar["candidate_questions"]]
        self.assertIn("Quantify tolerated PSF drift before gains stop transferring", titles)


if __name__ == "__main__":
    unittest.main()
