# Benchmark Gates Round 6p1

This note freezes the validator semantics for round6p1.

## Status values

- `pass`: the check passed under the current threshold or expectation
- `fail`: the check failed and should be treated as a genuine negative result
- `expected_fail`: the check confirms a known model boundary
- `informational`: the check is a recorded diagnostic, not a gate

## Status categories

- `hard_gate`: true validation gate; a `fail` here should return a non-zero process exit code
- `model_limit`: machine-readable model boundary; does not by itself force a non-zero exit code
- `diagnostic`: recorded context or experiment result; never forces a non-zero exit code
- `model_direction`: machine-readable experiment conclusion about which branch should or should not be prioritized next; never forces a non-zero exit code

## Current gate map

### Hard gates

- `na_geometry_convention`
- `low_na_ideal`
- `low_na_mie_smoke`
- `strict_material_range_requires_explicit_support`
- `analytic_material_range_warning_dedup`
- `sphere_complex_spectrum_mie_tmatrix`
- `amp_component_fixed_basis_sensitivity`
- `full_na_tmatrix_smoke`
- `bridge_vs_scalar_difference_gate`
- `bridge_consistency_gate`
- `low_na_asymptotic_channel_alignment_trend`
- `mu2_dispersion_benchmark_design`
- `full_na_sampling_convergence`
- `bridge_spectral_sampling_convergence`
- `asymptotic_spectral_sampling_convergence`
- `paper_safe_regression`
- `paper_facing_result_contract`
- `schema_regression_round6`

### Model-limit checks

- `low_na_asymptotic_absolute_alignment_gate`
- `low_na_asymptotic_failure_domain_lateral_shift`
- `mu2_dispersion_current_case_gate`

### Diagnostics

- `asymptotic_mu2_wavelength_freeze_diagnostic`
- `low_na_asymptotic_second_order_model_ablation`
- `low_na_asymptotic_directional_first_order_ablation`
- `low_na_asymptotic_slice_projected_stability_gate`
- `low_na_asymptotic_slice_projected_fidelity_gate`
- `low_na_asymptotic_mu2_wavelength_model_ablation`
- `low_na_asymptotic_lateral_shift_model_ablation`
- `low_na_asymptotic_first_order_not_prioritized`
- `low_na_asymptotic_endpoint_refit_not_prioritized`

## Exit-code policy

The validator should exit with code `1` only when:

- `status = "fail"`
- and `status_category = "hard_gate"`

When strict mode is enabled through `--strict-gates` or `OCT_VALIDATE_STRICT=1`, it should also exit with code `1` for:

- `status = "fail"`
- and `status_category = "model_limit"`

It should exit with code `0` when the only negatives are:

- `status = "fail"` with `status_category = "model_limit"`
- `status = "expected_fail"`
- `status = "informational"`
- `status_category = "model_direction"`

## Failure summary intent

In addition to the JSON report, the validator should emit a short text summary that states:

- which hard gates failed
- which model-limit failures were exposed
- which checks are `expected_fail`
- which comparison case looks worst
- which single metric is most dominant in that worst case
- which `dominant_error_bucket` currently dominates the most severe exposed case

## Dominant error bucket heuristic

- `lateral_shift`, `axial_centroid`, `axial_width`, and `sidelobe_structure` use direct threshold-normalized severities
- `raw_amplitude` uses a log-scaled severity so very large raw-return ratios do not automatically drown out the lateral-shift signal that currently drives the main bridge-vs-asymptotic mismatch

## Experiment semantics

- `low_na_asymptotic_second_order_model_ablation` now compares:
  - `tensor_closure`
  - `slice_projected_raw`
  - `slice_projected_scaled`
  - `directional_field_expansion_raw`
  - `directional_field_expansion_scaled`
  - `directional_field_expansion_first_order_raw`
  - `directional_field_expansion_first_order_scaled`
- `low_na_asymptotic_directional_first_order_ablation` freezes the 3-case decision panel for the odd-field experiment:
  - `tensor_closure`
  - `directional_field_expansion_scaled`
  - `directional_field_expansion_first_order_scaled`
