# Round 6p1 Error Attribution

## sphere_low_na_low_contrast
Sphere, low NA, low contrast. This should be the easiest alignment case.

| mode | peakline_x_um | peak_opd_um | centroid_opd_um | fwhm_opd_um | psr_db | sidelobe_energy_fraction | raw_peak_intensity | image_relative_l2_vs_bridge | peakline_x_delta_um_vs_bridge | raw_image_relative_l2_vs_bridge | raw_peak_relative_delta_vs_bridge |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| full_na_scalar_fixed_basis | 0 | 0 | -0.0070569 | 5.77492 | -26.6164 | 0.000500441 | 5.09733e-05 | 0.125574 | 2 | 46998.4 | 42462 |
| vector_pupil_overlap_bridge | 2 | 0 | -0.00697136 | 5.78362 | -26.5403 | 0.000509853 | 1.20042e-09 | 0 | 0 | 0 | 0 |
| low_na_asymptotic | 0 | 0 | -0.00704412 | 5.7862 | -26.5176 | 0.000512611 | 6.79032e-08 | 0.120516 | 2 | 59.5112 | 55.5663 |

Asymptotic dominant error bucket: `lateral_shift` (severity 4).

## mild_shape_medium_tilt
Small deformation with medium tilt. This is where bridge and asymptotic should start to separate.

| mode | peakline_x_um | peak_opd_um | centroid_opd_um | fwhm_opd_um | psr_db | sidelobe_energy_fraction | raw_peak_intensity | image_relative_l2_vs_bridge | peakline_x_delta_um_vs_bridge | raw_image_relative_l2_vs_bridge | raw_peak_relative_delta_vs_bridge |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| full_na_scalar_fixed_basis | 0 | -0.42 | -0.432364 | 5.89533 | -26.6012 | 0.000483363 | 0.000140332 | 0.609078 | 2 | 791.285 | 526.647 |
| vector_pupil_overlap_bridge | 2 | -0.36 | -0.330734 | 5.87207 | -26.1888 | 0.000501301 | 2.65957e-07 | 0 | 0 | 0 | 0 |
| low_na_asymptotic | 0 | -0.42 | -0.431372 | 5.89527 | -26.5956 | 0.000483362 | 2.19919e-05 | 0.567775 | 2 | 108.407 | 81.6895 |

Asymptotic dominant error bucket: `lateral_shift` (severity 4).

## failure_domain_high_tilt_high_contrast
Larger tilt and higher contrast. This should sit inside the asymptotic failure domain.

| mode | peakline_x_um | peak_opd_um | centroid_opd_um | fwhm_opd_um | psr_db | sidelobe_energy_fraction | raw_peak_intensity | image_relative_l2_vs_bridge | peakline_x_delta_um_vs_bridge | raw_image_relative_l2_vs_bridge | raw_peak_relative_delta_vs_bridge |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| full_na_scalar_fixed_basis | 0 | -2.13333 | -2.3054 | 5.24264 | -23.9469 | 0.00118648 | 4.48331e-05 | 1.13338 | 3 | 36.5679 | 21.7698 |
| vector_pupil_overlap_bridge | -3 | -2.06667 | -2.20244 | 5.28227 | -24.4734 | 0.000691303 | 1.96897e-06 | 0 | 0 | 0 | 0 |
| low_na_asymptotic | 0 | -2.13333 | -2.29819 | 5.24478 | -24.374 | 0.00109214 | 7.15513e-06 | 1.17125 | 3 | 3.63451 | 2.63394 |

Asymptotic dominant error bucket: `lateral_shift` (severity 6).

