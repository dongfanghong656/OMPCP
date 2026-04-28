# Result Schema Round 6p1

This note freezes the current paper-facing result contract for the four supported solver modes:

- `low_na_separable_baseline`
- `full_na_scalar_fixed_basis`
- `vector_pupil_overlap_bridge`
- `low_na_asymptotic`

## Shared primary fields

These fields are treated as primary and should remain stable across all four modes:

- `mode`
- `display_mode_label`
- `approximation_label`
- `solver_output_kind`
- `lateral_slice_axis`
- `x_um`
- `opd_um`
- `lambda_nm`
- `axial_axis_kind`
- `schema_version`
- `paper_safe`
- `axial_intensity_metrics`
- `axial_envelope_metrics`
- `peakline_x_um`
- `raw_peak_intensity`
- `normalization`
- `material_support`
- `depth_convention_helper`

## Material-support contract

`material_support` is a paper-facing provenance and validity contract, not just a warning bucket.

Each populated material entry should expose:

- `material`
- `role`
- `kind`
- `range_um`
- `has_explicit_range`
- `wavelength_units`
- `support_source`
- `range_basis`
- `extrapolation_policy`
- `policy_note`
- `strict_material_range`
- `status`

Current built-in project materials use an encoded OCT operating-window guard:

- `range_um = [0.700, 1.100]` for `TiO2-anatase`, `PS`, `SiO2`, and `PDMS`
- `range_um = [0.700, 1.100]` from table endpoints for `Fe2O3-o` and `Fe2O3-e`
- `extrapolation_policy = "error_outside_encoded_range"`

The validator gates named `strict_material_range_requires_explicit_support` and `analytic_material_range_warning_dedup` intentionally use unranged debug callables. They no longer mean the built-in project materials lack an encoded support range.

## Raw amplitude fields

These are paper-facing raw-return fields and should be kept when `paper_safe = true`:

- `raw_intensity_xz`
- `peakline_raw_axial_intensity`
- `raw_peak_intensity`
- `normalization.normalization_scope`
- `normalization.absolute_amplitude_supported`

These are still useful raw diagnostics, but are less central than the list above:

- `raw_envelope_xz`
- `centerline_raw_axial_intensity`
- `centerline_raw_axial_envelope`
- `peakline_raw_axial_envelope`

## Bridge-specific fields

These fields define the current bridge semantics and should remain visible at result level:

- `channel_projection_kind`
- `channel_definition`
- `projection_semantics_note`
- `polarization_model_kind`
- `supported_polarization_modes`

## Asymptotic-specific fields

These fields define the current asymptotic closure and should remain visible at result level:

- `B_k`
- `C2_k`
- `C2_tensor_k`
- `C2_slice_k`
- `C2_slice_projection_note`
- `per_azimuth_B_k`
- `per_azimuth_C2_k`
- `C2_abs_std_over_azimuth`
- `C2_azimuth_variation_summary`
- `C2_scalar_validity_indicator`
- `requested_second_order_model`
- `second_order_model`
- `runtime_field_assembly_contract`
- `runtime_field_assembly_contract_note`
- `runtime_field_assembly_shift_target`
- `runtime_field_assembly_shift_target_note`
- `runtime_field_assembly_supported_lateral_shift_models`
- `runtime_field_assembly_lateral_shift_constraint`
- `coefficient_map_runtime_mode`
- `coefficient_map_runtime_status`
- `coefficient_map_runtime_contract_status`
- `second_order_model_note`
- `second_order_closure_note`
- `lateral_shift_model`
- `lateral_shift_model_status`
- `lateral_shift_model_note`
- `lateral_shift_coupling`
- `lateral_shift_coupling_note`
- `lateral_shift_impl`
- `lateral_shift_impl_note`
- `rendered_basis_shift_target`
- `lateral_shift_delta_x_k_um`
- `lateral_shift_delta_summary`
- `D1_vector_k`
- `D1_slice_k`
- `mu2_profile`
- `mu2_tensor_profile`
- `mu2_tensor_reference`
- `reference_first_order_field_vector`
- `directional_first_order_field_profile`
- `directional_first_order_field_note`
- `directional_second_order_slice_field_profile`
- `mu2_profile_kind`
- `mu2_profile_semantics_note`
- `mu2_profile_complexity_note`
- `mu2_profile_phase_span_rad`
- `mu2_profile_real_imag_ratio`
- `mu2_profile_complexity_summary`
- `mu2_reference_wavelength_nm`
- `mu2_wavelength_model`
- `mu2_wavelength_model_status`
- `mu2_wavelength_model_note`
- `mu2_wavelength_samples_nm`
- `mu2_dispersion_sensitivity`
- `na_scalar_validity_status`
- `na_scalar_validity_note`
- `requires_vector_diffraction`
- `na_scalar_validity_threshold`

