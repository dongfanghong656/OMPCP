# Round 6p1 Measurement-Protocol Bias

These summaries now compare two measurement-layer routes on top of the solver stack:

- `solver_output_peak_slice_adapter`: direct measurement on reconstructed solver output.
- `fd_oct_reconstruction`: minimal FD-OCT interferogram + k-linearization + IFFT reconstruction built from solver spectral sample-arm fields.

This is still not a full measurement-grade OCT simulator, but the FD-OCT route is closer to the intended measurement chain than direct peak-slice extraction alone.

## sphere_low_na_low_contrast
Sphere, low NA, low contrast. This should be the easiest alignment case.

### measurement_pipeline_mode = fd_oct_reconstruction

#### extraction_mode = self_peak

| mode | measured_lateral_peak_x_um | measured_lateral_fwhm_um | measured_axial_fwhm_opd_um | measured_psr_db | measured_psr_definition | measured_sidelobe_to_main_db | measured_main_to_sidelobe_rejection_db | raw_peak_intensity | measured_peak_shift_um_vs_bridge | measured_lateral_width_bias_um_vs_bridge | measured_axial_width_bias_um_vs_bridge | measured_sidelobe_distortion_vs_bridge | extraction_plane_opd_um |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| full_na_scalar_fixed_basis | 0 | 4 | 6.46551 | 5.48184 | main_to_sidelobe_rejection_db | -5.48184 | 5.48184 | 6.11036e-06 | -2 | 0 | 0.0019466 | 0.000170359 | 0 |
| vector_pupil_overlap_bridge | 2 | 4 | 6.46357 | 5.48563 | main_to_sidelobe_rejection_db | -5.48563 | 5.48563 | 1.70849e-08 | 0 | 0 | 0 | 0 | 0 |
| low_na_separable_baseline | 0 | 4 | 6.43147 | 5.54891 | main_to_sidelobe_rejection_db | -5.54891 | 5.54891 | 4.3119e-08 | -2 | 0 | -0.032092 | -0.00283695 | 0 |
| low_na_asymptotic | 0 | 4 | 6.46551 | 5.48184 | main_to_sidelobe_rejection_db | -5.48184 | 5.48184 | 9.65568e-07 | -2 | 0 | 0.00194708 | 0.000170402 | 0 |

#### extraction_mode = reference_peak_plane

| mode | measured_lateral_peak_x_um | measured_lateral_fwhm_um | measured_axial_fwhm_opd_um | measured_psr_db | measured_psr_definition | measured_sidelobe_to_main_db | measured_main_to_sidelobe_rejection_db | raw_peak_intensity | measured_peak_shift_um_vs_bridge | measured_lateral_width_bias_um_vs_bridge | measured_axial_width_bias_um_vs_bridge | measured_sidelobe_distortion_vs_bridge | extraction_plane_opd_um |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| full_na_scalar_fixed_basis | 0 | 4 | 6.46551 | 5.48184 | main_to_sidelobe_rejection_db | -5.48184 | 5.48184 | 6.11036e-06 | -2 | 0 | 0.0019466 | 0.000170359 | 0 |
| vector_pupil_overlap_bridge | 2 | 4 | 6.46357 | 5.48563 | main_to_sidelobe_rejection_db | -5.48563 | 5.48563 | 1.70849e-08 | 0 | 0 | 0 | 0 | 0 |
| low_na_separable_baseline | 0 | 4 | 6.43147 | 5.54891 | main_to_sidelobe_rejection_db | -5.54891 | 5.54891 | 4.3119e-08 | -2 | 0 | -0.032092 | -0.00283695 | 0 |
| low_na_asymptotic | 0 | 4 | 6.46551 | 5.48184 | main_to_sidelobe_rejection_db | -5.48184 | 5.48184 | 9.65568e-07 | -2 | 0 | 0.00194708 | 0.000170402 | 0 |

### measurement_pipeline_mode = solver_output_peak_slice_adapter

#### extraction_mode = self_peak

