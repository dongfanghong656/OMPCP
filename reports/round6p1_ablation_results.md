# Round 6p1 A/B Experiments

## sphere_low_na_low_contrast
Sphere, low NA, low contrast. This should be the easiest alignment case.

### second_order_model
| variant | peakline_x_um | centroid_opd_um | fwhm_opd_um | psr_db | raw_peak_intensity | image_relative_l2_vs_bridge | peakline_x_delta_um_vs_bridge | raw_image_relative_l2_vs_bridge | raw_peak_relative_delta_vs_bridge |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| tensor_closure | 0 | -0.00704412 | 5.7862 | -26.5176 | 6.79032e-08 | 0.120516 | 2 | 59.5112 | 55.5663 |
| slice_projected_raw | 0 | -0.00704409 | 5.7862 | -26.5176 | 2.5307e-06 | 0.122532 | 2 | 2310.74 | 2107.18 |
| slice_projected_scaled | 0 | -0.00704409 | 5.7862 | -26.5176 | 1.09165e-09 | 0.122532 | 2 | 0.0719922 | 0.0906117 |
| directional_field_expansion_raw | 0 | -0.00704412 | 5.7862 | -26.5176 | 6.79032e-08 | 0.120035 | 2 | 59.9671 | 55.5663 |
| directional_field_expansion_scaled | 0 | -0.00704412 | 5.7862 | -26.5176 | 1.11043e-09 | 0.120035 | 2 | 0.0880266 | 0.0749644 |
| directional_field_expansion_first_order_raw | 0 | -0.00704409 | 5.7862 | -26.5176 | 5.91998e-07 | 0.123363 | 2 | 541.157 | 492.16 |
| directional_field_expansion_first_order_scaled | 0 | -0.00704409 | 5.7862 | -26.5176 | 1.08893e-09 | 0.123363 | 2 | 0.0697086 | 0.0928776 |

### mu2_wavelength_model
| variant | peakline_x_um | centroid_opd_um | fwhm_opd_um | psr_db | raw_peak_intensity | image_relative_l2_vs_bridge | peakline_x_delta_um_vs_bridge | raw_image_relative_l2_vs_bridge | raw_peak_relative_delta_vs_bridge |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| frozen_at_lambda0 | 0 | -0.00704412 | 5.7862 | -26.5176 | 6.79032e-08 | 0.120516 | 2 | 59.5112 | 55.5663 |
| endpoint_refit | 0 | -0.00704412 | 5.7862 | -26.5176 | 6.79032e-08 | 0.120528 | 2 | 59.5058 | 55.5663 |

### lateral_shift_model
| variant | peakline_x_um | centroid_opd_um | fwhm_opd_um | psr_db | raw_peak_intensity | image_relative_l2_vs_bridge | peakline_x_delta_um_vs_bridge | raw_image_relative_l2_vs_bridge | raw_peak_relative_delta_vs_bridge |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| none | 0 | -0.00704412 | 5.7862 | -26.5176 | 6.79032e-08 | 0.120516 | 2 | 59.5112 | 55.5663 |
| first_order_envelope_only_interp | 0 | -0.00704412 | 5.7862 | -26.5176 | 6.79032e-08 | 0.210884 | 2 | 58.8999 | 55.5663 |
| first_order_shift_envelope_and_mu2_interp | 0 | -0.00704412 | 5.7862 | -26.5176 | 6.79032e-08 | 0.210884 | 2 | 58.8999 | 55.5663 |
| first_order_shift_envelope_and_mu2_analytic_gaussian | 0 | -0.00704412 | 5.7862 | -26.5176 | 6.79032e-08 | 0.205431 | 2 | 58.8999 | 55.5663 |
| first_order_shift_envelope_and_mu2_interp_edge_hold | 0 | -0.00704412 | 5.7862 | -26.5176 | 6.79032e-08 | 0.120516 | 2 | 59.5112 | 55.5663 |

## mild_shape_medium_tilt
Small deformation with medium tilt. This is where bridge and asymptotic should start to separate.

### second_order_model
| variant | peakline_x_um | centroid_opd_um | fwhm_opd_um | psr_db | raw_peak_intensity | image_relative_l2_vs_bridge | peakline_x_delta_um_vs_bridge | raw_image_relative_l2_vs_bridge | raw_peak_relative_delta_vs_bridge |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| tensor_closure | 0 | -0.431372 | 5.89527 | -26.5956 | 2.19919e-05 | 0.567775 | 2 | 108.407 | 81.6895 |
| slice_projected_raw | 0 | -0.426245 | 5.895 | -26.5668 | 0.000788271 | 0.584883 | 2 | 4273.24 | 2962.9 |
| slice_projected_scaled | 0 | -0.426245 | 5.895 | -26.5668 | 1.71709e-07 | 0.584883 | 2 | 0.315334 | 0.354376 |
| directional_field_expansion_raw | 0 | -0.431372 | 5.89527 | -26.5956 | 2.19919e-05 | 0.569105 | 2 | 111.095 | 81.6895 |
| directional_field_expansion_scaled | 0 | -0.431372 | 5.89527 | -26.5956 | 1.81784e-07 | 0.569105 | 2 | 0.375307 | 0.316492 |
| directional_field_expansion_first_order_raw | 0 | -0.427333 | 5.89506 | -26.5729 | 0.000185911 | 0.589748 | 2 | 1016.23 | 698.025 |
| directional_field_expansion_first_order_scaled | 0 | -0.427333 | 5.89506 | -26.5729 | 1.70307e-07 | 0.589748 | 2 | 0.307754 | 0.359644 |

