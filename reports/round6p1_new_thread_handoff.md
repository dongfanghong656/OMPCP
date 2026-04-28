# Round6p1 New-Thread Handoff

## 1. Project Goal

Before editing solver physics or validator logic, read:

- `C:\codex-data\OCT_Research_System\oct-research-assist\references\theory_contract_round6p1_pro_aligned.md`

This workspace is building and validating a three-layer OCT forward-model stack for nonspherical / tilted-particle PSF analysis:

1. `full_na_scalar_fixed_basis`
2. `vector_pupil_overlap_bridge`
3. `low_na_asymptotic`

Current project intent is **not** to pretend any of these are exact where they are not.
The present state is:

- `full_na_scalar_fixed_basis` is still **not** a strict `(c_rx^H T c_tx)` OCT forward solution.
- `vector_pupil_overlap_bridge` is still a **bridge approximation**, not an exact overlap solver.
- `low_na_asymptotic` is still a **minimal usable asymptotic model**, not a full space-varying closure.

The current scientific question is no longer "is the schema/implementation obviously wrong?".
It is now:

> Why does `low_na_asymptotic` still fail mainly on lateral peak displacement, and can the current asymptotic basis family represent the bridge slice at all?

The Pro-aligned theory contract further narrows the current phase:

> treat the stack as a forward-diagnostic system, not a full measurement-grade OCT simulator, and prioritize coefficient extraction / usage mapping over new basis expansion unless new evidence overturns the current hierarchy.

## 2. Current High-Level Conclusion

The main open model limit is stable across the latest round6/round6p1 evidence:

- `most_critical_open_model_limit = "low_na_asymptotic_absolute_alignment_gate"`
- `dominant_error_bucket = "lateral_shift"`
- `final_recommended_next_action = "require_train_eval_generalization_before_promoting_fitted_map"`
- `final_recommended_next_action_source = "coefficient_map_ablation"`
- `evidence_dependency_status = "complete"`
- `guidance_confidence = "full_evidence"`

The latest slice-axis crosscheck no longer conflicts with that conclusion:

- `slice_axis_crosscheck_status = "consistent"`
- `slice_axis_crosscheck_recommended_next_action = "coefficient_debug_generalizes_across_slice_axes"`

Interpretation:

- the `x` slice still needs the odd basis and is rescued by `R0 + R1 + R2`
- the `y` slice does not need the odd basis in the same way
- that is now treated as a benign axis difference, not as a reason to downgrade the coefficient-debug recommendation

That means:

- the dominant mismatch is **not** axial width / PSR first
- it is **mainly that asymptotic does not push the peak off `x=0`**
- the current asymptotic family still behaves too much like an **even / symmetric shape-correction model**
- the latest basis-projection evidence says the existing `(R0, R1, R2)` family is expressive enough
- the newer coefficient-recovery evidence says the odd coefficient pathway is the more likely bottleneck, so the next debugging target is coefficient extraction / usage rather than more basis freedom
- the latest coefficient-map audit says the **map stage itself** is now the most actionable bottleneck: identity is not the best rendered-coefficient model on the representative panel, while `fitted_linear_map_3x3` currently gives the best bridge-alignment metrics
- the newer coefficient-map stability audit refines that result:
  - `fitted_linear_map_3x3` is best when each case fits its own map
  - on the expanded 5-case generalization panel, `low_order_coupled_odd_even_map` is currently the best **leave-one-out generalizing** shared map
  - the learned 3x3 maps are still too case-specific to promote directly into production
- the newest coefficient-map ablation report pushes this one step further into the main evidence chain:
  - the map family is now a first-class comparison variable in validator/evidence outputs
  - `fitted_linear_map_3x3` is still the best ablated model on the representative panel
  - but the top-level recommendation is now to require explicit train/eval generalization before promoting that fitted map
- a minimal measurement-protocol adapter now exists on top of solver outputs, so bridge/full_na/low_na/asymptotic can also be compared under one common extraction rule without pretending the stack is already a raw-domain OCT measurement simulator
- that measurement adapter now supports:
  - `self_peak`
  - `reference_peak_plane`
  so lateral-bias comparisons can be interpreted with or without axial-plane confounding

