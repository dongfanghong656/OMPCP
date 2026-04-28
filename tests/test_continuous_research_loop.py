import json
import shutil
import subprocess
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "continuous_research_loop.py"


class MockLoopRadarHandler(BaseHTTPRequestHandler):
    responses_by_schema = {}
    requests = []

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        payload = json.loads(body.decode("utf-8"))
        self.__class__.requests.append(payload)
        schema_name = payload.get("text", {}).get("format", {}).get("name", "")
        response_payload = self.__class__.responses_by_schema.get(schema_name, {})

        response = {"output_text": json.dumps(response_payload, ensure_ascii=False)}
        encoded = json.dumps(response, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, format, *args):
        return


class ContinuousResearchLoopTests(unittest.TestCase):
    def setUp(self):
        self.test_root = ROOT / "tmp" / "test-runs"
        self.test_root.mkdir(parents=True, exist_ok=True)
        self.workspace = self.test_root / "continuous-loop-workspace"
        shutil.rmtree(self.workspace, ignore_errors=True)
        self.workspace.mkdir(parents=True, exist_ok=True)

        self.vault_root = self.workspace / "vault"
        self.output_root = self.workspace / "reports"
        self.config_path = self.workspace / "config.json"
        self.profile_path = self.workspace / "profile.json"
        self.latest_literature_path = self.workspace / "latest-literature.json"
        self.manual_artifact_path = self.workspace / "manual-artifact.md"
        self.draft_file = self.workspace / "draft.md"
        self.journal_notes_file = self.workspace / "journal-notes.md"
        self.review_comments_file = self.workspace / "review-comments.md"
        self.current_changes_file = self.workspace / "current-changes.md"
        self.references_file = self.workspace / "references.md"

        (self.vault_root / "01_Daily").mkdir(parents=True, exist_ok=True)
        (self.vault_root / "02_Literature" / "Papers").mkdir(parents=True, exist_ok=True)
        (self.vault_root / "04_Progress").mkdir(parents=True, exist_ok=True)
        (self.vault_root / "09_Conversations").mkdir(parents=True, exist_ok=True)
        (self.vault_root / "11_Retrieval").mkdir(parents=True, exist_ok=True)

        (self.vault_root / "02_Literature" / "Papers" / "[2026] Chen - Stability.md").write_text(
            "# Stability\n\nA recent note says transferability depends on how quickly PSF mismatch destroys repeatability.\n",
            encoding="utf-8",
        )
        (self.vault_root / "04_Progress" / "open-risk.md").write_text(
            "# Open Risk\n\nWe still do not know the tolerated PSF drift band for the current setup.\n",
            encoding="utf-8",
        )
        (self.vault_root / "09_Conversations" / "2026-03-23.md").write_text(
            "# Notes\n\nThe next decisive experiment should probably quantify PSF drift tolerance first.\n",
            encoding="utf-8",
        )
        self.manual_artifact_path.write_text(
            "# Manual Artifact\n\nA MATLAB baseline run completed and is ready for structured analysis.\n",
            encoding="utf-8",
        )
        self.draft_file.write_text(
            "# Draft\n\nWe claim the Tukey 0.6 window is universally superior across OCT conditions.\n",
            encoding="utf-8",
        )
        self.journal_notes_file.write_text(
            "# Journal Notes\n\nTarget venue favors careful translational framing, clear limitations, and strong methodological transparency.\n",
            encoding="utf-8",
        )
        self.review_comments_file.write_text(
            "# Reviewer Comments\n\n1. The manuscript seems to overstate general superiority.\n",
            encoding="utf-8",
        )
        self.current_changes_file.write_text(
            "# Current Changes\n\nWe rewrote the abstract and results opening to use bounded benchmark language.\n",
            encoding="utf-8",
        )
        self.references_file.write_text(
            "# References\n\n- Validation-aware OCT deconvolution study\n- Repeatability analysis in OCT imaging\n",
            encoding="utf-8",
        )
        self.experiment_dir = self.workspace / "experiment"
        self.experiment_dir.mkdir(parents=True, exist_ok=True)
        (self.experiment_dir / "ranking_summary.json").write_text(
            json.dumps(
                {
                    "top_windows": [
                        {
                            "Name": "tukey_0p6",
                            "UnifiedScore": 0.98,
                            "ScoreTheory": 0.96,
                            "ScorePaperLike": 0.99,
                            "ScoreScenes": 1.0,
                        }
                    ]
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        (self.experiment_dir / "unified_ranking.csv").write_text(
            "Name,ScoreTheory,ScorePaperLike,ScoreScenes,UnifiedScore\n"
            "tukey_0p6,0.96,0.99,1.0,0.98\n"
            "hann,0.95,0.97,0.78,0.89\n",
            encoding="utf-8",
        )
        (self.experiment_dir / "theory_summary.csv").write_text(
            "MeanSharpness,MeanMainlobeWidth3dB,Name\n"
            "3.0,1.22,tukey_0p6\n"
            "3.6,1.31,hamming\n",
            encoding="utf-8",
        )
        (self.experiment_dir / "synthetic_scene_rmse.csv").write_text(
            "Name,scenario,scene_rmse\n"
            "tukey_0p6,low_snr_rolloff,0.0012\n"
            "hann,low_snr_rolloff,0.0015\n",
            encoding="utf-8",
        )

        self.profile_path.write_text(
            json.dumps(
                {
                    "updated_for": "OCT deconvolution reliability",
                    "primary_objective": "Keep literature, questions, and experiment evidence aligned over time.",
                    "evaluation_focus": ["repeatability", "artifact suppression"],
                    "writing_goal": "A cautious evidence-grounded manuscript.",
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
                    "Reliability": [
                        {
                            "title": "Calibration-aware OCT deconvolution stability",
                            "year": "2026",
                            "publication_date": "2026-03-20",
                            "url": "https://example.com/stability",
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

        MockLoopRadarHandler.requests = []
        MockLoopRadarHandler.responses_by_schema = {
            "question_radar_report": {
                "focus_summary": "The sustained program should prioritize PSF drift tolerance because it governs whether downstream claims remain stable.",
                "candidate_questions": [
                    {
                        "title": "Measure tolerated PSF drift",
                        "question": "What PSF drift range can the current pipeline tolerate before gains stop transferring across scans?",
                        "value_score": 9,
                        "time_horizon": "immediate",
                        "why_now": "This controls whether current claims are manuscript-safe.",
                        "novelty_or_gap": "The vault has the risk statement but not the measured tolerance band.",
                        "required_evidence": ["Repeat-session PSF measurements"],
                        "first_action": "Run a drift sweep on the phantom setup.",
                        "source_signals": ["open-risk.md", "Calibration-aware OCT deconvolution stability"],
                    }
                ],
                "selection_advice": [
                    "Keep the tolerance question at the top of the loop until it is backed by real experiment evidence."
                ],
            },
            "writing_memory_report": {
                "focus_summary": "Ground writing around ranked-candidate selection, not general superiority claims.",
                "reusable_claims": [
                    {
                        "claim": "tukey_0p6 is the strongest current candidate within this benchmark bundle.",
                        "evidence_basis": "It leads the unified ranking and remains strong on scene and paper-like metrics.",
                        "caution": "This does not establish universal superiority across OCT conditions.",
                        "fit_sections": ["Results", "Discussion"],
                    }
                ],
                "reusable_caveats": [
                    "Ranking-bundle leadership should be treated as a follow-up selection signal, not a manuscript-wide claim."
                ],
                "figure_narratives": [
                    {
                        "artifact": "results_report.md",
                        "caption_angle": "Show the current leader while emphasizing the validation boundary.",
                        "why_it_matters": "This keeps the figure from overstating transferability.",
                    }
                ],
                "reviewer_watchouts": ["Reviewers will ask whether the ranking transfers to real OCT evidence."],
                "terminology_preferences": [
                    {
                        "term": "current best candidate",
                        "preferred_usage": "Use for ranking-bundle conclusions.",
                        "avoid_phrase": "universally superior",
                    }
                ],
                "next_writing_targets": ["Rewrite the headline claim in manuscript-safe language."],
            },
            "self_review_report": {
                "review_summary": "The draft currently overstates what the benchmark bundle can support.",
                "overall_readiness": "Needs targeted revision before the claim is manuscript-safe.",
                "claim_alignment_issues": [
                    {
                        "claim_or_section": "Opening claim",
                        "issue": "Universal superiority is not supported by the available benchmark bundle.",
                        "severity": "high",
                        "evidence_gap": "No transfer validation across broader OCT conditions is shown.",
                        "revision_direction": "Rewrite the claim as a current best-candidate statement tied to this bundle.",
                    }
                ],
                "overclaim_risks": ["The wording implies cross-condition generality that the evidence does not provide."],
                "missing_controls_or_evidence": ["A broader transfer or drift validation layer is still missing."],
                "wording_risks": ["Replace 'universally superior' with a narrower evidence-bounded formulation."],
                "salvageable_strengths": ["The draft correctly focuses on the current top-ranked candidate."],
                "revision_actions": ["Tighten the opening claim and cite the ranking bundle explicitly."],
            },
            "draft_builder_report": {
                "positioning_summary": "Build the paper around bounded candidate selection, not universal superiority.",
                "claim_rewrites": [
                    {
                        "unsafe_claim": "tukey_0p6 is universally superior across OCT conditions.",
                        "safe_rewrite": "tukey_0p6 is the strongest current candidate within this benchmark bundle.",
                        "why_safer": "The rewrite matches the available evidence boundary.",
                    }
                ],
                "section_blocks": [
                    {
                        "section": "Results",
                        "goal": "State the current ranking outcome without overclaiming transferability.",
                        "paragraph_text": "Within the current benchmark bundle, tukey_0p6 emerged as the strongest candidate by unified ranking. We therefore use it as the primary follow-up candidate, while treating broader transfer claims as unresolved until additional validation is completed.",
                        "evidence_anchor": "analysis.json + results_report.json",
                        "carryover_caution": "Do not turn this into a cross-condition superiority claim.",
                    }
                ],
                "figure_callouts": [
                    {
                        "figure_or_artifact": "results_report.md",
                        "narrative_role": "Support the bounded ranking result.",
                        "safe_caption_hook": "Current benchmark-bundle leader used for follow-up validation.",
                    }
                ],
                "next_section_targets": ["Draft the discussion paragraph around validation boundary and follow-up need."],
            },
            "rebuttal_scaffold_report": {
                "review_risk_summary": "The most likely reviewer pressure point is overclaiming beyond the benchmark bundle.",
                "likely_reviewer_concerns": [
                    {
                        "concern": "The manuscript appears to overstate general superiority.",
                        "why_it_is_likely": "Both the self-review and writing memory flag this wording risk directly.",
                        "evidence_backed_response": "We have revised the wording to frame tukey_0p6 as the strongest current candidate within the present benchmark bundle.",
                        "concession_if_needed": "We agree that broader transferability remains to be established.",
                        "follow_up_action": "State the validation boundary earlier in Results and Discussion.",
                    }
                ],
                "manuscript_changes_to_preempt": [
                    "Replace universal language with benchmark-bundle language in the opening claim."
                ],
                "response_letter_phrases": [
                    "We thank the reviewer for highlighting the need to tighten claim-evidence alignment."
                ],
                "high_priority_evidence_requests": ["Real-OCT transfer validation beyond the current benchmark bundle."],
                "next_rebuttal_targets": ["Draft one reusable response paragraph for transferability concerns."],
            },
            "journal_targeting_report": {
                "journal_fit_summary": "The paper can fit a methods-forward translational venue if the framing stays conservative.",
                "journal_basis_note": "Advice is grounded in the provided journal notes rather than invented house rules.",
                "adaptation_rules": [
                    {
                        "section_or_element": "Abstract and Results lead",
                        "keep": "Bounded benchmark-bundle conclusion.",
                        "adapt_for_journal": "Move limitation language earlier and foreground reproducibility logic.",
                        "risk_if_unchanged": "The journal may read the claim as overextended for its translational audience.",
                    }
                ],
                "citation_actions": [
                    {
                        "claim_area": "Transferability framing",
                        "citation_need": "Add prior OCT deconvolution stability references.",
                        "evidence_type_needed": "Methods and validation literature",
                        "priority": "high",
                    }
                ],
                "presentation_priorities": ["Lead with reproducibility and validation boundary before broader impact."],
                "submission_checklist": ["Audit the abstract and discussion for any residual universal wording."],
                "next_journal_targets": ["Prepare a venue-specific cover letter angle around careful validation."],
            },
            "response_letter_report": {
                "round_label": "round-1",
                "response_strategy_summary": "Acknowledge the overclaim risk directly and point to the rewritten bounded language.",
                "tracked_points": [
                    {
                        "reviewer_point": "The manuscript seems to overstate general superiority.",
                        "response_text": "We revised the manuscript to describe tukey_0p6 as the strongest current candidate within the present benchmark bundle.",
                        "manuscript_change": "Abstract and Results opening rewritten with bounded language.",
                        "evidence_anchor": "journal_targeting.json + rebuttal_scaffold.json",
                        "status": "drafted",
                    }
                ],
                "tone_guardrails": ["Thank the reviewer and concede the previous wording was too broad."],
                "open_items": ["Keep future rounds aligned with the same bounded claim language."],
                "next_round_preparation": ["Track whether reviewers still request broader transfer evidence."],
            },
            "citation_audit_report": {
                "citation_risk_summary": "The main remaining citation risk is unsupported transferability language around the benchmark result.",
                "reference_basis_note": "The audit is grounded in the supplied draft and lightweight reference notes.",
                "claim_audits": [
                    {
                        "claim_or_sentence": "Any sentence implying broader transfer beyond the benchmark bundle",
                        "risk": "The statement would need stronger validation and literature anchoring.",
                        "citation_action": "Either narrow the claim or add validation/stability references.",
                        "evidence_or_reference_needed": "Prior OCT deconvolution stability and transfer studies",
                        "severity": "high",
                    }
                ],
                "reference_completeness_checks": ["Check that validation-boundary statements cite both method and repeatability literature."],
                "safe_keep_areas": ["The bounded best-candidate statement is already close to manuscript-safe language."],
                "priority_repairs": ["Audit abstract and discussion for any unsupported generality wording."],
                "final_citation_targets": ["Add one stability-focused OCT citation near the main claim boundary."],
            },
            "submission_qc_report": {
                "readiness_summary": "The package is close, but one last citation-aware wording audit is still required before submission.",
                "go_no_go": "Conditional go after final citation and wording repairs.",
                "critical_blocks": [
                    {
                        "blocker": "Residual unsupported generality wording could still survive in the final draft.",
                        "why_it_blocks": "It would reintroduce the main claim-evidence mismatch at submission time.",
                        "repair_direction": "Run one final sweep on abstract, results lead, and discussion boundary language.",
                        "severity": "high",
                    }
                ],
                "final_polish_actions": ["Tighten citation-backed boundary language in abstract and discussion."],
                "pre_submission_checklist": ["Confirm all broad claims have either been narrowed or explicitly supported."],
                "safe_to_submit_signals": ["The main response-letter logic and bounded claim framing are now aligned."],
                "next_actions": ["Do one last citation-and-wording sweep, then re-export the submission draft."],
            },
            "draft_health_report": {
                "health_summary": "The draft is stable overall, but one recurring citation-backed wording debt remains.",
                "overall_status": "yellow",
                "citation_debt_items": [
                    {
                        "item": "Residual broad language could still re-enter the discussion.",
                        "why_it_matters": "It would recreate the same overclaim risk just before submission.",
                        "source_stage": "citation_audit",
                        "repair_hint": "Recheck discussion tone after each final edit.",
                        "severity": "high",
                    }
                ],
                "stability_watchpoints": ["Watch the discussion and conclusion for reintroduced generality wording."],
                "recent_strengths": ["The abstract and results framing are already more stable than before."],
                "next_health_checks": ["Re-run after the next major wording edit or before export."],
            },
            "submission_memory_report": {
                "memory_summary": "This venue and revision pattern repeatedly reward early limitation language and bounded claims.",
                "venue_name": "Biomedical Optics Express",
                "round_label": "round-1",
                "durable_lessons": ["Lead with reproducibility and bounded validation before broader impact."],
                "venue_specific_rules": ["Keep translational framing cautious and method transparency visible."],
                "recurring_debts": ["Broad wording tends to return in discussion revisions."],
                "next_round_memory": ["Recheck discussion tone after every major rewrite."],
            },
        }

        self.server = HTTPServer(("127.0.0.1", 0), MockLoopRadarHandler)
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
            "continuous_research": {
                "report_folder_name": "continuous-research",
                "note_folder": "04_Progress",
                "write_progress_note": True,
                "openai": {
                    "api_key": "test-key",
                    "base_url": f"http://127.0.0.1:{self.server.server_port}/v1/responses",
                    "writing_memory_model": "gpt-5.4-writing",
                    "writing_memory_reasoning_effort": "high",
                    "writing_memory_max_output_tokens": 5000,
                    "self_review_model": "gpt-5.4-self-review",
                    "self_review_reasoning_effort": "high",
                    "self_review_max_output_tokens": 6000,
                    "draft_builder_model": "gpt-5.4-draft-builder",
                    "draft_builder_reasoning_effort": "high",
                    "draft_builder_max_output_tokens": 7000,
                    "rebuttal_scaffold_model": "gpt-5.4-rebuttal",
                    "rebuttal_scaffold_reasoning_effort": "high",
                    "rebuttal_scaffold_max_output_tokens": 7000,
                    "journal_targeting_model": "gpt-5.4-journal",
                    "journal_targeting_reasoning_effort": "high",
                    "journal_targeting_max_output_tokens": 7000,
                    "response_letter_model": "gpt-5.4-response-letter",
                    "response_letter_reasoning_effort": "high",
                    "response_letter_max_output_tokens": 7000,
                    "citation_audit_model": "gpt-5.4-citation",
                    "citation_audit_reasoning_effort": "high",
                    "citation_audit_max_output_tokens": 7000,
                    "submission_qc_model": "gpt-5.4-submission-qc",
                    "submission_qc_reasoning_effort": "high",
                    "submission_qc_max_output_tokens": 7000,
                    "draft_health_model": "gpt-5.4-draft-health",
                    "draft_health_reasoning_effort": "high",
                    "draft_health_max_output_tokens": 7000,
                    "submission_memory_model": "gpt-5.4-submission-memory",
                    "submission_memory_reasoning_effort": "high",
                    "submission_memory_max_output_tokens": 7000,
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

    def test_init_and_status_create_manifest_and_progress_note(self):
        stdout = self.run_cli(
            "init",
            "--config",
            str(self.config_path),
            "--title",
            "OCT reliability loop",
            "--objective",
            "Keep literature, questions, and experiment evidence aligned over time.",
        )
        outputs = json.loads(stdout)
        manifest_path = Path(outputs["manifest"])
        progress_note = Path(outputs["progress_note"])
        self.assertTrue(manifest_path.exists())
        self.assertTrue(progress_note.exists())

        status_stdout = self.run_cli("status", "--manifest", str(manifest_path))
        status_payload = json.loads(status_stdout)
        self.assertEqual(status_payload["title"], "OCT reliability loop")
        self.assertEqual(status_payload["stages"]["question_radar"]["status"], "pending")
        progress_text = progress_note.read_text(encoding="utf-8")
        self.assertIn("## Loop Snapshot", progress_text)
        self.assertIn("Completed stages: 0", progress_text)

    def test_run_daily_and_link_artifact_update_manifest(self):
        init_stdout = self.run_cli(
            "init",
            "--config",
            str(self.config_path),
            "--title",
            "OCT reliability loop",
        )
        manifest_path = Path(json.loads(init_stdout)["manifest"])

        daily_stdout = self.run_cli(
            "run-daily",
            "--manifest",
            str(manifest_path),
            "--skip-retrieval",
            "--latest-literature-file",
            str(self.latest_literature_path),
        )
        daily_outputs = json.loads(daily_stdout)
        self.assertTrue(Path(daily_outputs["progress_note"]).exists())
        self.assertIn("question_radar_note", daily_outputs["cycle_outputs"])

        link_stdout = self.run_cli(
            "link-artifact",
            "--manifest",
            str(manifest_path),
            "--stage",
            "experiment_analysis",
            "--path",
            str(self.manual_artifact_path),
            "--summary",
            "Baseline MATLAB artifact is ready for structured analysis.",
        )
        link_outputs = json.loads(link_stdout)
        self.assertTrue(Path(link_outputs["progress_note"]).exists())

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["stages"]["question_radar"]["status"], "completed")
        self.assertEqual(manifest["stages"]["literature_refresh"]["status"], "pending")
        self.assertEqual(manifest["stages"]["experiment_analysis"]["status"], "completed")
        self.assertIn("Baseline MATLAB artifact", manifest["stages"]["experiment_analysis"]["summary"])
        self.assertGreaterEqual(len(manifest["recent_runs"]), 2)

        progress_text = Path(link_outputs["progress_note"]).read_text(encoding="utf-8")
        self.assertIn("### experiment_analysis", progress_text)
        self.assertIn("manual-artifact.md", progress_text)

    def test_run_results_analysis_updates_analysis_and_report_stages(self):
        init_stdout = self.run_cli(
            "init",
            "--config",
            str(self.config_path),
            "--title",
            "OCT reliability loop",
        )
        manifest_path = Path(json.loads(init_stdout)["manifest"])

        analysis_stdout = self.run_cli(
            "run-results-analysis",
            "--manifest",
            str(manifest_path),
            "--experiment-dir",
            str(self.experiment_dir),
            "--title",
            "ECM baseline",
            "--write-progress-note",
        )
        outputs = json.loads(analysis_stdout)
        analysis_outputs = outputs["analysis_outputs"]
        self.assertTrue(Path(analysis_outputs["analysis_json"]).exists())
        self.assertTrue(Path(analysis_outputs["results_report_markdown"]).exists())

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["stages"]["experiment_analysis"]["status"], "completed")
        self.assertEqual(manifest["stages"]["results_report"]["status"], "completed")
        self.assertIn("Structured post-experiment analysis", manifest["stages"]["experiment_analysis"]["summary"])
        self.assertIn("Decision-oriented results report", manifest["stages"]["results_report"]["summary"])
        result_labels = {item["label"] for item in manifest["stages"]["results_report"]["artifacts"]}
        self.assertIn("results_report_json", result_labels)
        self.assertIn("results_report_markdown", result_labels)

    def test_run_writing_memory_and_self_review_update_manifest(self):
        init_stdout = self.run_cli(
            "init",
            "--config",
            str(self.config_path),
            "--title",
            "OCT reliability loop",
        )
        manifest_path = Path(json.loads(init_stdout)["manifest"])

        self.run_cli(
            "run-results-analysis",
            "--manifest",
            str(manifest_path),
            "--experiment-dir",
            str(self.experiment_dir),
            "--title",
            "ECM baseline",
        )

        writing_stdout = self.run_cli(
            "run-writing-memory",
            "--manifest",
            str(manifest_path),
            "--title",
            "ECM baseline writing memory",
            "--write-vault-note",
        )
        writing_outputs = json.loads(writing_stdout)
        self.assertTrue(Path(writing_outputs["writing_memory_outputs"]["writing_memory_json"]).exists())
        self.assertTrue(Path(writing_outputs["writing_memory_outputs"]["writing_memory_markdown"]).exists())
        self.assertTrue(Path(writing_outputs["writing_memory_outputs"]["vault_note"]).exists())
        self.assertTrue(Path(writing_outputs["progress_note"]).exists())

        review_stdout = self.run_cli(
            "run-self-review",
            "--manifest",
            str(manifest_path),
            "--draft-file",
            str(self.draft_file),
            "--title",
            "Draft review",
            "--write-vault-note",
        )
        review_outputs = json.loads(review_stdout)
        self.assertTrue(Path(review_outputs["self_review_outputs"]["self_review_json"]).exists())
        self.assertTrue(Path(review_outputs["self_review_outputs"]["self_review_markdown"]).exists())
        self.assertTrue(Path(review_outputs["self_review_outputs"]["vault_note"]).exists())
        self.assertTrue(Path(review_outputs["progress_note"]).exists())

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["stages"]["writing_memory"]["status"], "completed")
        self.assertEqual(manifest["stages"]["self_review"]["status"], "completed")

        schema_names = [payload.get("text", {}).get("format", {}).get("name") for payload in MockLoopRadarHandler.requests]
        self.assertIn("writing_memory_report", schema_names)
        self.assertIn("self_review_report", schema_names)

        writing_request = next(
            payload for payload in MockLoopRadarHandler.requests if payload.get("text", {}).get("format", {}).get("name") == "writing_memory_report"
        )
        self.assertEqual(writing_request["model"], "gpt-5.4-writing")
        self.assertEqual(writing_request["reasoning"]["effort"], "high")

        review_request = next(
            payload for payload in MockLoopRadarHandler.requests if payload.get("text", {}).get("format", {}).get("name") == "self_review_report"
        )
        self.assertEqual(review_request["model"], "gpt-5.4-self-review")
        self.assertEqual(review_request["reasoning"]["effort"], "high")

    def test_run_draft_builder_and_rebuttal_scaffold_update_manifest(self):
        init_stdout = self.run_cli(
            "init",
            "--config",
            str(self.config_path),
            "--title",
            "OCT reliability loop",
        )
        manifest_path = Path(json.loads(init_stdout)["manifest"])

        self.run_cli(
            "run-results-analysis",
            "--manifest",
            str(manifest_path),
            "--experiment-dir",
            str(self.experiment_dir),
            "--title",
            "ECM baseline",
        )
        self.run_cli(
            "run-writing-memory",
            "--manifest",
            str(manifest_path),
            "--title",
            "ECM baseline writing memory",
        )
        self.run_cli(
            "run-self-review",
            "--manifest",
            str(manifest_path),
            "--draft-file",
            str(self.draft_file),
            "--title",
            "Draft review",
        )

        draft_stdout = self.run_cli(
            "run-draft-builder",
            "--manifest",
            str(manifest_path),
            "--title",
            "Manuscript blocks",
            "--write-vault-note",
        )
        draft_outputs = json.loads(draft_stdout)
        self.assertTrue(Path(draft_outputs["draft_builder_outputs"]["draft_builder_json"]).exists())
        self.assertTrue(Path(draft_outputs["draft_builder_outputs"]["draft_builder_markdown"]).exists())
        self.assertTrue(Path(draft_outputs["draft_builder_outputs"]["vault_note"]).exists())

        rebuttal_stdout = self.run_cli(
            "run-rebuttal-scaffold",
            "--manifest",
            str(manifest_path),
            "--draft-file",
            str(self.draft_file),
            "--title",
            "Reviewer response prep",
            "--write-vault-note",
        )
        rebuttal_outputs = json.loads(rebuttal_stdout)
        self.assertTrue(Path(rebuttal_outputs["rebuttal_scaffold_outputs"]["rebuttal_scaffold_json"]).exists())
        self.assertTrue(Path(rebuttal_outputs["rebuttal_scaffold_outputs"]["rebuttal_scaffold_markdown"]).exists())
        self.assertTrue(Path(rebuttal_outputs["rebuttal_scaffold_outputs"]["vault_note"]).exists())

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["stages"]["draft_builder"]["status"], "completed")
        self.assertEqual(manifest["stages"]["rebuttal_scaffold"]["status"], "completed")

        draft_request = next(
            payload
            for payload in MockLoopRadarHandler.requests
            if payload.get("text", {}).get("format", {}).get("name") == "draft_builder_report"
        )
        self.assertEqual(draft_request["model"], "gpt-5.4-draft-builder")

        rebuttal_request = next(
            payload
            for payload in MockLoopRadarHandler.requests
            if payload.get("text", {}).get("format", {}).get("name") == "rebuttal_scaffold_report"
        )
        self.assertEqual(rebuttal_request["model"], "gpt-5.4-rebuttal")

    def test_run_journal_targeting_and_response_letter_update_manifest(self):
        init_stdout = self.run_cli(
            "init",
            "--config",
            str(self.config_path),
            "--title",
            "OCT reliability loop",
        )
        manifest_path = Path(json.loads(init_stdout)["manifest"])

        self.run_cli(
            "run-results-analysis",
            "--manifest",
            str(manifest_path),
            "--experiment-dir",
            str(self.experiment_dir),
            "--title",
            "ECM baseline",
        )
        self.run_cli("run-writing-memory", "--manifest", str(manifest_path), "--title", "ECM baseline writing memory")
        self.run_cli(
            "run-self-review",
            "--manifest",
            str(manifest_path),
            "--draft-file",
            str(self.draft_file),
            "--title",
            "Draft review",
        )
        self.run_cli("run-draft-builder", "--manifest", str(manifest_path), "--title", "Manuscript blocks")
        self.run_cli("run-rebuttal-scaffold", "--manifest", str(manifest_path), "--draft-file", str(self.draft_file))

        journal_stdout = self.run_cli(
            "run-journal-targeting",
            "--manifest",
            str(manifest_path),
            "--journal-name",
            "Biomedical Optics Express",
            "--journal-notes-file",
            str(self.journal_notes_file),
            "--draft-file",
            str(self.draft_file),
            "--title",
            "Target journal prep",
            "--write-vault-note",
        )
        journal_outputs = json.loads(journal_stdout)
        self.assertTrue(Path(journal_outputs["journal_targeting_outputs"]["journal_targeting_json"]).exists())
        self.assertTrue(Path(journal_outputs["journal_targeting_outputs"]["journal_targeting_markdown"]).exists())
        self.assertTrue(Path(journal_outputs["journal_targeting_outputs"]["vault_note"]).exists())

        response_stdout = self.run_cli(
            "run-response-letter",
            "--manifest",
            str(manifest_path),
            "--round-label",
            "round-1",
            "--review-comments-file",
            str(self.review_comments_file),
            "--current-changes-file",
            str(self.current_changes_file),
            "--draft-file",
            str(self.draft_file),
            "--title",
            "Reviewer response prep",
            "--write-vault-note",
        )
        response_outputs = json.loads(response_stdout)
        self.assertTrue(Path(response_outputs["response_letter_outputs"]["response_letter_json"]).exists())
        self.assertTrue(Path(response_outputs["response_letter_outputs"]["response_letter_markdown"]).exists())
        self.assertTrue(Path(response_outputs["response_letter_outputs"]["tracker_index_json"]).exists())
        self.assertTrue(Path(response_outputs["response_letter_outputs"]["vault_note"]).exists())

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["stages"]["journal_targeting"]["status"], "completed")
        self.assertEqual(manifest["stages"]["response_letter"]["status"], "completed")

        journal_request = next(
            payload
            for payload in MockLoopRadarHandler.requests
            if payload.get("text", {}).get("format", {}).get("name") == "journal_targeting_report"
        )
        self.assertEqual(journal_request["model"], "gpt-5.4-journal")

        response_request = next(
            payload
            for payload in MockLoopRadarHandler.requests
            if payload.get("text", {}).get("format", {}).get("name") == "response_letter_report"
        )
        self.assertEqual(response_request["model"], "gpt-5.4-response-letter")

    def test_run_citation_audit_and_submission_qc_update_manifest(self):
        init_stdout = self.run_cli(
            "init",
            "--config",
            str(self.config_path),
            "--title",
            "OCT reliability loop",
        )
        manifest_path = Path(json.loads(init_stdout)["manifest"])

        self.run_cli("run-results-analysis", "--manifest", str(manifest_path), "--experiment-dir", str(self.experiment_dir), "--title", "ECM baseline")
        self.run_cli("run-writing-memory", "--manifest", str(manifest_path), "--title", "ECM baseline writing memory")
        self.run_cli("run-self-review", "--manifest", str(manifest_path), "--draft-file", str(self.draft_file), "--title", "Draft review")
        self.run_cli("run-draft-builder", "--manifest", str(manifest_path), "--title", "Manuscript blocks")
        self.run_cli("run-rebuttal-scaffold", "--manifest", str(manifest_path), "--draft-file", str(self.draft_file))
        self.run_cli(
            "run-journal-targeting",
            "--manifest",
            str(manifest_path),
            "--journal-name",
            "Biomedical Optics Express",
            "--journal-notes-file",
            str(self.journal_notes_file),
            "--draft-file",
            str(self.draft_file),
        )
        self.run_cli(
            "run-response-letter",
            "--manifest",
            str(manifest_path),
            "--round-label",
            "round-1",
            "--review-comments-file",
            str(self.review_comments_file),
            "--current-changes-file",
            str(self.current_changes_file),
            "--draft-file",
            str(self.draft_file),
        )

        citation_stdout = self.run_cli(
            "run-citation-audit",
            "--manifest",
            str(manifest_path),
            "--draft-file",
            str(self.draft_file),
            "--references-file",
            str(self.references_file),
            "--title",
            "Citation sweep",
            "--write-vault-note",
        )
        citation_outputs = json.loads(citation_stdout)
        self.assertTrue(Path(citation_outputs["citation_audit_outputs"]["citation_audit_json"]).exists())
        self.assertTrue(Path(citation_outputs["citation_audit_outputs"]["citation_audit_markdown"]).exists())
        self.assertTrue(Path(citation_outputs["citation_audit_outputs"]["vault_note"]).exists())

        qc_stdout = self.run_cli(
            "run-submission-qc",
            "--manifest",
            str(manifest_path),
            "--draft-file",
            str(self.draft_file),
            "--title",
            "Final submission gate",
            "--write-vault-note",
        )
        qc_outputs = json.loads(qc_stdout)
        self.assertTrue(Path(qc_outputs["submission_qc_outputs"]["submission_qc_json"]).exists())
        self.assertTrue(Path(qc_outputs["submission_qc_outputs"]["submission_qc_markdown"]).exists())
        self.assertTrue(Path(qc_outputs["submission_qc_outputs"]["vault_note"]).exists())

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["stages"]["citation_audit"]["status"], "completed")
        self.assertEqual(manifest["stages"]["submission_qc"]["status"], "completed")

        citation_request = next(
            payload
            for payload in MockLoopRadarHandler.requests
            if payload.get("text", {}).get("format", {}).get("name") == "citation_audit_report"
        )
        self.assertEqual(citation_request["model"], "gpt-5.4-citation")

        qc_request = next(
            payload
            for payload in MockLoopRadarHandler.requests
            if payload.get("text", {}).get("format", {}).get("name") == "submission_qc_report"
        )
        self.assertEqual(qc_request["model"], "gpt-5.4-submission-qc")

    def test_run_draft_health_and_submission_memory_update_manifest(self):
        init_stdout = self.run_cli(
            "init",
            "--config",
            str(self.config_path),
            "--title",
            "OCT reliability loop",
        )
        manifest_path = Path(json.loads(init_stdout)["manifest"])

        self.run_cli("run-results-analysis", "--manifest", str(manifest_path), "--experiment-dir", str(self.experiment_dir), "--title", "ECM baseline")
        self.run_cli("run-writing-memory", "--manifest", str(manifest_path), "--title", "ECM baseline writing memory")
        self.run_cli("run-self-review", "--manifest", str(manifest_path), "--draft-file", str(self.draft_file), "--title", "Draft review")
        self.run_cli("run-draft-builder", "--manifest", str(manifest_path), "--title", "Manuscript blocks")
        self.run_cli("run-rebuttal-scaffold", "--manifest", str(manifest_path), "--draft-file", str(self.draft_file))
        self.run_cli(
            "run-journal-targeting",
            "--manifest",
            str(manifest_path),
            "--journal-name",
            "Biomedical Optics Express",
            "--journal-notes-file",
            str(self.journal_notes_file),
            "--draft-file",
            str(self.draft_file),
        )
        self.run_cli(
            "run-response-letter",
            "--manifest",
            str(manifest_path),
            "--round-label",
            "round-1",
            "--review-comments-file",
            str(self.review_comments_file),
            "--current-changes-file",
            str(self.current_changes_file),
            "--draft-file",
            str(self.draft_file),
        )
        self.run_cli(
            "run-citation-audit",
            "--manifest",
            str(manifest_path),
            "--draft-file",
            str(self.draft_file),
            "--references-file",
            str(self.references_file),
        )
        self.run_cli(
            "run-submission-qc",
            "--manifest",
            str(manifest_path),
            "--draft-file",
            str(self.draft_file),
        )

        health_stdout = self.run_cli(
            "run-draft-health",
            "--manifest",
            str(manifest_path),
            "--draft-file",
            str(self.draft_file),
            "--title",
            "Draft health snapshot",
            "--write-vault-note",
        )
        health_outputs = json.loads(health_stdout)
        self.assertTrue(Path(health_outputs["draft_health_outputs"]["draft_health_json"]).exists())
        self.assertTrue(Path(health_outputs["draft_health_outputs"]["draft_health_markdown"]).exists())
        self.assertTrue(Path(health_outputs["draft_health_outputs"]["vault_note"]).exists())

        memory_stdout = self.run_cli(
            "run-submission-memory",
            "--manifest",
            str(manifest_path),
            "--venue-name",
            "Biomedical Optics Express",
            "--round-label",
            "round-1",
            "--draft-file",
            str(self.draft_file),
            "--title",
            "Submission memory snapshot",
        )
        memory_outputs = json.loads(memory_stdout)
        self.assertTrue(Path(memory_outputs["submission_memory_outputs"]["submission_memory_json"]).exists())
        self.assertTrue(Path(memory_outputs["submission_memory_outputs"]["submission_memory_note"]).exists())
        self.assertTrue(Path(memory_outputs["submission_memory_outputs"]["submission_memory_registry"]).exists())

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["stages"]["draft_health"]["status"], "completed")
        self.assertEqual(manifest["stages"]["submission_memory"]["status"], "completed")

        health_request = next(
            payload
            for payload in MockLoopRadarHandler.requests
            if payload.get("text", {}).get("format", {}).get("name") == "draft_health_report"
        )
        self.assertEqual(health_request["model"], "gpt-5.4-draft-health")

        memory_request = next(
            payload
            for payload in MockLoopRadarHandler.requests
            if payload.get("text", {}).get("format", {}).get("name") == "submission_memory_report"
        )
        self.assertEqual(memory_request["model"], "gpt-5.4-submission-memory")

    def test_run_paper_finishing_bundle_completes_late_stage_chain(self):
        init_stdout = self.run_cli(
            "init",
            "--config",
            str(self.config_path),
            "--title",
            "OCT reliability loop",
        )
        manifest_path = Path(json.loads(init_stdout)["manifest"])

        self.run_cli(
            "run-results-analysis",
            "--manifest",
            str(manifest_path),
            "--experiment-dir",
            str(self.experiment_dir),
            "--title",
            "ECM baseline",
        )

        bundle_stdout = self.run_cli(
            "run-paper-finishing",
            "--manifest",
            str(manifest_path),
            "--draft-file",
            str(self.draft_file),
            "--outline-file",
            str(self.manual_artifact_path),
            "--journal-name",
            "Biomedical Optics Express",
            "--journal-notes-file",
            str(self.journal_notes_file),
            "--review-comments-file",
            str(self.review_comments_file),
            "--current-changes-file",
            str(self.current_changes_file),
            "--references-file",
            str(self.references_file),
            "--venue-name",
            "Biomedical Optics Express",
            "--round-label",
            "round-1",
            "--title-prefix",
            "BOE submission",
            "--write-vault-notes",
        )
        bundle_outputs = json.loads(bundle_stdout)
        self.assertIn("submission_memory", bundle_outputs["bundle_outputs"])
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        for stage in [
            "writing_memory",
            "self_review",
            "draft_builder",
            "rebuttal_scaffold",
            "journal_targeting",
            "response_letter",
            "citation_audit",
            "submission_qc",
            "draft_health",
            "submission_memory",
        ]:
            self.assertEqual(manifest["stages"][stage]["status"], "completed")


if __name__ == "__main__":
    unittest.main()
