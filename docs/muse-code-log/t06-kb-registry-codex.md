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

## Owner-requested registry correction (2026-10-30)

The owner supplied a revised registry field set and exact candidate names after
the first T06 commit. The registry and validator now use only `id`, `title`,
`publisher`, `region_tag`, `tier`, `local_path`, `retrieved`,
`verified_by_user`, and `notes`; `title_verified` and `edition_year` were
removed. All eight candidates remain `retrieved: false` and
`verified_by_user: false`.

The requested tier enum excludes `gap`, while JNKVV/RVSKVV is called a source
gap. It is stored as `cross-check` only to enforce non-citability; its note and
the content plan state this is an enum-compatibility placeholder, not a factual
classification. `verified` cards require retrieved sources with
`verified_by_user: true`; any `cross-check` source is rejected for citation.
The Official Rules file retains its prior evidence report and records the
Codex-permission statement as user-stated and UNVERIFIED.

The source-excerpts folder is absent; no production card was authored. MP-first
and the three crop names remain proposed, not confirmed. T06 remains PARTIAL.

Correction-pass verification:

- `python3 -m pytest tests/test_disease_card_schema.py -q`: **56 passed** (exit 0).
- `python3 -m pytest -q`: **960 passed** (exit 0).
- `python3 -m compileall -q src tests eval`: exit 0.
- Safe YAML parsing of all `kb/**/*.yaml`: 2 files parsed, exit 0.
- Safe secret-pattern scan over the nine scoped files: 0 matches, exit 0; emitted only counts and file/line locations.
- `.env` metadata only: `git check-ignore -v .env` exit 0 (`.gitignore:2`); `git ls-files -- .env` exit 0 with no tracked path; `git status --short --ignored -- .env` exit 0 (`!! .env`). Contents were not read.
- Untracked-file whitespace scan: 0 trailing whitespace; `git diff --check`: exit 0.

## Gap-tier and test regression follow-up (2026-10-30)

Compared `git diff e087e23 ef1aa7b -- tests/`:

- `test_unretrieved_or_unverified_title_source_cannot_be_cited` had two
  parameter cases (`retrieved`, `title_verified`); the latter was removed when
  the revised registry schema removed `title_verified`. This case is obsolete
  under the requested current field contract.
- `test_cross_check_and_gap_sources_cannot_be_cited` lost its `gap` parameter
  because that tier had been excluded from the enum. This was genuine lost
  behavior and is restored: both tiers are rejected for citations.
- `test_pau_citation_requires_edition_year` was removed when the revised source
  entry field set omitted `edition_year`; the test is not applicable to that
  contract and does not correspond to a validator field now.
- Source-ID renames in the synthetic fixture and chemical tests were data
  updates, not lost assertions. No other acceptance assertion was weakened.

The owner clarified that `gap` is a valid tier meaning a source not found. The
registry now gives JNKVV/RVSKVV `tier: gap` and notes “No package was found;
source not retrieved.” Added explicit tests for gap enum acceptance and
rejection of citations to either gap or cross-check sources.

Follow-up verification:

- `python3 -m pytest tests/test_disease_card_schema.py -q`: **58 passed** (exit 0).
- `python3 -m pytest -q`: **962 passed** (exit 0).
- `python3 -m compileall -q src tests eval`: exit 0.
- Safe YAML parsing of all `kb/**/*.yaml`: 2 files parsed, exit 0.
- Safe secret-pattern scan over scoped changed files: 0 matches, exit 0; output contains counts/locations only.
- `.env` metadata only: `git check-ignore -v .env` exit 0; `git ls-files -- .env` exit 0 with no path; `git status --short --ignored -- .env` exit 0 (`!! .env`). Contents were not read.
- `git diff --check`: exit 0.
