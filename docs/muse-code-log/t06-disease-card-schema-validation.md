# T06 — Fail-Closed Disease-Card Schema Validation

Date: 2026-10-29

## Scope

Implemented an offline structural validator for the B6 disease-card fields in the master specification (PDF page 8). The existing general safety-card loader remains unchanged in behavior. No disease cards, agronomic content, treatment recommendations, citations, or reviewer claims were added.

## Contract

- Required top-level fields: `id`, `crop`, `names`, `symptoms`, `confusable_with`, `follow_up_questions`, `low_risk_steps`, `chemical_options`, `when_to_refer`, `sources`, `reviewed_by`.
- `names` is nonempty text for both `en` and `hi`; `low_risk_steps` is a nonempty list of nonempty strings for each language. B6's displayed language keys are used exactly.
- Symptoms and sources are nonempty lists of nonempty strings. `confusable_with` is a list of nonempty identifiers and may be empty. Follow-up questions are a nonempty list of `{id, en, hi}` mappings with nonempty strings and unique IDs; ID syntax remains unconstrained because B6 does not define it.
- `chemical_options: []` is valid as specified. B6 specifies only that each option needs a cited source and a product-label instruction, but does not name a record schema. The narrow project-local structural minimum is `{text, source, label_instruction}`, each nonempty text. This checks shape only and does not verify the source, safety, or wording.
- `validate_disease_card()` validates a mapping; `load_disease_card()` loads and validates one YAML file. Existing `load_card()` and `load_safety_card()` interfaces are preserved.

## Verification

- `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_disease_card_schema.py tests/test_kb_loader.py` — 35 passed.
- `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider` — 639 passed, 0 failed.
- `git diff --check` — clean.

Schema validation does not establish source validity, native-speaker review, diagnosis accuracy, or treatment safety. No live SAM work or test was performed; Live SAM remains NO-GO.
