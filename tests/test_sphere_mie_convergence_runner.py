"""Tests for the sphere Mie convergence scaffold."""

from __future__ import annotations

import importlib.util
import json
import sys
import unittest
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def load_convergence_runner():
    candidate = ROOT / "scripts" / "sphere_mie_convergence_runner.py"
    spec = importlib.util.spec_from_file_location("sphere_mie_convergence_runner_for_tests", candidate)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class SphereMieConvergenceRunnerTests(unittest.TestCase):
    def test_parse_grid_panel_requires_two_unique_configs(self):
        runner = load_convergence_runner()
        panel = runner.parse_grid_panel("tiny:5,51,21,11;reference:7,81,31,15")
        self.assertEqual([spec.config_id for spec in panel], ["tiny", "reference"])
        with self.assertRaises(ValueError):
            runner.parse_grid_panel("only:5,51,21,11")
        with self.assertRaises(ValueError):
            runner.parse_grid_panel("dup:5,51,21,11;dup:7,81,31,15")

    def test_convergence_runner_writes_drift_metrics(self):
        runner = load_convergence_runner()
        unit_tmp = ROOT / "reports" / "_unit_test_tmp"
        unit_tmp.mkdir(parents=True, exist_ok=True)
        out_dir = unit_tmp / f"sphere_convergence_{uuid.uuid4().hex}"
        out_dir.mkdir(parents=True, exist_ok=False)
        code = runner.main(
            [
                "--project-root",
                str(ROOT),
                "--output-dir",
                str(out_dir),
                "--diameters",
                "200",
                "--na-values",
                "0.05",
                "--grid-panel",
                "tiny:5,51,21,11;reference:7,81,31,15",
                "--z-span-um",
                "8",
                "--x-span-um",
                "4",
            ]
        )
        self.assertEqual(code, 0)
        summary_path = out_dir / "sphere_mie_convergence_summary.json"
        self.assertTrue(summary_path.exists())
        self.assertTrue((out_dir / "sphere_mie_convergence_summary.md").exists())
        self.assertTrue((out_dir / "sphere_mie_convergence_summary.csv").exists())
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        self.assertEqual(summary["schema_version"], "sphere_mie_convergence_v1")
        self.assertEqual(summary["reference_config_id"], "reference")
        self.assertEqual(summary["ok_count"], 2)
        self.assertEqual(summary["failed_count"], 0)
        self.assertEqual(summary["paper_safety_status"], "not_paper_safe")
        self.assertIn("convergence_status", summary)
        self.assertIn("normalized_image_relative_l2_vs_ideal_abs_drift_vs_reference", summary["metric_ranges"])
        for row in summary["rows"]:
            self.assertTrue(row["convergence_reference_available"])
            self.assertIn("normalized_image_relative_l2_vs_ideal_abs_drift_vs_reference", row)


if __name__ == "__main__":
    unittest.main()
