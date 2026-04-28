# Round 6p1 Coefficient Map Stability

Recommended next action: `audit_coefficient_map_generalization_before_production`

Best generalizing model: `low_order_coupled_odd_even_map`

Generalization panel size: `5`

Promoted shared-map runtime model: `low_order_coupled_odd_even_map`

Promoted shared-map runtime scope: `general_asymptotic_rendered_basis_override`

Promoted shared-map contract status: `explicit_rendered_basis_override_contract`

Promoted shared-map supported lateral-shift models: `none, first_order`

Promoted shared-map lateral-shift constraint: `rendered_basis_override_supports_first_order_only_with_envelope_only_analytic_gaussian_or_rendered_interp`

Promoted shared-map shift target: `baseline_envelope_ratio`

## Full-panel shared map candidates

| model | artifact | Frobenius norm |
|---|---|---:|
| identity_slice_projected_rendered_basis | round6p1_shared_coefficient_map_candidate_identity_slice_projected_rendered_basis.npz | 1.73205 |
| shared_complex_scale_map | round6p1_shared_coefficient_map_candidate_shared_complex_scale_map.npz | 0.623177 |
| componentwise_complex_scale_map | round6p1_shared_coefficient_map_candidate_componentwise_complex_scale_map.npz | 166656 |
| low_order_coupled_odd_even_map | round6p1_shared_coefficient_map_candidate_low_order_coupled_odd_even_map.npz | 166659 |
| fitted_linear_map_3x3 | round6p1_shared_coefficient_map_candidate_fitted_linear_map_3x3.npz | 1.3587e+09 |

## Promoted shared-map runtime bundles

| case | model | artifact |
|---|---|---|
| sphere_low_na_low_contrast | low_order_coupled_odd_even_map | round6p1_sphere_low_na_low_contrast_shared_map_promoted_low_order_coupled_odd_even_map_coefficient_bundle.npz |
| mild_shape_medium_tilt | low_order_coupled_odd_even_map | round6p1_mild_shape_medium_tilt_shared_map_promoted_low_order_coupled_odd_even_map_coefficient_bundle.npz |
| failure_domain_high_tilt_high_contrast | low_order_coupled_odd_even_map | round6p1_failure_domain_high_tilt_high_contrast_shared_map_promoted_low_order_coupled_odd_even_map_coefficient_bundle.npz |
| mild_shape_higher_na_transition | low_order_coupled_odd_even_map | round6p1_mild_shape_higher_na_transition_shared_map_promoted_low_order_coupled_odd_even_map_coefficient_bundle.npz |
| high_contrast_lower_tilt_transition | low_order_coupled_odd_even_map | round6p1_high_contrast_lower_tilt_transition_shared_map_promoted_low_order_coupled_odd_even_map_coefficient_bundle.npz |

## Pairwise fitted-linear map distances

| case A | case B | normalized Frobenius distance |
|---|---|---:|
| sphere_low_na_low_contrast | mild_shape_medium_tilt | 6.08318 |
| sphere_low_na_low_contrast | failure_domain_high_tilt_high_contrast | 52.5849 |
| sphere_low_na_low_contrast | mild_shape_higher_na_transition | 13.4186 |
| sphere_low_na_low_contrast | high_contrast_lower_tilt_transition | 67.9036 |
| mild_shape_medium_tilt | failure_domain_high_tilt_high_contrast | 9.80147 |
| mild_shape_medium_tilt | mild_shape_higher_na_transition | 1.31796 |
| mild_shape_medium_tilt | high_contrast_lower_tilt_transition | 12.2743 |
| failure_domain_high_tilt_high_contrast | mild_shape_higher_na_transition | 1.21287 |
| failure_domain_high_tilt_high_contrast | high_contrast_lower_tilt_transition | 0.403691 |
| mild_shape_higher_na_transition | high_contrast_lower_tilt_transition | 5.78111 |

## identity_slice_projected_rendered_basis

Mean peakline delta `2.5`, mean image L2 `0.855074`, mean raw coeff residual `1.63379`.