| mode | measured_lateral_peak_x_um | measured_lateral_fwhm_um | measured_axial_fwhm_opd_um | measured_psr_db | measured_psr_definition | measured_sidelobe_to_main_db | measured_main_to_sidelobe_rejection_db | raw_peak_intensity | measured_peak_shift_um_vs_bridge | measured_lateral_width_bias_um_vs_bridge | measured_axial_width_bias_um_vs_bridge | measured_sidelobe_distortion_vs_bridge | extraction_plane_opd_um |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| full_na_scalar_fixed_basis | 0 | 4 | 5.7862 | -26.5176 | sidelobe_to_main_db | -26.5176 | 26.5176 | 4.29708e-07 | -2 | 0 | 0.00258013 | 2.7565e-06 | 0 |
| vector_pupil_overlap_bridge | 2 | 4 | 5.78362 | -26.5403 | sidelobe_to_main_db | -26.5403 | 26.5403 | 1.20042e-09 | 0 | 0 | 0 | 0 | 0 |
| low_na_separable_baseline | 0 | 4 | 5.77492 | -26.6164 | sidelobe_to_main_db | -26.6164 | 26.6164 | 5.21196e-06 | -2 | 0 | -0.00869905 | -9.41158e-06 | 0 |
| low_na_asymptotic | 0 | 4 | 5.7862 | -26.5176 | sidelobe_to_main_db | -26.5176 | 26.5176 | 6.79032e-08 | -2 | 0 | 0.00258077 | 2.75717e-06 | 0 |

#### extraction_mode = reference_peak_plane

| mode | measured_lateral_peak_x_um | measured_lateral_fwhm_um | measured_axial_fwhm_opd_um | measured_psr_db | measured_psr_definition | measured_sidelobe_to_main_db | measured_main_to_sidelobe_rejection_db | raw_peak_intensity | measured_peak_shift_um_vs_bridge | measured_lateral_width_bias_um_vs_bridge | measured_axial_width_bias_um_vs_bridge | measured_sidelobe_distortion_vs_bridge | extraction_plane_opd_um |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| full_na_scalar_fixed_basis | 0 | 4 | 5.7862 | -26.5176 | sidelobe_to_main_db | -26.5176 | 26.5176 | 4.29708e-07 | -2 | 0 | 0.00258013 | 2.7565e-06 | 0 |
| vector_pupil_overlap_bridge | 2 | 4 | 5.78362 | -26.5403 | sidelobe_to_main_db | -26.5403 | 26.5403 | 1.20042e-09 | 0 | 0 | 0 | 0 | 0 |
| low_na_separable_baseline | 0 | 4 | 5.77492 | -26.6164 | sidelobe_to_main_db | -26.6164 | 26.6164 | 5.21196e-06 | -2 | 0 | -0.00869905 | -9.41158e-06 | 0 |
| low_na_asymptotic | 0 | 4 | 5.7862 | -26.5176 | sidelobe_to_main_db | -26.5176 | 26.5176 | 6.79032e-08 | -2 | 0 | 0.00258077 | 2.75717e-06 | 0 |

## mild_shape_medium_tilt
Small deformation with medium tilt. This is where bridge and asymptotic should start to separate.

### measurement_pipeline_mode = fd_oct_reconstruction

#### extraction_mode = self_peak

| mode | measured_lateral_peak_x_um | measured_lateral_fwhm_um | measured_axial_fwhm_opd_um | measured_psr_db | measured_psr_definition | measured_sidelobe_to_main_db | measured_main_to_sidelobe_rejection_db | raw_peak_intensity | measured_peak_shift_um_vs_bridge | measured_lateral_width_bias_um_vs_bridge | measured_axial_width_bias_um_vs_bridge | measured_sidelobe_distortion_vs_bridge | extraction_plane_opd_um |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| full_na_scalar_fixed_basis | 0 | 4 | 6.86825 | 4.8175 | main_to_sidelobe_rejection_db | -4.8175 | 4.8175 | 0.000545605 | -2 | 0 | 0.244272 | 0.0187361 | 0 |
| vector_pupil_overlap_bridge | 2 | 4 | 6.62398 | 5.22313 | main_to_sidelobe_rejection_db | -5.22313 | 5.22313 | 2.89602e-06 | 0 | 0 | 0 | 0 | 0 |
| low_na_separable_baseline | 0 | 4 | 6.8684 | 4.81727 | main_to_sidelobe_rejection_db | -4.81727 | 4.81727 | 6.21507e-05 | -2 | 0 | 0.244427 | 0.018747 | 0 |
| low_na_asymptotic | 0 | 4 | 6.86474 | 4.82294 | main_to_sidelobe_rejection_db | -4.82294 | 4.82294 | 8.63658e-05 | -2 | 0 | 0.24076 | 0.0184834 | 0 |

