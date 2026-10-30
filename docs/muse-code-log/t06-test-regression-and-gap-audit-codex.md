# T06 validator test-regression and `gap` tier follow-up

Date: 2026-10-30
Tool: Codex

## Commit comparison

Compared `git diff e087e23 ef1aa7b -- tests/` against the actual test and validator changes.

- `test_unretrieved_or_unverified_title_source_cannot_be_cited(field)` lost the `title_verified` parameter case when it became `test_unretrieved_source_cannot_be_cited()`. The current registry contract in `src/mydrak/kb/loader.py` does not contain `title_verified`; exact-field validation rejects it as unknown. Added a focused regression case proving the retired field is rejected. The retrieved-source citation case remains tested.
- `test_pau_citation_requires_edition_year()` was removed when `edition_year` was removed from the registry contract. `SOURCE_FIELDS` excludes it and citation validation has no PAU edition-year rule. This is a superseded project-local rule under the later contract correction, not equivalent coverage for another current field. Added a focused test proving the retired field is rejected. If edition-year gating is still required, the registry contract must be explicitly revised to carry that field; this follow-up does not silently restore it.
- `test_cross_check_and_gap_sources_cannot_be_cited(tier)` was narrowed to cross-check only when `gap` was removed from the tier enum. In the current branch, this coverage has already been restored: `gap` is in `_TIERS`, both `gap` and `cross-check` are rejected for citations, and the registry marks JNKVV/RVSKVV as `gap` with a note that no package was found. The enum acceptance test also exists.
- The synthetic fixture's source IDs changed to the current registry ID. This is fixture maintenance, not lost validation.
- The synthetic-card test gained a check that an unmarked `SYNTHETIC_TEST` card is rejected. This strengthens coverage.
- Registry integrity gained a retrieved-flag boolean check, and seed assertions were updated to current registry fields. These are additions/contract updates, not removed coverage.

## Files changed in this follow-up

- `tests/test_disease_card_schema.py`: added two parameter cases for rejecting removed `title_verified` and `edition_year` fields under the current strict registry schema.
- `docs/DAILY_LOG.md`: recorded the comparison and verification.
- The existing current-branch `gap` implementation and tests were verified; `src/mydrak/kb/loader.py`, `kb/sources.yaml`, and the gap citation tests needed no change.

## Verification

- `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_disease_card_schema.py -q` — exit 0, **60 passed**.
- `python3 -m pytest -q` — exit 0, **984 passed**.
- `python3 -m compileall -q src tests eval` — exit 0.
- YAML parsing — exit 0; both YAML files under `kb/` parsed.
- Safe scan command: inline Python scanning only added lines in the two tracked changed files and the new session log — exit 0, **49 lines checked, 0 matches**; output contained counts only.
- `git check-ignore -v .env` — exit 0, ignored by `.gitignore:2`.
- `git ls-files -- .env` — exit 0, no tracked path output.
- `git status --short --ignored -- .env` — exit 0, `!! .env` (ignored); `.env` contents were not accessed.
- `git diff --check` — exit 0. Untracked session-log whitespace scan — exit 0, **1 file checked, 0 issues**.

No network/API calls, dependency installations, credentials, media, or credits were used. Live SAM remains NO-GO.
