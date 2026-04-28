# Round 6p1 Coefficient Map Ablation

Recommended next action: `require_train_eval_generalization_before_promoting_fitted_map`

Reference rendered coefficients source: `bridge_recovered`

Train/eval split kind: `even_odd_wavelength_split`

Best ablated map model: `fitted_linear_map_3x3`

Case-specific fitted-map diagnostic artifacts are written separately from native and shared promoted bundles.

## Aggregate model comparison

| model | mean peakline delta | mean image L2 | mean eval raw residual | mean eval orth residual | mean map cond | best-case wins |
|---|---:|---:|---:|---:|---:|---:|
| identity_slice_projected_rendered_basis | 2.33333 | 0.630063 | 1.63906 | 19.0744 | 1 | 0 |
| shared_complex_scale_map | 2.33333 | 0.630063 | 0.139154 | 7.60718 | 1 | 0 |
| componentwise_complex_scale_map | 3.33333 | 0.0516336 | 0.139154 | 0.121695 | 2.36239e+06 | 0 |
| low_order_coupled_odd_even_map | 3.33333 | 0.0111047 | 0.0288509 | 0.012429 | 2.18348e+16 | 0 |
| fitted_linear_map_3x3 | 0 | 0.00869197 | 0.015013 | 0.0066074 | 2.25784e+21 | 3 |

## sphere_low_na_low_contrast
Sphere, low NA, low contrast. This should be the easiest alignment case.

Case-specific fitted-map artifact: `round6p1_sphere_low_na_low_contrast_case_specific_fitted_map_diagnostic_bundle.npz`

| map model | train raw residual | eval raw residual | train orth residual | eval orth residual | image L2 | peakline delta | map cond | best |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| identity_slice_projected_rendered_basis | 1.58555 | 1.5887 | 20.9441 | 20.9449 | 0.122935 | 2 | 1 | no |
| shared_complex_scale_map | 0.143417 | 0.141135 | 8.68364 | 8.68396 | 0.122935 | 2 | 1 | no |
| componentwise_complex_scale_map | 0.143417 | 0.141135 | 0.00695609 | 0.00683588 | 0.00372299 | 4 | 5.41222e+06 | no |
| low_order_coupled_odd_even_map | 0.00565804 | 0.00546757 | 0.000292161 | 0.000282541 | 0.000675897 | 4 | 6.55039e+16 | no |
| fitted_linear_map_3x3 | 0.00565799 | 0.00546745 | 0.0002741 | 0.000264079 | 0.000680832 | 0 | 6.7735e+21 | yes |

## mild_shape_medium_tilt
Small deformation with medium tilt. This is where bridge and asymptotic should start to separate.

Case-specific fitted-map artifact: `round6p1_mild_shape_medium_tilt_case_specific_fitted_map_diagnostic_bundle.npz`

| map model | train raw residual | eval raw residual | train orth residual | eval orth residual | image L2 | peakline delta | map cond | best |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| identity_slice_projected_rendered_basis | 1.81181 | 1.80932 | 29.8811 | 29.8674 | 0.587814 | 2 | 1 | no |
| shared_complex_scale_map | 0.133781 | 0.132617 | 11.1012 | 11.096 | 0.587814 | 2 | 1 | no |
| componentwise_complex_scale_map | 0.133781 | 0.132617 | 0.167137 | 0.165863 | 0.0658875 | 0 | 1.304e+06 | no |
| low_order_coupled_odd_even_map | 0.034025 | 0.0321862 | 0.0087979 | 0.00832776 | 0.00523202 | 0 | 3.62038e+11 | no |
| fitted_linear_map_3x3 | 0.0113509 | 0.010929 | 0.00290266 | 0.00279563 | 0.00319905 | 0 | 5.12837e+15 | yes |

## failure_domain_high_tilt_high_contrast
Larger tilt and higher contrast. This should sit inside the asymptotic failure domain.

Case-specific fitted-map artifact: `round6p1_failure_domain_high_tilt_high_contrast_case_specific_fitted_map_diagnostic_bundle.npz`

| map model | train raw residual | eval raw residual | train orth residual | eval orth residual | image L2 | peakline delta | map cond | best |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| identity_slice_projected_rendered_basis | 1.51737 | 1.51916 | 6.40591 | 6.41089 | 1.17944 | 3 | 1 | no |
| shared_complex_scale_map | 0.145196 | 0.14371 | 3.03967 | 3.0416 | 1.17944 | 3 | 1 | no |
| componentwise_complex_scale_map | 0.145196 | 0.14371 | 0.193236 | 0.192385 | 0.0852902 | 6 | 370959 | no |
| low_order_coupled_odd_even_map | 0.0496838 | 0.048899 | 0.029139 | 0.0286767 | 0.0274061 | 6 | 4.99431e+09 | no |
| fitted_linear_map_3x3 | 0.0292382 | 0.0286425 | 0.0171129 | 0.0167625 | 0.022196 | 0 | 4.58555e+14 | yes |
