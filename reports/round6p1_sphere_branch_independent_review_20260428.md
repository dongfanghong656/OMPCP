# Round6p1 Sphere Branch Independent Review

## Scope

This review focused on the exact-sphere `Mie` branch introduced after Pro review. The inspected path was:

```text
full_na, eps = 0, ideal = false, force_tmatrix = false
-> pure Mie S1/S2
-> angle-resolved pupil field
-> scalar full-NA fixed-basis propagation
-> sample_arm_spectral_cube
-> FD-OCT measurement scaffold
```

The review did not attempt to certify paper-safe particle-size conclusions. It only checked whether the exact-sphere route is separated from the non-spherical T-matrix route and whether the evidence contracts are machine-readable.

## Findings

### Fixed finding: sample-arm spectral cube contract was implicit

The solver returned `sample_arm_spectral_cube`, but the result summary did not expose a compact contract for its shape, axis order, quantity kind, or FD-OCT scaffold availability. This made the route harder for Pro and downstream validators to audit without opening the NPZ arrays.

Fix applied:

- `scripts/oct_nonspherical_psf_solver.py` now exposes:
  - `sample_arm_spectral_cube_shape`
  - `sample_arm_spectral_cube_axis_order = "lambda_x"`
  - `sample_arm_spectral_cube_quantity_kind = "complex_sample_arm_spectral_field"`
  - `sample_arm_spectral_cube_contract_status`
  - `fd_oct_measurement_scaffold_route_available`
- `scripts/sphere_particle_sweep_runner.py` propagates those fields into sweep rows and adds:
  - `interpretation_status`
  - `paper_safety_status`
  - `sphere_branch_contract_checks`
- `scripts/validate_oct_nonspherical_psf_solver.py` now includes the spectral-cube route contract in the `full_na_sphere_mie_branch_without_tmatrix` gate.
- `reports/result_schema_round6p1.md` and `reports/known_limits_round6p1.md` now document the new fields and their limits.

## Independent review status

No new implementation-level blocker was found in the exact-sphere branch contract after this fix.

Confirmed contract:

```text
sphere_mie_used = true
tmatrix_used = false
tmatrix_backend_required = false
scattering_branch = sphere_mie_full_na
lateral_response_model = sphere_mie_angle_resolved_pupil_field
particle_lateral_scattering_enters_profile = true
sample_arm_spectral_cube_contract_status = valid_lambda_x_complex_field
fd_oct_measurement_scaffold_route_available = true
```

## Verification

Fresh local verification:

```text
in-memory compile check for 6 changed files: OK
python -m unittest discover -s tests -p test_sphere_mie_branch_contract.py: 5 tests OK
python scripts/sphere_particle_sweep_runner.py --diameters 200,500,1000 --na-values 0.05 --n-lambda 41 --n-z 401 --n-x 81 --n-bfp-dense 41 --output-dir reports/sphere_mie_full_na_acceptance_20260428_v2: exit 0, 3/3 cases OK
python scripts/validate_oct_nonspherical_psf_solver.py --output-json reports/round6p1_validation_summary_local_sphere_branch_v2.json --failure-summary-txt reports/round6p1_validation_failure_summary_local_sphere_branch_v2.txt: exit 0
python 12_test_low_na_asymptotic_helpers.py: 82 tests OK
```

The direct `py_compile` command was not used as final evidence because this Windows workspace produced a `WinError 5` permission error while writing `__pycache__`. The in-memory compile check avoids that filesystem-specific bytecode-write issue.

## Remaining limits

- The exact-sphere branch is still a scalar fixed-basis model, not a full vector Debye or calibrated OCT instrument model.
- The sphere sweep is still contract/smoke evidence, not a paper-safe conclusion about 200-1000 nm particle PSF distortion.
- Non-spherical evidence still depends on a compatible T-matrix backend or the planned portable backend.
- The low-NA separable baseline still uses a Gaussian lateral surrogate and should not be used as evidence that particle scattering cannot affect lateral PSF.

