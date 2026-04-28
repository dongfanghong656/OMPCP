"""Tests for CI evidence artifact import planning."""

from __future__ import annotations

import importlib.util
import sys
import unittest
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def load_importer():
    candidate = ROOT / "scripts" / "import_ci_evidence_artifacts.py"
    spec = importlib.util.spec_from_file_location("import_ci_evidence_artifacts_for_tests", candidate)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class CiEvidenceImporterTests(unittest.TestCase):
    def test_import_plan_includes_sphere_convergence_summaries(self):
        importer = load_importer()
        unit_tmp = ROOT / "reports" / "_unit_test_tmp"
        artifact_dir = unit_tmp / f"ci_artifact_{uuid.uuid4().hex}"
        rebuild_dir = artifact_dir / "round6p1_cp310_ci_rebuild"
        convergence_dir = artifact_dir / "sphere_mie_convergence_ci_smoke"
        rebuild_dir.mkdir(parents=True, exist_ok=False)
        convergence_dir.mkdir(parents=True, exist_ok=False)
        (rebuild_dir / "round6p1_validation_summary.json").write_text("{}", encoding="utf-8")
        (convergence_dir / "sphere_mie_convergence_summary.json").write_text("{}", encoding="utf-8")
        (convergence_dir / "sphere_mie_convergence_summary.md").write_text("# ok\n", encoding="utf-8")
        (convergence_dir / "sphere_mie_convergence_summary.csv").write_text("a,b\n1,2\n", encoding="utf-8")
        (convergence_dir / "debug_detail.json").write_text("{}", encoding="utf-8")

        plan = importer.build_import_plan(
            artifact_dir,
            unit_tmp / f"reports_out_{uuid.uuid4().hex}",
        )
        destinations = {
            item["destination_relative_path"]
            for item in plan["planned_files"]
        }
        self.assertIn(
            "sphere_mie_convergence_ci_smoke/sphere_mie_convergence_summary.json",
            destinations,
        )
        self.assertIn(
            "sphere_mie_convergence_ci_smoke/sphere_mie_convergence_summary.md",
            destinations,
        )
        self.assertIn(
            "sphere_mie_convergence_ci_smoke/sphere_mie_convergence_summary.csv",
            destinations,
        )
        self.assertNotIn(
            "sphere_mie_convergence_ci_smoke/debug_detail.json",
            destinations,
        )


if __name__ == "__main__":
    unittest.main()
