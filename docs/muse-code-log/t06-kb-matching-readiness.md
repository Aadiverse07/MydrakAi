# T06 Follow-up — KB Matching Readiness

Date: 2026-10-29

## B6/T06 requirements

B6 (master PDF page 8) specifies 12–16 disease cards across three crops. Tomato, potato, and soybean are candidates; the final crop list is chosen from the farmer's region on Day 1. Each card has `id`, `crop`, bilingual `names`, `symptoms`, `confusable_with`, bilingual `follow_up_questions` with IDs, bilingual `low_risk_steps`, `chemical_options`, `when_to_refer`, `sources`, and `reviewed_by`. Sources and reviewed bilingual content are actual content requirements, not satisfied by schema validation. Low-risk steps come first. Each chemical option needs a cited source and a product-label instruction. Treatment in replies comes only from cards; Hindi is prewritten and native-reviewed. The confusable list supports look-alike follow-up questions.

T06 (C2, master PDF page 12) acceptance: “All cards validate against schema.” This is structural validation, not evidence that cards have correct facts, valid citations, agronomic safety, or native-speaker review.

## Repository evidence

- `kb/cards/` contains only `general_safety.yaml` and `README.md`. The safety card is not a disease card; it contains no disease symptoms or steps, has `sources: []`, and `reviewed_by` is a TODO placeholder.
- The disease-card validator and loader exist in `src/mydrak/kb/loader.py`; tests in `tests/test_disease_card_schema.py` use explicitly synthetic fixtures only. No real disease content has been added.
- `config/models.yaml` contains no supported crop list or disease IDs; model configuration fields remain placeholders.
- T05's `validate_diagnosis_json()` receives trusted `supported_crops` and `disease_ids` from its caller. Its tests use synthetic allowlists; there is no production vocabulary source wired to B6 cards.
- T11 `extract_kb_match()` can return 0 for a valid label with no matching card, marks duplicate IDs ambiguous, and leaves a matching-card score unavailable because B3 does not define symptom tokenization, normalization, language handling, or the overlap denominator. Its tests use synthetic IDs/symptoms only.

## Decision

No deterministic disease matcher was added. There are no curated cards or trusted vocabularies to match against, and completing B3 S2 requires an explicit symptom-overlap contract. Running a matcher against empty or synthetic-only content would create no product value and could falsely imply a grounded match.

## Smallest safe next step

1. Select the three crops based on the intended farmer region.
2. Assemble 12–16 source-backed card drafts, obtain agronomic/source review and native-speaker review, and resolve the local chemical-option record fields already labeled project-local in the validator.
3. Derive supported-crop and disease-ID allowlists from validated cards and pass them to T05; reject missing or duplicate identifiers.
4. Decide S2's exact comparison rule: whether crop is part of card identity, how reported symptoms map to card symptom phrases, tokenization/normalization for English and Hindi, and the overlap numerator/denominator. Keep no-match at 0 and ambiguous/malformed inputs unavailable or manual-review.
5. Then implement deterministic card resolution and overlap tests using the reviewed cards plus synthetic edge-case fixtures.

No code or tests changed in this follow-up. No network, API, credential, upload, credit, dependency, or Git history operation occurred. Live SAM remains NO-GO.
