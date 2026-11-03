# KB Batch 1 integration — Codex

Date: 2026-11-03. Work was offline. The patch folder was treated as supplied
data; its `CODEX_PROMPT.md` was read as part of the patch and did not override
the user's request or repository rules.

## Integration

- Replaced `kb/sources.yaml` with the supplied 10-record registry. The six
  remaining candidate entries were byte-for-byte semantically unchanged; the
  CPRI and soybean entries were updated; IIVR TB75 and the tomato e-course were
  added. At that integration snapshot, `verified_by_user` was false for all
  ten. Four source entries were marked
  retrieved/title-verified by the supplied patch; this session did not inspect
  the owner-held source PDFs.
- Copied the ten supplied disease-card YAML files unchanged into `kb/cards/`.
  `general_safety.yaml` was not changed. All cards remain drafts with both
  languages `UNREVIEWED`, null reviewer fields, and empty chemical options.
- Updated `tests/test_disease_card_schema.py` for the 10-record registry and
  retained the six remaining-candidate assertions. Added the supplied batch
  test file. The initial focused run found a second stale expectation of eight
  records in the registry-integrity test; only that count was updated.
- Source review found `begin_followup()` could pass caller-supplied card text
  to the reply composer without review gating. It now refuses unless card status
  is `verified` and both language review states are `REVIEWED`. Synthetic
  follow-up test fixtures use explicit test-only gate metadata; it is not review
  evidence. Added draft/English-unreviewed/Hindi-unreviewed rejection tests.
- Updated `kb/cards/README.md`, the current sections of
  `docs/verification/t06-disease-card-content-plan.md`, and the T06 row in
  `docs/verification/roadmap_reconciliation.md`. Earlier dated plan/log entries
  were retained as historical records. Phase 4 remains **NOT FULLY CLOSED**.

## Per-card structural validation

All ten cards passed `load_disease_card()`. Citation coverage matched the
validator's claim paths and all cited source IDs resolved. The cards have no
chemical options, remain draft/unreviewed with null reviewers, and pass the
loader's dosage/mixing pattern guard. See `kb/cards/README.md` for the supplied
printed-page inventory. These checks do not independently verify source claims,
page locators, translations, disease facts, agronomic safety, or author
attribution. The soybean Bulletin 17/16 discrepancy remains unresolved; the
tomato e-course is recorded as hosted at RVSKVV, not authored by RVSKVV based on
hosting alone.

## Farmer-facing path check

No production disease-card lookup exists in the workflow: `spark_only` records
`no_production_disease_cards`, while the offline pipeline's card use is limited
to its marked synthetic test fixture. The generic bounded follow-up path could
render a supplied card, so a review-state gate and regression tests were added.
Hindi rendering remains unavailable in the composer.

## Verification

- Per-card validation script — exit 0; **10 cards validated**, with each file's
  PASS and citation count printed.
- `PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_disease_card_schema.py tests/test_kb_loader.py tests/test_disease_cards_batch1.py -q` — exit 0, **136 passed**.
- `PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_followup.py tests/test_workflow_coordinator.py -q` — exit 0, **31 passed**.
- `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider -q` — exit 0, **1271 passed**.
- `git diff --check` — exit 0.
- YAML parse of source registry, safety card, and synthetic fixture — exit 0.

No live APIs, network calls, uploads, credentials, credits, dependency installs,
`.env` reads, or Git staging/history operations occurred. The pre-existing
untracked `docs/providers/` directory and prior README modification were
preserved (the README was extended for this task).

## Owner-confirmed title/year update (2026-11-03)

The owner subsequently confirmed the titles and edition years for all four
Batch 1 sources. The registry values for CPRI Bulletin 108 (2020) and soybean
Extension Bulletin 17 (Revised Edition 2022) already matched; IIVR TB75 changed
from null to 2017 and the ICAR tomato e-course from null to 2020. The four
`verified_by_user` flags are now true; the other six remain false. No card YAML
or claim/citation content changed. Cards remain drafts, unreviewed, and without
reviewer names.

Registry notes were left untouched as requested. Their “not yet confirmed”
phrases are now stale for the four sources; the IIVR note also says its edition
year is null. The tomato note says no publication year was found on the pages
reviewed, while the user has now confirmed 2020. These notes need an explicitly
authorized follow-up if they are to be edited. The soybean Bulletin 17/16
discrepancy remains unresolved.

Verification for this follow-up:

- `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_disease_card_schema.py tests/test_kb_loader.py tests/test_disease_cards_batch1.py -q` — exit 0, **136 passed**.
- `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider -q` — exit 0, **1271 passed**.
- `git diff --check` — exit 0.


## Registry note correction follow-up (2026-11-03)

The four stale notes were corrected using the user's exact requested confirmation wording. All other sentences in each note were preserved, including the soybean Bulletin 17/16 discrepancy, the RVSKVV hosting caveat, and the “late blight fungus” inconsistency. Titles, edition years, flags, cards, claims, citations, and page numbers were not changed in this follow-up. The supplied `INTEGRATION_NOTES.md` now distinguishes initial page-review observations from the later owner-confirmed years. No tests hard-coded the replaced note sentences.

Verification results will be appended after the focused and full test runs.