#### extraction_mode = reference_peak_plane

| mode | measured_lateral_peak_x_um | measured_lateral_fwhm_um | measured_axial_fwhm_opd_um | measured_psr_db | measured_psr_definition | measured_sidelobe_to_main_db | measured_main_to_sidelobe_rejection_db | raw_peak_intensity | measured_peak_shift_um_vs_bridge | measured_lateral_width_bias_um_vs_bridge | measured_axial_width_bias_um_vs_bridge | measured_sidelobe_distortion_vs_bridge | extraction_plane_opd_um |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| full_na_scalar_fixed_basis | 0 | 4 | 6.86825 | 4.8175 | main_to_sidelobe_rejection_db | -4.8175 | 4.8175 | 0.000545605 | -2 | 0 | 0.244272 | 0.0187361 | 0 |
| vector_pupil_overlap_bridge | 2 | 4 | 6.62398 | 5.22313 | main_to_sidelobe_rejection_db | -5.22313 | 5.22313 | 2.89602e-06 | 0 | 0 | 0 | 0 | 0 |
| low_na_separable_baseline | 0 | 4 | 6.8684 | 4.81727 | main_to_sidelobe_rejection_db | -4.81727 | 4.81727 | 6.21507e-05 | -2 | 0 | 0.244427 | 0.018747 | 0 |
| low_na_asymptotic | 0 | 4 | 6.86474 | 4.82294 | main_to_sidelobe_rejection_db | -4.82294 | 4.82294 | 8.63658e-05 | -2 | 0 | 0.24076 | 0.0184834 | 0 |

### measurement_pipeline_mode = solver_output_peak_slice_adapter

#### extraction_mode = self_peak

| mode | measured_lateral_peak_x_um | measured_lateral_fwhm_um | measured_axial_fwhm_opd_um | measured_psr_db | measured_psr_definition | measured_sidelobe_to_main_db | measured_main_to_sidelobe_rejection_db | raw_peak_intensity | measured_peak_shift_um_vs_bridge | measured_lateral_width_bias_um_vs_bridge | measured_axial_width_bias_um_vs_bridge | measured_sidelobe_distortion_vs_bridge | extraction_plane_opd_um |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| full_na_scalar_fixed_basis | 0 | 4 | 5.89533 | -26.6012 | sidelobe_to_main_db | -26.6012 | 26.6012 | 0.000140332 | -2 | 2.62783 | 0.0232592 | -1.79383e-05 | -0.42 |
| vector_pupil_overlap_bridge | 2 | 1.37217 | 5.87207 | -26.1888 | sidelobe_to_main_db | -26.1888 | 26.1888 | 2.65957e-07 | 0 | 0 | 0 | 0 | -0.36 |
| low_na_separable_baseline | 0 | 4 | 5.89532 | -26.6016 | sidelobe_to_main_db | -26.6016 | 26.6016 | 1.59898e-05 | -2 | 2.62783 | 0.023251 | -1.79437e-05 | -0.42 |
| low_na_asymptotic | 0 | 4 | 5.89527 | -26.5956 | sidelobe_to_main_db | -26.5956 | 26.5956 | 2.19919e-05 | -2 | 2.62783 | 0.0231991 | -1.79398e-05 | -0.42 |

#### extraction_mode = reference_peak_plane

