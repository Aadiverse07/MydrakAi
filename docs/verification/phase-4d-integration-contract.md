# Phase 4D integration contract (offline, evidence-backed)

**Date:** 2026-10-28. **Scope:** contract and evidence review ONLY. This
document authorizes no live test, no client, and no request. Live SAM
remains **NO-GO**.

Labels used throughout: **VERIFIED IN REPO** (confirmed by current
code/tests), **OFFICIAL SOURCE RECORDED** (the repository already records
a specific official source for the exact claim), **PROJECT-LOCAL
ASSUMPTION** (synthetic fixture grammar or internal design choice),
**UNVERIFIED** (not established by repository evidence), **BLOCKED**
(must be resolved before a live test).

## A. Current implementation versus future boundary

What exists (all offline, all mock-first):

- `src/mydrak/sam/output.py` — validates a **project-local synthetic
  JSON mapping grammar** (`image`/`objects`/`id`/`box`/`mask`/`encoding`/
  `data`, optional `score`). Boxes are absolute source pixels; masks are
  opaque strings that fit inside their frame; unknown keys rejected;
  zero-match valid. 71 tests in `tests/test_sam_output.py`. It does not
  parse Meta wire text.
- `src/mydrak/sam/response_text.py` — validates the **documented
  single-image text shape**: `<0f>` frame marker, comma-separated
  `id<|box;x1=..;y1=..;x2=..;y2=..;w=..;h=..;c=..|>`
  `<|mask;x=0;y=0;c=..;data=<H>,<W>,<enc>payload|>` records. Enforced:
  source-pixel boxes against caller-supplied dimensions, zero mask
  origin, strictly-smaller mask dims, both-or-neither confidence with
  agreement, ASCII-only unsigned numerics with a digit cap, opaque
  never-decoded payloads, strict frame syntax (only empty output is a
  zero-match), bounded record scan. 75 tests in
  `tests/test_sam_response_text.py`. It performs shape validation only.
- `src/mydrak/sam/transport.py` — `SamScanRequest` (IDs, scope, prompt;
  never image bytes), deterministic `FakeSamTransport`, default-is-fake,
  `request_live_transport()` raises, `run_scan` validates → counts one
  guard attempt → dispatches once → parses, timeouts to manual review
  with no retries, results wrapped in `MockScanResult` whose
  `"synthetic-mock"` provenance the constructor enforces.
- `src/mydrak/sam/guard.py` — default-off campaign guard: explicit
  local-operator authorization (single-use token fingerprints, campaign
  ID + scope + expiry binding), max 5 attempts per epoch counted before
  dispatch, durable file-backed budget with in-process loss/rollback
  tripwire, persistent breaker, explicit reset + re-authorization.
  46 tests in `tests/test_sam_live_guard.py` cover guard + transport.
- Downstream handoff boundary: parsed frames return to the caller
  wrapped with their synthetic marker. Nothing here performs diagnosis,
  and mock results must never be presented as model output.

What does not exist: no live SAM client, no image-upload path, no SSE
assembler, no mask decoder, no retry/polling/background dispatch, no
billing control, no authorization/notice product flow.

## B. Evidence classification

