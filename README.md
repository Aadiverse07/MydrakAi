# Mydrak AI v3 — the plant doctor that knows when it doesn't know.

Theme fit: Indie Developer, Theme 1 (Build for Your World) — an image-first,
voice-friendly crop health assistant for smallholder farmers.
Meta products planned (spec Part B): Muse Spark 1.3 (tier-2 reasoning), Muse
Glimmer (tier-1 cheap diagnosis), SAM 3.1 (lesion severity masks), Muse Voice
Transcribe (Hindi voice input), Muse Code (builder; logs in
`docs/muse-code-log/`).

> Phase 0 status: foundation scaffold only. No bot, model, SAM, or dashboard
> implementation. No integration is claimed to work. Every model ID, endpoint,
> price, and limit is `UNVERIFIED` until tested against official Meta docs.

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
