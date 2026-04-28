"""Contract tests for the separated sphere-only Mie branch."""

from __future__ import annotations

import importlib.util
import json
import sys
import unittest
import uuid
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from physics.mie_sphere import compare_backscatter_convention, mie_efficiencies, mie_s1_s2


def load_solver():
    candidates = (
        ROOT / "scripts" / "oct_nonspherical_psf_solver.py",
        ROOT / "scripts" / "01_oct_nonspherical_psf_solver.py",
        ROOT / "oct_nonspherical_psf_solver.py",
        ROOT / "01_oct_nonspherical_psf_solver.py",
    )
    for candidate in candidates:
        if candidate.exists():
            for path in (ROOT, candidate.parent):
                if str(path) not in sys.path:
                    sys.path.insert(0, str(path))
            spec = importlib.util.spec_from_file_location("oct_nonspherical_psf_solver_for_sphere_tests", candidate)
            assert spec and spec.loader
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            sys.modules.setdefault("oct_nonspherical_psf_solver", module)
            spec.loader.exec_module(module)
            return module
    raise FileNotFoundError("Cannot find solver module.")


def load_sphere_runner():
    candidate = ROOT / "scripts" / "sphere_particle_sweep_runner.py"
    spec = importlib.util.spec_from_file_location("sphere_particle_sweep_runner_for_tests", candidate)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class SphereMieKernelTests(unittest.TestCase):
    def test_backscatter_convention_matches_round6_s22(self):
        m_rel = 2.48 / 1.40
        x = 2.0 * np.pi * 0.100 * 1.40 / 0.855
        diag = compare_backscatter_convention(m_rel, x)
        self.assertLess(diag["abs_s22_minus_round6"], 1e-12)
        self.assertLess(diag["abs_s11_plus_s22"], 1e-12)

    def test_nonabsorbing_efficiencies_have_near_zero_absorption(self):
        eff = mie_efficiencies(1.50 / 1.33, 1.2)
        self.assertGreater(eff["qext"], 0.0)
        self.assertGreater(eff["qsca"], 0.0)
        self.assertLess(abs(eff["qabs"]), 1e-10)

    def test_s1_s2_shapes_follow_mu_grid(self):
        mu = np.linspace(-1.0, 1.0, 17)
        result = mie_s1_s2(2.48 / 1.40, 1.1, mu)
        self.assertEqual(result.s1.shape, mu.shape)
        self.assertEqual(result.s2.shape, mu.shape)
        self.assertTrue(np.all(np.isfinite(result.s1)))
        self.assertTrue(np.all(np.isfinite(result.s2)))


class SphereBranchSolverTests(unittest.TestCase):
    def test_full_na_sphere_uses_mie_branch_not_tmatrix(self):
        solver = load_solver()
        source = solver.SourceConfig(lambda0_nm=855.0, fwhm_nm=56.0, n_lambda=21)
        grid = solver.GridConfig(z_span_um=15.0, n_z=301, x_span_um=6.0, n_x=61, na=0.05, n_bfp_dense=41, n_bfp_sparse=7)
        config = solver.SolverConfig(
            mode="full_na",
            particle_material="TiO2-anatase",
            medium_material="PDMS",
            diameter_nm=500.0,
            eps=0.0,
            beta_deg=0.0,
            amp_component="S22",
            ideal=False,
            force_tmatrix=False,
        )
        result = solver.solve_oct_particle_response(source, grid, config)
        self.assertFalse(result.get("tmatrix_used"), result.get("tmatrix_library"))
        self.assertTrue(result.get("sphere_mie_used"))
        self.assertEqual(result.get("scattering_branch"), "sphere_mie_full_na")
        self.assertEqual(result.get("lateral_response_model"), "sphere_mie_angle_resolved_pupil_field")
        self.assertTrue(result.get("particle_lateral_scattering_enters_profile"))
        self.assertEqual(result.get("sample_arm_spectral_cube_shape"), [source.n_lambda, grid.n_x])
        self.assertEqual(result.get("sample_arm_spectral_cube_axis_order"), "lambda_x")
        self.assertEqual(result.get("sample_arm_spectral_cube_quantity_kind"), "complex_sample_arm_spectral_field")
        self.assertTrue(result.get("fd_oct_measurement_scaffold_route_available"))
        self.assertTrue(np.all(np.isfinite(result["raw_intensity_xz"])))
        self.assertGreater(float(result["raw_peak_intensity"]), 0.0)

    def test_force_tmatrix_keeps_legacy_route_for_crosscheck(self):
        solver = load_solver()
        source = solver.SourceConfig(lambda0_nm=855.0, fwhm_nm=56.0, n_lambda=5)
        grid = solver.GridConfig(z_span_um=5.0, n_z=51, x_span_um=2.0, n_x=21, na=0.05, n_bfp_dense=15, n_bfp_sparse=5)
        config = solver.SolverConfig(mode="full_na", diameter_nm=200.0, eps=0.0, force_tmatrix=True)
        try:
            result = solver.solve_oct_particle_response(source, grid, config)
        except Exception as exc:
            message = (str(exc) + repr(type(exc))).lower()
            self.assertTrue(
                "t-matrix" in message or "pytmatrix" in message or "libpytmatrix" in message,
                message,
            )
            return
        self.assertTrue(result.get("tmatrix_used"))
        self.assertFalse(result.get("sphere_mie_used", False))


class SphereSweepRunnerTests(unittest.TestCase):
    def test_sweep_reports_psf_bias_against_ideal_reference(self):
        runner = load_sphere_runner()
        unit_tmp = ROOT / "reports" / "_unit_test_tmp"
        unit_tmp.mkdir(parents=True, exist_ok=True)
        tmp = unit_tmp / f"sphere_runner_bias_{uuid.uuid4().hex}"
        tmp.mkdir(parents=True, exist_ok=False)
        code = runner.main(
            [
                "--project-root",
                str(ROOT),
                "--output-dir",
                str(tmp),
                "--diameters",
                "200",
                "--na-values",
                "0.05",
                "--n-lambda",
                "7",
                "--n-z",
                "81",
                "--n-x",
                "31",
                "--n-bfp-dense",
                "15",
                "--z-span-um",
                "8",
                "--x-span-um",
                "4",
            ]
        )
        self.assertEqual(code, 0)
        summary = json.loads((tmp / "sphere_mie_full_na_sweep_summary.json").read_text(encoding="utf-8"))
        self.assertTrue((tmp / "sphere_mie_full_na_sweep_summary.md").exists())
        self.assertEqual(summary["ideal_reference_comparison"]["status"], "computed_for_all_na_values")
        self.assertEqual(summary["psf_bias_against_ideal_reference_status"], "computed_not_paper_safe")
        self.assertTrue(summary["ideal_reference_comparison"]["all_ok_rows_have_ideal_reference"])
        row = summary["rows"][0]
        self.assertTrue(row["ideal_reference_available"])
        self.assertEqual(row["psf_bias_against_ideal_reference_status"], "computed_against_ideal_full_na_reference")
        for key in (
            "peakline_x_delta_um_vs_ideal",
            "ideal_peak_plane_lateral_profile_relative_l2_vs_ideal",
            "normalized_image_relative_l2_vs_ideal",
        ):
            self.assertIn(key, row)
            self.assertIsNotNone(row[key])
        self.assertIn("normalized_image_relative_l2_vs_ideal", summary["metric_ranges"])


if __name__ == "__main__":
    unittest.main()
