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

Offline code now includes explicitly constructed Glimmer (Together) and Spark
(Meta) clients plus one-request smoke CLIs. They accept only user-supplied
provider contract notes in `docs/providers/`; those notes, model IDs, endpoints,
prices, timeouts, and account access remain UNVERIFIED. No smoke request was
run. The clients require `--live-authorized`, `MYDRAK_LIVE=1`, a positive
`--max-spend-usd`, a persistent ignored spend ledger, the appropriate credential
environment variable, configured input-token estimate and output-token maximum,
and known prices before dispatch. The tier-1 and tier-2 `max_input_tokens_estimate`
values in `config/models.yaml` are user supplied and unverified. A local
worst-case reservation is an estimate, not a provider billing cap or guarantee
against charges. Together credentials use `TOGETHER_API_KEY`; Meta credentials
use `META_API_KEY`. Neither is loaded from `.env` by this code. Mock workflow
and replay remain disconnected from live clients and never fall back to them.
The separately selected Spark-only path requires explicit per-run authorization.
Any live request still requires separate user authorization and all
eligibility, billing, privacy, retention, and compatibility gates.

The user reports approximately $97.40 in API credits and reserves at least $50
for judging/final demo; these account figures are unverified, making $47.40 an
upper bound on possible development spend. The first live-test cap must be set
by the user, and any live call requires separate authorization after the
account, billing, privacy, and compatibility gates are met.

## Telegram runner (Phase 11; wire use remains blocked)

The offline runner supports `/start`, `/language`, `/help`, `/rescan` (which
states rescan is unimplemented), private-chat and allowlist decisions, hashed
local limits, and cached replay. It never reads `.env`; supply environment
variables through the process or deployment environment. Restricted access
uses `TELEGRAM_BOT_TOKEN` and comma-separated `TELEGRAM_ALLOWED_CHAT_IDS`, with
`--live-authorized`, `MYDRAK_LIVE=1`, a positive `--max-spend-usd`, and an
existing spend ledger. The supplied Telegram excerpt omits HTTP method/body
encoding and raw Update/File response schemas, so the default transport refuses
polling and sending with a `TODO(verify)` boundary. No live Telegram run is
currently possible through this code.

Public mode also requires `--public-access` and `MYDRAK_PUBLIC=1`, plus a
complete `config/bot_limits.yaml`. Start with `config/bot_limits.example.yaml`;
it intentionally supplies no numeric limits. Missing or invalid limits refuse
startup. Public access permits any private chat; photos may be sent to an AI
model provider and costs can accrue, while a software spend alert/cap does not
guarantee zero billing. The host must remain running. Telegram photos are
private by default; current model config does not enable private uploads and
the runner has no verified rights-evidence source, so photo analysis fails
closed. Hindi remains unavailable pending review. Do not enable public access
until wire details, privacy review, and safeguards are resolved.

Cached offline scenarios need no Telegram token, polling, model call, or
network: `python3 scripts/run_telegram_bot.py --replay` (or name a registered
fixture after `--replay`).

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
