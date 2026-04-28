# OCT Research Assist

This is an OCT-focused research operations system inspired by `research-assist`, but adapted for:

- `SD-OCT` and `SS-OCT`
- lateral resolution enhancement
- deconvolution and PSF studies
- MATLAB-heavy workflows
- a mixed evidence base of phantom, ex vivo, and local PDFs

## Design goals

1. Keep the knowledge base readable by both humans and Codex
2. Treat Zotero as evidence, not just storage
3. Maintain an Obsidian-compatible vault as the durable ground truth
4. Generate a daily digest from recent papers and project state
5. Allow every future conversation to expand the same library
6. Preserve durable people and relationship context alongside research notes
7. Keep tri-agent bridge state visible in the same vault instead of scattering it across runtime folders only

## Layout

- `config.example.json`: Runtime configuration template
- `config.json`: Local runtime configuration for this workspace
- `profiles/`: Research interest profiles
- `references/`: Architecture and workflow notes
- `scripts/`: Retrieval, ingestion, digest, and note-maintenance scripts
- `vault/`: Obsidian-compatible knowledge vault
- `reports/`: Generated daily digest and system probes

## Solver guardrails

For OCT solver / PSF / T-matrix / non-spherical particle-response code work, read:

- `references/OCT_SOLVER_IMPLEMENTATION_GUARDRAILS.md`
- `references/OCT_SOLVER_DEBUGGING_PLAYBOOK.md`
- `references/theory_contract_round6p1_pro_aligned.md`
- `references/theory_contract_round6.md`
- `references/solver_upgrade_strategy_bridge_asymptotic.md`
- `references/round6_task_sheet_bridge_asymptotic.md`

Those notes capture the repeated physical-model, naming, export-semantics, validator, and reviewer-facing mistakes discovered during the 2026-04 solver review iterations, so future code does not silently reintroduce them.

Priority note:

- `references/theory_contract_round6p1_pro_aligned.md` is now the primary theory guide for the current coefficient-debug phase.
- If it conflicts with older round6 wording, follow the Pro-aligned theory contract first.

## Tri-agent vault sync

If Codex, Claude Code, or Antigravity update runtime state under `C:/codex-data/ai_bridge`, refresh the vault-facing mirror with:

```powershell
python scripts/sync_tri_agent_workspace.py
```

This writes unified Obsidian notes for:

- provider roles and runtime health
- queued and completed tasks
- packet-level conversation index
- bridge knowledge and materials index
- cross-agent progress and modification history

## Current status

- Ready:
  - local vault
  - openclaw-inspired system map, learning path, automation playbooks, and search guide
  - local profile
  - arXiv/OpenAlex retrieval
  - multi-source discovery-to-Zotero normalization pipeline
  - local PDF to Zotero import with attachment upload, tags, and collection classification
  - Zotero-to-vault backfill notes with paper-note sync blocks
  - paper note generation
  - MinerU-based translated paper rendering for Obsidian
  - conversation note generation
  - relationship memory with person profiles and interaction-event history
  - daily digest generation
  - Zotero environment probing with custom data-directory detection
  - Zotero local sqlite snapshot generation
  - Google Scholar MCP config scaffold
- Pending credentials:
  - Zotero Web API writeback
  - email delivery login password
  - Google Drive private access

## Local secret store

`config.json` can now keep secure references instead of plaintext credentials. The actual values are stored in a local DPAPI-backed file under:

- `../.codex-local/secure-secrets.v1.json`

That local store is encrypted for the current Windows user and ignored by git. The repo only keeps reference objects such as:

```json
{
  "$secure_ref": "zotero.web"
}
```

Migrate any existing plaintext secrets out of `config.json`:

```powershell
python scripts/local_secret_store.py migrate-config --config config.json
```

Check status without revealing values:

```powershell
python scripts/local_secret_store.py status --config config.json
```

Set or replace one local secret value:

```powershell
python scripts/local_secret_store.py set --config config.json --secret-id zotero.web --value "..."
```

## Translation workflow

The ingestion pipeline now supports a second stage after MinerU extraction:

- `manual` mode:
  - run `scripts/ingest_pdf_to_vault.ps1 ... -Translate -TranslationMode manual`
  - this creates a `translation-template.json` file under the translated-paper output folder
  - fill the `translation` field for each block, then render the final note with `scripts/translate_paper.py build --mode manual`