## 3. What Has Already Been Tested

### 3.1 Branches that are now effectively deprioritized

These branches have already been tested and should **not** be the next main focus:

- `mu2_wavelength_model = "endpoint_refit"`
  - almost no improvement on the 3 representative cases
  - now treated as `experimental_not_prioritized`

- `lateral_shift_model = "first_order"`
  - did not improve `peakline_x_delta_um`
  - often worsened `image_relative_l2`
  - `delta_x_k_um` scale is far too small to explain the 2-3 um bridge/asymptotic lateral gap
  - now treated as `experimental_not_prioritized`

- `second_order_model = "slice_projected"`
  - raw version was numerically unstable
  - scaled version stabilized raw amplitude but still did not fix lateral peakline error
  - useful as a diagnostic, not as current main upgrade direction

### 3.2 Directional basis branch already tested

An explicit odd-field experiment has already been added:

- `directional_field_expansion_first_order`

This uses an odd first-order field basis:

- `B_k * R0(x) + D1_slice_k * R1(x) + C2_slice_k * R2(x)`

It was compared against:

- `tensor_closure`
- `directional_field_expansion`
- scaled/raw variants

Current conclusion:

- it is cleaner than plain envelope-shift heuristics
- but it still does **not** move `peakline_x_um` off `0`
- top-level machine-readable result is currently:
  - `directional_first_order_is_promising = false`

So this branch is also **not yet the answer**.

## 4. Representative Cases

The project now consistently uses 3 representative cases for evidence / ablation:

1. `sphere_low_na_low_contrast`
2. `mild_shape_medium_tilt`
3. `failure_domain_high_tilt_high_contrast`

These are the cases that should be used first in any new diagnostic before adding more complexity.

## 4.1 Coefficient Contract

Coefficient-path debugging should now treat `B_k / D1_slice_k / C2_slice_k` as one frozen contract, not as ad hoc arrays pulled from result dicts.

That contract now fixes:

- wavelength axis semantics
- slice-direction label
- fit-strategy metadata
- field-domain semantics
- shared-scale interpretation note

Use the package-level contract extractor before comparing or injecting coefficients.

## 4.2 Canonical Coefficient Bundle

The coefficient path now has a package-level canonical bundle:

- `C:\codex-data\OCT_Research_System\oct-research-assist\solvers\coefficient_path_bundle.py`

It also now has an explicit executable coefficient-map stage:

- `map_projected_to_rendered_coefficients(...)`

Supported audit models currently include:

- `identity_slice_projected_rendered_basis`
- `shared_complex_scale_map`
- `componentwise_complex_scale_map`
- `low_order_coupled_odd_even_map`
- `fitted_linear_map_3x3`

The current engineering interpretation is:

- do **not** assume projected angular coefficients are already the rendered coefficients
- treat the rendered `(a0, a1, a2)` space as the production-facing truth layer
- audit the map into that space before adding more basis freedom

## 4.3 Minimal measurement wrapper

A minimal Fourier-domain OCT wrapper now exists:

- `C:\codex-data\OCT_Research_System\oct-research-assist\oct_forward\fd_oct_measurement.py`

It currently provides:

- sample/reference interference-spectrum construction
- k-linearization to a uniform `k` grid
- optional dispersion-phase compensation
- IFFT A-scan reconstruction

It should be treated as the first measurement-grade wrapper scaffold, not as proof that the project is already a full acquisition / reconstruction simulator.

It is no longer only a parked scaffold:

- `measurement_protocol/psf_bias_protocol.py` now uses it as one of the main measurement-layer routes
- `measurement_protocol/bias_experiment.py` now records both:
  - `solver_output_peak_slice_adapter`
  - `fd_oct_reconstruction`
- `default_measurement_pipeline_mode` now prefers:
  - `fd_oct_reconstruction` when the solver result exposes the spectral sample-arm contract
  - otherwise it falls back to:
    - `solver_output_peak_slice_adapter`
- `validate_oct_nonspherical_psf_solver.py` now accepts that measurement package as explicit evidence and surfaces:
  - `measurement_pipeline_evidence_status`
  - `measurement_pipeline_default_mode`
  - `fd_oct_measurement_wrapper_status`
  - `measurement_reference_arm_policy`
  - `measurement_reference_arm_policy_status`

