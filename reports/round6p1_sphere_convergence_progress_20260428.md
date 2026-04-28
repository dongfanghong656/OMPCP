# Sphere Mie Convergence Progress Review - 2026-04-28

## Scope

This note adds the first numerical-convergence scaffold for the sphere Mie
full-NA PSF-bias trend. It follows the previous ideal-reference comparison and
asks whether the observed `*_vs_ideal` metrics are stable across a small
grid/spectrum panel.

## Implementation Change

Added `scripts/sphere_mie_convergence_runner.py`.

The runner:

- evaluates sphere Mie full-NA cases across named numerical configurations,
- computes the same ideal-reference PSF-bias metrics as
  `sphere_particle_sweep_runner.py`,
- compares each metric against an explicit reference configuration,
- writes JSON, CSV, and Markdown summaries,
- does not write per-case NPZ arrays.

Schema:

- `schema_version = "sphere_mie_convergence_v1"`
- `paper_safety_status = "not_paper_safe"`
- `convergence_status`
- `convergence_reference_summary`
- `metric_ranges`
- `rows[*].*_abs_drift_vs_reference`

## Local Evidence

Command:

```powershell
python scripts\sphere_mie_convergence_runner.py --diameters 200,500,1000 --na-values 0.05 --grid-panel "coarse:21,201,61,31;reference:41,401,81,41" --output-dir reports\sphere_mie_convergence_20260428
```

Result:

- `ok_count = 6`
- `failed_count = 0`
- `reference_config_id = reference`
- `convergence_status = preliminary_convergence_attention_not_paper_safe`
- `paper_safety_status = not_paper_safe`

Maximum absolute drift against the reference configuration:

- `peakline_x_delta_um_vs_ideal = 0.0`
- `self_peak_lateral_fwhm_delta_um_vs_ideal = 0.0`
- `self_peak_lateral_centroid_delta_um_vs_ideal = 1.2439831929784541e-05`
- `ideal_peak_plane_lateral_profile_relative_l2_vs_ideal = 3.154390438847278e-05`
- `normalized_image_relative_l2_vs_ideal = 0.12893171199608922`

## Verification

- `python -m unittest discover -s tests -p test_sphere_mie_convergence_runner.py`: `2 tests OK`
- `python -m unittest discover -s tests -p "test_sphere_mie*.py"`: `8 tests OK`
- `python 12_test_low_na_asymptotic_helpers.py`: `82 tests OK`
- In-memory compile check: `scripts/sphere_mie_convergence_runner.py`,
  `scripts/sphere_particle_sweep_runner.py`, and
  `tests/test_sphere_mie_convergence_runner.py`

Note: broad `python -m unittest discover -s tests -p test_*.py` is not a valid
round6p1 verification gate in this checkout. It includes unrelated vault/Zotero
tests with persistent temp-dir and state assumptions on this Windows host.

## Interpretation

The preliminary panel keeps peakline and lateral FWHM stable, but the full x-z
image relative-L2 metric still shows non-negligible numerical drift. This is a
useful stop sign: the trend is promising enough to continue, but not stable
enough to call paper-safe.

## Next Minimum Gate

The next gate should use at least three settings for each of:

- spectrum sampling (`n_lambda`),
- axial sampling (`n_z`),
- lateral sampling (`n_x`),
- BFP sampling (`n_bfp_dense`).

The gate should also decide whether the paper-facing criterion should be based
on peak/FWHM stability, full-image relative L2 stability, or both.