- `ai` mode:
  - store `openai.translate` in the local secret store or export `OPENAI_API_KEY`
  - run `scripts/ingest_pdf_to_vault.ps1 ... -Translate -TranslationMode ai`
  - the system will translate text blocks, preserve formulas, copy MinerU images, and emit an Obsidian-friendly markdown file under `08_Attachments/translated-papers`

The translated note path and the manual-template path are written back into the seeded paper note when available.

## Discovery to Zotero workflow

The workspace now includes `scripts/discovery_to_zotero.py` for the specific case where literature leads come from `Consensus`, `X-MOL`, `Google Scholar`, exported `RIS/CSV`, or direct `OpenAlex` search:

- normalize lead metadata into one internal schema
- enrich or verify metadata through `OpenAlex`
- deduplicate against the local Zotero sqlite library
- write directly to Zotero through the Web API when credentials are configured
- otherwise generate a clean `RIS` import file plus machine-readable run logs

Use the unified lead schema before pasting copied discovery results:

- field specification: `references/discovery-lead-schema.md`
- JSON template: `references/discovery-leads.example.json`
- CSV template: `references/discovery-leads.example.csv`
- operating model and commands: `references/discovery-to-zotero-workflow.md`

## Local PDF to Zotero workflow

The workspace now also includes `scripts/local_pdf_to_zotero.py` for importing local paper PDFs into Zotero:

- infer title, authors, year, and DOI from PDF metadata, file name, and the first pages
- enrich metadata through `OpenAlex` when DOI or title resolution succeeds
- reuse existing paper-note frontmatter as an override source when the PDF text is noisy
- deduplicate against the local Zotero sqlite library
- attach the PDF to an existing Zotero parent item when possible
- otherwise create a new Zotero parent item and upload the PDF attachment
- add tags and assign collections from CLI flags, metadata files, folder paths, and keyword rules

Use these supporting files:

- metadata template: `references/local-pdf-upload.example.json`
- workflow doc: `references/local-pdf-to-zotero-workflow.md`
- config example: `references/config-templates.md`

## Zotero to vault workflow

The workspace also includes `scripts/zotero_to_vault.py` for writing Zotero item state back into the Obsidian-compatible vault:

- read candidate items from a `local_pdf_to_zotero.py` `run.json` file or from live PDF discovery inputs
- or scan existing `02_Literature/Papers` notes that already carry Zotero sync blocks
- resolve or seed the matching paper note under `02_Literature/Papers`
- create a Zotero backfill note under `12_Zotero/04_Item-Backfills`
- insert a managed `Zotero Sync` block into the paper note with the Zotero key, tags, collections, attachments, and a link back to the Zotero note
- fall back to local candidate metadata when the Zotero Web API is temporarily unavailable

Use these supporting files:

- workflow doc: `references/zotero-to-vault-workflow.md`
- batch source report: `reports/local-pdf-to-zotero/<run-id>/run.json`

## Zotero curation workflow

The workspace also includes `scripts/zotero_curate.py` for the case where a Zotero item already exists but its tags, collections, or selected metadata fields need to be normalized in a repeatable way:

- curate by Zotero item key instead of re-importing the paper
- add, remove, or reorder tags
- add, remove, or create collections from human-readable collection paths
- preserve existing extras while forcing a stable research-library ordering
- write a dedicated curation report before the vault backfill step

Use these supporting files:

- workflow doc: `references/zotero-curation-workflow.md`
- template: `references/zotero-curation.example.json`

For large cleanup passes, the workspace also includes `scripts/build_zotero_tag_hygiene_targets.py`, which scans `02_Literature/Papers`, reads the current Zotero tags, strips configured provenance noise such as `discovery:*` and `verification:*`, and emits a ready-to-run curation JSON file for `scripts/zotero_curate.py`.

The companion `scripts/build_zotero_collection_hygiene_targets.py` does the same for collections: it reads the current remote collection paths, drops configured operational collections such as `Local PDF Imports`, and emits an exact `collection_paths` target set for each Zotero-backed paper note.

When you want a full vault backfill without depending on noisy PDF parsing, use `scripts/build_zotero_backfill_run_from_notes.py`. It scans `02_Literature/Papers`, extracts `zotero_key` plus the stored `source_pdf`, and emits a stable `run.json` that can be fed directly into `scripts/zotero_to_vault.py`.