| mode | measured_lateral_peak_x_um | measured_lateral_fwhm_um | measured_axial_fwhm_opd_um | measured_psr_db | measured_psr_definition | measured_sidelobe_to_main_db | measured_main_to_sidelobe_rejection_db | raw_peak_intensity | measured_peak_shift_um_vs_bridge | measured_lateral_width_bias_um_vs_bridge | measured_axial_width_bias_um_vs_bridge | measured_sidelobe_distortion_vs_bridge | extraction_plane_opd_um |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| full_na_scalar_fixed_basis | 0 | 4 | 5.89533 | -26.6012 | sidelobe_to_main_db | -26.6012 | 26.6012 | 0.000140332 | -2 | 2.62783 | 0.0232592 | -1.79383e-05 | -0.36 |
| vector_pupil_overlap_bridge | 2 | 1.37217 | 5.87207 | -26.1888 | sidelobe_to_main_db | -26.1888 | 26.1888 | 2.65957e-07 | 0 | 0 | 0 | 0 | -0.36 |
| low_na_separable_baseline | 0 | 4 | 5.89532 | -26.6016 | sidelobe_to_main_db | -26.6016 | 26.6016 | 1.59898e-05 | -2 | 2.62783 | 0.023251 | -1.79437e-05 | -0.36 |
| low_na_asymptotic | 0 | 4 | 5.89527 | -26.5956 | sidelobe_to_main_db | -26.5956 | 26.5956 | 2.19919e-05 | -2 | 2.62783 | 0.0231991 | -1.79398e-05 | -0.36 |

## failure_domain_high_tilt_high_contrast
Larger tilt and higher contrast. This should sit inside the asymptotic failure domain.

### measurement_pipeline_mode = fd_oct_reconstruction

#### extraction_mode = self_peak

| mode | measured_lateral_peak_x_um | measured_lateral_fwhm_um | measured_axial_fwhm_opd_um | measured_psr_db | measured_psr_definition | measured_sidelobe_to_main_db | measured_main_to_sidelobe_rejection_db | raw_peak_intensity | measured_peak_shift_um_vs_bridge | measured_lateral_width_bias_um_vs_bridge | measured_axial_width_bias_um_vs_bridge | measured_sidelobe_distortion_vs_bridge | extraction_plane_opd_um |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| full_na_scalar_fixed_basis | 0 | 5.598 | 7.02759 | 4.57204 | main_to_sidelobe_rejection_db | -4.57204 | 4.57204 | 0.000395438 | 3 | 4.70347 | -0.0517354 | -0.00318078 | 0 |
| vector_pupil_overlap_bridge | -3 | 0.894527 | 7.07933 | 4.50057 | main_to_sidelobe_rejection_db | -4.50057 | 4.50057 | 1.75491e-05 | 0 | 0 | 0 | 0 | 0 |
| low_na_separable_baseline | 0 | 3.9547 | 7.02647 | 4.57366 | main_to_sidelobe_rejection_db | -4.57366 | 4.57366 | 4.52719e-05 | 3 | 3.06017 | -0.0528622 | -0.00326228 | 0 |
| low_na_asymptotic | 0 | 2.22801 | 7.02479 | 4.57613 | main_to_sidelobe_rejection_db | -4.57613 | 4.57613 | 6.32566e-05 | 3 | 1.33348 | -0.054539 | -0.00340238 | 0 |

#### extraction_mode = reference_peak_plane

| mode | measured_lateral_peak_x_um | measured_lateral_fwhm_um | measured_axial_fwhm_opd_um | measured_psr_db | measured_psr_definition | measured_sidelobe_to_main_db | measured_main_to_sidelobe_rejection_db | raw_peak_intensity | measured_peak_shift_um_vs_bridge | measured_lateral_width_bias_um_vs_bridge | measured_axial_width_bias_um_vs_bridge | measured_sidelobe_distortion_vs_bridge | extraction_plane_opd_um |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| full_na_scalar_fixed_basis | 0 | 5.598 | 7.02759 | 4.57204 | main_to_sidelobe_rejection_db | -4.57204 | 4.57204 | 0.000395438 | 3 | 4.70347 | -0.0517354 | -0.00318078 | 0 |
| vector_pupil_overlap_bridge | -3 | 0.894527 | 7.07933 | 4.50057 | main_to_sidelobe_rejection_db | -4.50057 | 4.50057 | 1.75491e-05 | 0 | 0 | 0 | 0 | 0 |
| low_na_separable_baseline | 0 | 3.9547 | 7.02647 | 4.57366 | main_to_sidelobe_rejection_db | -4.57366 | 4.57366 | 4.52719e-05 | 3 | 3.06017 | -0.0528622 | -0.00326228 | 0 |
| low_na_asymptotic | 0 | 2.22801 | 7.02479 | 4.57613 | main_to_sidelobe_rejection_db | -4.57613 | 4.57613 | 6.32566e-05 | 3 | 1.33348 | -0.054539 | -0.00340238 | 0 |

