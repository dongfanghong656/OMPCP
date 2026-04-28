# Sphere Mie PSF Bias Progress Review - 2026-04-28

## Scope

This note records the next step after separating the exact sphere branch from the
non-spherical T-matrix route. The goal is not to claim a paper-safe PSF result,
but to make the first particle-aware sphere Mie full-NA PSF-bias trend directly
auditable.

## Implementation Change

`scripts/sphere_particle_sweep_runner.py` now computes an ideal uniform-pupil
full-NA reference for each NA value and compares every sphere Mie full-NA case
against that reference.

The runner now reports:

- `psf_bias_against_ideal_reference_status`
- `ideal_reference_comparison`
- `peakline_x_delta_um_vs_ideal`
- `self_peak_lateral_fwhm_delta_um_vs_ideal`
- `self_peak_lateral_centroid_delta_um_vs_ideal`
- `self_peak_lateral_profile_relative_l2_vs_ideal`
- `ideal_peak_plane_peak_x_delta_um_vs_ideal`
- `ideal_peak_plane_lateral_fwhm_delta_um_vs_ideal`
- `ideal_peak_plane_lateral_profile_relative_l2_vs_ideal`
- `normalized_image_relative_l2_vs_ideal`

It also writes a lightweight `sphere_mie_full_na_sweep_summary.md` next to the
JSON and CSV outputs.

## Local Evidence

Command:

```powershell
python scripts\sphere_particle_sweep_runner.py --diameters 200,500,1000 --na-values 0.05 --n-lambda 41 --n-z 401 --n-x 81 --n-bfp-dense 41 --output-dir reports\sphere_mie_full_na_psf_bias_20260428
```

Result:

- `sweep_status = complete`
- `ok_count = 3`
- `failed_count = 0`
- `psf_bias_against_ideal_reference_status = computed_not_paper_safe`
- `paper_safety_status = not_paper_safe`
- `ideal_reference_comparison.status = computed_for_all_na_values`

Selected metric ranges:

- `peakline_x_delta_um_vs_ideal = [0.0, 0.0]`
- `self_peak_lateral_fwhm_delta_um_vs_ideal = [0.0, 0.0]`
- `ideal_peak_plane_lateral_profile_relative_l2_vs_ideal = [0.0004119694058447278, 0.0016839331089368544]`
- `normalized_image_relative_l2_vs_ideal = [0.043283978876534984, 0.8443749282065282]`

Per-diameter normalized image L2 against the ideal reference:

| diameter_nm | normalized_image_relative_l2_vs_ideal |
|---:|---:|
| 200 | 0.043283978876534984 |
| 500 | 0.3080226534742257 |
| 1000 | 0.8443749282065282 |

## Interpretation

The first small panel shows no lateral peakline or lateral FWHM shift on this
grid, but the normalized full x-z image discrepancy increases strongly with
diameter. This is the right kind of trend evidence for Pro review, because it
separates "peak/width did not move in this coarse panel" from "the full
particle-aware field is changing."

## Remaining Limits

- This is still a scalar fixed-basis full-NA route, not a vector Debye or
  calibrated device model.
- The FD-OCT layer remains a measurement scaffold, not a full raw detector
  interferometer model.
- The sweep panel is intentionally small. It is not convergence-tested across
  `n_lambda`, `n_z`, `n_x`, `n_bfp_dense`, NA, material, or bandwidth.
- `paper_safety_status` remains `not_paper_safe` by design.

## Recommended Next Review Question

Ask whether the next minimum paper-safety gate should be:

1. grid and spectrum convergence for the pure sphere Mie branch,
2. measurement-wrapper calibration against an analytic reflector case,
3. vector diffraction scope gating for higher NA, or
4. all three before interpreting 200-1000 nm trends.
