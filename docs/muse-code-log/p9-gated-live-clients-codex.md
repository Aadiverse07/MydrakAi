# Phase 9 — Gated live provider client groundwork

**Tool:** Codex
**Date:** 2026-10-30
**Scope:** offline code and tests only; no live execution.

## Pre-edit scope and acceptance

Planned files: `src/mydrak/live/__init__.py`, `guard.py`, `retry.py`,
`tests/test_live_guard.py`, `README.md`,
`docs/verification/roadmap_reconciliation.md`, `docs/DAILY_LOG.md`, and this
session log. Acceptance: every missing authorization gate fails closed; unknown
prices or token bounds and spend-cap overruns refuse before dispatch; successful
reservations accumulate in a persistent local SQLite ledger; retry tests show at
most two retries and fallback; private content is denied to Contributor mode;
mock and replay paths have no live fallback.

## Findings and implementation

The checked-in `config/models.yaml` was inspected and still has `TODO(verify)`
for model IDs, endpoints, prices, timeouts, and Glimmer host choice. `tier1` and
`tier2` have only `max_tokens`; no input-token upper bound exists. Provider
request/response shapes are also incomplete: Spark body details, Glimmer host
contract, Voice multipart field names, and Telegram wire API fields are not
established. Therefore no provider-specific client or smoke request was written.
This follows the master specification's instruction not to invent API details.

Added a shared offline-testable authorization and spend reservation primitive.
It requires the explicit CLI authorization boolean, `MYDRAK_LIVE=1`, a present
credential variable in an injected environment mapping, positive spend cap,
verified model/endpoint/timeout, explicit input/output token maxima, known token
prices, and a persistent SQLite ledger. It atomically reserves the worst-case
estimated cost before a future dispatch. Reservation does not prove billing or
cap charges. Added a generic injected retry helper with caller-supplied backoff,
maximum two retries, and supplied fallback. It performs no provider I/O.

The existing `require_external_processing_allowed()` policy already blocks
private data on Contributor mode and requires verified public-test provenance
for Contributor. Tests exercise this boundary; no data sender was introduced.
Existing SAM transport remains exact-type fake-only and has no live fallback.

The user reports approximately $97.40 API credit and reserves at least $50 for
judging/final demo. These account facts are unverified by Codex; $47.40 is only a
possible upper bound for development. The user must set the first live-test cap.
Live calls require separate authorization and all account, billing, privacy,
provider, and compatibility gates. No live test is authorized here.

## Offline follow-up (2026-10-31)

Follow-up files: `src/mydrak/live/guard.py`, `tests/test_live_guard.py`,
`.env.example`, `README.md`, this roadmap, `docs/DAILY_LOG.md`, and this log.

The worktree now contains user-supplied values in `config/models.yaml`; that
pre-existing modification was preserved and was not staged. IDs, endpoints,
prices, and timeouts remain UNVERIFIED. Added a config loader that accepts
numeric prices and rejects missing or `TODO(verify)` fields. Tests demonstrate
that the single `max_tokens` field cannot establish separate maximum
input/output token costs, so the reservation gate refuses a call. Added only a
blank `TOGETHER_API_KEY=` line to `.env.example` for future tier-1 setup.

Provider-specific clients and smoke scripts remain unimplemented because the
request/response contracts (especially Glimmer provider, Spark body, Voice
multipart fields, and Telegram wire API) are not evidenced in the repository.
No endpoint was contacted. Live SAM remains NO-GO.

## Status

This is partial Phase 9 groundwork, not provider-client completion. T02 remains
BLOCKED. T05, T10, and T12 remain PARTIAL/BLOCKED until clients/configuration
and required smoke evidence are available. Live SAM remains **NO-GO**.
