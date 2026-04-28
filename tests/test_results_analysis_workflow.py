import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "results_analysis_workflow.py"


class ResultsAnalysisWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.test_root = ROOT / "tmp" / "test-runs"
        self.test_root.mkdir(parents=True, exist_ok=True)
        self.workspace = self.test_root / "results-analysis-workspace"
        shutil.rmtree(self.workspace, ignore_errors=True)
        self.workspace.mkdir(parents=True, exist_ok=True)

        self.vault_root = self.workspace / "vault"
        self.output_root = self.workspace / "reports"
        self.experiment_dir = self.workspace / "experiment"
        self.config_path = self.workspace / "config.json"

        (self.vault_root / "04_Progress").mkdir(parents=True, exist_ok=True)
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

        config = {
            "vault_root": str(self.vault_root).replace("\\", "/"),
            "output_root": str(self.output_root).replace("\\", "/"),
            "obsidian": {
                "progress_folder": "04_Progress",
            },
        }
        self.config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def tearDown(self):
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

    def test_results_analysis_workflow_generates_analysis_and_report(self):
        stdout = self.run_cli(
            "--config",
            str(self.config_path),
            "--experiment-dir",
            str(self.experiment_dir),
            "--title",
            "ECM baseline",
            "--write-progress-note",
        )
        outputs = json.loads(stdout)

        analysis = json.loads(Path(outputs["analysis_json"]).read_text(encoding="utf-8"))
        report = json.loads(Path(outputs["results_report_json"]).read_text(encoding="utf-8"))
        report_md = Path(outputs["results_report_markdown"]).read_text(encoding="utf-8")

        self.assertEqual(analysis["unified_ranking_summary"]["best_name"], "tukey_0p6")
        self.assertEqual(analysis["scene_summary"]["best_scene_rmse_name"], "tukey_0p6")
        self.assertIn("tukey_0p6 is the current best candidate", report["headline"])
        self.assertIn("## Safe Claims", report_md)
        self.assertTrue(Path(outputs["progress_note"]).exists())


if __name__ == "__main__":
    unittest.main()
