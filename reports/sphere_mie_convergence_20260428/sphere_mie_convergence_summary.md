# Sphere Mie Convergence Summary

- schema_version: `sphere_mie_convergence_v1`
- convergence_status: `preliminary_convergence_attention_not_paper_safe`
- paper_safety_status: `not_paper_safe`
- reference_config_id: `reference`
- ok_count: `6`
- failed_count: `0`

## Drift Ranges

- peakline_x_delta_um_vs_ideal_abs_drift_vs_reference: `[0.0, 0.0]`
- self_peak_lateral_fwhm_delta_um_vs_ideal_abs_drift_vs_reference: `[0.0, 0.0]`
- self_peak_lateral_centroid_delta_um_vs_ideal_abs_drift_vs_reference: `[0.0, 1.2439831929784541e-05]`
- ideal_peak_plane_lateral_profile_relative_l2_vs_ideal_abs_drift_vs_reference: `[0.0, 3.154390438847278e-05]`
- normalized_image_relative_l2_vs_ideal_abs_drift_vs_reference: `[0.0, 0.12893171199608922]`

## Rows

| config_id | diameter_nm | na | image_l2_vs_ideal | image_l2_abs_drift | peakline_abs_drift_um |
|---|---:|---:|---:|---:|---:|
| coarse | 200.0 | 0.05 | 0.05157596034753957 | 0.008291981471004586 | 0.0 |
| coarse | 500.0 | 0.05 | 0.3447496173448215 | 0.03672696387059582 | 0.0 |
| coarse | 1000.0 | 0.05 | 0.9733066402026174 | 0.12893171199608922 | 0.0 |
| reference | 200.0 | 0.05 | 0.043283978876534984 | 0.0 | 0.0 |
| reference | 500.0 | 0.05 | 0.3080226534742257 | 0.0 | 0.0 |
| reference | 1000.0 | 0.05 | 0.8443749282065282 | 0.0 | 0.0 |

## Interpretation

This is a numerical-convergence scaffold for the sphere Mie full-NA PSF-bias trend.
It is not a paper-safe device-level OCT conclusion.