When note filenames or frontmatter years drift away from the canonical Zotero item, use `scripts/reconcile_zotero_note_consistency.py` before the next backfill. It aligns the paper-note year, rewrites year-bound template fields such as `citation_title`, `citation_key`, and `filename_title`, renames the note when needed, and updates vault links to the renamed note. A follow-up `scripts/zotero_to_vault.py --scan-paper-notes` pass then refreshes the Zotero sync blocks and removes stale duplicate backfill notes for the same `zotero_key`.

When a paper note is missing bibliographic fields that already exist in Zotero, use `scripts/sync_paper_note_frontmatter_from_zotero.py`. It fills missing `venue`, `doi`, `url`, and `authors` frontmatter values from the remote Zotero item without overwriting existing note metadata unless you pass `--overwrite`.

For legacy markdown that still contains reversible Chinese mojibake such as `鍩轰簬...`, the workspace also includes `scripts/repair_mojibake_note_content.py`. It scores suspicious notes, attempts a conservative `cp936/gbk -> utf-8` reversal on long non-ASCII segments, and only writes the repaired text when the mojibake score drops.

On this machine, apparent Chinese mojibake can also come from terminal display encoding rather than the underlying UTF-8 file contents. If a note looks garbled in PowerShell, verify it through a UTF-8 aware Python read or a vault/editor view before treating it as on-disk corruption.

## Research question workflow

The repository now includes a first-pass workflow for turning a messy academic question into:

- auto-retrieved evidence snippets from relevant vault notes
- an `evidence_brief.json` briefing that buckets evidence into claims, strongest support, weaknesses, transfer value, and related roles
- a structured `question_pack.json`
- a structured `answer.json`
- a structured `critique.json`
- a human-readable `answer.md`
- a human-readable `critique.md`
- an optional vault conversation note and research-question note

The flow now searches relevant vault notes by default before structuring the question, then uses `gpt-5-mini` for question extraction, `gpt-5.4` with high reasoning effort for the answer stage, and a second `gpt-5.4` critique pass that acts like a skeptical reviewer. Configure these under `academic_qa` in `config.json` with secure refs, or export `OPENAI_API_KEY`.

For structured paper notes under `02_Literature/Papers`, the retriever now tries to preserve evidence roles such as `core_claim`, `strongest_evidence`, `weakness_or_risk`, `transfer_value`, and `user_question_answer` so the later model stages can treat different note blocks differently.

Those role hints are also collapsed into a fixed `evidence_brief` object before the prepare stage, so the model sees a research-style evidence briefing first and the raw evidence list second.

Example:

```powershell
python scripts/research_question_flow.py run `
  --config config.json `
  --title "PSF mismatch under lateral deconvolution" `
  --question "When OCT lateral-resolution enhancement relies on a measured or fitted PSF, how sensitive is the final gain to PSF mismatch and noise amplification?" `
  --evidence-file ".\reports\2026-03-20_OCT知识分类框架与底层习惯.md" `
  --evidence-text "Current system constraint: we do not have a strict ground truth, so the answer must discuss evidence strategy under no-ground-truth conditions."
```

To stop after the structuring step and inspect the generated pack first:

```powershell
python scripts/research_question_flow.py prepare --config config.json --question-file .\my-question.md
```

To answer an existing pack later:

```powershell
python scripts/research_question_flow.py answer --config config.json --question-pack .\reports\research-question-flow\...\question_pack.json
```

To skip the reviewer-style critique pass for a faster run:

```powershell
python scripts/research_question_flow.py run --config config.json --question-file .\my-question.md --skip-critique
```

To disable the vault note retrieval step and rely only on manually supplied evidence:

```powershell
python scripts/research_question_flow.py run --config config.json --question-file .\my-question.md --skip-auto-evidence
```

## Question radar workflow

The repository now also includes a `question_radar.py` workflow for mining high-value academic questions before you commit to a full answer pass. It supports three modes:

- `conversation`: mine latent research questions from a discussion transcript and optional supporting evidence
- `manual`: manually generate a ranked set of academic questions from a topic prompt
- `daily`: scan recent vault activity, merge it with the latest literature snapshot, and write a visible question radar note plus a daily-note summary

The radar workflow writes a structured `question_radar.json`, a human-readable `question_radar.md`, a `context_snapshot.json`, and, by default, a vault note under the configured question folder. In daily mode it also appends a compact summary to the current daily note so the generated questions surface in the place you are most likely to check.

Configure the defaults under `question_radar` in `config.json`. The workflow uses `gpt-5.4` with high reasoning effort by default and reuses the existing `academic_qa` auto-evidence retrieval settings for `conversation` and `manual` mode.

Mine questions from a conversation:

```powershell
python scripts/question_radar.py conversation `
  --config config.json `
  --title "PSF validation discussion" `
  --conversation-file .\conversation.md `
  --write-daily-note
