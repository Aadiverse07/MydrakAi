# T06 KB registry, schema, and validator — Codex session log

Date: 2026-10-30

## Scope and source

Implemented the self-contained offline T06 schema/registry slice. Read B6 and
C2 T06 in `docs/MydrakDeepseekreformed.pdf`, project instructions, T06 content
plan, roadmap, loader, tests, and existing logs. B6 specifies 12–16 cards
across three crops, bilingual fields, Hindi native-speaker review, citations,
and chemical label instructions; C2 accepts cards validating against schema.
The added registry and review metadata are project-local decisions supplied
by the owner, not B6 wire/schema requirements.

## Changes

- Added `kb/sources.yaml` with only the eight supplied candidate entries; all
  retrieval/title/user-verification flags remain false. Soybean citation title
  remains unresolved; PAU edition year is null; cross-check/gap entries are
  not citable.
- Extended `src/mydrak/kb/loader.py` with exact-field registry validation,
  claim-path references, source eligibility gates, region/review gates, and
  conservative dosage/mixing-pattern rejection. Kept general safety-card
  loading independent. The one `SYNTHETIC_TEST` YAML fixture is accepted only
  through the explicit test validator and is refused by production loading.
- Recorded provisional MP / tomato-potato-soybean scope, source posture,
  unreviewed Hindi, and the owner’s Codex-permission statement as unverified.
- No production disease cards were drafted because
  `docs/kb/source_excerpts/` is absent. No diseases, citations, or advice were
  authored from memory.

Pillow is not relevant to this phase. No dependencies, network, credentials,
`.env` contents, media, or credits were used.

## Verification

- `python3 -m pytest tests/test_disease_card_schema.py -q`: **59 passed** (exit 0).
- `python3 -m pytest -q`: **963 passed** (exit 0).
- `python3 -m compileall -q src tests eval`: exit 0.
- Safe YAML parsing of all `kb/**/*.yaml`: 2 files parsed, exit 0.
- Safe secret-pattern scan over the nine scoped files: 0 matches, exit 0; only counts and file/line locations were emitted.
- `.env` metadata only: `git check-ignore -v .env` exit 0 (`.gitignore:2`); `git ls-files -- .env` exit 0 with no tracked path; `git status --short --ignored -- .env` exit 0 (`!! .env`). The file was not opened.
- `git diff --check`: exit 0.

## Remaining

T06 remains **PARTIAL**. Needed: owner confirmation of three crops and card
allocation; source excerpts and verification for candidate titles; PAU edition
if used; source retrieval/user confirmation; qualified content and native
Hindi review. Schema checks do not establish agronomic validity or source
truth. Live SAM remains **NO-GO**.