- `low_na_asymptotic_slice_projected_stability_gate` asks whether post-hoc amplitude matching actually pulls `slice_projected` back out of raw-amplitude blow-up.
- `low_na_asymptotic_slice_projected_fidelity_gate` asks whether the stabilized `slice_projected` branch improves the bridge-facing fidelity metrics after that raw-amplitude cleanup.
- `low_na_asymptotic_first_order_not_prioritized` records the current negative result: the first-order branch has been tested and is not currently the branch to prioritize.
- `low_na_asymptotic_endpoint_refit_not_prioritized` records the current negative result: the endpoint-refit branch has been tested and is not currently the branch to prioritize.
- `low_na_asymptotic_lateral_shift_model_ablation` now compares:
  - `none`
  - `first_order_envelope_only_interp`
  - `first_order_shift_envelope_and_mu2_interp`
  - `first_order_shift_envelope_and_mu2_analytic_gaussian`
  - `first_order_shift_envelope_and_mu2_interp_edge_hold`
- The lateral-shift ablation is intended to answer two implementation questions before any model promotion:
  - does coupling the shift into the x-dependent second-order correction help?
  - does replacing `np.interp` with an analytic Gaussian shift reduce shift-induced raw-amplitude artifacts?
  - does zero-padding at the x-grid boundary account for part of the raw-amplitude change, compared with an `interp_edge_hold` boundary treatment?

## Runtime semantics

- `second_order_model` now means the **requested asymptotic branch family**.
- `requested_second_order_model` duplicates that requested branch explicitly so downstream consumers do not need to infer whether a later runtime override changed the actual field assembly semantics.
- `runtime_field_assembly_contract` now records the **actual field-assembly contract** used to assemble the runtime field.
- When `coefficient_map_runtime_mode = "native_branch_assembly"`, the expected default is:
  - `runtime_field_assembly_contract = requested_second_order_model`
- When `coefficient_map_runtime_mode = "rendered_basis_override"`, the expected runtime contract is:
  - `runtime_field_assembly_contract = "rendered_basis_override"`
  even if `requested_second_order_model` remains:
  - `tensor_closure`
  - `slice_projected`
  - `directional_field_expansion`
  - or `directional_field_expansion_first_order`

- Therefore downstream gate consumers should not treat `second_order_model` by itself as the full runtime semantics once coefficient-map runtime override is active.

## Measurement-layer semantics

- The round6p1 measurement-bias package now compares two measurement-layer routes:
  - `solver_output_peak_slice_adapter`
  - `fd_oct_reconstruction`
- `fd_oct_reconstruction` should be preferred as the default package-level measurement route when the solver result exposes the spectral sample-arm contract:
  - `lambda_nm`
  - `sample_arm_spectral_cube`
- `solver_output_peak_slice_adapter` remains the backward-compatible fallback when that spectral contract is unavailable.
- This does **not** mean the project is already a full instrument-grade OCT simulator.
- It means the minimal FD-OCT wrapper is now part of the main evidence-chain comparison package rather than an isolated helper module.
- For medium-effective k-space reconstruction, benchmark consumers must read the depth axis as:
  - `fd_oct_depth_convention = "geometric_roundtrip_conjugate_to_medium_effective_wavenumber"`
  - `geometric_roundtrip_um` as the FFT-conjugate axis
  - `single_pass_geometric_depth_um = geometric_roundtrip_um / 2`
  - `optical_roundtrip_path_um = reference_n_medium * geometric_roundtrip_um`
  The old `opd_um` name is a compatibility alias only.
- The top-level validation summary should surface the measurement evidence with:
  - `measurement_pipeline_evidence_status`
  - `measurement_pipeline_default_mode`
  - `fd_oct_measurement_wrapper_status`
  - `measurement_reference_arm_policy`
  - `measurement_reference_arm_policy_status`
- Current reference-arm normalization is still scaffold-level: when `measurement_reference_arm_field` is absent, the FD-OCT path uses a flat synthetic reference arm.
- If T-matrix evidence cannot be recomputed in the local runtime, use
  `30_refresh_round6p1_measurement_contract_artifacts.py` only as a contract-label refresh bridge. A refreshed artifact
  should surface `measurement_artifact_freshness_status = "source_contract_refreshed_existing_numerical_evidence"` and
  must not be described as a fresh numerical evidence rebuild.
