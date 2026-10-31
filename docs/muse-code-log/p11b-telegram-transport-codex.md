# Phase 11b — Telegram HTTP transport

**Tool:** Codex. **Scope:** offline implementation and loopback tests only; no
Telegram or model requests were made.

## Source contract

Used only the locally supplied `docs/providers/telegram.md` formats: the
`https://api.telegram.org/bot<token>/METHOD_NAME` URL, POST JSON for ordinary
methods, multipart for byte uploads, the JSON `ok/result` wrapper, documented
Update/Message/Chat/User/PhotoSize/File fields, and
`https://api.telegram.org/file/bot<token>/<file_path>` with a 20 MB download
bound. No web sources were fetched.

## Implementation

- Replaced the default refusing transport with `TelegramHttpTransport`, using
  `urllib.request`; ordinary Telegram method parameters are JSON POST bodies,
  byte `sendPhoto` uses `multipart/form-data`, and photo references remain
  JSON values. File downloads use the documented URL and a caller-supplied byte
  bound. A project-local 20 MiB response-read cap bounds JSON memory use.
- API wrapper errors and low-level HTTP exceptions are converted to fixed safe
  errors; response descriptions, headers, bodies, token-bearing URLs, and
  redirect targets are not exposed. The token is held only in the in-memory
  transport needed to construct documented request URLs; representations are
  redacted.
- Added defensive Update/Message/PhotoSize normalization. Unknown fields are
  ignored; malformed or unsupported updates with an `update_id` are skipped and
  acknowledged by advancing offset; duplicates are not processed twice. An
  unusable update with no ID stops polling safely because it cannot be
  acknowledged. A PhotoSize candidate must have a valid file ID, dimensions,
  and known positive `file_size` at or below 20 MB; among those, the greatest
  width × height is selected. Candidates missing the optional size are skipped
  to preserve pre-download size gates.
- Existing allowlist, public-mode, daily/cooldown/photo-size/spend protections,
  `/start` privacy notice, retry bounds, STOP behavior, hash-only identifiers,
  and replay/provider isolation remain in place.
- The end-to-end loopback photo test uses synthetic update/photo data and an
  injected workflow reading the registered cached synthetic referral. It makes
  no provider call and does not claim photo-specific analysis.

T03 remains **PARTIAL** until the user confirms a live run. This session did not
run anything live. Account eligibility, billing/privacy gates, and actual
Telegram compatibility remain unverified; public mode requires operator-filled
limits, and private-photo analysis remains fail-closed without the existing
rights/provider evidence.

## Verification

- Focused: `PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_telegram_client.py tests/test_telegram_config.py tests/test_telegram_limits.py tests/test_telegram_runner.py tests/test_run_telegram_bot.py tests/test_telegram_http_transport.py -q` — exit 0, **55 passed**.
- Full suite: `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider -q` — exit 0, **1194 passed**.
- `PYTHONDONTWRITEBYTECODE=1 python3 -m compileall -q src tests eval` — exit 0.
- TOML/YAML parsing — exit 0; `pyproject.toml` plus 5 `config/*.yaml` files parsed.
- Safe secret-pattern scan — 13 scoped changed/new files, excluding `.env` without reading it and excluding user-supplied `docs/providers/` from the commit scope. **0** matches for Telegram-token shapes, bearer credentials, private-key headers, or credential assignments. The scan reported match counts and locations only; no values were emitted.
- `git diff --check` — exit 0. Untracked-file whitespace scan — 3 newly created files checked, 0 trailing-whitespace lines.
- Metadata only: `git check-ignore -v .env .mydrak-spend-ledger.sqlite3 .mydrak-bot-limits.sqlite3 config/bot_limits.yaml .DS_Store docs/crop1.jpeg eval/data/dev eval/results` — exit 0; ignore rules reported. `git ls-files -- ...` for the same protected paths — exit 0, no tracked paths. `git status --short --ignored -- ...` reports ignored `.env`, spend ledger, `.DS_Store`, crop image, and evaluation data/results. `.env` was never read.
- No live Telegram/model calls, external requests, uploads, credential reads, dependency installs, or credit use occurred. Loopback tests bound only to `127.0.0.1` and suppressed HTTP request logs.
