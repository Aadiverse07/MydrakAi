# SAM model-ID documentation consistency (Codex audit follow-up)

Date: 2026-10-29 (UTC). Documentation-only. No code, test, config, or
dependency changes. No API calls, uploads, credentials, installs,
staging, commits, or pushes. Live testing deferred/unauthorized.

## Baseline

Branch `integration/phase-2-task-1-sam-parser`, HEAD `858b1b79` (unchanged).

## Finding

Three sentences across the verification docs were inconsistent with the
enforced contract (`SAM_DOCUMENTED_MODEL_ID = "sam-3.1"` in the
SAM-specific request boundary): they implied the documented ID
authorizes no client configuration at all, and listed the discrepancy
without separating the VERIFIED documented value from its UNVERIFIED
live API-side resolution.

## Changes (3 sentences, 2 files)

- `docs/verification/official_meta_api_matrix.md` line 44: `sam-3.1`
  stated as the documented API model ID enforced by the SAM-specific
  request boundary; UNVERIFIED list extended to eligibility,
  billing/credits, media limits, response compatibility, retention/ZDR,
  live compatibility.
- Same file line 50: discrepancy restated as UNVERIFIED *live API-side
  resolution*; `sam-3.1` itself noted as the documented value enforced
  offline. All existing UNVERIFIED labels preserved.
- `docs/verification/sam_live_integration_readiness.md` line 175:
  marketing label still not to be configured from; offline boundary
  enforces documented `sam-3.1` as a format gate only, establishing no
  eligibility, billing, compatibility, or live success.

Inspected and left unchanged: `src/mydrak/sam/client.py` module
documentation (~line 19, already states enforcement + distinction),
readiness row 39 (already consistent), `sam-request-hardening-2.md`
(accurate historical record of round-2 results; history not rewritten),
all readiness gates including the §10 "no API call authorized" gate and
NO-GO conclusions (3 occurrences intact).

No technical-contract change was required; scope stayed docs-only.

## Verification (observed)

- Focused: `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest
  -p no:cacheprovider tests/test_sam_client.py -q` → **144 passed**.
- Full suite, same flags → **519 passed, 0 failed**.
- `git diff --check` → clean.
- Read-back of all three edited sentences → confirmed; gates/NO-GO intact.
- Secret-pattern counts on both docs → pre-existing prose mentions only
  (auth-scheme words, no values); none introduced by these edits.
- `.env` metadata-only: ignored (`!!`), untracked, never opened.

Phase 4 NOT complete. **Live SAM remains NO-GO.**
