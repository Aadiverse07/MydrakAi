# Mydrak AI v3 — the plant doctor that knows when it doesn't know.

Theme fit: Indie Developer, Theme 1 (Build for Your World) — an image-first,
voice-friendly crop health assistant for smallholder farmers.
Meta products planned (spec Part B): Muse Spark 1.3 (tier-2 reasoning), Muse
Glimmer (tier-1 cheap diagnosis), SAM 3.1 (lesion severity masks), Muse Voice
Transcribe (Hindi voice input), Muse Code (builder; logs in
`docs/muse-code-log/`).

> Current status: offline workflow, cached replay, mock Telegram adapter, and
> guarded Spark-only code exist. Telegram's raw Bot API mapping remains blocked
> by missing request/response details in the local provider excerpt. No Phase
> 11 Telegram live run has been made. Live SAM remains NO-GO.

## Layout

```text
config/          models.yaml, thresholds.yaml, severity.yaml
src/mydrak/      bot audio vision sam decider kb reply recovery trace util
kb/cards/        curated disease cards + general_safety.yaml (KB-only treatment source)
tests/           minimal tests for executable foundation code
eval/            harness skeleton (data/dev, data/test, results/)
dashboard/       deferred to a later phase (placeholder)
scripts/         deferred smoke scripts (placeholder; no live calls in Phase 0)
docs/            architecture.md, DAILY_LOG.md, muse-code-log/
```

## Setup (Phase 0)