```

Generate questions manually from a prompt:

```powershell
python scripts/question_radar.py manual `
  --config config.json `
  --title "PSF mismatch pressure points" `
  --prompt "Generate a small set of high-value questions about PSF mismatch, repeatability, and manuscript-grade validation."
```

Run the daily question radar using the latest literature file only:

```powershell
python scripts/question_radar.py daily `
  --config config.json `
  --latest-literature-file .\vault\11_Retrieval\2026-03-23-retrieval.json `
  --skip-live-literature
```

Run the daily question radar with live OpenAlex/arXiv refresh:

```powershell
python scripts/question_radar.py daily --config config.json
```

## Daily research cycle

If you want one command that ties together literature retrieval, daily question generation, and the digest report, use `daily_research_cycle.py`.

By default it runs:

1. `retrieve_recent_papers.py`
2. `question_radar.py daily`
3. `daily_digest.py`

It then writes a summary bundle under `reports/daily-research-cycle/...` and appends a short `Daily Research Cycle` section to the current daily note.

Run the full cycle:

```powershell
python scripts/daily_research_cycle.py --config config.json
```

Run the cycle without refreshing literature live and instead reuse an existing retrieval snapshot:

```powershell
python scripts/daily_research_cycle.py `
  --config config.json `
  --skip-retrieval `
  --latest-literature-file .\vault\11_Retrieval\2026-03-23-retrieval.json
```

## Continuous research loop

To turn the current scripts into a long-running research program instead of isolated one-off runs, use `continuous_research_loop.py`.

This workflow adds a lightweight `manifest.json` inspired by staged autonomous-research systems, but keeps the human researcher in the loop. The manifest tracks long-lived stages such as:

- literature refresh
- question radar
- question answering
- experiment analysis
- results report
- writing memory
- self review
- draft builder
- rebuttal scaffold
- journal targeting
- response letter
- citation audit
- submission QC
- draft health
- submission memory

It can:

- initialize a persistent research session
- run the daily cycle and attach its outputs to the session
- keep a progress note in the vault updated from the manifest
- attach manual artifacts from MATLAB runs, experiment folders, or writing drafts to the appropriate stage
- extract reusable writing memory from grounded analysis outputs
- run an evidence-constrained self review on a manuscript draft
- generate section-aware manuscript blocks from grounded artifacts
- prepare reviewer-response and rebuttal scaffolds before submission
- adapt the current paper stack toward a specific journal or venue
- track response-letter drafts across rounds instead of overwriting them
- audit citation and evidence-linking risk before final export
- run one last go/no-go QC pass before submission
- support recurring draft health checks instead of one-shot QC
- write durable venue/round memory so later revisions start with context
- run the whole late-stage paper-finishing chain in one command when the draft is ready

Create a new research session:

```powershell
python scripts/continuous_research_loop.py init `
  --config config.json `
  --title "OCT deconvolution reliability program" `
  --objective "Build a continuous evidence loop from literature and questions into experiment-grounded manuscript claims."
```

Run the daily cycle through the manifest:

```powershell
python scripts/continuous_research_loop.py run-daily `
  --manifest .\reports\continuous-research\...\manifest.json
```

Attach a manual experiment artifact to the long-running loop:

```powershell
python scripts/continuous_research_loop.py link-artifact `
  --manifest .\reports\continuous-research\...\manifest.json `
  --stage experiment_analysis `
  --path .\reports\2026-03-23_ecm_window_baseline\summary.md `
  --summary "ECM baseline run completed and is ready for structured post-experiment analysis."
```

Inspect the current loop state:

```powershell
python scripts/continuous_research_loop.py status `
  --manifest .\reports\continuous-research\...\manifest.json
