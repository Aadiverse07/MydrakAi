# Phase 0.3 — Verification blockers and fail-closed data policy

**Date:** 2026-10-27 (Asia/Kolkata)
**Branch:** `integration/phase-0-3-data-policy`

## Scope and findings

- Inspected repository instructions, architecture, daily log, verification reports, and relevant PDF requirements (B10/B12). `DATA_POLICY=private` existed in `.env.example`, but there was no runtime policy parser or gate. No API client, upload, SDK invocation, or outbound processing call site exists.
- Added `src/mydrak/privacy/data_policy.py`, a local, no-I/O gate. Missing `DATA_POLICY` selects `private`; invalid or empty values fail. Private data (including image/audio/derived personal data when classified private) requires a verified Standard route, confirmed rights, explicit user authorization, and a privacy notice. Public-test data requires opt-in `public_test`, verified provenance and rights, and a verified provider mode. The setting alone never authorizes processing; Contributor is rejected for private data.
- This gate does not collect consent, establish legal rights, prove public provenance, or independently verify an actual provider route. There is no sender to wire it into yet, so outbound processing remains absent and blocked.
- Rechecked official primary sources. Meta's Contributor help disallows personal information in Contributor Services and directs personal-information use cases to Standard Services. Meta Terms §4.1 requires necessary rights; §5.1 says Standard request content is not used to train Meta Models; §4.4 allows certain retention. Speech-to-text docs list Hindi among 25 languages. The full hackathon Official Rules, participant credit amount/eligibility/expiry, account-specific billing/ZDR, Telegram OGG direct support, and exact media limits remain unresolved. Details and consequences are in the updated verification matrix and blocker reports.

## Checks actually run

- `python3 -m pytest` — **38 passed**, 0 failed.
- `python3 -m compileall -q src tests` — **passed** (exit 0).
- Python `tomllib` parse of `pyproject.toml` and PyYAML parse of all `config/*.yaml` — **passed**.
- Secret-pattern scan of the new policy module and its tests for private-key headers, common provider token formats, and literal credential assignments — **passed; no candidate matches**. The scan reports no values and does not establish absence of every secret in the repository or credential stores.
- `git diff --cached --check` — **passed** after staging the complete scoped change.

No API calls, authentication tests, uploads, API keys, billing settings, payment methods, or spend alerts were accessed or changed. No model credits were used.

## Remaining blockers and readiness

**NO-GO for live API testing.** The complete event rules and account credit entitlements are not verified; the product has no privacy notice or authorization flow; provider route/evidence has no actual runtime integration; and no sender is connected to the gate. Standard-mode no-training language must not be represented as zero retention.

## Git handoff

The task began on a clean `main`; local and remote `main` and the existing integration branch agreed at `00f98f7fd0b79e97be707b68510198462aa724ec`. Work is isolated on `integration/phase-0-3-data-policy`. Commit and push status are recorded in the final handoff after staged review and verification.
