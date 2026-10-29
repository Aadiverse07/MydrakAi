# Mydrak AI v3 — architecture (foundation and Phase 1 snapshot)

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

## Phase 2 authorization boundary — planning only

Phase 2 planning and offline/mock parser work are authorized. **SAM 3.1 is not
implemented**: this repository has no SAM client, outbound request, media
upload, or production parser. Planning may describe and verify interfaces from
official documentation; parser work, if separately undertaken within this
phase, must use synthetic fixtures and run without network access. No farmer
media, credentials, or personal data may be used in offline fixtures.

The official SAM documentation describes model ID `sam-3.1` on the Responses
API, a text concept prompt plus image/video part, and box/mask output. The
official output is special-token text with frame/object records, boxes, and
encoded masks; it is not the local `sam/severity.py` interface. The existing
`src/mydrak/sam/output.py` is an offline parser for a project-local synthetic
fixture grammar only: it does not parse, validate, or establish compatibility
with actual Meta SAM wire output, and the production SAM integration remains
not implemented. Generic Meta file handling lists image MIME types and size
limits, but those are not confirmed as SAM-specific. SAM-specific still-image formats, dimensions,
payload limits, and any applicable account credit entitlement remain
**UNVERIFIED**. See
[`verification/official_meta_api_matrix.md`](verification/official_meta_api_matrix.md)
and [`verification/credit_protection.md`](verification/credit_protection.md).

Any future outbound SAM operation requires separate authorization and must be
blocked before request construction reaches a network, upload, or SDK boundary
unless all policy checks pass: Standard/non-contributor route verified for the
actual request; rights and provenance verified; user authorization and privacy
notice established; and billing/credit eligibility confirmed. `DATA_POLICY`
and caller-supplied booleans are not evidence of consent, rights, provider
routing, account eligibility, or ZDR. The existing local privacy gate is not
yet wired to an outbound sender. Standard mode's no-training statement does
not guarantee zero retention; account- and SAM-specific ZDR/retention status
remains **UNVERIFIED**. Until those checks are independently established, all
private farmer images, audio, and derived personal data remain blocked from
external processing.