```

The synchronized progress note now includes a compact loop snapshot, so you can quickly see how many stages are completed, which ones are still pending, and what the current focus should be.

Run a strict post-experiment analysis package plus a decision-oriented report:

```powershell
python scripts/results_analysis_workflow.py `
  --config config.json `
  --experiment-dir .\reports\2026-03-23_ecm_window_baseline `
  --title "ECM baseline" `
  --write-progress-note
```

Attach that analysis directly into the long-running manifest:

```powershell
python scripts/continuous_research_loop.py run-results-analysis `
  --manifest .\reports\continuous-research\...\manifest.json `
  --experiment-dir .\reports\2026-03-23_ecm_window_baseline `
  --title "ECM baseline" `
  --write-progress-note
```

Extract reusable writing memory from the latest grounded analysis artifacts:

```powershell
python scripts/writing_memory_workflow.py `
  --config config.json `
  --analysis-json .\reports\results-analysis\...\analysis.json `
  --results-report-json .\reports\results-analysis\...\results_report.json `
  --results-report-markdown .\reports\results-analysis\...\results_report.md `
  --title "ECM baseline writing memory" `
  --write-vault-note
```

Attach that writing memory to the long-running manifest:

```powershell
python scripts/continuous_research_loop.py run-writing-memory `
  --manifest .\reports\continuous-research\...\manifest.json `
  --title "ECM baseline writing memory" `
  --write-vault-note
```

Run an evidence-constrained self review on a draft:

```powershell
python scripts/self_review_workflow.py `
  --config config.json `
  --draft-file .\vault\06_Writing\current-draft.md `
  --analysis-json .\reports\results-analysis\...\analysis.json `
  --results-report-json .\reports\results-analysis\...\results_report.json `
  --writing-memory-json .\reports\writing-memory\...\writing_memory.json `
  --title "Current draft review" `
  --write-vault-note
```

Attach that self review to the long-running manifest:

```powershell
python scripts/continuous_research_loop.py run-self-review `
  --manifest .\reports\continuous-research\...\manifest.json `
  --draft-file .\vault\06_Writing\current-draft.md `
  --title "Current draft review" `
  --write-vault-note
```

Both `writing_memory_workflow.py` and `self_review_workflow.py` use the `continuous_research.openai` config block. By default they stay on `gpt-5.4` with high reasoning effort so the late-stage writing loop matches the rest of the research pipeline while still returning strict structured outputs.

Build grounded manuscript blocks from results, writing memory, and self-review artifacts:

```powershell
python scripts/draft_builder_workflow.py `
  --config config.json `
  --analysis-json .\reports\results-analysis\...\analysis.json `
  --results-report-json .\reports\results-analysis\...\results_report.json `
  --writing-memory-json .\reports\writing-memory\...\writing_memory.json `
  --self-review-json .\reports\self-review\...\self_review.json `
  --outline-file .\vault\06_Writing\outline.md `
  --title "Manuscript blocks" `
  --write-vault-note
```

Attach those manuscript blocks to the long-running manifest:

```powershell
python scripts/continuous_research_loop.py run-draft-builder `
  --manifest .\reports\continuous-research\...\manifest.json `
  --outline-file .\vault\06_Writing\outline.md `
  --title "Manuscript blocks" `
  --write-vault-note
```

Prepare a rebuttal and reviewer-response scaffold from grounded review artifacts:

```powershell
python scripts/rebuttal_scaffold_workflow.py `
  --config config.json `
  --self-review-json .\reports\self-review\...\self_review.json `
  --writing-memory-json .\reports\writing-memory\...\writing_memory.json `
  --results-report-json .\reports\results-analysis\...\results_report.json `
  --draft-file .\vault\06_Writing\current-draft.md `
  --title "Reviewer response prep" `
  --write-vault-note
```

Attach that rebuttal scaffold to the long-running manifest:

```powershell
python scripts/continuous_research_loop.py run-rebuttal-scaffold `
  --manifest .\reports\continuous-research\...\manifest.json `
  --draft-file .\vault\06_Writing\current-draft.md `
  --title "Reviewer response prep" `
  --write-vault-note
```

The full late-stage writing stack now shares the same `continuous_research.openai` block, with separate model slots for `writing_memory`, `self_review`, `draft_builder`, and `rebuttal_scaffold`. The default path keeps all four on `gpt-5.4` with high reasoning effort so you can route them consistently or override them stage by stage later.

