"""Contract tests for the separated sphere-only Mie branch."""

from __future__ import annotations

import importlib.util
import sys
import unittest
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


if __name__ == "__main__":
    unittest.main()
