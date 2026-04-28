# Pro Review Handoff - 2026-04-28

This handoff indexes the current review-ready state after the sphere Mie branch
and CPython 3.10 T-matrix evidence refresh.

## Current Remote State

- Repository: <https://github.com/dongfanghong656/OMPCP>
- Current `main` commit: `cae977d72c65dce16d550d8679af8539804b1bd1`
- Sphere branch code/evidence commit: `5dc1840f913f3835de64ccd364f28fc96f2b1ae2`
- CPython 3.10 + T-matrix CI run: <https://github.com/dongfanghong656/OMPCP/actions/runs/25055145522>
- CI result used for imported evidence: `completed / success`

The latest `main` commit is report-only. The full CPython 3.10 T-matrix rebuild
was performed by CI run `25055145522` at commit `5dc1840f...`; its lightweight
reports were imported into the canonical `reports/` directory and then published
in commit `cae977d...`.

## What Changed Since The Previous Pro Packet

- Added a pure sphere Mie full-NA branch that does not require the non-spherical
  T-matrix backend when `eps = 0`, `ideal = false`, and `force_tmatrix = false`.
- Added explicit sphere branch metadata:
  `sphere_mie_used`, `tmatrix_used`, `tmatrix_backend_required`,
  `scattering_branch`, `lateral_response_model`, and
  `particle_lateral_scattering_enters_profile`.
- Added explicit sample-arm spectral cube contract metadata:
  `sample_arm_spectral_cube_shape`,
  `sample_arm_spectral_cube_axis_order`,
  `sample_arm_spectral_cube_quantity_kind`,
  `sample_arm_spectral_cube_contract_status`, and
  `fd_oct_measurement_scaffold_route_available`.
- Updated the sphere sweep runner so rows and summaries expose the sphere branch
  contract, FD-OCT scaffold availability, `interpretation_status`, and
  `paper_safety_status`.
- Tightened validator checks so `full_na_sphere_mie_branch_without_tmatrix`
  requires both the sphere Mie branch and a valid spectral cube contract.
- Imported fresh CPython 3.10 T-matrix evidence from GitHub Actions into the
  canonical reports directory with a checksum manifest.
- Added the first sphere Mie full-NA convergence scaffold:
  `reports/round6p1_sphere_convergence_progress_20260428.md` and
  `reports/sphere_mie_convergence_20260428/sphere_mie_convergence_summary.md`.

## Primary Evidence Files

- `reports/round6p1_validation_summary.json`
- `reports/round6p1_validation_failure_summary.txt`
- `reports/round6p1_measurement_protocol_bias.json`
- `reports/round6p1_ci_evidence_import_manifest.md`
- `reports/round6p1_cp310_evidence_rebuild_readiness.md`
- `reports/pytmatrix-diagnose.json`
- `reports/particle_size_sweep_ci_backend_provenance.json`
- `reports/particle_size_sweep_ci/particle_size_sweep_summary.json`
- `reports/round6p1_sphere_branch_independent_review_20260428.md`
- `reports/sphere_mie_full_na_acceptance_20260428_v2/sphere_mie_full_na_sweep_summary.json`
- `reports/round6p1_sphere_psf_bias_progress_20260428.md`
- `reports/sphere_mie_full_na_psf_bias_20260428/sphere_mie_full_na_sweep_summary.md`
- `reports/round6p1_sphere_convergence_progress_20260428.md`
- `reports/sphere_mie_convergence_20260428/sphere_mie_convergence_summary.md`

## Verified Status

- Local sphere Mie branch contract tests: `5 tests OK`.
- Local full helper suite: `82 tests OK`.
- Local sphere Mie full-NA acceptance sweep: `3 / 3 cases OK`.
- Local validator: `exit 0`.
- GitHub Actions CPython 3.10 T-matrix run: `success`.
- Imported CI reports: `35` files, checksummed in
  `round6p1_ci_evidence_import_manifest`.
- Sphere Mie convergence scaffold: `preliminary_convergence_attention_not_paper_safe`.

Key machine-readable findings in the current validation summary:

- `full_na_sphere_mie_branch_without_tmatrix`: `pass`
- `sphere_sample_arm_spectral_cube_contract_status`:
  `valid_lambda_x_complex_field`
- `sphere_fd_oct_measurement_scaffold_route_available`: `true`
- `measurement_fd_oct_depth_policy_status`:
  `medium_effective_k_geometric_depth_axis_declared`
- `promoted_shared_map_model_id`: `low_order_coupled_odd_even_map`
- `dominant_error_bucket`: `lateral_shift`
- `final_recommended_next_action`:
  `require_train_eval_generalization_before_promoting_fitted_map`

## Remaining Limits To Review

- The sphere branch is now a particle-aware Mie full-NA route, but it is still
  not a final device-grade OCT truth simulator.
- The FD-OCT measurement layer remains a scaffold-level measurement wrapper,
  not a complete raw-domain interferometer model.
- The pure sphere route is separated from T-matrix, but non-spherical evidence
  still depends on the CPython 3.10 Windows-compatible PyTMatrix backend in CI.
- The project still carries the round6p1 main model limit:
  `low_na_asymptotic_absolute_alignment_gate` with dominant `lateral_shift`.
- The promoted shared coefficient map remains the best shared diagnostic route;
  the fitted 3x3 map should not be promoted without train/eval generalization.

## Review Request

Please focus review on these questions:

1. Is the pure sphere Mie branch contract sufficient to separate exact spheres
   from non-spherical T-matrix evidence?
2. Are the `sample_arm_spectral_cube_*` fields enough for downstream FD-OCT
   measurement-protocol auditing?
3. Does the current imported CPython 3.10 T-matrix evidence resolve artifact
   freshness concerns from the previous packet?
4. What is the next minimum evidence needed before claiming 200-1000 nm sphere
   PSF distortion trends are paper-safe?