### measurement_pipeline_mode = solver_output_peak_slice_adapter

#### extraction_mode = self_peak

| mode | measured_lateral_peak_x_um | measured_lateral_fwhm_um | measured_axial_fwhm_opd_um | measured_psr_db | measured_psr_definition | measured_sidelobe_to_main_db | measured_main_to_sidelobe_rejection_db | raw_peak_intensity | measured_peak_shift_um_vs_bridge | measured_lateral_width_bias_um_vs_bridge | measured_axial_width_bias_um_vs_bridge | measured_sidelobe_distortion_vs_bridge | extraction_plane_opd_um |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| full_na_scalar_fixed_basis | 0 | 5.63115 | 5.24264 | -23.9469 | sidelobe_to_main_db | -23.9469 | 23.9469 | 4.48331e-05 | 3 | 4.69857 | -0.0396282 | 0.000495177 | -2.13333 |
| vector_pupil_overlap_bridge | -3 | 0.932581 | 5.28227 | -24.4734 | sidelobe_to_main_db | -24.4734 | 24.4734 | 1.96897e-06 | 0 | 0 | 0 | 0 | -2.06667 |
| low_na_separable_baseline | 0 | 3.9547 | 5.24362 | -23.9531 | sidelobe_to_main_db | -23.9531 | 23.9531 | 5.12616e-06 | 3 | 3.02212 | -0.0386508 | 0.000486568 | -2.13333 |
| low_na_asymptotic | 0 | 2.23009 | 5.24478 | -24.374 | sidelobe_to_main_db | -24.374 | 24.374 | 7.15513e-06 | 3 | 1.29751 | -0.0374906 | 0.000400839 | -2.13333 |

#### extraction_mode = reference_peak_plane

| mode | measured_lateral_peak_x_um | measured_lateral_fwhm_um | measured_axial_fwhm_opd_um | measured_psr_db | measured_psr_definition | measured_sidelobe_to_main_db | measured_main_to_sidelobe_rejection_db | raw_peak_intensity | measured_peak_shift_um_vs_bridge | measured_lateral_width_bias_um_vs_bridge | measured_axial_width_bias_um_vs_bridge | measured_sidelobe_distortion_vs_bridge | extraction_plane_opd_um |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| full_na_scalar_fixed_basis | 0 | 5.63112 | 5.24264 | -23.9469 | sidelobe_to_main_db | -23.9469 | 23.9469 | 4.48331e-05 | 3 | 4.69854 | -0.0396282 | 0.000495177 | -2.06667 |
| vector_pupil_overlap_bridge | -3 | 0.932581 | 5.28227 | -24.4734 | sidelobe_to_main_db | -24.4734 | 24.4734 | 1.96897e-06 | 0 | 0 | 0 | 0 | -2.06667 |
| low_na_separable_baseline | 0 | 3.9547 | 5.24362 | -23.9531 | sidelobe_to_main_db | -23.9531 | 23.9531 | 5.12616e-06 | 3 | 3.02212 | -0.0386508 | 0.000486568 | -2.06667 |
| low_na_asymptotic | 0 | 2.22996 | 5.24478 | -24.374 | sidelobe_to_main_db | -24.374 | 24.374 | 7.15513e-06 | 3 | 1.29738 | -0.0374906 | 0.000400839 | -2.06667 |

