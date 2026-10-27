# Mydrak AI v3 — architecture (Phase 0 snapshot)

Source: `docs/MydrakDeepseekreformed.pdf`, Part B. This file summarizes the
planned pipeline; nothing below is implemented yet except the pure foundation
functions (`decider`, `sam/severity.py`, `kb/loader.py`, `util/config.py`,
`reply/confidence.py`).

## Planned flow

```text
Farmer (Telegram): photo (+ optional voice OGG)
  -> bot handler; voice -> ffmpeg (OGG->wav 16k mono) -> Voice Transcribe
  -> preprocess (EXIF fix, resize, quality check; fail -> retake request)
  -> cache lookup (hash hit -> reuse stored result)
  -> Tier 1: Glimmer x2 samples -> structured JSON (crop, issue, symptoms, confidence)
  -> Decider: S1 agreement + S2 KB match + S3 quality + S4 stated confidence
       score >= accept ............ answer (tier 1)
       escalate band .............. Spark 1.3 (+ SAM crops) once, then re-score
       still unsure ............... follow-up question (max 2), then expert referral
  -> SAM 3.1: leaf + lesion masks -> severity_pct + overlay
  -> KB lookup (crop + disease card) -> steps from KB only
  -> reply composer (Hindi/English templates) + overlay -> Telegram
  -> trace row -> SQLite -> dashboard
```

## Module responsibilities (spec B1)

bot: Telegram updates, conversation state. Never model calls or business logic.
audio: OGG conversion, transcription. Never diagnosis.
vision: preprocess, quality, model clients, parsing. Never treatment advice.
sam: client, mask math, severity, overlay. Never diagnosis.
decider: signals, score, policy. Never network calls.
kb: load/match cards, supply treatment text. Never model calls.
reply: compose final message from structured data + templates. Never invent facts.
recovery: scan store, severity comparison (should-have). Never diagnosis.
trace: SQLite rows, cost accounting. Never business logic.
util: retry, timeout, config, hashing. Nothing domain-specific.

## Phase 0 implemented

Pure, network-independent, tested: `decider/signals.py` (`combine`),
`decider/policy.py` (`decide`), `sam/severity.py` (`severity_pct`, `band`,
`recovery_trend`), `kb/loader.py`, `util/config.py`,
`reply/confidence.py`. All model IDs, endpoints, prices, and limits remain
`UNVERIFIED` in `config/models.yaml`.

## Phase 1 implemented (mock-only intake)

`intake/adapter.py` (`process_intake`): accepts synthetic image *descriptors*
(never raw bytes), validates format/dimensions/size against local test
boundaries, runs the privacy gate (`privacy/data_policy.py`) before the
deterministic mock diagnosis or the optional caller-supplied `sender` hook,
and returns a structured response (MOCK-labeled findings, plain-word
uncertainty, safety-card safety line + referral) with a privacy-safe trace
(request ID, stages, decision outcome, timings; no bytes, credentials, or
personal data). Blocked requests never invoke `sender`. Telegram intake, model
clients, SAM client, and production senders remain NOT implemented.

## Deferred (later tasks T02-T19)

Telegram bot, audio pipeline, model clients, SAM client/overlay rendering,
trace DB, eval harness runs, dashboard, replay mode, failure-injection suite.