Adapt the current paper stack toward a target journal:

```powershell
python scripts/journal_targeting_workflow.py `
  --config config.json `
  --journal-name "Biomedical Optics Express" `
  --journal-notes-file .\vault\06_Writing\journal-notes.md `
  --draft-builder-json .\reports\draft-builder\...\draft_builder.json `
  --self-review-json .\reports\self-review\...\self_review.json `
  --rebuttal-scaffold-json .\reports\rebuttal-scaffold\...\rebuttal_scaffold.json `
  --draft-file .\vault\06_Writing\current-draft.md `
  --title "Target journal prep" `
  --write-vault-note
```

Attach that journal-targeting layer to the long-running manifest:

```powershell
python scripts/continuous_research_loop.py run-journal-targeting `
  --manifest .\reports\continuous-research\...\manifest.json `
  --journal-name "Biomedical Optics Express" `
  --journal-notes-file .\vault\06_Writing\journal-notes.md `
  --draft-file .\vault\06_Writing\current-draft.md `
  --title "Target journal prep" `
  --write-vault-note
```

Generate a versioned response-letter package and keep the rounds indexed:

```powershell
python scripts/response_letter_workflow.py `
  --config config.json `
  --round-label "round-1" `
  --review-comments-file .\vault\06_Writing\reviewer-comments.md `
  --current-changes-file .\vault\06_Writing\revision-notes.md `
  --rebuttal-scaffold-json .\reports\rebuttal-scaffold\...\rebuttal_scaffold.json `
  --journal-targeting-json .\reports\journal-targeting\...\journal_targeting.json `
  --draft-builder-json .\reports\draft-builder\...\draft_builder.json `
  --draft-file .\vault\06_Writing\current-draft.md `
  --title "Reviewer response prep" `
  --write-vault-note
```

Attach that response-letter package to the long-running manifest:

```powershell
python scripts/continuous_research_loop.py run-response-letter `
  --manifest .\reports\continuous-research\...\manifest.json `
  --round-label "round-1" `
  --review-comments-file .\vault\06_Writing\reviewer-comments.md `
  --current-changes-file .\vault\06_Writing\revision-notes.md `
  --draft-file .\vault\06_Writing\current-draft.md `
  --title "Reviewer response prep" `
  --write-vault-note
```

The `journal_targeting` and `response_letter` stages use the same `continuous_research.openai` block as the earlier writing stages, with their own model slots so you can keep the whole submission layer on `gpt-5.4` by default or reroute individual stages later.

Audit the current draft for citation and evidence-linking risk:

```powershell
python scripts/citation_audit_workflow.py `
  --config config.json `
  --draft-file .\vault\06_Writing\current-draft.md `
  --journal-targeting-json .\reports\journal-targeting\...\journal_targeting.json `
  --response-letter-json .\reports\response-letter-tracker\...\response_letter.json `
  --references-file .\vault\06_Writing\references.md `
  --title "Citation sweep" `
  --write-vault-note
```

Attach that citation audit to the long-running manifest:

```powershell
python scripts/continuous_research_loop.py run-citation-audit `
  --manifest .\reports\continuous-research\...\manifest.json `
  --draft-file .\vault\06_Writing\current-draft.md `
  --references-file .\vault\06_Writing\references.md `
  --title "Citation sweep" `
  --write-vault-note
```

Run a final polish and pre-submission QC pass:

```powershell
python scripts/submission_qc_workflow.py `
  --config config.json `
  --draft-file .\vault\06_Writing\current-draft.md `
  --citation-audit-json .\reports\citation-audit\...\citation_audit.json `
  --journal-targeting-json .\reports\journal-targeting\...\journal_targeting.json `
  --response-letter-json .\reports\response-letter-tracker\...\response_letter.json `
  --title "Final submission gate" `
  --write-vault-note
```

Attach that final QC layer to the long-running manifest:

```powershell
python scripts/continuous_research_loop.py run-submission-qc `
  --manifest .\reports\continuous-research\...\manifest.json `
  --draft-file .\vault\06_Writing\current-draft.md `
  --title "Final submission gate" `
  --write-vault-note
