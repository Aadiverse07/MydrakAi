# SAM request serialization + dispatch hardening (Codex audit follow-up)

Date: 2026-10-29 (UTC). Offline-only. No API calls, uploads, credentials,
installs, staging, commits, or pushes. Live testing deferred/unauthorized.

## Baseline

Branch `integration/phase-2-task-1-sam-parser`, HEAD `858b1b79`.
Focused file `tests/test_sam_client.py`: 63 passed, 1 failed — the single
failure was caused by this task's first edit (a `urllib.parse` import
tripped the `test_no_real_network_primitives` token scan). Full suite at
start: 439 passed + that 1 failure. `config/models.yaml`, `run_scan`,
`FakeSamTransport` default, `docs/architecture.md` untouched.

## Fixes (all in `src/mydrak/sam/client.py`, stdlib `re` only)

1. Dispatch revalidation: new `_validate_body_shape` rejects non-mappings,
   unexpected keys at every level, malformed nesting, bad image refs, and
   non-boolean `stream` with value-free errors. `SamHttpRequest`
   construction and `dispatch_http` both enforce it; dispatch additionally
   requires body `model`, canonical endpoint, and timeout to match the
   config. Mismatches fail before the session is touched.
2. Nested-mutation bypass closed: dispatch revalidates the stored body and
   hands the session a deep copy, never the stored mapping. Constructor
   still validates + copies, so post-construction caller mutation and
   session-side mutation cannot affect later dispatches.
3. Exception safety: injected-session failures convert to the fixed error
   `SAM session call failed` (`from None`), so echoes cannot leak the
   credential, prompt, or image data. `SamConfigError` from a session
   propagates unchanged. No secret logging; still no real HTTP client.
4. Strict URL syntax (`_parse_url`, no `urllib` — the token scan forbids it):
   scheme allowlist, non-empty hostname (ASCII labels or bracketed IPv6),
   `@` userinfo rejected, port ASCII digits 1–65535. Endpoint requires
   `https`; image refs allow `http`/`https`. Syntax only, no reachability.
5. Data-URL mediatype must now fully match `image/*` (case-insensitive);
   `text/*`, `application/*`, `video/*`, empty/parameterized types
   rejected. No allowlist of SAM formats, dimensions, or payload limits.
6. Docs: module docstring now states the documented `sam-3.1` model ID is
   a request-format fact only and establishes nothing about eligibility,
   credits, billing, or live compatibility (all UNVERIFIED, no live call
   authorized). Stale matrix/readiness text left to its owners per the
   preserve rule; historical session logs not rewritten.

## Tests (`tests/test_sam_client.py`: 64 → 104, all pass)

New: nested-body mutation rejected pre-session; unexpected top/nested keys;
model/timeout/endpoint mismatch; session receives a copy (`is`/`==`
checks + re-dispatch after session-side mutation); leaking-session
sanitization (exact fixed message, no credential/prompt/image leak,
`__cause__ is None`, taxonomy carve-out); 11 valid + 17 rejected URL/
data-URL cases; 6 rejected endpoints.

## Verification (observed)

- `python3 -m pytest tests/test_sam_client.py -q` → **104 passed**.
- `python3 -m pytest -q` → **479 passed, 0 failed**.
- `python3 -m compileall -q src tests eval` → clean.
- TOML + all three YAML + JSONL line parse → OK (0 executed live records).
- `git diff --check` → clean.
- Secret-pattern scan on changed files → only protocol/test-fixture
  names; no literal secrets (counts only).
- `.env` metadata-only: ignored (`!!`), untracked, never read.

## Remaining UNVERIFIED / out of scope

SAM media formats/dimensions/payload ceilings, envelope parsing, retry
semantics, account eligibility/credits/billing, retention/ZDR, live
compatibility, `sam-3.1` vs `sam-3-1`, diagnosis. Non-ASCII hostnames are
rejected as malformed by local strictness (not a reachability claim).

Phase 4 NOT complete. **Live SAM remains NO-GO.**
