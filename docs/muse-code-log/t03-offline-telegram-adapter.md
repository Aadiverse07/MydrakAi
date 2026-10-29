# T03 — Offline-First Telegram Adapter and State Flow

Date: 2026-10-29

## Specification basis

Master specification B7 (PDF page 8) defines per-chat states `idle -> awaiting_photo -> analyzing -> (answered | awaiting_followup | retake | referred)`, a rescan branch, and `/start`, photo, voice note, `/language`, `/rescan`, and `/help`. T03's acceptance test is a photo triggering a handler and `/start` working (PDF page 12, C2). The repository does not define a Telegram update wire format, so this task introduces only a normalized project-local synthetic update contract.

## Implementation

- Added `src/mydrak/bot/adapter.py` with bounded enum states, strict metadata checks for the normalized DTO, explicit command handling, immutable state records, and trusted orchestration methods for `analyzing` and downstream B7 outcomes. Update fields cannot set policy, language state, or workflow outcome.
- `/start` returns a welcome/language-choice message with a one-line offline privacy statement. English is available; Hindi returns an explicit unavailable result. `/help` is local. `/rescan` is deferred because scan storage is absent.
- Photo input first passes the configured data-policy gate. Denial transitions to referral/block status before the deferred-processing hook. An allowed photo returns `unsupported_deferred`; no bytes, image descriptors, diagnosis, or SAM fixtures are accepted. Voice is deferred because T10 is absent. A text reply in `awaiting_followup` is not interpreted and routes to manual review/referral.
- Outbound delivery is disabled by default. If explicitly enabled for tests, only the exact in-memory `FakeTelegramTransport` is accepted; no SDK, socket, webhook, polling, or network integration exists.
- Existing T16 follow-up loop remains the source of the two-question bound; this adapter does not infer findings from answers or choose follow-up questions.

## Verification

- `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_bot_adapter.py tests/test_mock_intake.py tests/test_workflow_coordinator.py tests/test_followup.py` — 85 passed.
- `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider` — 660 passed, 0 failed.
- No API/Telegram/network calls, media uploads, credential access, dependency installs, or Git history operations. Live SAM remains NO-GO.