```

The full submission-quality layer now shares the same `continuous_research.openai` block, with separate model slots for `citation_audit` and `submission_qc`. The default path keeps both on `gpt-5.4` with high reasoning effort so the last-stage checks stay consistent with the rest of the system.

Run a recurring draft health snapshot after late-stage edits:

```powershell
python scripts/draft_health_check_workflow.py `
  --config config.json `
  --draft-file .\vault\06_Writing\current-draft.md `
  --citation-audit-json .\reports\citation-audit\...\citation_audit.json `
  --submission-qc-json .\reports\submission-qc\...\submission_qc.json `
  --journal-targeting-json .\reports\journal-targeting\...\journal_targeting.json `
  --response-letter-json .\reports\response-letter-tracker\...\response_letter.json `
  --title "Draft health snapshot" `
  --write-vault-note
```

Attach that health snapshot to the long-running manifest:

```powershell
python scripts/continuous_research_loop.py run-draft-health `
  --manifest .\reports\continuous-research\...\manifest.json `
  --draft-file .\vault\06_Writing\current-draft.md `
  --title "Draft health snapshot" `
  --write-vault-note
```

Write durable submission memory by venue and revision round:

```powershell
python scripts/submission_memory_workflow.py `
  --config config.json `
  --venue-name "Biomedical Optics Express" `
  --round-label "round-1" `
  --draft-health-json .\reports\draft-health\...\draft_health.json `
  --submission-qc-json .\reports\submission-qc\...\submission_qc.json `
  --citation-audit-json .\reports\citation-audit\...\citation_audit.json `
  --response-letter-json .\reports\response-letter-tracker\...\response_letter.json `
  --journal-targeting-json .\reports\journal-targeting\...\journal_targeting.json `
  --draft-file .\vault\06_Writing\current-draft.md
```

Attach that durable memory layer to the long-running manifest:

```powershell
python scripts/continuous_research_loop.py run-submission-memory `
  --manifest .\reports\continuous-research\...\manifest.json `
  --venue-name "Biomedical Optics Express" `
  --round-label "round-1" `
  --draft-file .\vault\06_Writing\current-draft.md `
  --title "Submission memory snapshot"
```

The automation-and-memory layer uses the same `continuous_research.openai` block, with dedicated model slots for `draft_health` and `submission_memory`. The default path keeps both on `gpt-5.4` with high reasoning effort so scheduled checks and durable memory stay aligned with the rest of the pipeline.

If you want to run the whole late-stage paper-finishing chain in one shot after `results_analysis` is already in the manifest, use:

```powershell
python scripts/continuous_research_loop.py run-paper-finishing `
  --manifest .\reports\continuous-research\...\manifest.json `
  --draft-file .\vault\06_Writing\current-draft.md `
  --outline-file .\vault\06_Writing\outline.md `
  --journal-name "Biomedical Optics Express" `
  --journal-notes-file .\vault\06_Writing\journal-notes.md `
  --review-comments-file .\vault\06_Writing\reviewer-comments.md `
  --current-changes-file .\vault\06_Writing\revision-notes.md `
  --references-file .\vault\06_Writing\references.md `
  --venue-name "Biomedical Optics Express" `
  --round-label "round-1" `
  --title-prefix "BOE submission" `
  --write-vault-notes
```

That bundle will run, in order:

- `writing_memory`
- `self_review`
- `draft_builder`
- `rebuttal_scaffold`
- `journal_targeting`
- `response_letter`
- `citation_audit`
- `submission_qc`
- `draft_health`
- `submission_memory`

## Relationship memory workflow

The vault can now keep durable memory about recurring people mentioned in conversation, such as supervisors, collaborators, classmates, family, or friends. The implementation separates:

- person profiles in `13_People`
- interaction-level events in `14_Relationships`
- machine-readable registries in each folder's `_registry.json`

Bootstrap the folders:

```powershell
python scripts/relationship_memory.py bootstrap --config config.json
```

Write structured people memory into the vault:

```powershell
python scripts/relationship_memory.py upsert --config config.json --payload references/relationship-memory-payload.example.json --source-note 2026-03-20-demo
```

Query a person or keyword:

```powershell
python scripts/relationship_memory.py query --config config.json --person "王老师"
python scripts/relationship_memory.py query --config config.json --keyword "找工作"
```

If you already use `append_conversation_note.py`, you can pass `--memory-payload` so the conversation note and the relationship memory update happen together.