## Experimental fields

The following fields are explicit experiment knobs and should not be silently removed or renamed:

- `solver.second_order_model`
- `solver.mu2_wavelength_model`
- `solver.lateral_shift_model`
- `solver.lateral_shift_coupling`
- `solver.lateral_shift_impl`
- `second_order_model`
- `mu2_wavelength_model`
- `lateral_shift_model`
- `lateral_shift_coupling`
- `lateral_shift_impl`

## Runtime semantics note

`second_order_model` is the requested asymptotic branch family, not always the full runtime assembly story.

When `coefficient_map_runtime_mode = "rendered_basis_override"`:

- `requested_second_order_model` keeps the requested native branch label
- `runtime_field_assembly_contract = "rendered_basis_override"` records the actual field assembly contract
- `coefficient_map_runtime_contract_status` records whether this is still branch-limited or an explicit rendered-basis override

Current round6p1 implementation detail that is now part of the contract:

- `rendered_basis_override` supports:
  - `lateral_shift_model = "none"`
  - `lateral_shift_model = "first_order"` only when:
    - `lateral_shift_coupling = "envelope_only"`
    - and one of:
      - `rendered_basis_shift_target = "baseline_envelope_ratio"` with `lateral_shift_impl = "analytic_gaussian"`
      - `rendered_basis_shift_target = "rendered_field_interp"` with `lateral_shift_impl in {"interp", "interp_edge_hold"}`
- this is surfaced through:
  - `runtime_field_assembly_supported_lateral_shift_models`
  - `runtime_field_assembly_lateral_shift_constraint`
  - `runtime_field_assembly_shift_target`
  - `runtime_field_assembly_shift_target_note`

The minimal measurement-grade wrapper now begins at:

- `oct_forward/fd_oct_measurement.py`

It currently exposes:

- sample-arm plus reference-arm interference-spectrum construction
- k-linearization onto a uniform `k` grid
- optional dispersion-phase compensation
- IFFT A-scan reconstruction
- an explicit medium-effective depth-axis contract:
  - `fd_oct_depth_convention = "geometric_roundtrip_conjugate_to_medium_effective_wavenumber"`
  - `geometric_roundtrip_um`
  - `single_pass_geometric_depth_um`
  - `optical_roundtrip_path_um`
  - deprecated compatibility aliases `opd_um`, `single_pass_depth_from_reference_n_um`, and `double_pass_depth_from_reference_n_um`

This is still a minimal Fourier-domain OCT wrapper, not yet a full instrument-grade acquisition model.

## Measurement-report package schema

The round6p1 measurement report package now exposes two measurement-layer routes on top of solver outputs:

- `solver_output_peak_slice_adapter`
- `fd_oct_reconstruction`

At package level the current schema should expose:

- `measurement_pipeline_modes`
- `cases[*].measurement_pipeline_modes`
- `cases[*].pipeline_comparison_modes`
- `cases[*].default_measurement_pipeline_mode`
- `cases[*].default_comparison_mode`
- `cases[*].comparison_modes`

Current contract intent:

- `comparison_modes` is a backward-compatible alias for the tables under the selected `default_measurement_pipeline_mode`
- `default_measurement_pipeline_mode` should prefer `fd_oct_reconstruction` when the solver result exposes:
  - `lambda_nm`
  - `sample_arm_spectral_cube`
- otherwise it should fall back to:
  - `solver_output_peak_slice_adapter`

At per-comparison level the current measurement contract should expose:

- `measurement_pipeline_mode`
- `measurement_protocol_kind`
- `measurement_protocol_note`
- `measurement_extraction_mode`
- `fd_oct_depth_convention`
- `fd_oct_depth_axis_note`
- `fd_oct_single_pass_geometric_depth_um`
- `fd_oct_optical_roundtrip_path_um`

This means the measurement layer is no longer just a standalone scaffold: the minimal FD-OCT wrapper is now part of the main evidence-chain comparison package, even though it is still not a full instrument-grade simulator.

## Validation-summary measurement fields

When the measurement package is explicitly supplied to the validator, the top-level validation summary should also expose:

- `measurement_pipeline_case_names`
- `measurement_pipeline_modes`
- `measurement_default_pipeline_modes`
- `measurement_pipeline_default_mode`
- `measurement_pipeline_evidence_status`
- `fd_oct_measurement_wrapper_status`
- `measurement_report_schema_versions`
- `measurement_pipeline_failures`
- `measurement_reference_arm_policy`
- `measurement_reference_arm_policy_status`
- `measurement_reference_arm_policy_note`
- `measurement_fd_oct_depth_conventions`
- `measurement_fd_oct_k_axis_kinds`
- `measurement_fd_oct_medium_index_policies`
- `measurement_fd_oct_depth_policy_status`
- `measurement_artifact_freshness_status`
- `measurement_artifact_freshness_note`
- `measurement_contract_refreshed_row_count`

