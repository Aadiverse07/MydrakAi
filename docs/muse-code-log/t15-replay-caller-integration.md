# T15 replay caller integration

## Requirement basis

B10 requires replay mode to serve cached responses without network access;
C2 T15 requires replay to run with networking disabled; D3 asks for offline
replay for all demo cases. This slice connects the existing cache implementation
to the repository's normalized application entry point. It does not add a
Telegram SDK or invent missing D3 scenarios.

## Caller and behavior

`OfflineTelegramAdapter.handle_update()` handles the project-local command
`/replay synthetic-referral-01`. The fixture ID is the only currently
registered replay ID and is resolved through a SHA-256 cache key. The adapter
uses the injected exact `TraceStore` instance and `DEMO_MODE`; the existing
cache payload validation and fixed synthetic English response selection remain
in force. Unknown IDs, missing/corrupt entries, missing stores, and disabled
`live` mode produce one generic unavailable outcome. None falls through to
workflow or provider execution. Conversation state is not altered and outbound
delivery remains disabled unless the existing exact fake transport is
explicitly enabled.

Successful replay reads are recorded using the existing B9 `cases`/`steps`
schema: a generated case ID, final replay outcome, `input_type=text`, and one
`replay_cache_read` completed step. The trace contains no fixture ID, cache key,
command text, user identifier, image data, or response body. If trace recording
fails, the response is not returned.

## Tests

`tests/test_bot_adapter.py` covers allowlisted selection, repeatability,
successful cache read, trace records, unknown/malformed IDs, missing/corrupt
entries, `DEMO_MODE=live`, absent store, no network sockets, and default-off
delivery. `tests/test_offline_replay.py` continues to cover cache schema,
payload, timestamps, duplicate protection, synthetic outcomes, and backup
preservation.

## Verification

- `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_bot_adapter.py tests/test_offline_replay.py tests/test_trace_store.py` — 84 passed.
- `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider` — 878 passed.
- `python3 -m compileall -q src tests eval` — passed.
- `pyproject.toml`, all three `config/*.yaml` files, and the JSONL test log
  parsed successfully; 2 JSONL rows, 0 executed.
- `git diff --check` — passed; scoped whitespace scan — 0 trailing-whitespace
  lines; safe secret-pattern scan — 0 matches, `.env` excluded.
- Metadata-only Git checks confirm `.env` is ignored and untracked. Its content
  was not read.

## Status

T15 remains **PARTIAL**. The caller is connected for one registered synthetic
fixture with safe cached content. D3's complete demo-case inventory is not in
the repository, so it was not fabricated. The adapter is still a normalized
offline boundary, not a real Telegram wire handler. No image-hash lookup or
provider response replay was introduced. Live mode remains disabled and live
SAM remains **NO-GO**.

No network/API calls, uploads, credential access, dependency installation,
credit use, or Git history/staging operations occurred.