| Contract element | Label | Evidence / reason |
|---|---|---|
| Synthetic mapping grammar (exact keys, JSON shape, score semantics) | PROJECT-LOCAL ASSUMPTION | `output.py` docstring: fixture grammar mirroring the verified shape only |
| Record kinds (object ID, box, mask per frame line), source pixels, zero-match validity | OFFICIAL SOURCE RECORDED | Matrix SAM row cites dev.meta.ai overview + reading-segmentation |
| Exact token spelling (`<0f>`, `<\|box;…\|>`, `<\|mask;…\|>`, `data=H,W,enc`) | OFFICIAL SOURCE RECORDED | Matrix Phase 3B note: parser-repo READMEs + `protocol/sam3.md`; primary pages not freshly fetched |
| `~` lossless / `!` one-bit labels; Base85, not Base64 | OFFICIAL SOURCE RECORDED | Same parser-repo sources; decoding itself is UNVERIFIED |
| Zero origin; strictly-smaller masks; both-or-neither confidence; strict frame syntax | OFFICIAL SOURCE RECORDED | Codex review of the primary grammar page, recorded in matrix Phase 3C note + readiness §2; own snippets corroborate spelling only |
| Base85 alphabet variant, padding, decoding correctness | UNVERIFIED | Readiness §9: docs do not specify them; no decoder exists |
| Confidence 0..1 range on requested box/mask values | OFFICIAL SOURCE RECORDED (recorded citation, not fresh verification) | Matrix Phase 4B grammar-shape bullet cites the output-grammar page for "the same 0..1 value"; no fresh page fetch confirms it beyond that recorded citation — do not read it as an independently verified official contract |
| Synthetic `score` 0..1 field; `x2 == w` edge acceptance | PROJECT-LOCAL ASSUMPTION | `output.py` score semantics and the `response_text.py` edge rule are local definitions, separate from the recorded official range |
| Size/digit caps, 5-attempt budget, prompt/ID bounds, lock timeout | PROJECT-LOCAL ASSUMPTION | Declared local bounds in code; never Meta limits |
| File-backed budget durability, rollback tripwire, operator-gate semantics | VERIFIED IN REPO | `guard.py` + 46 guard/transport tests; cross-restart deletion explicitly out of scope |
| Mock-only transport, provenance wrapper, no-retry behavior | VERIFIED IN REPO | `transport.py` + tests, including forged-reply and subclass rejection |
| Model ID `sam-3.1`; `POST /v1/responses`; `input_text` + image parts | OFFICIAL SOURCE RECORDED | Matrix/readiness cite Models + Overview pages |
| `sam-3-1` product-page label vs `sam-3.1` | UNVERIFIED | Discrepancy explicitly unresolved; configures nothing |
| Prices ($2.50/1k images etc.), 3000 RPM | OFFICIAL SOURCE RECORDED | Pricing page = rates only, not entitlement |
| Credit coverage, billing state, spend caps for this account | UNVERIFIED | No account evidence; alerts are not hard caps |
| Standard no-training terms + retention allowances | OFFICIAL SOURCE RECORDED | Terms §§4.4, 5.1 as recorded |
| Account/model ZDR status | UNVERIFIED | Requires qualified enablement; never inspected |
| Privacy notice / consent product flow | UNVERIFIED | No flow exists; env flags are not consent |
| Either parser's live-wire compatibility | UNVERIFIED | No live sample; compatibility unproven by design |
| Any live test | BLOCKED | Every §E gate below is unsatisfied |
| Cost-log semantics (null = unknown, 0 = verified zero only) | VERIFIED IN REPO | JSONL schema line; zero executed records in file |

## C. Future request/response contract questions (unanswered)

- Actual accepted input format and encoding (URL vs data URL vs upload).
- Still-image formats, dimensions, and payload limits applicable to SAM.
- Mask encoding variant, raster layout, and decoding semantics.
- Box-area semantics for adapter mapping (observed project-local
  difference, not Meta evidence): `response_text.py` accepts
  zero-width/height boxes (`0 <= x1 <= x2`, `0 <= y1 <= y2` at
  `response_text.py:189,191`) while `output.py` rejects zero-area boxes
  (`0 <= x_min < x_max` at `output.py:143`). Official wire-format box
  semantics and the correct production mapping stay UNVERIFIED.
- Response framing: streaming (SSE) vs single response; per-frame delivery.
- Error/status shapes, timeout behavior, and ambiguous-outcome handling.
- Account/model access, eligibility, and resolved model identifier.
- How mock and live results stay separated at every layer.
- Retry policy and its provider-side cost implications. Narrowed scope:
  a one-request smoke test, if separately authorized in the future, must
  use zero retries; the existing B11 application-level bounded
  retry/fallback policy (timeout, at most 2 retries, defined fallback
  per `AGENTS.md`; readiness §5) remains applicable at the project
  level. SAM-specific provider retry semantics, failure classification,
  and cost implications remain UNVERIFIED. This states a requirement
  only; it authorizes no test and changes no status.

## D. Privacy, consent, and cost blockers

Per `phase-4c-privacy-notice-questions.md` and readiness §5/§10, all
unknown: which services receive images/prompts; what is stored where;
retention/deletion timelines; access controls; required notice/consent
wording and recording; authentication and per-request Standard routing;
actual account access, credits, expiry, and billing exposure. No legal
approval exists; no hard spending cap exists; ZDR is not enabled by
anything in this repository.

## E. Explicit no-go criteria

A separately authorized live test requires ALL of: resolved model
identifier + account access evidence; complete hackathon rules review;
verified credits/expiry/eligibility plus reviewed billing exposure with
explicit charge acceptance; rights-cleared non-personal test image with
approval; shipped notice + per-request authorization on a verified
Standard route with a retention/ZDR decision; confirmed SAM media
limits; an offline-validated parser/decoder adapter; one-call guard
with retries disabled; and separate direct user authorization recorded
after all of the above. Failing any item blocks the test.
