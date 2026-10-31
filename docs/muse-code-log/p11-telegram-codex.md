# Phase 11 — Telegram wire boundary and bot runner

**Tool:** Codex.
**Mode:** Offline implementation and tests only. No Telegram or model requests were made.

## Source review

Read `AGENTS.md`, architecture and daily logs, the C2 roadmap, B7/B11/B12 in the master PDF, the existing bot adapter, live guard, Spark-only workflow, replay, reply templates, trace store, and the user-supplied `docs/providers/telegram.md` excerpt.

The local Telegram excerpt names `getUpdates`, `sendMessage`, `sendPhoto`, and `getFile`, their listed parameters, and the documented download URL and size notes. It does **not** specify the HTTP method/body encoding, Bot API response envelope, or nested `Update`/`Message`/`PhotoSize`/`File` field schemas. Those facts are marked `TODO(verify)`. The default transport refuses before opening a socket; the project-local normalized update used by tests is not claimed to be Telegram's schema.

## Implemented offline

- Added `src/mydrak/telegram/client.py` with bounded method parameter construction, in-memory download interface, redacted representation, sanitized errors, and an unverified fail-closed default transport.
- Added access configuration: allowlist is default and requires `TELEGRAM_ALLOWED_CHAT_IDS`; public mode requires `--public-access` plus `MYDRAK_PUBLIC=1` and a complete `config/bot_limits.yaml`.
- Added an atomic SQLite public-limit store keyed by a SHA-256 user digest. It stores digest, UTC date, request count, and last request timestamp only. User/global daily limits, cooldown, photo size, and pre-call spend-ledger headroom block provider work.
- Added `TelegramBotRunner` for normalized synthetic updates, private chats, `/start`, `/language`, `/help`, `/rescan`, text/other handling, STOP and SIGINT, send retry (initial attempt plus at most two retries), and hash-only traces. A successfully delivered `/start` notice is required before a photo can proceed.
- Photo bytes are obtained through the injected client only after size, access, consent, private-upload config, and rights/provider evidence checks; they are passed in memory to the existing `spark_only` workflow and not written to disk. The contributor model is never selected. Current CLI evidence/config are insufficient for private processing, so it refuses by default. Overlay delivery is supported if a future workflow returns one; Spark-only currently returns none.
- Added `--replay [fixture-id]`, which seeds/reads only registered synthetic cached responses without Telegram or model calls. Added README setup/warnings, `.env.example` placeholders, `.gitignore` entries, roadmap and daily-log updates.
- B7 photo captions are not yet consumed as symptom hints; the local provider excerpt does not supply a raw Message schema, and no caption text enters model input or traces.
- Committed the user-supplied `config/models.yaml` separately after a safe scan found zero credential-assignment, private-key, or bearer-pattern matches. Values remain user-supplied and unverified. `docs/providers/` remained unstaged.

## Acceptance evidence and limitations

Offline tests cover method fields and bounds, missing allowlists, public-mode flag/env/config gates, hashed-only persistence, user/global/day/cooldown/size/spend gates, group ignore, `/start`-before-photo, private upload and evidence denial, mock Spark-only routing with standard mode, overlay send, two-retry send behavior, failed-send trace, STOP, malformed updates, token/content/identifier redaction, default socket refusal, and no-network cached replay.

The task is **PARTIAL**. No actual Telegram request serialization or raw response parsing was guessed. The default wire transport cannot poll or deliver until the provider excerpt documents those formats and a verified standard-library transport is implemented. Public mode must remain disabled until limits, privacy conditions, and those wire details are resolved. No live Telegram run is authorized or reported.

## Verification

- Focused: `PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_telegram_client.py tests/test_telegram_config.py tests/test_telegram_limits.py tests/test_telegram_runner.py tests/test_run_telegram_bot.py -q` — **44 passed**.
- `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider -q` — exit 0, **1183 passed**.
- `PYTHONDONTWRITEBYTECODE=1 python3 -m compileall -q src tests eval` — exit 0.
- TOML/YAML parse probe — exit 0; `pyproject.toml` and **5** `config/*.yaml` files parsed.
- Safe scan over **22** changed/new candidate files (excluding `.env` and user-supplied, unstaged `docs/providers/`) — **0 non-synthetic credential assignments, 0 bearer candidates, 0 private-key blocks, 0 Telegram-token-shape candidates**. Four literal secret-like strings are synthetic test values; only counts and locations were emitted. The separate `config/models.yaml` scan before its own commit found zero credential-assignment, bearer, and private-key candidates.
- `git diff --check` — exit 0. Untracked-file whitespace scan — **15** files checked, 0 trailing-whitespace lines.
- Metadata only: `git check-ignore -v .env config/bot_limits.yaml .mydrak-bot-limits.sqlite3 .DS_Store docs/crop1.jpeg eval/data/dev eval/results` — exit 0; ignore rules were reported for existing ignored paths. `git ls-files -- .env config/bot_limits.yaml .mydrak-bot-limits.sqlite3 docs/crop1.jpeg eval/data/dev eval/results` — exit 0, no tracked paths. `git status --short --ignored -- ...` showed ignored `.env`, `.DS_Store`, `docs/crop1.jpeg`, `eval/data/dev/`, and `eval/results/`; `.env` was never read. The actual `config/bot_limits.yaml` and local bot-limit DB do not exist.
- Source module sizes: all new Telegram modules are at or below 300 lines (`runner.py`: 300). No live request, network test, image upload, credential use, or credit spend occurred.