| held-out case | image L2 | peakline delta | raw coeff residual | orth coeff residual | improves identity peakline | improves identity image L2 |
|---|---:|---:|---:|---:|---|---|
| sphere_low_na_low_contrast | 0.122935 | 2 | 1.58711 | 20.9445 | no | no |
| mild_shape_medium_tilt | 0.587814 | 2 | 1.81057 | 29.8743 | no | no |
| failure_domain_high_tilt_high_contrast | 1.17944 | 3 | 1.51825 | 6.40837 | no | no |
| mild_shape_higher_na_transition | 1.25862 | 2.5 | 1.80304 | 17.0613 | no | no |
| high_contrast_lower_tilt_transition | 1.12656 | 3 | 1.44999 | 5.78421 | no | no |

## shared_complex_scale_map

Mean peakline delta `2.5`, mean image L2 `0.855074`, mean raw coeff residual `0.159503`.

| held-out case | image L2 | peakline delta | raw coeff residual | orth coeff residual | improves identity peakline | improves identity image L2 |
|---|---:|---:|---:|---:|---|---|
| sphere_low_na_low_contrast | 0.122935 | 2 | 0.157214 | 8.16107 | no | yes |
| mild_shape_medium_tilt | 0.587814 | 2 | 0.146684 | 11.739 | no | no |
| failure_domain_high_tilt_high_contrast | 1.17944 | 3 | 0.172456 | 2.83465 | no | yes |
| mild_shape_higher_na_transition | 1.25862 | 2.5 | 0.14296 | 6.67911 | no | yes |
| high_contrast_lower_tilt_transition | 1.12656 | 3 | 0.178202 | 2.59757 | no | no |

## componentwise_complex_scale_map

Mean peakline delta `0.4`, mean image L2 `0.330856`, mean raw coeff residual `0.159503`.

| held-out case | image L2 | peakline delta | raw coeff residual | orth coeff residual | improves identity peakline | improves identity image L2 |
|---|---:|---:|---:|---:|---|---|
| sphere_low_na_low_contrast | 0.0690712 | 0 | 0.157214 | 0.926457 | yes | yes |
| mild_shape_medium_tilt | 0.638876 | 2 | 0.146684 | 1.05993 | no | no |
| failure_domain_high_tilt_high_contrast | 0.349592 | 0 | 0.172456 | 0.369404 | yes | yes |
| mild_shape_higher_na_transition | 0.142942 | 0 | 0.14296 | 0.31143 | yes | yes |
| high_contrast_lower_tilt_transition | 0.453798 | 0 | 0.178202 | 0.459134 | yes | yes |

## low_order_coupled_odd_even_map

Mean peakline delta `0`, mean image L2 `0.19553`, mean raw coeff residual `0.141966`.

| held-out case | image L2 | peakline delta | raw coeff residual | orth coeff residual | improves identity peakline | improves identity image L2 |
|---|---:|---:|---:|---:|---|---|
| sphere_low_na_low_contrast | 0.0937458 | 0 | 0.179844 | 1.55488 | yes | yes |
| mild_shape_medium_tilt | 0.389046 | 0 | 0.135004 | 0.674518 | yes | yes |
| failure_domain_high_tilt_high_contrast | 0.0409396 | 0 | 0.130522 | 0.156118 | yes | yes |
| mild_shape_higher_na_transition | 0.227478 | 0 | 0.1466 | 0.376254 | yes | yes |
| high_contrast_lower_tilt_transition | 0.226439 | 0 | 0.117862 | 0.265276 | yes | yes |

## fitted_linear_map_3x3

Mean peakline delta `2.4`, mean image L2 `0.164841`, mean raw coeff residual `0.133679`.

| held-out case | image L2 | peakline delta | raw coeff residual | orth coeff residual | improves identity peakline | improves identity image L2 |
|---|---:|---:|---:|---:|---|---|
| sphere_low_na_low_contrast | 0.112863 | 0 | 0.164556 | 3.27866 | yes | yes |
| mild_shape_medium_tilt | 0.27274 | 0 | 0.138434 | 0.532246 | yes | yes |
| failure_domain_high_tilt_high_contrast | 0.0641794 | 6 | 0.11342 | 0.196044 | no | yes |
| mild_shape_higher_na_transition | 0.115607 | 0 | 0.121783 | 0.388745 | yes | yes |
| high_contrast_lower_tilt_transition | 0.258814 | 6 | 0.130202 | 0.287525 | no | yes |
