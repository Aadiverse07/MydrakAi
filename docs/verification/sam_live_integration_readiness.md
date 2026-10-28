# SAM 3.1 live-integration readiness assessment

**Date:** 2026-10-27. **Scope:** documentation, compatibility, privacy, and
cost assessment ONLY. No API calls, uploads, credentials, or code changes were
made for this assessment. SAM 3.1 is **NOT IMPLEMENTED** in this repository.

**Evidence basis:** the in-repo verified reports in `docs/verification/`
(recorded 2026-10-27 from official Meta pages) and the inspected source in
`src/mydrak/sam/output.py`, `src/mydrak/workflow/offline.py`,
`src/mydrak/privacy/data_policy.py`, and `src/mydrak/vision/source.py`.
No fresh official pages were fetched for this report; links below are the
recorded ones and must be rechecked before any live step.

## 1. Executive summary

Live SAM 3.1 integration is **not ready and not authorized**. The official
interface shape (model ID, endpoint, request parts, output record kinds,
pricing basis, Standard data terms) is verified and recorded, but every
item required to send a real image safely remains unverified: SAM-specific
media/payload limits, mask decoding, credit
eligibility and account billing state, per-request Standard routing, user
authorization and privacy notice, and account/model ZDR status. The
synthetic-grammar parser validates only a project-local fixture format;
the Phase 3B text parser (2026-10-28, `src/mydrak/sam/response_text.py`)
validates the documented single-image text shape with opaque, never-decoded
payloads — shape parsing only, not decoding, transport, or live
compatibility. A provider adapter with its own contract tests, verified
against documentation or an authorized sample, remains mandatory before any
live response is trusted. Recommendation: **NO-GO** until the blockers in
section 3 clear in the listed order.

## 2. Verified facts and official references

