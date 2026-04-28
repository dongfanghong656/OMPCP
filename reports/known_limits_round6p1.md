# Known Limits Round 6p1

This note freezes the current known limits without mixing them with implementation history.

## Baseline limits

- `full_na_scalar_fixed_basis` is not a strict `c_rx^H T c_tx` OCT forward model.
- It remains a fixed-basis scalar pupil-propagation baseline, not a measured-channel solver.
- Exact spherical particles now have a separated pure Mie full-NA branch:
  - `scattering_branch = "sphere_mie_full_na"`
  - `sphere_mie_used = true`
  - `tmatrix_used = false`
  - `lateral_response_model = "sphere_mie_angle_resolved_pupil_field"`
  This avoids requiring the non-spherical T-matrix backend for `eps = 0`, `ideal = false`, `force_tmatrix = false`
  sphere cases.
- The sphere-only Mie branch is still a scalar fixed-basis pupil-field model, not a full vector Debye / calibrated OCT
  instrument model. It should be read as the exact homogeneous-sphere scattering route inside the current forward-
  diagnostic stack, not as final device-level PSF truth.
- The sphere-only sweep runner now records the `sample_arm_spectral_cube` contract and FD-OCT measurement-scaffold
  availability, but these are route-contract checks. They do not by themselves make the sweep paper-safe.
- The sphere-only sweep runner now also compares each case against an ideal uniform-pupil full-NA reference and reports
  `*_vs_ideal` PSF-bias fields. These fields are trend scaffolds for Pro review, not convergence- or device-calibrated
  paper-safe conclusions.
- The sphere Mie convergence runner compares the trend metrics across numerical settings and reports drift against an
  explicit reference configuration. This is only a numerical-stability scaffold; it does not replace measurement-wrapper
  calibration, vector-diffraction scope gating, or device-level validation.
- The old `low_na_separable_baseline` remains an axial spectral smoke path with a Gaussian lateral surrogate; it still
  must not be used as evidence that particle scattering does not affect the lateral PSF.

## Bridge limits

- `vector_pupil_overlap_bridge` is a bridge approximation, not an exact overlap solver.
- Its polarization layer is still a `lab_to_local_jones_surrogate`.
- Supported polarization modes are still limited to:
  - `linear_x`
  - `linear_y`
  - `co_pol`
  - `cross_pol`

## Asymptotic limits

- `low_na_asymptotic` is still the minimal usable asymptotic layer, not a high-fidelity surrogate for strong tilt or strong anisotropy.
- It is currently better at shape-level corrections than at reproducing pronounced lateral peak shifts.
- The promoted shared coefficient-map is now a real runtime contract, but it is still **override-only**, not the native default asymptotic runtime.
- The current promoted shared runtime model is:
  - `promoted_shared_map_model_id = low_order_coupled_odd_even_map`
- Its current runtime scope is:
  - `general_asymptotic_rendered_basis_override`
- Its current hard runtime restriction is:
  - `promoted_shared_map_runtime_supported_lateral_shift_models = ["none", "first_order"]`
  - `promoted_shared_map_runtime_shift_target = "baseline_envelope_ratio"`
  - `promoted_shared_map_runtime_lateral_shift_constraint = rendered_basis_override_supports_first_order_only_with_envelope_only_analytic_gaussian_or_rendered_interp`
- Therefore the promoted shared-map should currently be read as:
  - a formal rendered-basis override contract for asymptotic runtime experiments
  - not yet a native default asymptotic assembly contract
  - and not yet a generally promoted runtime for arbitrary lateral-shift families
  - specifically, first-order shift is only promoted through the minimal rendered-basis override path:
    - `lateral_shift_coupling = "envelope_only"`
    - `rendered_basis_shift_target = "baseline_envelope_ratio"` with `lateral_shift_impl = "analytic_gaussian"`
    - or `rendered_basis_shift_target = "rendered_field_interp"` with `lateral_shift_impl in {"interp", "interp_edge_hold"}`
