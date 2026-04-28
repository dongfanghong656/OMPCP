# Round 6p1 Coefficient Map Audit

Recommended next action: `audit_coefficient_map_stage_before_basis_expansion`

## sphere_low_na_low_contrast

Native asymptotic: image L2 `0.123363`, peakline delta `2`.

| map model | raw coeff residual | orth coeff residual | shared-scale residual | injected image L2 | injected peakline delta | best |
|---|---:|---:|---:|---:|---:|---|
| identity_slice_projected_rendered_basis | 1.58711 | 20.9445 | 0.14229 | 0.122935 | 2 | no |
| shared_complex_scale_map | 0.14229 | 8.67959 | 0.14229 | 0.122935 | 2 | no |
| componentwise_complex_scale_map | 0.14229 | 0.00689669 | 0.14229 | 0.00365113 | 4 | no |
| low_order_coupled_odd_even_map | 0.005563 | 0.000287361 | 0.005563 | 0.000664575 | 4 | no |
| fitted_linear_map_3x3 | 0.00556289 | 0.000268975 | 0.00556289 | 0.000665817 | 0 | yes |

## mild_shape_medium_tilt

Native asymptotic: image L2 `0.589748`, peakline delta `2`.

| map model | raw coeff residual | orth coeff residual | shared-scale residual | injected image L2 | injected peakline delta | best |
|---|---:|---:|---:|---:|---:|---|
| identity_slice_projected_rendered_basis | 1.81057 | 29.8743 | 0.133202 | 0.587814 | 2 | no |
| shared_complex_scale_map | 0.133202 | 11.1035 | 0.133202 | 0.587814 | 2 | no |
| componentwise_complex_scale_map | 0.133202 | 0.166765 | 0.133202 | 0.0656606 | 0 | no |
| low_order_coupled_odd_even_map | 0.0331191 | 0.00856631 | 0.0331191 | 0.00513413 | 0 | no |
| fitted_linear_map_3x3 | 0.0111361 | 0.00284808 | 0.0111361 | 0.00313093 | 0 | yes |

## failure_domain_high_tilt_high_contrast

Native asymptotic: image L2 `1.16728`, peakline delta `3`.

| map model | raw coeff residual | orth coeff residual | shared-scale residual | injected image L2 | injected peakline delta | best |
|---|---:|---:|---:|---:|---:|---|
| identity_slice_projected_rendered_basis | 1.51825 | 6.40837 | 0.144464 | 1.17944 | 3 | no |
| shared_complex_scale_map | 0.144464 | 3.03993 | 0.144464 | 1.17944 | 3 | no |
| componentwise_complex_scale_map | 0.144464 | 0.192673 | 0.144464 | 0.0849799 | 6 | no |
| low_order_coupled_odd_even_map | 0.0492887 | 0.0289063 | 0.0492887 | 0.0272101 | 6 | no |
| fitted_linear_map_3x3 | 0.0289382 | 0.0169364 | 0.0289382 | 0.0220518 | 0 | yes |