### mu2_wavelength_model
| variant | peakline_x_um | centroid_opd_um | fwhm_opd_um | psr_db | raw_peak_intensity | image_relative_l2_vs_bridge | peakline_x_delta_um_vs_bridge | raw_image_relative_l2_vs_bridge | raw_peak_relative_delta_vs_bridge |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| frozen_at_lambda0 | 0 | -0.431372 | 5.89527 | -26.5956 | 2.19919e-05 | 0.567775 | 2 | 108.407 | 81.6895 |
| endpoint_refit | 0 | -0.431372 | 5.89527 | -26.5956 | 2.19919e-05 | 0.567803 | 2 | 108.374 | 81.6895 |

### lateral_shift_model
| variant | peakline_x_um | centroid_opd_um | fwhm_opd_um | psr_db | raw_peak_intensity | image_relative_l2_vs_bridge | peakline_x_delta_um_vs_bridge | raw_image_relative_l2_vs_bridge | raw_peak_relative_delta_vs_bridge |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| none | 0 | -0.431372 | 5.89527 | -26.5956 | 2.19919e-05 | 0.567775 | 2 | 108.407 | 81.6895 |
| first_order_envelope_only_interp | 0 | -0.431372 | 5.89527 | -26.5956 | 2.19919e-05 | 0.608581 | 2 | 107.794 | 81.6895 |
| first_order_shift_envelope_and_mu2_interp | 0 | -0.431372 | 5.89527 | -26.5956 | 2.19919e-05 | 0.608581 | 2 | 107.794 | 81.6895 |
| first_order_shift_envelope_and_mu2_analytic_gaussian | 0 | -0.431372 | 5.89527 | -26.5956 | 2.19919e-05 | 0.606224 | 2 | 107.794 | 81.6895 |
| first_order_shift_envelope_and_mu2_interp_edge_hold | 0 | -0.431372 | 5.89527 | -26.5956 | 2.19919e-05 | 0.567775 | 2 | 108.407 | 81.6895 |

## failure_domain_high_tilt_high_contrast
Larger tilt and higher contrast. This should sit inside the asymptotic failure domain.

### second_order_model
| variant | peakline_x_um | centroid_opd_um | fwhm_opd_um | psr_db | raw_peak_intensity | image_relative_l2_vs_bridge | peakline_x_delta_um_vs_bridge | raw_image_relative_l2_vs_bridge | raw_peak_relative_delta_vs_bridge |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| tensor_closure | 0 | -2.29819 | 5.24478 | -24.374 | 7.15513e-06 | 1.17125 | 3 | 3.63451 | 2.63394 |
| slice_projected_raw | 0 | -2.27356 | 5.25063 | -24.5179 | 0.000276378 | 1.1404 | 3 | 189.777 | 139.367 |
| slice_projected_scaled | 0 | -2.27356 | 5.25063 | -24.5179 | 9.95404e-07 | 1.1404 | 3 | 0.832027 | 0.494455 |
| directional_field_expansion_raw | 0 | -2.29819 | 5.24478 | -24.374 | 7.15513e-06 | 1.14712 | 3 | 3.75123 | 2.63394 |
| directional_field_expansion_scaled | 0 | -2.29819 | 5.24478 | -24.374 | 3.59529e-07 | 1.14712 | 3 | 0.933673 | 0.817403 |
| directional_field_expansion_first_order_raw | 0 | -2.27858 | 5.24936 | -24.4889 | 6.41612e-05 | 1.16728 | 3 | 44.3786 | 31.5861 |
| directional_field_expansion_first_order_scaled | 0 | -2.27858 | 5.24936 | -24.4889 | 9.66345e-07 | 1.16728 | 3 | 0.838356 | 0.509214 |

### mu2_wavelength_model
| variant | peakline_x_um | centroid_opd_um | fwhm_opd_um | psr_db | raw_peak_intensity | image_relative_l2_vs_bridge | peakline_x_delta_um_vs_bridge | raw_image_relative_l2_vs_bridge | raw_peak_relative_delta_vs_bridge |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| frozen_at_lambda0 | 0 | -2.29819 | 5.24478 | -24.374 | 7.15513e-06 | 1.17125 | 3 | 3.63451 | 2.63394 |
| endpoint_refit | 0 | -2.29819 | 5.24478 | -24.374 | 7.15513e-06 | 1.17011 | 3 | 3.6318 | 2.63394 |

### lateral_shift_model
| variant | peakline_x_um | centroid_opd_um | fwhm_opd_um | psr_db | raw_peak_intensity | image_relative_l2_vs_bridge | peakline_x_delta_um_vs_bridge | raw_image_relative_l2_vs_bridge | raw_peak_relative_delta_vs_bridge |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| none | 0 | -2.29819 | 5.24478 | -24.374 | 7.15513e-06 | 1.17125 | 3 | 3.63451 | 2.63394 |
| first_order_envelope_only_interp | 0 | -2.29819 | 5.24478 | -24.374 | 7.15513e-06 | 1.17935 | 3 | 3.64198 | 2.63394 |
| first_order_shift_envelope_and_mu2_interp | 0 | -2.29819 | 5.24478 | -24.374 | 7.15513e-06 | 1.17935 | 3 | 3.64198 | 2.63394 |
| first_order_shift_envelope_and_mu2_analytic_gaussian | 0 | -2.29819 | 5.24478 | -24.374 | 7.15513e-06 | 1.17859 | 3 | 3.64113 | 2.63394 |
| first_order_shift_envelope_and_mu2_interp_edge_hold | 0 | -2.29819 | 5.24478 | -24.374 | 7.15513e-06 | 1.17125 | 3 | 3.63451 | 2.63394 |