Current expected values for complete round6p1 evidence packages:

- `measurement_pipeline_evidence_status = "fd_oct_reconstruction_in_evidence_chain"`
- `fd_oct_measurement_wrapper_status = "integrated_in_measurement_evidence_chain"`
- `measurement_pipeline_default_mode = "fd_oct_reconstruction"`
- `measurement_reference_arm_policy = "flat_synthetic_reference_when_measurement_reference_arm_field_absent"`
- `measurement_reference_arm_policy_status = "scaffold_not_calibrated"`
- `measurement_fd_oct_depth_policy_status = "medium_effective_k_geometric_depth_axis_declared"`
- If the local runtime cannot recompute T-matrix evidence, `measurement_artifact_freshness_status` may be
  `source_contract_refreshed_existing_numerical_evidence`. This means the depth-axis contract labels were synchronized
  to the current source, but numerical evidence still needs regeneration under a compatible backend.

These fields are measurement-evidence metadata. They should not by themselves override the coefficient-path recommended action unless future measurement-grade gates are added.

## Sphere-only Mie full-NA branch fields

The `full_na_scalar_fixed_basis` result now separates exact spherical particles from the non-spherical T-matrix route.
When `eps = 0`, `ideal = false`, and `force_tmatrix = false`, the expected branch is the pure Mie sphere branch.
Solver summaries and sweep reports may expose:

- `sphere_mie_used`
- `scattering_branch`
- `tmatrix_backend_required`
- `lateral_response_model`
- `particle_lateral_scattering_enters_profile`
- `sphere_mie_metadata`
- `sphere_mie_nmax_min`
- `sphere_mie_nmax_max`
- `sample_arm_spectral_cube_shape`
- `sample_arm_spectral_cube_axis_order`
- `sample_arm_spectral_cube_quantity_kind`
- `sample_arm_spectral_cube_contract_status`
- `fd_oct_measurement_scaffold_route_available`

Expected exact-sphere full-NA values are:

- `sphere_mie_used = true`
- `tmatrix_used = false`
- `tmatrix_backend_required = false`
- `scattering_branch = "sphere_mie_full_na"`
- `lateral_response_model = "sphere_mie_angle_resolved_pupil_field"`
- `particle_lateral_scattering_enters_profile = true`
- `sample_arm_spectral_cube_axis_order = "lambda_x"`
- `sample_arm_spectral_cube_quantity_kind = "complex_sample_arm_spectral_field"`
- `sample_arm_spectral_cube_contract_status = "valid_lambda_x_complex_field"`
- `fd_oct_measurement_scaffold_route_available = true`

The standalone sphere sweep runner writes `sphere_mie_full_na_sweep_summary.json` with:

- `schema_version = "sphere_mie_sweep_v1"`
- `sweep_status`
- `interpretation_status`
- `paper_safety_status`
- `psf_bias_against_ideal_reference_status`
- `ideal_reference_comparison`
- `sphere_branch_contract`
- `sphere_branch_contract_checks`
- `metric_ranges`
- `rows[*].sphere_mie_used`
- `rows[*].tmatrix_used`
- `rows[*].scattering_branch`
- `rows[*].lateral_response_model`
- `rows[*].sample_arm_spectral_cube_contract_status`
- `rows[*].fd_oct_measurement_scaffold_route_available`
- `rows[*].ideal_reference_available`
- `rows[*].peakline_x_delta_um_vs_ideal`
- `rows[*].self_peak_lateral_fwhm_delta_um_vs_ideal`
- `rows[*].self_peak_lateral_centroid_delta_um_vs_ideal`
- `rows[*].self_peak_lateral_profile_relative_l2_vs_ideal`
- `rows[*].ideal_peak_plane_peak_x_delta_um_vs_ideal`
- `rows[*].ideal_peak_plane_lateral_fwhm_delta_um_vs_ideal`
- `rows[*].ideal_peak_plane_lateral_profile_relative_l2_vs_ideal`
- `rows[*].normalized_image_relative_l2_vs_ideal`

The runner also writes `sphere_mie_full_na_sweep_summary.md` as a lightweight review
summary. The ideal-reference comparison uses an ideal uniform-pupil full-NA reference
computed with the same grid, NA, spectrum, and scalar fixed-basis propagation settings.

