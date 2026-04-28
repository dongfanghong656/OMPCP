# Sphere Mie Full-NA Sweep Summary

- schema_version: `sphere_mie_sweep_v1`
- sweep_status: `complete`
- psf_bias_against_ideal_reference_status: `computed_not_paper_safe`
- paper_safety_status: `not_paper_safe`
- ok_count: `3`
- failed_count: `0`

## Ideal Reference Comparison

- status: `computed_for_all_na_values`
- reference_kind: `ideal_uniform_pupil_full_na`
- all_ok_rows_have_ideal_reference: `True`
- comparison_modes: `self_peak_plane, ideal_peak_plane, normalized_full_xz_image`

## Metric Ranges

- peakline_x_delta_um_vs_ideal: `[0.0, 0.0]`
- self_peak_lateral_fwhm_delta_um_vs_ideal: `[0.0, 0.0]`
- self_peak_lateral_centroid_delta_um_vs_ideal: `[-6.195193756831669e-06, -6.806337987447368e-08]`
- ideal_peak_plane_lateral_profile_relative_l2_vs_ideal: `[0.0004119694058447278, 0.0016839331089368544]`
- normalized_image_relative_l2_vs_ideal: `[0.043283978876534984, 0.8443749282065282]`

## Rows

| diameter_nm | na | status | peakline_delta_um | fwhm_delta_um | image_l2_vs_ideal |
|---:|---:|---|---:|---:|---:|
| 200.0 | 0.05 | ok | 0.0 | 0.0 | 0.043283978876534984 |
| 500.0 | 0.05 | ok | 0.0 | 0.0 | 0.3080226534742257 |
| 1000.0 | 0.05 | ok | 0.0 | 0.0 | 0.8443749282065282 |

## Interpretation

This report is a PSF-bias trend scaffold, not a paper-safe device-level OCT truth claim.
It compares the sphere Mie full-NA solver output against an ideal uniform-pupil full-NA reference.
