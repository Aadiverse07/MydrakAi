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
