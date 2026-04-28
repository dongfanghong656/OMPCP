# Pro Review Entry: Sphere-only Mie Full-NA Branch

## What changed

- Added a pure Mie sphere branch for `mode=full_na`, `eps=0`, `ideal=false`, `force_tmatrix=false`.
- The exact-sphere route no longer requires the non-spherical T-matrix backend.
- The solver now reports explicit branch fields:
  - `sphere_mie_used`
  - `tmatrix_used`
  - `tmatrix_backend_required`
  - `scattering_branch`
  - `lateral_response_model`
  - `particle_lateral_scattering_enters_profile`
  - `sphere_mie_metadata`
  - `sphere_mie_nmax_min`
  - `sphere_mie_nmax_max`
- Added `scripts/sphere_particle_sweep_runner.py` for sphere-only full-NA sweeps.
- Added contract tests for the Mie kernel and solver routing.
- Updated schema / known-limits documentation so the new branch is not confused with the low-NA Gaussian lateral surrogate or the non-spherical T-matrix route.

## Main claim to review

For exact homogeneous spheres, the project now has a particle-aware scalar full-NA pupil-field branch:

```text
pure Mie S1/S2
-> angle-resolved pupil field
-> full-NA scalar fixed-basis field
-> sample_arm_spectral_cube
-> existing FD-OCT measurement scaffold
```

Expected exact-sphere runtime contract:

```text
sphere_mie_used = true
tmatrix_used = false
tmatrix_backend_required = false
scattering_branch = sphere_mie_full_na
lateral_response_model = sphere_mie_angle_resolved_pupil_field
particle_lateral_scattering_enters_profile = true
```

## Verification run locally

- `compile_ok 6` for the new/changed Python files.
- `python -m unittest discover -s tests -p test_sphere_mie_branch_contract.py`: 5 tests passed.
- `python 12_test_low_na_asymptotic_helpers.py`: 82 tests passed.
- `python scripts/validate_oct_nonspherical_psf_solver.py ...`: exit 0; includes `full_na_sphere_mie_branch_without_tmatrix`.
- `python scripts/sphere_particle_sweep_runner.py --diameters 200,500 --na-values 0.05 --n-lambda 21 --n-z 201 --n-x 41 --n-bfp-dense 31 ...`: 2/2 cases passed.
- `python scripts/oct_nonspherical_psf_solver.py --mode full_na --diameter-nm 500 --eps 0 ...`: exit 0; returned `sphere_mie_used=true` and `tmatrix_used=false`.

## Evidence artifacts in this packet

- `sphere_mie_full_na_sweep_summary.json`
- `sphere_mie_full_na_sweep.csv`
- `sphere_mie_full_na_cli_smoke_20260428.json`
- `round6p1_validation_summary_local_sphere_branch.json`
- `round6p1_validation_failure_summary_local_sphere_branch.txt`

## Known limits still open

- This is still a scalar fixed-basis branch, not a full vector Debye / calibrated OCT instrument model.
- This branch closes the exact-sphere route only; non-spherical particles still require a compatible T-matrix backend or the planned portable backend.
- The old `low_na_separable_baseline` still has a Gaussian lateral surrogate and must not be used as evidence that particle scattering cannot affect lateral PSF.
- Current local runtime is CPython 3.13; non-spherical T-matrix evidence is still skipped locally because the vendored binary is CPython 3.10 Windows-specific.
