# T15 — Offline replay and local trace backup

## Source basis

The master spec C2 lists T15, “Replay mode + backup,” acceptance “Replay runs
with network disabled” (PDF p. 12). B10 says `DEMO_MODE` selects live or
replay, with replay serving cached responses without network. B9 defines the
SQLite cache table (`key`, `response_json`, `ts`). The offline constraints for
this work do not permit a live mode or external calls.

## Implementation

- Added `src/mydrak/replay/replay.py`: an explicitly labeled, in-memory
  synthetic fixture is sent only through the existing offline coordinator.
  The fixture is not serialized to SQLite. Replays return the coordinator's
  safe outcome and its synthetic provenance; invalid fixture provenance is
  rejected before trace insertion.
- Added `TraceStore.backup_to()` using the standard-library SQLite backup API.
  It writes a local backup file with restrictive creation permissions and
  refuses to replace an existing destination or the source database.
- Added `tests/test_offline_replay.py` for repeatable offline outcomes, socket
  blocking, policy-denied cases, invalid provenance, backup contents, and
  preservation of existing backup destinations.

## Verification

- `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_offline_replay.py tests/test_trace_store.py tests/test_workflow_coordinator.py` — **28 passed**.
- `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider` — **834 passed**.
- `python3 -m compileall -q src tests eval` — exit 0.
- TOML/YAML/JSONL parsing and `git diff --check` — exit 0; 1 TOML, 4 YAML,
  and 1 JSONL files parsed.
- Scoped safe secret scan — 0 matches, contents suppressed; scoped whitespace
  scan — 0 findings. `.env` is ignored and untracked by Git metadata only; it
  was not read.
- No network/API calls, uploads, credentials, credits, installs, or Git history
  operations occurred.

## Remaining scope

T15 remains **PARTIAL**. This is synthetic fixture re-execution, not B10's
cached-response replay. There is no `DEMO_MODE` setting or B9 `cache` table,
and no cache payload policy has been defined. Arbitrary model/user response
text is not cached. The user can continue implementing the cached replay mode
after a privacy-safe cache payload boundary is established. Live integration
remains unauthorized.