| Item | Status | Reference / reason |
|---|---|---|
| Model ID `sam-3.1` | VERIFIED | [Models](https://dev.meta.ai/docs/models), matrix SAM row. Discrepancy with `sam-3-1` on the product/pricing page remains explicitly UNRESOLVED (matrix Phase 3B note); it authorizes no client configuration |
| Base URL + `POST /v1/responses`, Bearer API key | VERIFIED | [Overview](https://dev.meta.ai/docs/sam/overview) |
| `input_text` + `input_image`/`input_video` request parts | VERIFIED | [Overview](https://dev.meta.ai/docs/sam/overview), anatomy of request/response |
| `output_text` special-token records, per image/frame, with object ID, box, mask | VERIFIED | [Output grammar](https://dev.meta.ai/docs/sam/reading-segmentation), line structure |
| Boxes use source pixels; mask carries dimensions/encoding; zero matches valid | VERIFIED | [Output grammar](https://dev.meta.ai/docs/sam/reading-segmentation) |
| Video MP4/MOV, H.264/H.265/MPEG-4 | VERIFIED | [Overview](https://dev.meta.ai/docs/sam/overview), input description |
| Price $2.50/1k images; $0.20/1k frames, 50-frame minimum; 3000 RPM/team | VERIFIED | [Pricing](https://dev.meta.ai/docs/pricing-rate-limits) — rates only, not entitlement |
| Standard designation: no training use; retention allowed for service/legal/safety | VERIFIED | [Terms](https://dev.meta.ai/legal/terms-of-service) §§4.4, 5.1 |
| Contributor must not receive personal information | VERIFIED | [Contributor help](https://dev.meta.ai/help/policies-and-privacy/contributor-tier), Terms §6.2 |
| Local gate fails closed; no sender wired; no network imports in `src/` | VERIFIED | Inspected `data_policy.py`, `intake/adapter.py`, import scan |
| Single-image text shape: `<0f>` frame, comma-separated `id<\|box;…\|><\|mask;…\|>` records, `data=<H>,<W>,<enc>payload`; zero origin; mask dims strictly smaller than source; confidence both-or-neither with agreement; strict frame syntax (empty output only = zero-match) | VERIFIED (Codex review of primary grammar) | [Output grammar](https://dev.meta.ai/docs/sam/reading-segmentation) via Codex review; token spelling corroborated by [meta-sam TS parser README](https://github.com/meta-models/meta-sam/blob/HEAD/typescript/packages/parser/README.md), [protocol/sam3.md](https://github.com/meta-models/meta-sam/blob/HEAD/protocol/sam3.md) — rechecked 2026-10-28; see matrix Phase 3C note for source tiers |
| `~` = documented default lossless encoding, `!` = documented one-bit encoding; payloads are Base85, not Base64 | VERIFIED (parser-repo sources) | Same parser-repo sources as above; decoding correctness itself remains UNVERIFIED (no decoder implemented or tested) |
| Offline text-shape parser exists; payloads stay opaque and never reach `synthetic-grid-v1`/IoU-Dice; errors never echo untrusted output | VERIFIED | `src/mydrak/sam/response_text.py`, `tests/test_sam_response_text.py` (74 tests; `tests/test_sam_output.py` has 71); no network/token imports in the module |

## 3. Unverified assumptions and blockers

| Item | Status | Reason |
|---|---|---|
| SAM-specific still-image formats, dimensions, payload limits, output ceilings | UNVERIFIED | Generic file-handling limits are not SAM-specific (matrix) |
| Exact wire schema: primary-source machine schema, mask-decoding correctness, live-sample conformance | UNVERIFIED | Record-level text shape corroborated via official parser-repo sources (matrix Phase 3B note), but no primary-source machine schema, no decoder, and no live sample exist |
| Credit amount, model eligibility, allocation, expiry for this account | UNVERIFIED | Event page + pricing give no per-account entitlement |
| Account billing state, payment settings, spend exposure | UNVERIFIED | No account inspection performed |
| Per-request Standard routing + ZDR for this account/model | UNVERIFIED | ZDR needs qualified enablement; varies by model |
| User authorization + privacy-notice product flow | UNVERIFIED | Product has neither; env flags are not consent |
| Full Official Rules (eligibility, allowed integrations, deliverables) | UNVERIFIED | Rules document not accessible at review |
| Freshness of every link above | UNVERIFIED | No fresh fetch in this assessment; recheck required |
| Wire compatibility of the local parser | NOT APPLICABLE yet | No wire sample exists; compatibility unproven by design |

## 4. Parser and adapter compatibility analysis

Inspected `src/mydrak/sam/output.py` (frozen `SamSegmentation`/`SamObject`/
`SamMask`; strict keys; pixel boxes; opaque mask strings; zero-match valid)
and `src/mydrak/workflow/offline.py` (fixture parsed independently of the
image file; provenance labels `validated_local_metadata` vs
`supplied_fixture`).

- From the synthetic grammar: exact key names (`image`/`objects`/`id`/`box`/
  `mask`/`encoding`/`data`), JSON mapping shape, optional-`score` semantics,
  and the opaque-string treatment of payloads.
- From official docs: record kinds (object ID, box, mask per line/frame),
  pixel coordinate system, zero mask origin, strictly-smaller mask dims,
  both-or-neither confidence, zero-match validity for empty output.
- Still unknown, so a provider adapter is REQUIRED: Base85 mask decoding
  (encoding markers `~`/`!` verified as labels; decoding itself unverified —
  never RLE/base64-guessed), transport framing, per-frame splitting,
  coordinate normalization confirmation, and error taxonomy for
  non-conforming output. The adapter mapping itself must be verified
  against documentation or an authorized sample. The Phase 3B text parser
  covers record tokenization and shape validation only; the synthetic
  workflow makes no conformance claim (its docstrings forbid reading it as
  SAM-processed).
- No unsupported claims found in the workflow: findings are provenance-labeled
  and the mock/intake path never presents fixture data as model output.

## 5. Privacy and credit risks

- Private farmer photos sent anywhere before authorization/notice/route
  verification would violate project policy and Meta Contributor restrictions;
  Standard mode still permits defined retention, so "no training" must never
  be described as zero retention or time-bounded deletion.
- Any live request spends real money against an unverified credit entitlement.
  **Account payment-method status: UNVERIFIED.** Earlier notes record a
  user-reported payment-method observation, but the current account state has
  not been independently verified. Do not assume that a payment instrument is
  present or that the granted credits will cover a request. Spend-limit alerts
  are notifications, not hard caps (credit-protection report).
- Required safeguards before a future live request: explicit per-request user
  authorization plus an established privacy notice disclosing external
  processing; verified Standard/non-contributor route for the actual request;
  confirmed rights and provenance; minimum-necessary transmission (resized
  single image, no extras); bounded retries (≤2) with single escalation and
  defined fallbacks per spec B11; explicit timeout/empty/malformed/unavailable
  behaviors ending in retake, follow-up, or expert referral — never a guess;
  credentials in environment only, never in logs, traces, or remote URLs;
  a pre-approved fixed request budget with dashboard recheck before/after.
- The existing gate (`require_external_processing_allowed`) already encodes
  the route/rights/authorization/notice checks but is not wired to any sender;
  wiring it is future implementation work, not a configuration change.

## 6. Offline tests required before live integration

- Adapter contract tests on synthetic wire-like samples (only after the wire
  format is verified): record→internal mapping, per-frame splitting, encoding
  translation, and rejection of non-conforming records.
- Malformed-response tests: truncated output, empty output, wrong types,
  unknown keys, oversized payloads — all fail closed into retake/ask/refer.
- Transport-boundary tests behind a mockable sender: timeouts, HTTP errors,
  rate-limit responses, and service-unavailable paths, each asserting bounded
  retries and safe fallback without leaking credentials or image bytes.
- Privacy tests: blocked-by-default private data, Contributor-route refusal,
  and trace/log scans proving no bytes, tokens, or personal data persist.
- Cost tests: token/frame accounting from the pricing basis with a fixed
  request budget enforced before any live call.

## 7. Proposed minimal implementation sequence

1. Close verification gaps: Official Rules, credit entitlement/expiry,
   SAM-specific media/payload limits, exact wire schema/encoding sample.
2. Build the provider adapter plus offline contract and malformed-response
   tests; no network.
3. Wire the privacy gate to the sender boundary; add the authorization and
   privacy-notice product flow; add cost controls and failure-injection tests.
4. Run one explicitly approved smoke test on public synthetic imagery in
   Standard mode within a fixed micro-budget, with pre/post dashboard checks.
5. Only then consider real farmer imagery, still gated per request.

## 8. Go/no-go recommendation

**NO-GO for live SAM integration.** Reasons: (a) no verified mask decoding,
transport framing, or live-sample-validated adapter exists — text-shape
parsing alone cannot consume a live response; (b) no credit
entitlement, billing review, or spending cap is established; (c) the product
has no authorization or privacy-notice flow, so private images remain blocked
by standing policy; (d) SAM-specific limits and account/model ZDR status are
unknown. Proceeding now would require guessing the wire format, assuming
payment coverage, and moving private data without consent evidence — all
explicitly forbidden by repository rules. Revisit only after sequence steps
1–3 are complete with fresh official references.
