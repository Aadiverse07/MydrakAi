# SAM offline client boundary — Muse session log

**Date:** 2026-10-28. **Branch:** `integration/phase-2-task-1-sam-parser`.
**Baseline HEAD:** `858b1b797aaadef17bff012d4d9047d0a933e622` (verified before editing).
Pre-existing changes preserved; nothing staged, committed, or pushed.

## Added

- `src/mydrak/sam/client.py` (new): `SamClientConfig` (frozen; all four
  fields required with no defaults — model ID, https-only endpoint,
  finite positive timeout, env-var name; blank/malformed/`TODO` values
  fail closed with generic errors), `from_mapping` (strict keys),
  `resolve_api_key` (per-call read from injected mapping or
  `os.environ`, mirroring `data_policy_from_env`; never stored/logged/
  echoed), `SamOutboundCall` (credential-free metadata envelope — NOT a
  provider JSON body, none invented), `SamSession` protocol,
  `prepare_call` (request construction, no bytes), `dispatch_call`
  (validates, resolves, invokes once; failures propagate, never retry).
  No network imports, no HTTP session, no serialization. `.env`
  autoload not claimed; launcher convention unresolved (documented).
  `config/models.yaml` untouched; `sam-3.1` vs `sam-3-1` unresolved.
- `tests/test_sam_client.py` (new, 36 tests): valid construction,
  mapping strictness, repo placeholders rejected, 26 invalid-config
  cases, zero session calls on missing credential/invalid config,
  credential absence from repr/envelope/JSON/errors, metadata-only
  session receipt, field validation, no-network-import scan,
  default-transport-still-fake with unchanged mock behavior.
- `docs/DAILY_LOG.md`: dated entry (observed results only).

## Verification (observed)

- New file **36 passed** first run; full suite **411 passed, 0 failed**
  (375 + 36).
- `compileall -q src tests eval` clean; TOML + 3 YAML parse OK;
  `git diff --check` clean; untracked whitespace scan clean.
- Secret-pattern count scan: 0 in new/changed files and added lines.
- `.env` ignored + untracked via metadata only; never read. No API
  calls, uploads, credentials, credits, deps, staging, or commits.

## Unresolved request-contract questions (unchanged)

Complete serialized JSON nesting/field names, verified request
example, resolved model ID/endpoint, SAM media limits, provider error
and retry semantics, billing behavior. Serialization stays BLOCKED.
