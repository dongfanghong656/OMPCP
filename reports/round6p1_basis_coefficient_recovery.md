# Round 6p1 Basis Coefficient Recovery

Recommended next action: `debug_coefficient_extraction_or_usage_mapping`
Basis conditioning status: `poor`
Coefficient interpretability status: `ill_conditioned`
Shared-scale consistency status: `mixed_bc2_caution`

## sphere_low_na_low_contrast

Vector alignment residual: `0.14229`; scale abs: `0.385065`; phase: `-4.47196e-07` rad.

Shared-scale consistency: residual `0.14229`; scale abs `0.385065`; phase `-4.47196e-07` rad.

| Component | relative_residual | scale_abs | scale_phase_rad | mean_abs_ratio_recovered_over_asymptotic |
|---|---:|---:|---:|---:|
| a0_vs_B_k | 0.129545 | 2.15301 | -4.58112e-07 | 2.13665 |
| a1_vs_D1_slice_k | 0.168665 | 2.08443e+06 | -0.0119502 | 2.0957e+06 |
| a2_vs_C2_slice_k | 0.14229 | 0.385065 | -4.47196e-07 | 0.381846 |

| Component under shared scale | relative_residual | mean_abs_ratio |
|---|---:|---:|
| a0_vs_B_k | 0.824472 | 5.54881 |
| a1_vs_D1_slice_k | 1 | 5.44246e+06 |
| a2_vs_C2_slice_k | 0.14229 | 0.991639 |

Recovered energy ratios: `|a1|/|a0| = 0.288231`, `|a2|/|a0| = 55915.7`.

Orthonormalized recovered energy ratios: `|q1|/|q0| = 0.000597794`, `|q2|/|q0| = 0.0317855`.

Asymptotic energy ratios: `|D1|/|B| = 2.93864e-07`, `|C2|/|B| = 312882`.

Basis Gram condition number: `3.41085e+14`; R-factor condition number after orthonormalization: `1.84685e+07`.

Coefficient contract: fit strategy `split_even_odd`, residual model `even`, slice `x`, wavelength axis `vacuum_wavelength_nm`, assembly `directional_field_expansion_first_order`, map `identity_slice_projected_rendered_basis`.

Coefficient bundle artifact: `round6p1_sphere_low_na_low_contrast_native_identity_coefficient_bundle.npz`

## mild_shape_medium_tilt

Vector alignment residual: `0.133202`; scale abs: `0.354372`; phase: `-0.00278947` rad.

Shared-scale consistency: residual `0.133202`; scale abs `0.354372`; phase `-0.00278947` rad.

| Component | relative_residual | scale_abs | scale_phase_rad | mean_abs_ratio_recovered_over_asymptotic |
|---|---:|---:|---:|---:|
| a0_vs_B_k | 0.126007 | 2.1266 | 0.0531534 | 2.18409 |
| a1_vs_D1_slice_k | 0.251635 | 462563 | -0.122281 | 470876 |
| a2_vs_C2_slice_k | 0.133202 | 0.354372 | -0.00278947 | 0.364854 |

| Component under shared scale | relative_residual | mean_abs_ratio |
|---|---:|---:|
| a0_vs_B_k | 0.836574 | 6.16328 |
| a1_vs_D1_slice_k | 0.999999 | 1.32876e+06 |
| a2_vs_C2_slice_k | 0.133202 | 1.02958 |

Recovered energy ratios: `|a1|/|a0| = 0.13612`, `|a2|/|a0| = 14692.9`.

Orthonormalized recovered energy ratios: `|q1|/|q0| = 0.00146596`, `|q2|/|q0| = 0.175275`.

Asymptotic energy ratios: `|D1|/|B| = 6.31372e-07`, `|C2|/|B| = 87955.1`.

Basis Gram condition number: `1.31093e+12`; R-factor condition number after orthonormalization: `1.14496e+06`.

Coefficient contract: fit strategy `split_even_odd`, residual model `even`, slice `x`, wavelength axis `vacuum_wavelength_nm`, assembly `directional_field_expansion_first_order`, map `identity_slice_projected_rendered_basis`.

Coefficient bundle artifact: `round6p1_mild_shape_medium_tilt_native_identity_coefficient_bundle.npz`

## failure_domain_high_tilt_high_contrast

Vector alignment residual: `0.144464`; scale abs: `0.395667`; phase: `0.00333048` rad.

Shared-scale consistency: residual `0.144464`; scale abs `0.395667`; phase `0.00333048` rad.

| Component | relative_residual | scale_abs | scale_phase_rad | mean_abs_ratio_recovered_over_asymptotic |
|---|---:|---:|---:|---:|
| a0_vs_B_k | 0.0724868 | 2.0996 | 0.0750811 | 2.06696 |
| a1_vs_D1_slice_k | 0.741018 | 146613 | 1.245 | 206838 |
| a2_vs_C2_slice_k | 0.144464 | 0.395667 | 0.00333048 | 0.390596 |

| Component under shared scale | relative_residual | mean_abs_ratio |
|---|---:|---:|
| a0_vs_B_k | 0.813249 | 5.22399 |
| a1_vs_D1_slice_k | 1 | 522757 |
| a2_vs_C2_slice_k | 0.144464 | 0.987184 |

Recovered energy ratios: `|a1|/|a0| = 0.0783448`, `|a2|/|a0| = 3372.03`.

Orthonormalized recovered energy ratios: `|q1|/|q0| = 0.00152898`, `|q2|/|q0| = 0.478898`.

Asymptotic energy ratios: `|D1|/|B| = 7.82912e-07`, `|C2|/|B| = 17844.2`.

Basis Gram condition number: `9.10923e+08`; R-factor condition number after orthonormalization: `30181.5`.

Coefficient contract: fit strategy `split_even_odd`, residual model `even`, slice `x`, wavelength axis `vacuum_wavelength_nm`, assembly `directional_field_expansion_first_order`, map `identity_slice_projected_rendered_basis`.

Coefficient bundle artifact: `round6p1_failure_domain_high_tilt_high_contrast_native_identity_coefficient_bundle.npz`
