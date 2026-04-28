import json
import shutil
import subprocess
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "research_question_flow.py"


class MockOpenAIHandler(BaseHTTPRequestHandler):
    prepare_response = {}
    answer_response = {}
    critique_response = {}
    requests = []

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        payload = json.loads(body.decode("utf-8"))
        self.__class__.requests.append(payload)

        if len(self.__class__.requests) == 1:
            output_text = json.dumps(self.__class__.prepare_response, ensure_ascii=False)
        elif len(self.__class__.requests) == 2:
            output_text = json.dumps(self.__class__.answer_response, ensure_ascii=False)
        else:
            output_text = json.dumps(self.__class__.critique_response, ensure_ascii=False)

        response = {"output_text": output_text}
        encoded = json.dumps(response, ensure_ascii=False).encode("utf-8")

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, format, *args):
        return


class ResearchQuestionFlowTests(unittest.TestCase):
    def setUp(self):
        self.test_root = ROOT / "tmp" / "test-runs"
        self.test_root.mkdir(parents=True, exist_ok=True)
        self.workspace = self.test_root / "question-flow-workspace"
        shutil.rmtree(self.workspace, ignore_errors=True)
        self.workspace.mkdir(parents=True, exist_ok=True)

        self.vault_root = self.workspace / "vault"
        self.output_root = self.workspace / "reports"
        self.config_path = self.workspace / "config.json"
        self.evidence_path = self.workspace / "evidence.md"
        self.evidence_path.write_text(
            "# Evidence\n\nMeasured PSF mismatch appears to trade spatial sharpening for noise growth.\n",
            encoding="utf-8",
        )
        (self.vault_root / "02_Literature" / "Papers").mkdir(parents=True, exist_ok=True)
        (self.vault_root / "03_Concepts").mkdir(parents=True, exist_ok=True)
        (self.vault_root / "04_Progress").mkdir(parents=True, exist_ok=True)
        (self.vault_root / "02_Literature" / "Papers" / "[2024] Chen - Adaptive OCT Deconvolution.md").write_text(
            "---\n"
            'title: "Adaptive OCT Deconvolution"\n'
            "---\n\n"
            "> [!q2-focus]\n"
            "> Q2: What is the paper's core claim?\n"
            "> q2_status:: draft\n"
            "> The paper argues that locally adaptive PSF modeling plus artifact control is more trustworthy than a fixed kernel.\n\n"
            "> [!evidence]\n"
            "> The adaptive model improves lateral detail recovery while keeping artifact score below the fixed-kernel baseline.\n\n"
            "- question_id:: UQ-01\n"
            "  question_text:: Can this method really show information recovery instead of visual sharpening?\n"
            "  tentative_answer:: Partially yes, because it reports artifact score and control comparisons.\n",
            encoding="utf-8",
        )
        (self.vault_root / "03_Concepts" / "Concept - Point Spread Function.md").write_text(
            "# Point Spread Function\n\nA fixed PSF can fail when field dependence or session drift changes the effective blur.\n\nArtifact control matters because visual sharpening alone can be misleading.\n",
            encoding="utf-8",
        )
        (self.vault_root / "04_Progress" / "three-month-manuscript-track.md").write_text(
            "# Track\n\nThe working research question is whether physically grounded deconvolution can improve lateral resolution without unacceptable artifact growth.\n\nEvaluation without strict ground truth should rely on repeatability, phantom geometry, and negative controls.\n",
            encoding="utf-8",
        )

        MockOpenAIHandler.requests = []
        MockOpenAIHandler.prepare_response = {
            "title": "PSF mismatch under lateral deconvolution",
            "core_question": "How sensitive is OCT lateral deconvolution to PSF mismatch under noisy conditions?",
            "research_goal": "Determine whether apparent lateral-resolution gain remains trustworthy when the PSF is imperfect.",
            "answer_type": "mechanism-and-validation",
            "background_context": "The project studies OCT lateral-resolution enhancement without strict ground truth.",
            "known_facts": [
                "Deconvolution strength depends on the assumed PSF.",
                "Noise amplification can mimic detail recovery."
            ],
            "unknowns": [
                "How robust the gain is across realistic PSF mismatch levels.",
                "Which validation strategy is convincing without strict ground truth."
            ],
            "constraints": [
                "No strict ground truth is available.",
                "The answer should stay useful for OCT experiments."
            ],
            "assumptions_to_check": [
                "The measured PSF is stable enough across the field.",
                "Noise growth is not misread as resolution gain."
            ],
            "subquestions": [
                "What failure modes appear first when the PSF is wrong?",
                "Which task-based metrics are more trustworthy than a single sharpness score?"
            ],
            "evidence_items": [
                {
                    "source": "evidence.md",
                    "snippet": "Measured PSF mismatch appears to trade spatial sharpening for noise growth.",
                    "why_it_matters": "It directly points to the central reliability tradeoff."
                }
            ],
            "expected_output": {
                "audience": "graduate OCT researcher",
                "format": "structured analysis",
                "must_include": [
                    "evidence-vs-inference split",
                    "validation suggestions",
                    "uncertainties"
                ],
                "must_avoid": [
                    "fabricated citations",
                    "overconfident conclusions"
                ]
            }
        }
        MockOpenAIHandler.answer_response = {
            "summary": "PSF mismatch can easily turn apparent lateral sharpening into a fragile or misleading gain unless validation is designed around failure cases.",
            "direct_answer": "The gain is usually sensitive to PSF mismatch, so the practical question is not whether images look sharper but whether the recovered detail survives noise, repeat scans, and negative controls.",
            "reasoning_steps": [
                "Start from the fact that deconvolution inverts a blur model and therefore inherits PSF-model error.",
                "Treat noise amplification and artifact injection as competing explanations for apparent detail recovery.",
                "Use no-ground-truth validation strategies that rely on geometry, repeatability, and negative controls."
            ],
            "evidence_chain": [
                {
                    "claim": "PSF mismatch can produce unstable gains.",
                    "support": "The provided evidence already links mismatch to sharpening-noise tradeoffs.",
                    "confidence": "medium"
                }
            ],
            "assumptions": [
                "The evidence snippet reflects the user's actual OCT regime."
            ],
            "counterarguments": [
                "If the PSF is tightly measured and stable, sensitivity may be lower than feared."
            ],
            "uncertainties": [
                "The exact robustness threshold is still unknown without targeted experiments."
            ],
            "next_actions": [
                "Run a controlled PSF-perturbation sweep.",
                "Compare repeat-scan consistency before and after deconvolution.",
                "Add a deliberate wrong-PSF negative control."
            ],
            "follow_up_questions": [
                "How field-dependent is the measured PSF in the current setup?"
            ]
        }
        MockOpenAIHandler.critique_response = {
            "critique_summary": "The answer is directionally strong, but it still relies on a few untested assumptions about PSF stability and may under-specify the validation burden.",
            "overall_verdict": "Useful as a working judgment, but not yet strong enough to treat as a publication-grade conclusion.",
            "confidence_adjustment": "Reduce confidence from moderate to cautious-moderate until negative controls and repeatability checks are actually run.",
            "critical_issues": [
                {
                    "issue": "The answer assumes PSF instability is a major risk without quantifying the current system's actual PSF drift.",
                    "severity": "high",
                    "why_it_matters": "If PSF drift is small in practice, the current warning may be too conservative or mis-targeted.",
                    "suggested_fix": "Measure field and session dependence of the PSF before treating mismatch sensitivity as the dominant bottleneck."
                },
                {
                    "issue": "The answer recommends checks but does not prioritize which one would falsify the main claim fastest.",
                    "severity": "medium",
                    "why_it_matters": "Without prioritization, the workflow may stay broad instead of becoming experimentally decisive.",
                    "suggested_fix": "Make the wrong-PSF negative control the first pressure test because it directly probes artifact sensitivity."
                }
            ],
            "evidence_gaps": [
                "No direct evidence was provided about the current setup's PSF stationarity.",
                "No repeat-scan evidence was provided yet."
            ],
            "hidden_assumptions": [
                "The observed sharpening-noise tradeoff generalizes to the user's main experimental regime."
            ],
            "failure_modes": [
                "Noise amplification could still be mistaken for lateral detail recovery.",
                "A globally measured PSF may fail under field-dependent blur."
            ],
            "recommended_checks": [
                "Quantify PSF variation across field position and repeat sessions.",
                "Run the wrong-PSF negative control first.",
                "Compare any gain against a task-based metric rather than a single sharpness score."
            ],
            "salvageable_strengths": [
                "The answer correctly frames the problem as evidence reliability rather than visual sharpness alone.",
                "The proposed repeatability and negative-control checks are directionally appropriate."
            ]
        }

        self.server = HTTPServer(("127.0.0.1", 0), MockOpenAIHandler)
        self.server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.server_thread.start()

        config = {
            "profile_path": str(self.workspace / "profile.json").replace("\\", "/"),
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
                "people_folder": "13_People",
                "relationship_folder": "14_Relationships",
            },
            "academic_qa": {
                    "enable_critique": True,
                "enable_auto_evidence": True,
                "question_folder": "04_Research/Questions",
                "report_folder_name": "research-question-flow",
                "auto_evidence_paths": [
                    "02_Literature/Papers",
                    "03_Concepts",
                    "04_Progress"
                ],
                "auto_evidence_min_score": 1,
                "auto_evidence_max_notes": 4,
                "auto_evidence_max_chars_per_note": 400,
                "auto_evidence_max_candidates_log": 10,
                "openai": {
                    "api_key": "test-key",
                    "base_url": f"http://127.0.0.1:{self.server.server_port}/v1/responses",
                    "extract_model": "gpt-5-mini",
                    "extract_reasoning_effort": "minimal",
                    "extract_max_output_tokens": 4000,
                    "reason_model": "gpt-5.4",
                    "reason_reasoning_effort": "high",
                    "reason_max_output_tokens": 8000,
                    "critic_model": "gpt-5.4",
                    "critic_reasoning_effort": "high",
                    "critic_max_output_tokens": 6000,
                }
            }
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

    def test_run_creates_reports_and_vault_notes(self):
        stdout = self.run_cli(
            "run",
            "--config",
            str(self.config_path),
            "--title",
            "PSF mismatch under lateral deconvolution",
            "--question",
            "How sensitive is OCT lateral deconvolution to PSF mismatch and noise amplification when we do not have strict ground truth?",
            "--evidence-file",
            str(self.evidence_path),
            "--evidence-text",
            "Current constraint: the validation strategy must work without strict ground truth.",
        )

        outputs = json.loads(stdout)
        run_dir = Path(outputs["run_dir"])
        self.assertTrue((run_dir / "retrieval_candidates.json").exists())
        self.assertTrue((run_dir / "evidence_brief.json").exists())
        self.assertTrue((run_dir / "question_pack.json").exists())
        self.assertTrue((run_dir / "answer.json").exists())
        self.assertTrue((run_dir / "answer.md").exists())
        self.assertTrue((run_dir / "critique.json").exists())
        self.assertTrue((run_dir / "critique.md").exists())

        input_snapshot = json.loads((run_dir / "input_snapshot.json").read_text(encoding="utf-8"))
        evidence_brief = json.loads((run_dir / "evidence_brief.json").read_text(encoding="utf-8"))
        auto_sources = [item["source"] for item in input_snapshot["auto_evidence"]]
        self.assertIn("02_Literature/Papers/[2024] Chen - Adaptive OCT Deconvolution.md", auto_sources)
        self.assertIn("03_Concepts/Concept - Point Spread Function.md", auto_sources)
        self.assertIn("04_Progress/three-month-manuscript-track.md", auto_sources)
        self.assertIn("core_claim", evidence_brief["bucket_order"])
        self.assertIn("strongest_evidence", evidence_brief["bucket_order"])
        self.assertIn("manual_input", evidence_brief["bucket_order"])
        self.assertGreaterEqual(evidence_brief["bucket_counts"]["core_claim"], 1)
        chen_item = next(
            item for item in input_snapshot["auto_evidence"]
            if item["source"] == "02_Literature/Papers/[2024] Chen - Adaptive OCT Deconvolution.md"
        )
        self.assertIn("artifact score below the fixed-kernel baseline", chen_item["content"])
        self.assertEqual(chen_item["evidence_role"], "core_claim")
        self.assertIn("strongest_evidence", chen_item["evidence_role_labels"])
        self.assertIn("user_question_answer", chen_item["evidence_role_labels"])
        self.assertIn("callout:q2-focus", chen_item["retrieval_reason"])

        retrieval_debug = json.loads((run_dir / "retrieval_candidates.json").read_text(encoding="utf-8"))
        self.assertGreaterEqual(retrieval_debug["selected_count"], 3)
        top_candidate = next(
            item for item in retrieval_debug["candidates"]
            if item["path"] == "02_Literature/Papers/[2024] Chen - Adaptive OCT Deconvolution.md"
        )
        self.assertEqual(top_candidate["evidence_role"], "core_claim")
        self.assertIn("strongest_evidence", top_candidate["evidence_role_labels"])

        question_pack = json.loads((run_dir / "question_pack.json").read_text(encoding="utf-8"))
        self.assertEqual(question_pack["title"], "PSF mismatch under lateral deconvolution")
        self.assertIn("evidence_brief", question_pack)
        self.assertIn("core_claim", question_pack["evidence_brief"]["bucket_order"])

        answer_markdown = (run_dir / "answer.md").read_text(encoding="utf-8")
        self.assertIn("## Evidence Briefing", answer_markdown)
        self.assertIn("## Direct Answer", answer_markdown)
        self.assertIn("deliberate wrong-PSF negative control", answer_markdown)
        self.assertIn("## Critique Summary", answer_markdown)
        self.assertIn("PSF drift", answer_markdown)

        critique_markdown = (run_dir / "critique.md").read_text(encoding="utf-8")
        self.assertIn("## Critical Issues", critique_markdown)
        self.assertIn("wrong-PSF negative control", critique_markdown)

        conversation_path = Path(outputs["conversation_note"])
        question_note_path = Path(outputs["question_note"])
        self.assertTrue(conversation_path.exists())
        self.assertTrue(question_note_path.exists())

        daily_path = self.vault_root / "01_Daily" / f"{Path(conversation_path).stem[:10]}.md"
        self.assertTrue(daily_path.exists())
        daily_text = daily_path.read_text(encoding="utf-8")
        self.assertIn(conversation_path.stem, daily_text)

        question_note_text = question_note_path.read_text(encoding="utf-8")
        self.assertIn("# Question Definition", question_note_text)
        self.assertIn("PSF mismatch can easily turn apparent lateral sharpening", question_note_text)
        self.assertIn("# Reviewer Pressure Test", question_note_text)

        self.assertEqual(len(MockOpenAIHandler.requests), 3)
        self.assertEqual(MockOpenAIHandler.requests[0]["model"], "gpt-5-mini")
        self.assertEqual(MockOpenAIHandler.requests[1]["model"], "gpt-5.4")
        self.assertEqual(MockOpenAIHandler.requests[2]["model"], "gpt-5.4")

    def test_run_can_skip_auto_evidence(self):
        stdout = self.run_cli(
            "run",
            "--config",
            str(self.config_path),
            "--title",
            "PSF mismatch under lateral deconvolution",
            "--question",
            "How sensitive is OCT lateral deconvolution to PSF mismatch and noise amplification when we do not have strict ground truth?",
            "--skip-auto-evidence",
            "--skip-critique",
            "--skip-vault-write",
        )

        outputs = json.loads(stdout)
        run_dir = Path(outputs["run_dir"])
        input_snapshot = json.loads((run_dir / "input_snapshot.json").read_text(encoding="utf-8"))
        evidence_brief = json.loads((run_dir / "evidence_brief.json").read_text(encoding="utf-8"))
        self.assertEqual(input_snapshot["auto_evidence"], [])
        self.assertEqual(input_snapshot["manual_evidence"], [])
        self.assertEqual(evidence_brief["bucket_order"], [])

        retrieval_debug = json.loads((run_dir / "retrieval_candidates.json").read_text(encoding="utf-8"))
        self.assertFalse(retrieval_debug["enabled"])


if __name__ == "__main__":
    unittest.main()
