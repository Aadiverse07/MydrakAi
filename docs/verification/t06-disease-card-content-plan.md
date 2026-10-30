# T06 Disease-Card Content Plan and Readiness

Status: **BLOCKED pending scope and evidence decisions.** This is a planning document, not a disease-card source or approval record.

## Specification requirements

Master specification B6 (PDF p. 8) calls for **12–16 disease cards across three crops**. It names tomato, potato, and soybean as candidate crops and says the final crop list is chosen from the farmer's region on Day 1. The repository does not identify that region or approve a final list. The three names are candidates, not sufficient evidence to select the deployment scope. No per-crop card allocation is specified.

Each card must contain:

- `id`, `crop`
- bilingual `names` (`en`, `hi`)
- `symptoms`, `confusable_with`
- bilingual `follow_up_questions`, with question `id`s
- bilingual `low_risk_steps`
- `chemical_options` (empty is allowed)
- `when_to_refer`, `sources`, `reviewed_by`

B6 further requires treatment text to come only from cards; Hindi text must be pre-written and reviewed by a native speaker; low-risk steps come first; a non-empty chemical option needs a cited source and a “follow the product label” instruction; and `confusable_with` informs distinguishing follow-up questions. C2 T06 acceptance (PDF p. 12) is **“All cards validate against schema.”** Passing that structural check does not establish factual validity, source support, agronomic safety, or review approval.

## Current repository evidence

- `kb/cards/` contains `general_safety.yaml` and `README.md`, but no production disease cards. The general safety card is not a disease card.
- `validate_disease_card()` / `load_disease_card()` check structure. The non-empty chemical-option shape `{text, source, label_instruction}` is explicitly a project-local minimum because B6 does not define that record shape. Validation does not assess source quality or reviewer qualifications.
- Tests in `tests/test_disease_card_schema.py` use synthetic placeholders only.
- T05 `validate_diagnosis_json()` accepts `supported_crops` and `disease_ids` from its caller; no approved production vocabulary is wired to cards.
- T11 `extract_kb_match()` returns 0 for a no-card label and computes overlap for a supplied matching card using the project-approved S2 contract: distinct observed phrases that exactly match normalized card phrases divided by distinct normalized observed phrases. Normalization lowercases, trims, collapses whitespace, and turns punctuation into word boundaries. Extra card phrases do not affect the denominator; no observations return unavailable. This is a project-local decision, not a claim that B3 specifies those mechanics. No production disease-card corpus exists.

## Content workflow (requirements vs. recommendation)

**B6 requirements:** provide source documents or URLs in `sources`; include `reviewed_by`; keep required text bilingual; obtain native-speaker review of Hindi; order low-risk steps first; and support every chemical option with a citation plus product-label instruction.

**Recommended project-local evidence gate (not a new B6 schema field):** maintain a separate review ledger with one row per factual/content claim, recording card ID, field/claim, source URL or document plus page/section locator, what the source supports, reviewer name/role/date, language-review status, and approval status. Do not mark approval based on a placeholder or schema test. Select an authoritative source hierarchy with the agronomic reviewer; B6 itself does not name source publishers or define their hierarchy. Have a qualified agronomic reviewer check disease claims, low-risk steps, referral conditions, and any chemical text before approval. B6 requires `reviewed_by` but does not specify reviewer qualifications; this agronomic gate is a recommended safety practice.

English and Hindi content must both be present. B6 specifically requires native-speaker review for Hindi; the project should also identify who reviews English clarity and preserve each review result in the ledger. No reviewer or approval is currently identified.

## Decisions needed before card authoring

1. Identify the intended farmer region and approve the final three crops from the B6 candidates; confirm the 12–16 total and per-crop allocation.
2. Approve a source-selection standard and source set appropriate to that region, including how each claim will be traceable to a source locator.
3. Assign the agronomic/source reviewer and native Hindi reviewer, and decide where dated review evidence will live. Do not fill `reviewed_by` until review actually occurs.
4. Decide whether cards will contain any chemical options. If yes, confirm the project-local record shape before authoring; B6 only requires a citation and label instruction, while the validator currently requires `{text, source, label_instruction}`.
5. Treat the S2 phrase normalization and denominator as project-local implementation choices. Before production use, decide whether language-specific synonym/translation handling is needed; current matching is exact phrase matching only and does not translate or infer equivalence.