So the current branch should now be read as:

- a three-layer forward-diagnostic stack
- plus a minimal FD-OCT measurement wrapper that is now connected into the main measurement evidence chain
- but still not a full instrument-grade OCT acquisition / reconstruction simulator

This bundle is the current best answer to the earlier structural ambiguity between:

- angular-fit coefficients
- slice-projected coefficients
- rendered field-basis coefficients

The current branch now freezes the rendered production-facing coefficient space as:

- `a_render_k = (a0_k, a1_k, a2_k)`

where these coefficients multiply the actually rendered basis:

- `R0(x)`
- `R1(x)`
- `R2(x)`

Use this bundle instead of rebuilding coefficient semantics from loose result dict fragments.

The central structural change in the latest round is that the coefficient map is now an explicit executable stage:

- `map_projected_to_rendered_coefficients(...)`

The current production map is still:

- `identity_slice_projected_rendered_basis`

but the code now supports additional map models for audit and debugging work:

- `shared_complex_scale_map`
- `componentwise_complex_scale_map`
- `low_order_coupled_odd_even_map`
- `fitted_linear_map_3x3`

There is now also a second-stage audit for this map family:

- `reports/round6p1_coefficient_map_stability.json`
- `reports/round6p1_coefficient_map_stability.md`
- `reports/round6p1_coefficient_map_ablation.json`
- `reports/round6p1_coefficient_map_ablation.md`

This report answers a different question from the map audit:

- map audit:
  - "which map matches best if a case is allowed to fit itself?"
- map stability:
  - "which map still helps when fit on other representative cases and applied to a held-out case?"

Current answer:

- the map stage is real and useful
- but its strongest 3x3 case-specific form is not yet stable enough to become the production default
- the next engineering target is shared/constrained map generalization over an expanded panel, with `low_order_coupled_odd_even_map` currently the best shared candidate
- the currently promoted shared runtime model is:
  - `promoted_shared_map_model_id = low_order_coupled_odd_even_map`
- but its runtime scope is still:
  - `general_asymptotic_rendered_basis_override`
- and its current runtime constraint is:
  - `promoted_shared_map_runtime_supported_lateral_shift_models = ["none", "first_order"]`
  - `promoted_shared_map_runtime_shift_target = "baseline_envelope_ratio"`
  - `promoted_shared_map_runtime_lateral_shift_constraint = rendered_basis_override_supports_first_order_only_with_envelope_only_analytic_gaussian_or_rendered_interp`
- so it is now an explicit rendered-basis override contract, but not yet the native default for every asymptotic branch and not yet a generally promoted runtime for arbitrary lateral-shift families
- the currently supported promoted-shared first-order path is intentionally narrow:
  - `lateral_shift_coupling = "envelope_only"`
  - `rendered_basis_shift_target = "baseline_envelope_ratio"` with `lateral_shift_impl = "analytic_gaussian"`
  - or `rendered_basis_shift_target = "rendered_field_interp"` with `lateral_shift_impl in {"interp", "interp_edge_hold"}`
- result payloads now also split:
  - `requested_second_order_model`
  - `runtime_field_assembly_contract`
  so downstream tooling does not need to infer actual runtime assembly semantics from `second_order_model` alone
- runtime payloads now also expose:
  - `runtime_field_assembly_shift_target`
  - `runtime_field_assembly_shift_target_note`
  - `na_scalar_validity_status`
  - `requires_vector_diffraction`
  so downstream tooling can distinguish field-assembly shift semantics from scalar-domain validity.

Representative runs now also write semantically split coefficient artifacts:

- native asymptotic baseline bundle:
  - `reports/round6p1_<case>_native_identity_coefficient_bundle.npz`
- promoted shared-map runtime bundle:
  - `reports/round6p1_<case>_shared_map_promoted_<model>_coefficient_bundle.npz`
- case-specific fitted-map diagnostic bundle:
  - `reports/round6p1_<case>_case_specific_fitted_map_diagnostic_bundle.npz`

These artifacts are the preferred offline debugging surface for coefficient-path inspection. They now support:

- actual serialized `fit_diagnostics` payloads, not only key lists
- `read_coefficient_path_bundle_npz(...)`
- `validate_coefficient_path_bundle_payload(...)`

Legacy generic `reports/round6p1_<case>_coefficient_bundle.npz` artifacts are now treated as stale compatibility leftovers and are removed by the evidence builder before fresh report regeneration.

The six core coefficient-path diagnostics should now be treated as consumers of this bundle, not as independent coefficient reconstructions:

- basis projection
- coefficient recovery
- coefficient injection
- fit sensitivity
- fit strategy ablation
- slice-axis crosscheck

## 5. Validator / Reporting State

Validator has already been upgraded substantially.

### Implemented

- machine-readable `status`
- machine-readable `status_category`
- machine-readable `status_reason`
- strict gate support via `--strict-gates` or `OCT_VALIDATE_STRICT=1`
- top-level:
  - `most_critical_open_model_limit`
  - `recommended_next_action`
  - `directional_first_order_is_promising`

### Important semantic split already in place

`mu2` dispersion reporting has been split into:

- `mu2_dispersion_current_case_gate`
- `mu2_dispersion_benchmark_design`

This avoids confusing "current case is fine" with "frozen-at-lambda0 is universally safe".

### Standalone diagnostics

Standalone coefficient-path diagnostics now probe backend availability before heavy work.

If the current runtime cannot load a supported T-matrix backend, they should:

- write a structured skipped JSON/MD report
- exit cleanly
- avoid raw traceback as the user-facing failure mode

## 6. Key Files Already Modified

Core solver / experiments:

- `C:\codex-data\OCT_Research_System\oct-research-assist\scripts\11_low_na_asymptotic.py`
- `C:\codex-data\OCT_Research_System\oct-research-assist\scripts\oct_nonspherical_psf_solver.py`
- `C:\codex-data\OCT_Research_System\oct-research-assist\scripts\validate_oct_nonspherical_psf_solver.py`
- `C:\codex-data\OCT_Research_System\oct-research-assist\scripts\build_round6p1_evidence_package.py`
- `C:\codex-data\OCT_Research_System\oct-research-assist\test_low_na_asymptotic_helpers.py`

Reports / docs already updated:

- `C:\codex-data\OCT_Research_System\oct-research-assist\reports\round6p1_update.md`
- `C:\codex-data\OCT_Research_System\oct-research-assist\reports\round6p1_validation_summary.json`
- `C:\codex-data\OCT_Research_System\oct-research-assist\reports\round6p1_validation_failure_summary.txt`
- `C:\codex-data\OCT_Research_System\oct-research-assist\reports\round6p1_ablation_results.md`
- `C:\codex-data\OCT_Research_System\oct-research-assist\reports\round6p1_error_attribution.md`
- `C:\codex-data\OCT_Research_System\oct-research-assist\reports\round6p1_measurement_protocol_bias.md`
- `C:\codex-data\OCT_Research_System\oct-research-assist\reports\result_schema_round6p1.md`
- `C:\codex-data\OCT_Research_System\oct-research-assist\reports\benchmark_gates_round6p1.md`
- `C:\codex-data\OCT_Research_System\oct-research-assist\reports\known_limits_round6p1.md`

Latest already-built Plus review bundle before the shell failure:

- `C:\codex-data\OCT_Research_System\oct-research-assist\reports\plus_review_bundle_round6_latest_20260420-115325.zip`

## 7. Basis Projection And Coefficient Recovery Diagnostics

A basis-projection diagnostic script already exists and has been run:

- `C:\codex-data\OCT_Research_System\oct-research-assist\scripts\14_bridge_basis_projection_diagnostics.py`
- `C:\codex-data\OCT_Research_System\oct-research-assist\scripts\15_bridge_basis_coefficient_recovery.py`

### Purpose

This script is intended to answer the next critical question:

> Can the current bridge complex slice be represented by the existing asymptotic basis family `(R0, R1, R2)` at all?

### What it is supposed to do

For each representative case:

1. obtain bridge complex slice field `E_bridge(k, x)`
2. obtain asymptotic basis profiles:
   - `R0`
   - `R1`
   - `R2`
