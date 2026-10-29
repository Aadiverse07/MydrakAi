# SAM dispatch hardening, round 2 (Codex audit follow-up)

Date: 2026-10-29 (UTC). Offline-only. No API calls, uploads, credentials,
installs, staging, commits, or pushes. Live testing deferred/unauthorized.

## Baseline

Branch `integration/phase-2-task-1-sam-parser`, HEAD `858b1b79` (unchanged).
Worktree shape as after round 1 plus its log. Focused file
`tests/test_sam_client.py`: 104 passed before edits.

## Fixes (all in `src/mydrak/sam/client.py`, stdlib only)

1. Total session-exception sanitization: removed the `SamConfigError`
   carve-out. Every injected-session failure becomes the fixed error
   `SAM session call failed` (`from None`); original message, cause, and
   chained traceback never render through the public error.
2. Construction snapshot: `SamHttpRequest` records a canonical-JSON
   sha256 digest at construction (change detection only, not a security
   claim — same-process code can always rebuild a request). Dispatch
   revalidates shape, then rejects any body whose digest differs
   (`SAM HTTP body changed after construction`). Read access unchanged:
   `body` stays a plain dict (indexing, keys, equality, JSON round-trip
   all preserved).
3. Strict base64: payload must satisfy charset, length multiple of 4, and
   padding rules (max two `=`, padding only trailing). `QUI`, `QUJD=`,
   `AB=C`, `A===`, `====` rejected; `QUI=`, `TQ==` accepted.
4. Bracketed hosts validated with `ipaddress.IPv6Address` (stdlib, no
   network, no reachability claim), replacing the charset check.
   `[2001:db8::1]`, `[::ffff:192.0.2.1]` accepted; `[xyz]`, `[]`,
   `[12345::]`, `[::1::2]`, bad-embedded-IPv4 rejected.
5. Message `type`: omitted or `"type": "message"` accepted; any other
   value rejected; extra keys still rejected as unexpected.
6. Docs: matrix line 44 no longer claims "no request builder, no client"
   — it now records the offline-only serializer/dispatch boundary, states
   the documented `sam-3.1` model ID establishes nothing about
   eligibility/credits/billing/live-compat (UNVERIFIED/BLOCKED), and
   describes URL checks as syntax validation only (public accessibility
   and approval need separate evidence). `_parse_url` docstring says the
   same. Historical logs not rewritten; `architecture.md` untouched.

## Tests (`tests/test_sam_client.py`: 104 → 135, all pass)

Updated the old taxonomy test: `SamConfigError` from a session is now
sanitized (exact fixed message, no marker/key/prompt leak in `str` or
rendered exception, `__cause__ is None`). New: valid post-construction
mutation rejected pre-session (`changed after construction`, zero posts);
read-access preservation; 4 accepted / 8 rejected base64 payloads; 3
accepted / 7 rejected IPv6 hosts; `type: message` round-trip through
construct + dispatch; 5 unsupported type values; extra-key rejection.

## Verification (observed)

- `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_sam_client.py -q` → **135 passed**.
- Full suite, same flags → **510 passed, 0 failed**.
- In-memory `compile()` over all 50 `src`/`tests`/`eval` files → OK (no
  bytecode written by the check).
- `pyproject.toml` + 3 YAML + JSONL line parse → OK (0 executed records).
- `git diff --check` → clean.
- Secret scan (counts + value-safe literal check) → no literal secrets;
  only protocol/test-fixture names and synthetic env-var names.
- `.env` metadata-only: ignored (`!!`), untracked, never read.
- No-network token scan on `client.py` → 0 hits.

## Remaining UNVERIFIED / limitations

SAM media formats/dimensions/payload ceilings, envelope parsing, retry
semantics, account eligibility/credits/billing, retention/ZDR, live
compatibility, `sam-3.1` vs `sam-3-1`, diagnosis. Non-ASCII hostnames
rejected by local strictness (not a reachability claim). Snapshot is
accidental-mutation detection, not tamper-proofing.

Phase 4 NOT complete. **Live SAM remains NO-GO.**