This branch is a particle-aware scalar pupil-field path for homogeneous spheres. It is not a substitute for the
non-spherical T-matrix route, and it is still bounded by the scalar fixed-basis / FD-OCT measurement-scaffold limits.

## Sphere Mie convergence report fields

`scripts/sphere_mie_convergence_runner.py` writes:

- `sphere_mie_convergence_summary.json`
- `sphere_mie_convergence_summary.md`
- `sphere_mie_convergence_summary.csv`

The JSON schema exposes:

- `schema_version = "sphere_mie_convergence_v1"`
- `report_kind = "sphere_mie_convergence"`
- `grid_panel`
- `reference_config_id`
- `convergence_status`
- `convergence_reference_summary`
- `metric_ranges`
- `interpretation_status`
- `paper_safety_status`
- `rows[*].config_id`
- `rows[*].n_lambda`
- `rows[*].n_z`
- `rows[*].n_x`
- `rows[*].n_bfp_dense`
- `rows[*].*_drift_vs_reference`
- `rows[*].*_abs_drift_vs_reference`

This report compares the sphere Mie full-NA PSF-bias metrics across numerical settings.
The reference configuration is the explicitly named `reference_config_id`; by default this is
the last grid-panel entry. A passing preliminary convergence status is not a paper-safe device
claim.

## Validation-summary CPython 3.10 evidence-rebuild fields

The round6p1 evidence package may include a controlled CPython 3.10 / T-matrix rebuild readiness report.
This is a runtime-readiness contract, not a physics-result field. It exists to prevent a source-contract refresh from
being mistaken for a fresh numerical evidence rebuild when the local runtime cannot load the vendored T-matrix backend.

When `round6p1_cp310_evidence_rebuild_readiness.json` is supplied to the validator, the top-level validation summary
should expose:

- `cp310_evidence_rebuild_readiness_status`
- `cp310_evidence_rebuild_ready`
- `cp310_evidence_rebuild_reason`
- `cp310_evidence_rebuild_selected_python_command`
- `cp310_evidence_rebuild_selected_python_version`
- `cp310_evidence_rebuild_status`
- `cp310_evidence_rebuild_execute_requested`
- `cp310_evidence_rebuild_recommended_next_action`
- `cp310_evidence_rebuild_guidance_status`

Current expected values on a runtime without a compatible CPython 3.10 T-matrix backend are:

- `cp310_evidence_rebuild_readiness_status = "cp310_runtime_unavailable"`
- `cp310_evidence_rebuild_ready = false`
- `cp310_evidence_rebuild_recommended_next_action = "install_or_select_cp310_runtime_or_portable_tmatrix_backend"`
- `cp310_evidence_rebuild_guidance_status = "fresh_evidence_rebuild_blocked_by_runtime"`

These fields should be read together with `measurement_artifact_freshness_status`. If the CPython 3.10 readiness gate
is not ready, a refreshed measurement/validation artifact can synchronize source-contract labels but must not be described
as freshly regenerated T-matrix numerical evidence.

## T-matrix backend provenance fields

Round6p1 now separates backend selection/provenance from the physics solver. Solver and sweep entrypoints may expose:

- `tmatrix_backend_requested_id`
- `tmatrix_backend_available`
- `tmatrix_backend_id`
- `tmatrix_backend_library_path`
- `tmatrix_backend_reason`
- `tmatrix_backend_provenance`
- `backend_provenance_path`

The allowed backend ids are:

- `auto`
- `vendored_pytmatrix`
- `ctypes_legacy`
- `portable_isoc`

Current semantics:

- `auto` records the legacy discovery result without forcing a particular implementation.
- `vendored_pytmatrix` requires the Python `pytmatrix.fortran_tm.pytmatrix` implementation when selected explicitly.
- `ctypes_legacy` requires the legacy shared-library route when selected explicitly.
- `portable_isoc` is a reserved backend id for the planned ISO_C_BINDING + ctypes route and currently reports unavailable/not implemented.

If `--require-tmatrix-backend` is set, or a non-`auto` backend is selected explicitly, entrypoints should fail structurally
when the requested backend is unavailable. This prevents skipped or fallback T-matrix evidence from being mistaken for fresh
non-spherical numerical evidence.

## Diagnostics versus contract

Treat these as diagnostics rather than core paper-facing outputs:

- `fit_diagnostics`
- `per_azimuth_relative_fit_residual`
- `mu2_profile_weight_denominator_abs`
- `derived_geometry_series`

The contract intent for round6p1 is:

- keep primary fields stable
- keep raw amplitude fields explicit
- keep bridge and asymptotic semantics visible at result level
- do not silently demote experiment knobs into hidden implementation-only behavior