- Before claiming a fresh T-matrix numerical evidence rebuild, run the controlled readiness gate:
  - `31_controlled_cp310_evidence_rebuild.py`
- By default this gate is probe-only and should write:
  - `round6p1_cp310_evidence_rebuild_readiness.json`
  - `round6p1_cp310_evidence_rebuild_readiness.md`
- A fresh rebuild is only attempted when the caller explicitly passes `--execute` and the readiness report says:
  - `cp310_evidence_rebuild_ready = true`
- If readiness is blocked, the benchmark package should surface:
  - `cp310_evidence_rebuild_readiness_status`
  - `cp310_evidence_rebuild_recommended_next_action`
  and should treat any source-contract refresh as non-numerical evidence maintenance.
- Backend reproducibility is also gated by explicit T-matrix backend provenance. Fresh non-spherical evidence should report:
  - `tmatrix_backend_requested_id`
  - `tmatrix_backend_available = true`
  - `tmatrix_backend_id`
  - `tmatrix_backend_library_path`
  - `backend_provenance_path`
- A run with `--require-tmatrix-backend` or explicit non-`auto` `--tmatrix-backend` must fail structurally when the requested backend is unavailable.
- `portable_isoc` is currently a planned backend contract, not an implemented backend; it should only pass once the ISO_C_BINDING + ctypes shared-library path is implemented and cross-validated.

## Top-level summary fields

- `report_version_tag` identifies the active validator/report contract family and should currently read `round6p1`.
- `most_critical_open_model_limit` identifies the single open `fail / model_limit` that should currently dominate upgrade planning.
- `recommended_next_action` is now the resolved top-level action after precedence is applied, not just the raw open-model-limit heuristic.
- `final_recommended_next_action` mirrors the resolved top-level action for downstream consumers that want an explicit "this is the final answer" field.
- `final_recommended_next_action_source` records whether the resolved action came from the open-model-limit heuristic or from explicit basis-projection evidence.
- `worst_case_name`, `worst_metric_name`, and `worst_metric_value` surface the single most severe exposed comparison without making downstream tooling re-scan every nested check payload.
- `directional_first_order_is_promising` records whether the new odd-field basis lowered `peakline_x_delta_um` on the fixed 3-case panel without destabilizing raw amplitude enough to disqualify it.
- `basis_projection_guidance_status` records whether explicit basis-projection evidence was supplied for this validator run.
- Explicit basis-projection evidence is now used only to resolve the final recommendation; the validator no longer publishes a second competing top-level action field from basis projection.
- `best_generalizing_coefficient_map_model_id` records the current best leave-one-out shared/generalizing map family from the stability report.
- `promoted_shared_map_model_id` records which shared map is currently promoted into runtime as the explicit shared override candidate.
- `promoted_shared_map_runtime_scope` records the current promoted runtime scope. It currently means:
  - `general_asymptotic_rendered_basis_override`
- `promoted_shared_map_runtime_contract_status` records whether the promoted shared map is still branch-limited or already a general explicit override contract.
- `promoted_shared_map_runtime_supported_lateral_shift_models` records which lateral-shift settings are currently supported by the promoted shared runtime contract.
- `promoted_shared_map_runtime_shift_target` records the currently promoted rendered-basis shift target for the runtime contract.
- `promoted_shared_map_runtime_lateral_shift_constraint` records the current hard runtime restriction. It currently means:
  - `rendered_basis_override_supports_first_order_only_with_envelope_only_analytic_gaussian_or_rendered_interp`
  which should be read as:
  - the promoted shared map may be activated across general asymptotic branches
  - with `lateral_shift_model = "none"` under the plain override path
  - or with `lateral_shift_model = "first_order"` only when:
    - `lateral_shift_coupling = "envelope_only"`
    - and one of:
      - `rendered_basis_shift_target = "baseline_envelope_ratio"` with `lateral_shift_impl = "analytic_gaussian"`
      - `rendered_basis_shift_target = "rendered_field_interp"` with `lateral_shift_impl in {"interp", "interp_edge_hold"}`
