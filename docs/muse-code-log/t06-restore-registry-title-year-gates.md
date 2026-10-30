# T06 registry title and edition-year citation gates

Date: 2026-10-30
Tool: Codex

## Change

Restored the owner-required registry fields `title_verified` (boolean) and
`edition_year` (positive integer or null). Every seeded candidate has
`title_verified: false` and `edition_year: null`. Registry notes now explicitly
describe title verification and the PAU edition-year gap. The T06 content plan
marks the temporary field-removal snapshot as superseded and documents the
current citation gates.

Production citations now fail if the source is not retrieved, its title is not
verified, it is a `gap` or `cross-check` source, or it is the PAU entry with a
null edition year. Existing verified-card user-review requirements are
unchanged. The existing `gap` enum, JNKVV/RVSKVV gap entry, and both gap and
cross-check rejection tests remain intact.

Tests replace the retired-field rejection cases with the original
`title_verified` citation gate and PAU edition-year gate. Registry type tests
cover both new fields, and the seed test confirms every candidate begins with
both fields in the required unverified/null state. Other registry tests were
kept.

## Verification

- `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_disease_card_schema.py -q` — exit 0, **60 passed**.
- `python3 -m pytest -q` — exit 0, **984 passed**.
- `python3 -m compileall -q src tests eval` — exit 0.
- YAML parse — exit 0; **7 files** parsed across `config/`, `kb/`, and `tests/fixtures/kb/`.
- Safe secret scan — exit 0; **138 changed/addition lines scanned, 0 matches**; only counts and locations are printed.
- `git check-ignore -v .env` — exit 0; ignored by `.gitignore:2`.
- `git ls-files -- .env` — exit 0; no tracked path output.
- `git status --short --ignored -- .env` — exit 0; `!! .env`. Contents were not accessed.
- `git diff --check` — exit 0. New session-log whitespace check — exit 0; **1 file checked, 0 issues**.

No source documents were retrieved, no production disease cards were written,
and no network/API calls, uploads, credentials, dependency installations, or
credit usage occurred. Live SAM remains NO-GO.