## Safe allowlist and matching path

After cards are sourced and approved, validate every card, then build the trusted T05 crop allowlist from the unique `crop` values and disease-ID allowlist from unique `id` values in that approved production-card set. Exclude `general_safety.yaml` and all synthetic/test fixtures. Fail closed on missing/duplicate IDs, unapproved crop values, or cards lacking review evidence. This derivation is a proposed repository process; no production card set currently exists.

The S2 overlap helper exists, but do not use it as production matching until the approved card set and trusted vocabulary exist. No disease facts, citations, treatment content, reviewer identities, or approvals are supplied by this plan.

## Phase 4 T06 registry and schema work (2026-10-30)

**Registry field/title snapshot superseded by the later 2026-10-30 follow-up
below.** The following record is retained for history; current registry
requirements are in the follow-up section.

Project owner supplied a provisional scope: Madhya Pradesh first, with tomato,
potato, and soybean proposed crops. The crops are **not confirmed**. The stated
source posture is a national ICAR package plus an MP advisory overlay. Cards
remain `draft` until sources are retrieved and verified by the user. No Hindi
reviewer is confirmed; every Hindi string remains `UNREVIEWED`.

`kb/sources.yaml` now records only the eight source candidates supplied by the
project owner. All start with `retrieved: false`, `title_verified: false`, and
`verified_by_user: false`. The CPRI GAP title/year/publisher detail remains
unverified against the PDF. The soybean bulletin title remains unresolved. PAU
is supplementary/Punjab and has no edition year; the validator rejects PAU
citation until an edition is identified. The CPRI Hindi entry is cross-check
only and not citable. No other source details were added.

The validator adds a project-local schema for `status`, `region_tags`,
`claim_sources` (`claim`, `source_id`, `page`, `section`), language review
status/reviewer fields, and citation eligibility. It requires source trace
references for all card content paths. Non-empty chemical options retain the
existing local `{text, source, label_instruction}` shape, where `source` is a
registry ID. Dosage/mixing detection is a conservative local text-pattern
guard, not a complete language-aware safety review. The single
`SYNTHETIC_TEST` fixture is test-only and rejected by the production loader.
These structural gates do not establish agricultural correctness, source
validity, translation quality, or review approval.

No files exist under `docs/kb/source_excerpts/`; therefore no production card
was drafted. Required next evidence: project-owner confirmation of the three
crops and per-crop card allocation; actual source documents/excerpts with page
and section locators; confirmation of the CPRI and soybean titles; PAU edition
year if used; and qualified English/agronomic and native-Hindi review evidence.

## Revised registry request (2026-10-30)

The latest owner request defines registry fields as `id`, `title`, `publisher`,
`region_tag`, `tier`, `local_path`, `retrieved`, `verified_by_user`, and
`notes`; it does not include `title_verified` or `edition_year`. The eight
registry titles now exactly follow the supplied names. Every source remains
unretrieved and unverified by the user. The user-proposed scope remains MP
first with tomato, potato, and soybean **to be confirmed**; source posture is
national ICAR package plus MP advisory overlay. No Hindi reviewer is confirmed
and Hindi remains UNREVIEWED. The Codex-permission statement is user-stated;
Official Rules evidence remains UNVERIFIED.

The owner subsequently clarified that `gap` is a valid tier for sources not
found. JNKVV/RVSKVV is now `tier: gap`, with the note “No package was found;
source not retrieved.” Both `gap` and `cross-check` are non-citable. Registry
citation requires `retrieved: true`; verified cards additionally require
`verified_by_user: true`. The CPRI Hindi entry is tagged `cross-check` and the
JNKVV/RVSKVV gap entry is tagged `gap`, so neither can be cited.

No files exist under `docs/kb/source_excerpts/`; no production cards were
drafted. Needed next: local excerpts with document/page/section references,
owner confirmation of target crops, and actual retrieval/user verification for
sources. Hindi remains unreviewed.
