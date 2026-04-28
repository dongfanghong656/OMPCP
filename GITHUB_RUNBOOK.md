# GitHub Runbook

This repository is prepared for the OMPCP GitHub workflow that regenerates T-matrix-backed round6p1 evidence on Windows CPython 3.10.

## Local smoke checks

```powershell
python 12_test_low_na_asymptotic_helpers.py
python scripts/validate_oct_nonspherical_psf_solver.py
python scripts/build_round6p1_evidence_package.py
```

On non-Windows or non-CPython-3.10 environments, T-matrix-dependent diagnostics may structured-skip. That is expected unless a compatible backend is installed.

## Required-backend evidence rebuild

Use this on Windows x64 with CPython 3.10 and a working PyTMatrix backend:

```powershell
python scripts/controlled_cp310_evidence_rebuild.py `
  --execute `
  --strict `
  --tmatrix-backend vendored_pytmatrix `
  --reports-dir reports `
  --rebuild-reports-dir reports/round6p1_cp310_rebuild
```

Then run the smallest T-matrix-required particle-size sweep:

```powershell
python scripts/particle_size_sweep_runner.py `
  --diameters 200,300 `
  --mode vector_pupil_overlap_bridge `
  --tmatrix-backend vendored_pytmatrix `
  --require-tmatrix-backend `
  --backend-provenance-out reports/particle_size_sweep_backend_provenance.json `
  --output-dir reports/particle_size_sweep_required_backend `
  --no-plots
```

## GitHub Actions

The workflow at `.github/workflows/build-pytmatrix-backend.yml` runs on `windows-2022`, installs CPython 3.10, builds the vendored PyTMatrix backend, validates it, rebuilds evidence with a required backend, and uploads `reports/**` plus the compiled backend artifact.

The bootstrap step also copies the MinGW/Fortran runtime DLLs next to the generated `pytmatrix*.pyd`. Without those DLLs, the extension can compile successfully but still fail at import time with `DLL load failed`, which is exactly the failure mode this workflow is meant to catch.

The workflow is intentionally strict: if the backend cannot be built or required evidence cannot be regenerated, CI should fail instead of producing a skipped report that looks complete.

## Import CI Evidence Back Into Canonical Reports

After downloading and extracting the `pytmatrix-reports` GitHub Actions artifact, import the CPython 3.10 evidence into the local canonical `reports/` directory:

```powershell
python scripts/import_ci_evidence_artifacts.py `
  --artifact-dir reports/actions_run_<RUN_ID>_reports `
  --reports-dir reports `
  --source-run-id <RUN_ID> `
  --source-head-sha <HEAD_SHA>
```

Use `--dry-run` first when checking a new artifact layout. The import writes:

- `reports/round6p1_ci_evidence_import_manifest.json`
- `reports/round6p1_ci_evidence_import_manifest.md`
- CI provenance fields inside `reports/round6p1_validation_summary.json`

This step is intentionally separate from the evidence rebuild. It prevents source/report drift by making it explicit when the canonical local reports came from a GitHub Actions CPython 3.10 + T-matrix run rather than the current local interpreter.
