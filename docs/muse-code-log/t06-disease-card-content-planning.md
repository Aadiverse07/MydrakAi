# T06 — Disease-Card Content Planning and Readiness

Date: 2026-10-29

Reviewed master B6 and C2 T06, the disease-card validator and synthetic schema tests, T05 allowlist interface, T11 S2 extractor, prior T06 logs, card inventory, and repository state.

## Finding

B6 requires 12–16 cards across three crops and names tomato, potato, and soybean as candidates. It says the final list is selected based on farmer region on Day 1; no target region or approved crop set is recorded in the repository. Only `general_safety.yaml` exists in `kb/cards/`; it is not a disease card. C2 T06 acceptance is all cards validating against schema, but the validator's shape checks do not establish factual content or review.

T05 receives crop and disease allowlists from its caller, with no production vocabulary wired from approved cards. T11 leaves matching-card S2 unavailable because the required keyword-overlap fraction lacks defined normalization, tokenization, bilingual handling, and denominator. No matcher or production card was added.

## Planning deliverable

Created `docs/verification/t06-disease-card-content-plan.md`. It records B6 fields and content rules, distinguishes explicit requirements from recommended project-local source/review traceability, describes allowlist derivation after approval, and lists owner decisions needed before content authoring. The existing schema-validation and KB-matching logs were preserved.

## Verification

- `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_disease_card_schema.py tests/test_kb_loader.py` — **35 passed**. These remain synthetic schema/loader tests, not agricultural-content verification.
- `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider` — **784 passed**.
- `python3 -m compileall -q src tests eval` — exit 0.
- `pyproject.toml` and four config/card YAML files parsed successfully.
- Safe secret-pattern scan: 0 matches in the two new documents and added DAILY_LOG lines. `.env` ignored/untracked was confirmed using Git metadata only; its contents were not read.
- `git diff --check` — exit 0; whitespace scan found 0 trailing-whitespace lines in the two new documents.

No code or tests changed. No live services, network, credentials, uploads, credits, dependency installs, or Git history operations occurred. Live SAM remains NO-GO.
