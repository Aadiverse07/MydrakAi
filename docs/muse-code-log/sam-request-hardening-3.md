# SAM dispatch hardening, round 3 (Codex audit follow-up)

Date: 2026-10-29 (UTC). Offline-only. No API calls, uploads, credentials,
installs, staging, commits, or pushes. Live testing deferred/unauthorized.

## Baseline

Branch `integration/phase-2-task-1-sam-parser`, HEAD `858b1b79` (unchanged).
Focused file `tests/test_sam_client.py`: 135 passed before edits.

## Fixes

1. Exception-context severance (`dispatch_http`, highest priority): the
   sanitized error is now raised OUTSIDE the `except` block via a
   `session_failed` flag. `raise ... from None` alone left the original
   reachable via `__context__`; now both `__context__` and `__cause__`
   are `None`. Message stays the fixed `SAM session call failed`.
2. Mutation contract (decision: preserve digest design): `SamHttpRequest`
   keeps its plain readable `body` plus construction sha256 snapshot;
   dispatch rejects anything mutated (shape-invalid or merely different)
   before the session runs. No immutability is claimed — class and
   `_body_snapshot` docstrings say detection-only, and same-process
   rebuilds remain possible by design. Rationale for not freezing with
   proxy/tuple containers: read compatibility (`type(body) is dict`,
   dict equality, JSON round-trip) relied on by existing tests and the
   injected session's plain-mapping shape.
3. Model contract (decision: enforce at the HTTP boundary, keep config
   layer generic): new `SAM_DOCUMENTED_MODEL_ID = "sam-3.1"`;
   `serialize_sam_body` and `dispatch_http` reject anything else
   (`SAM model ID must be sam-3.1`), including the marketing `sam-3-1`
   variant. `SamClientConfig`/`prepare_call`/`dispatch_call` stay
   model-agnostic (generic validated-config envelope, heavily tested
   with `test-sam-model`); the module docstring records this split.
   `sam-3.1` remains a request-format fact only — eligibility, billing,
   live compatibility stay UNVERIFIED.
4. Docs (minimal, in-scope only): matrix line 30 ("live client"),
   matrix line 44 and readiness row 39 ("authorizes no client
   configuration" → enforced offline format gate only; no live use,
   eligibility, billing, or compatibility). `sam-request-hardening-2.md`
   left as historical record — it describes round-2 results accurately
   and makes no forward-looking false claim. Client docstrings updated
   (model split, detection wording, severed context). `architecture.md`
   untouched.

## Tests (`tests/test_sam_client.py`: 135 → 144, all pass first run)

New: `__context__`/`__cause__` are `None` plus fake-secret absence from
`str`, exception-only, and FULL formatted traceback for both
`RuntimeError` and session-raised `SamConfigError` (secret built from
fragments so it never appears in test source lines); serialize rejects
`other-model`/`sam-3-1`/`SAM-3.1`/padded ID; dispatch rejects foreign
model configs pre-session and hand-built foreign-model bodies via the
consistency check; nested valid image-URL swap rejected pre-session.

## Verification (observed)

- Focused: `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest
  -p no:cacheprovider tests/test_sam_client.py -q` → **144 passed**.
- Full suite, same flags → **519 passed, 0 failed**.
- In-memory `compile()` over all 50 `src`/`tests`/`eval` files → OK.
- `pyproject.toml` + 3 YAML + JSONL line parse → OK (0 executed records).
- `git diff --check` → clean.
- Secret scan: pattern counts benign; value-safe literal check → 0 real
  secrets (single flagged literal is a `pytest.raises(match=...)`
  string). `.env` metadata-only: ignored (`!!`), untracked, never opened.
- No-network token scan on `client.py` → 0 hits.

## Remaining UNVERIFIED / limitations

Envelope parsing, retry semantics, media limits, eligibility/credits/
billing, retention/ZDR, live compatibility, the wider `sam-3.1` vs
`sam-3-1` discrepancy, diagnosis. Digest detects accidental mutation; it
is not tamper-proofing. Standard traceback frame source lines are
inherent to Python and carry no values.

Phase 4 NOT complete. **Live SAM remains NO-GO.**
