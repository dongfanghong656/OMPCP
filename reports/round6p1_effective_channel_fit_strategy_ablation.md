# Round 6p1 Effective-Channel Fit Strategy Ablation

Recommended next action: `joint_low_order_fit_not_yet_decisive`

## sphere_low_na_low_contrast
Sphere, low NA, low contrast. This should be the easiest alignment case.

| Strategy | fit residual model | fit residual max | even fit residual max | low-order fit residual max | peakline_x_delta_um | image_relative_l2 | centroid_opd_delta_um | raw_peak_relative_delta | a1_vs_D1 residual | a2_vs_C2 residual | shared_scale residual |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| split_even_odd | even | 0.668403 | 0.668403 | 0.668403 | 2 | 0.123363 | 7.27332e-05 | 492.16 | 0.168665 | 0.14229 | 0.14229 |
| joint_low_order | low_order | 0.668403 | 0.668403 | 0.668403 | 2 | 0.123363 | 7.27332e-05 | 492.16 | 0.168665 | 0.14229 | 0.14229 |

## mild_shape_medium_tilt
Small deformation with medium tilt. This is where bridge and asymptotic should start to separate.

| Strategy | fit residual model | fit residual max | even fit residual max | low-order fit residual max | peakline_x_delta_um | image_relative_l2 | centroid_opd_delta_um | raw_peak_relative_delta | a1_vs_D1 residual | a2_vs_C2 residual | shared_scale residual |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| split_even_odd | even | 0.670127 | 0.670127 | 0.670127 | 2 | 0.589748 | 0.0965991 | 698.025 | 0.251635 | 0.133202 | 0.133202 |
| joint_low_order | low_order | 0.670127 | 0.670127 | 0.670127 | 2 | 0.589748 | 0.0965991 | 698.025 | 0.251635 | 0.133202 | 0.133202 |

## failure_domain_high_tilt_high_contrast
Larger tilt and higher contrast. This should sit inside the asymptotic failure domain.

| Strategy | fit residual model | fit residual max | even fit residual max | low-order fit residual max | peakline_x_delta_um | image_relative_l2 | centroid_opd_delta_um | raw_peak_relative_delta | a1_vs_D1 residual | a2_vs_C2 residual | shared_scale residual |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| split_even_odd | even | 0.669526 | 0.669526 | 0.669521 | 3 | 1.16728 | 0.0761385 | 31.5861 | 0.741018 | 0.144464 | 0.144464 |
| joint_low_order | low_order | 0.669521 | 0.669526 | 0.669521 | 3 | 1.16728 | 0.0761385 | 31.5861 | 0.741018 | 0.144464 | 0.144464 |