Requires Python 3.11+. No API keys needed — Phase 0 makes no network calls.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python3 -m pytest
```

Copy `.env.example` to `.env` when later phases need keys. Never commit `.env`.

## Live provider gate (code exists; live use is not authorized)

Offline code now includes explicitly constructed Glimmer (NVIDIA selected;
Together remains selectable) and Spark (Meta) clients plus one-request smoke CLIs. A separate SAM 3.1 Responses-stream client and guarded smoke CLI are also present; no SAM or Glimmer smoke was run.
They accept only user-supplied
provider contract notes in `docs/providers/`; those notes, model IDs, endpoints,
prices, timeouts, and account access remain UNVERIFIED. No smoke request was
run. The clients require `--live-authorized`, `MYDRAK_LIVE=1`, a positive
`--max-spend-usd`, a persistent ignored spend ledger, the appropriate credential
environment variable selected by `glimmer_host.choice`, configured input-token estimate and output-token maximum,
and known prices before dispatch. The tier-1 and tier-2 `max_input_tokens_estimate`
values in `config/models.yaml` are user supplied and unverified. A local
worst-case reservation is an estimate, not a provider billing cap or guarantee
against charges. The selected NVIDIA Glimmer profile reads `NVIDIA_API_KEY`; the
Together profile reads `TOGETHER_API_KEY`; Meta credentials use `META_API_KEY`.
Credentials are read from process environment variables, never from `.env`.
NVIDIA pricing values are nonzero UNVERIFIED placeholders used only to reserve
ledger budget, not NVIDIA billed prices. The NVIDIA hosted endpoint remains
UNVERIFIED until a smoke test passes. Do not send private farmer photos to it
until its retention and privacy terms are reviewed; `DATA_POLICY=private` is
not approved for NVIDIA Glimmer. Mock workflow
and replay remain disconnected from live clients and never fall back to them.
The separately selected Spark-only path requires explicit per-run authorization.
Any live request still requires separate user authorization and all
eligibility, billing, privacy, retention, and compatibility gates.

SAM remains **NO-GO** for live use. Its smoke path requires both the shared
CLI/environment/spend-ledger guard and the persistent SAM campaign guard; a
successful smoke would be necessary but not sufficient to resolve account,
privacy, image-limit, decoder, and compatibility blockers. The request path
and inline image data-URL acceptance remain UNVERIFIED where the supplied
provider note identifies them as inferred.

An isolated Muse Voice Transcribe client and guarded smoke CLI are also
implemented with the stdlib multipart transport and local ffmpeg conversion.
No voice smoke was run. Provider/account compatibility, retention, and Hindi
field quality remain UNVERIFIED. Telegram updates do not yet expose a
normalized voice-file seam, so voice transcription is not wired into bot
handling.

The user reports approximately $97.40 in API credits and reserves at least $50
for judging/final demo; these account figures are unverified, making $47.40 an
upper bound on possible development spend. The first live-test cap must be set
by the user, and any live call requires separate authorization after the
account, billing, privacy, and compatibility gates are met.

## Telegram runner (Phase 11b; live run not yet confirmed)

The runner supports `/start`, `/privacy`, `/agree`, `/withdraw`, `/language`,
`/help`, `/rescan` (which states rescan is unimplemented), private-chat and
allowlist decisions, hashed local limits, and cached replay. The standard-library transport follows the request,
response, Update/File, and download formats recorded in
`docs/providers/telegram.md`; loopback tests cover those formats. This does not
establish live account access or successful Telegram compatibility. T03 remains
PARTIAL until the user confirms a live run. The runner never reads `.env`; pass
environment variables through the process or deployment environment.

## Consent-gated private photos

The local `config/reply.yaml` settings `consent_notice_approved`,
`allow_private_upload`, and `private_tier1_allowed` default to `false`. The
English notice in `src/mydrak/reply/templates.py` remains marked **DRAFT**;
turning on the approval setting records the operator's decision to use that
wording, not legal approval or provider-retention verification. Its SAM wording
matches this repository: SAM segmentation is synthetic/mock and no live SAM
request is made. Meta/provider retention terms remain UNVERIFIED. The
project-owner-supplied Meta pricing-page statement about standard-model product
improvement has not been independently rechecked in this task.

Operator sequence before any photo path is enabled:

1. Review the DRAFT notice and verify the applicable provider, privacy, billing,
   rights, and deployment requirements. Only then set
   `consent_notice_approved: true` in the local `config/reply.yaml`.
2. Only after those gates are satisfied, set `allow_private_upload: true` in
   that same local file. It remains `false` by default and was not enabled here.
3. Keep `private_tier1_allowed: false`. The available private path selects
   `spark_only`; enabling the flag currently fails closed because no private
   Glimmer route exists.
4. Start the restricted operator bot with the normal live guard and an
   allowlisted chat. In Telegram, use `/start`, read `/privacy`, then send
   `/agree`. The consent record is keyed by the existing hashed-user scheme;
   `/withdraw` revokes it. A missing, revoked, or stale consent blocks before
   Telegram fetches the photo.

Consent rows in `.mydrak-bot-limits.sqlite3` contain only `user_hash`,
`consent_version`, `consented_at`, and nullable `revoked_at`. A separate notice
view row stores only the hashed user, notice version, and shown timestamp. The
trace database stores structured case/step/signal/measurement/scan metadata
(including image hashes and scan plant labels), token/cost fields when known,
and synthetic replay-cache responses. The trace schema also contains an
evaluation-run metadata table that the Telegram runner does not write. The
limits database stores hashed user/day photo counts, last-request timestamps,
and daily aggregate counts. In-memory conversation state and the started-chat
set are keyed by hashed chat IDs and contain only status/language or the hash.
No photo bytes or message text are written to these local
trace/cache/consent records. The local SQLite files have no implemented expiry,
deletion command, or encryption guarantee.

This is not authorization to make a live model or Telegram call. The live SAM
transport remains separately gated and NO-GO; the Telegram workflow currently
uses only synthetic SAM behavior.

## Telegram live check

These are operator runbook commands only; Codex did not run them. Supply values
through the process environment and shell placeholders. Do not put secrets in
command text or public files.

**Stage 1 — restricted operator check:** set `TELEGRAM_BOT_TOKEN` and
`TELEGRAM_ALLOWED_CHAT_IDS` to the operator's own numeric chat ID, then run:

```sh
TELEGRAM_ALLOWED_CHAT_IDS="$OPERATOR_NUMERIC_CHAT_ID" MYDRAK_LIVE=1 python3 scripts/run_telegram_bot.py --live-authorized --max-spend-usd "$BOT_MAX_SPEND_USD" --ledger "$EXISTING_SPEND_LEDGER"
```

A user-confirmed T03 live check means polling and offset handling work for that
operator, `/start`, `/help`, and `/language en` receive successful replies, and
the restricted runner can be stopped safely. It does not verify photo upload,
privacy consent, or model diagnosis.

**Stage 2 — public mode:** only after Stage 1 is confirmed and the separate
privacy, consent, deployment, and budget decisions are approved, run with the
operator-reviewed local limits file:

```sh
MYDRAK_PUBLIC=1 MYDRAK_LIVE=1 python3 scripts/run_telegram_bot.py --public-access --live-authorized --max-spend-usd "$BOT_MAX_SPEND_USD" --ledger "$EXISTING_SPEND_LEDGER" --bot-limits config/bot_limits.yaml
```

Public mode requires `--public-access`, `MYDRAK_PUBLIC=1`, and the complete,
ignored `config/bot_limits.yaml`; missing or invalid limits refuse startup.
Public access permits any private chat, and the host must remain running.
Private uploads and consent-notice approval are default-off local settings. A
photo still fails closed unless the notice has been shown and approved, current
consent is active, the configured model is the standard Spark ID, the separate
upload setting is enabled, and the shared live guards pass. User consent is a
self-attestation, not legal verification. Hindi remains unavailable pending
review. Do not enable public access until privacy and consent decisions are
resolved.

The configured `$15` global spend cap is checked against the persistent shared
ledger's cumulative estimated reservations; it is not a daily or per-process
reset. Daily request counters use UTC calendar dates and advance at UTC
midnight. They are reserved only for the photo path; voice messages currently
normalize as unsupported and do not count as requests. The spend ledger is an
estimate, not a provider billing cap.

Use cached replay for offline operation:

```sh
python3 scripts/run_telegram_bot.py --replay synthetic-referral-01
```

Cached offline scenarios need no Telegram token, polling, model call, or
network. The default `--replay` fixture is `synthetic-referral-01`; only
registered synthetic fixtures are accepted.

## Safety and honest limits

- Preliminary guidance only; never a confirmed diagnosis. Does not replace an
  agricultural expert (Kisan Call Centre / local KVK).
- Treatment text comes exclusively from verified `kb/cards/*.yaml` cards.
  Phase 0 ships only `general_safety.yaml` (safety line + referral); disease
  cards are pending verified sourcing — none are included.
- All Hindi user-visible text will be pre-written and reviewer-approved; none
  is generated live, and none is included yet.
- Uncertain cases end with a retake request, a follow-up question, or expert
  referral. Confidence is stated in plain words only (fairly sure / not sure /
  cannot tell), never a fake-precise percentage.
- Eval figures in the spec (e.g. accuracy/cost chart values) are targets, not
  results. No evaluation has been run; no results are claimed.