3. fit three models by least squares:
   - `R0`
   - `R0 + R2`
   - `R0 + R1 + R2`
4. report:
   - `field_relative_l2`
   - `intensity_relative_l2`
   - `peakline_x_um`
   - `peakline_x_delta_um_vs_bridge`
   - coefficient ratios such as `|a1|/|a0|`, `|a2|/|a0|`

Current report outputs:

- `C:\codex-data\OCT_Research_System\oct-research-assist\reports\round6p1_basis_projection_diagnostics.json`
- `C:\codex-data\OCT_Research_System\oct-research-assist\reports\round6p1_basis_projection_diagnostics.md`
- `C:\codex-data\OCT_Research_System\oct-research-assist\reports\round6p1_basis_coefficient_recovery.json`
- `C:\codex-data\OCT_Research_System\oct-research-assist\reports\round6p1_basis_coefficient_recovery.md`
- `C:\codex-data\OCT_Research_System\oct-research-assist\reports\round6p1_coefficient_injection_diagnostics.json`
- `C:\codex-data\OCT_Research_System\oct-research-assist\reports\round6p1_coefficient_injection_diagnostics.md`

### Current interpretation

- `R0 + R1 + R2` is expressive enough to recover the bridge peakline location.
- The coefficient-recovery report shows that bridge-recovered `a1(k)` is orders of magnitude larger than the current asymptotic `D1_slice_k / B_k` ratio.
- `a0` and `a2` are less wrong than `a1`, but they still do not share one clean global complex rescaling; treat them as "less wrong than `a1`", not as already solved.
- The current next action is therefore:
  - `debug_coefficient_extraction_or_usage_mapping`
- The coefficient-injection report strengthens this further:
  - when bridge-recovered `(a0, a1, a2)` are injected into the current asymptotic directional field structure, solver-vs-bridge agreement improves dramatically on all 3 representative cases.
  - This means the current field structure is not the main bottleneck; the coefficient extraction / usage path is the better debugging target.

### Reporting behavior

`validate_oct_nonspherical_psf_solver.py` no longer auto-loads old basis-projection JSON from disk.

- If a caller explicitly passes a basis-projection and/or coefficient-recovery report, validator merges it.
- Otherwise validator intentionally falls back to placeholder guidance for that diagnostic family.

This prevents stale artifacts from contaminating a fresh validation run.

## 8. Current Status

The current stack should now be described more carefully:

- It **is**:
  - a particle-response solver family
  - a bridge / asymptotic diagnostic stack
  - a minimal measurement-bias extraction layer (`measurement_protocol/psf_bias_protocol.py`) on top of solver outputs
- It is **not yet**:
  - a raw-domain OCT interferogram simulator
  - a recon-domain complex-volume forward model
  - a finished inverse / deconvolution stack

Important baseline caveat:

- `low_na_separable_baseline` is now explicitly labeled as an **axial-spectrum baseline**
- its lateral profile remains a Gaussian system surrogate
- therefore it must not be interpreted as a particle-aware lateral PSF baseline

The earlier shell blocker has been resolved in later threads. The project is currently in a state where:

 - basis-projection evidence is active
 - coefficient-recovery evidence is active
 - top-level validator guidance already resolves to the coefficient-recovery conclusion when the explicit evidence package is rebuilt
 - a first Pro-aligned package split now exists:
   - `apps/report_paths.py`
   - `physics/tmatrix_backend.py`
   - `solvers/effective_channel_coefficients.py`
 - numbered scripts are still the outer compatibility shell, but these package modules are now the preferred anchor points for new runtime-path, backend, and coefficient-path work

## 9. First Actions For A New Thread

If a new thread resumes this project, the first useful steps are:

1. Re-run:
   - `C:\codex-data\OCT_Research_System\oct-research-assist\scripts\build_round6p1_evidence_package.py`
2. Confirm the top-level summary still says:
   - `final_recommended_next_action = "debug_coefficient_extraction_or_usage_mapping"`