- `C2_slice_k` is now exposed and benchmarked, but slice-direction diagnostics still do not automatically guarantee better lateral fidelity.
- `second_order_model = "slice_projected"` is still experimental; after post-hoc amplitude matching it can calm raw-return instability, but it still has not improved `peakline_x_delta_um` on the fixed round6p1 panel.
- `second_order_model = "directional_field_expansion_first_order"` is still experimental; even with an explicit odd first-order field basis it has not yet reduced `peakline_x_delta_um` on the fixed round6p1 panel, so the current open model limit is not solved by a simple first-order directional add-on.
- `lateral_shift_model = "first_order"` is still experimental; on the fixed round6p1 panel it has not reduced `peakline_x_delta_um` and currently worsens image-level agreement.
- The more self-consistent `shift_envelope_and_mu2` coupling branch and the `analytic_gaussian` shift implementation both remain experimental; on the fixed round6p1 panel they still do not improve `peakline_x_delta_um`, and their `delta_x_k` estimates remain extremely small relative to the observed bridge-side lateral miss.
- `mu2_tensor_profile` still uses a reduced wavelength model rather than a full `x,k`-dependent closure.
- `fitted_linear_map_3x3` is currently the strongest case-specific coefficient-map model in ablation, but it remains too ill-conditioned and too case-specific to promote directly into production.
- `low_order_coupled_odd_even_map` is currently the best shared/generalizing map family, but it still carries substantial gauge / conditioning burden and has not yet been promoted to native default runtime semantics.
- A minimal Fourier-domain OCT wrapper now exists in:
  - `oct_forward/fd_oct_measurement.py`
  and it is now connected into the measurement-bias evidence chain through:
  - `measurement_protocol/psf_bias_protocol.py`
  - `measurement_protocol/bias_experiment.py`
- The current measurement report can therefore compare:
  - `solver_output_peak_slice_adapter`
  - `fd_oct_reconstruction`
  and it prefers `fd_oct_reconstruction` when the solver result exposes the spectral sample-arm contract.
- The FD-OCT wrapper now locks the medium-effective wavenumber convention explicitly:
  - `k = 2*pi*n_medium/lambda0`
  - the FFT-conjugate axis is `geometric_roundtrip_um`
  - `single_pass_geometric_depth_um = geometric_roundtrip_um / 2`
  - `optical_roundtrip_path_um = reference_n_medium * geometric_roundtrip_um`
  The legacy `opd_um` field is retained only as a compatibility alias and must not be divided by `n` again.
- The top-level validator now surfaces that measurement evidence, but the reference-arm policy is still scaffold-level:
  - `measurement_reference_arm_policy = "flat_synthetic_reference_when_measurement_reference_arm_field_absent"`
  - `measurement_reference_arm_policy_status = "scaffold_not_calibrated"`
- On runtimes that cannot load the vendored CPython 3.10 T-matrix backend, `30_refresh_round6p1_measurement_contract_artifacts.py`
  may refresh legacy FD-OCT depth-axis labels in existing artifacts. That is a source-contract synchronization step, not a
  fresh numerical evidence recompute.
- `31_controlled_cp310_evidence_rebuild.py` now records whether the local runtime can perform a controlled CPython 3.10
  T-matrix evidence rebuild, but it does not itself make the backend portable. If the report says
  `cp310_evidence_rebuild_readiness_status = "cp310_runtime_unavailable"` or
  `backend_unavailable_in_cp310_runtime`, the next step is still to install/select a compatible CPython 3.10 runtime or
  provide a portable T-matrix backend before claiming fresh non-spherical numerical evidence.
- T-matrix backend selection is now an explicit provenance contract:
  - `--tmatrix-backend auto|vendored_pytmatrix|ctypes_legacy|portable_isoc`
  - `--tmatrix-lib-path PATH`
  - `--require-tmatrix-backend`
  - `--backend-provenance-out PATH`
  `portable_isoc` is intentionally reserved but not implemented yet, so it must be treated as a structured unavailable
  backend until the ISO_C_BINDING + ctypes shared-library route exists.
- But this is still only a minimal measurement-grade scaffold, not yet a full acquisition/reconstruction model with complete instrument effects such as full instrument roll-off, calibrated k-clock behavior, or realistic noise injection.
- Scalar asymptotic validity is now surfaced explicitly in runtime results:
  - `na_scalar_validity_status`
  - `requires_vector_diffraction`
  These fields should be treated as a domain-of-validity guard, not as proof that vector diffraction has already been solved.

## mu2 wavelength-model limits

- `mu2_wavelength_model = "frozen_at_lambda0"` remains the default.
- `mu2_wavelength_model = "endpoint_refit"` is only a cheap band-edge surrogate, not a full spectral closure.
- `endpoint_refit` is now treated as an experimental branch that is not currently prioritized.
- `mu2_dispersion_sensitivity` should be read as an applicability indicator, not as proof that the full wavelength dependence is solved.

## Validation limits

- A passing hard gate does not mean the solver is exact.
- A model-limit failure means the current approximation boundary has been exposed honestly.
- The current validator is intended to separate:
  - code or contract regressions
  - exposed model limits
  - recorded diagnostics

## Not started yet

- `glmt_overlap_exact_regular_particle` has not been started.
- No true exact-overlap regular-particle path should be claimed before that work exists.