3. Use the coefficient-recovery report to inspect why the current `D1_slice_k` pathway under-realizes the odd directional coefficient seen in the bridge fit.
4. Use the shared-scale and orthonormalization diagnostics in `round6p1_basis_coefficient_recovery.{json,md}` to check whether a mismatch is truly physical or partly a basis-conditioning artifact.
5. Use `round6p1_coefficient_injection_diagnostics.{json,md}` to confirm whether replacing solver coefficients with bridge-recovered coefficients closes the gap; if it does, prioritize coefficient-path debugging over basis-family expansion.
6. Treat the current `joint_low_order` fit-strategy evidence cautiously but no longer as semantically broken.
   - A residual-bookkeeping bug was fixed: `joint_low_order` residuals are now evaluated with the full low-order reconstruction instead of the even-only tensor reconstruction.
   - The fit-strategy ablation still lands on:
     - `effective_channel_fit_strategy_recommended_next_action = "joint_low_order_fit_not_yet_decisive"`
   - So the present evidence says:
     - `joint_low_order` is no longer being judged by the wrong residual,
     - but it still does not yet outrank coefficient-path debugging as the next best action.

### Step 5

Regenerate a new Plus review bundle that includes the refreshed basis-projection and coefficient-recovery evidence.

## 11. Decision Rule After Basis Projection

This is the main scientific fork for the next round.

### If `R0 + R1 + R2` fits bridge significantly better than `R0 + R2`

Interpretation:

- the current basis family may actually be expressive enough
- the problem is more likely in coefficient extraction / coefficient usage

Recommended direction:

- debug asymptotic coefficient extraction or promote a stronger directional basis usage
- if coefficient injection also sharply improves bridge agreement, prioritize coefficient extraction / usage mapping before adding any new basis freedom

### If `R0 + R1 + R2` still does not fit bridge well

Interpretation:

- the current asymptotic basis family itself is too weak
- continuing to patch this asymptotic family is likely low-yield

Recommended direction:

- stop expanding the current asymptotic basis family
- shift emphasis toward higher-order overlap / bridge / exact-regular-particle work

## 12. One-Sentence Handoff Prompt For The New Thread

Use this exact prompt in the new conversation if needed:

> Continue from `reports/round6p1_new_thread_handoff.md`. Do not change the default solver. First restore shell execution if needed, then run `scripts/14_bridge_basis_projection_diagnostics.py`, turn `basis_projection_recommended_next_action` from a placeholder into a real top-level validator conclusion, rerun verification, and regenerate the latest Plus review bundle.

Updated prompt for the current state:

> Continue from `reports/round6p1_new_thread_handoff.md`. Do not change the default solver. Rebuild the full evidence package, verify that `final_recommended_next_action = "debug_coefficient_extraction_or_usage_mapping"` with source `coefficient_injection`, confirm that `joint_low_order` still remains not yet decisive after the corrected low-order residual bookkeeping, then focus on debugging how `B_k`, `D1_slice_k`, and `C2_slice_k` are extracted and mapped into the solver-level field model.

Current package anchors that should be preferred over numbered-script-local helper copies:

- `apps/report_paths.py`
- `diagnostics/bridge_basis_projection.py`
- `diagnostics/basis_coefficient_recovery.py`
- `diagnostics/coefficient_injection.py`
- `diagnostics/fit_sensitivity.py`
- `diagnostics/fit_strategy_ablation.py`
- `diagnostics/slice_axis_crosscheck.py`
- `diagnostics/coefficient_map_stability.py`
- `measurement_protocol/bias_experiment.py`
- `oct_forward/result_contract.py`
- `physics/tmatrix_backend.py`
- `solvers/effective_channel_coefficients.py`
- `solvers/coefficient_path_bundle.py`
- `solvers/low_na_effective_channel.py`

When refactoring or debugging the asymptotic coefficient path, prefer updating these package modules first and keep:

- `11_low_na_asymptotic.py`
- `14_bridge_basis_projection_diagnostics.py`
- `15_bridge_basis_coefficient_recovery.py`
- `16_effective_channel_fit_sensitivity.py`
- `17_bridge_coefficient_injection_diagnostics.py`
- `18_effective_channel_fit_strategy_ablation.py`
- `19_lateral_slice_axis_crosscheck.py`

as compatibility shells until the rest of the numbered-script migration is complete.
