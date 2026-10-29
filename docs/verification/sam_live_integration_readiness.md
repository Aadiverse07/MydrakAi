# SAM 3.1 live-integration readiness assessment

**Initial assessment:** 2026-10-27. **Phase 4B review:** 2026-10-28.
**Scope:** documentation, compatibility, privacy, and cost assessment ONLY.
No API calls, uploads, credentials, or live tests were made. The offline
Phase 3 parser is implemented; SAM 3.1 client integration, mask decoding, and
production processing remain **NOT IMPLEMENTED**.

**Evidence basis:** the in-repo verified reports in `docs/verification/`
(recorded 2026-10-27 from official Meta pages) and the inspected source in
`src/mydrak/sam/output.py`, `src/mydrak/workflow/offline.py`,
`src/mydrak/privacy/data_policy.py`, and `src/mydrak/vision/source.py`.
The original assessment used in-repo reports recorded 2026-10-27. Phase 4B
rechecked the linked official SAM, billing, terms, and ZDR pages on 2026-10-28.
Recheck before any future live step.

## 1. Executive summary

Live SAM 3.1 integration is **not ready and not authorized**. The official
interface shape (model ID, endpoint, request parts, output record kinds,
pricing basis, Standard data terms) is verified and recorded, but every
item required to send a real image safely remains unverified: SAM-specific
media/payload limits, local decoder integration/correctness, credit
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
| Model ID `sam-3.1` | VERIFIED | [Models](https://dev.meta.ai/docs/models), matrix SAM row. Discrepancy with `sam-3-1` on the product/pricing page remains explicitly UNRESOLVED (matrix Phase 3B note); the ID is enforced only as an offline request-format gate and authorizes no live use, eligibility, billing, or compatibility (see BLOCKED rows below) |
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
| `~` = documented default lossless encoding, `!` = documented one-bit encoding; payloads are Base85, not Base64 | VERIFIED (official output grammar, rechecked 2026-10-28) | [Output grammar](https://dev.meta.ai/docs/sam/reading-segmentation); exact alphabet/variant and local decoder correctness remain UNVERIFIED |
| Offline text-shape parser exists; payloads stay opaque and never reach `synthetic-grid-v1`/IoU-Dice; errors never echo untrusted output | VERIFIED | `src/mydrak/sam/response_text.py`, `tests/test_sam_response_text.py` (Phase 3: 74 tests; Phase 4B adds 1); `tests/test_sam_output.py` has 71; no network/token imports in the module |

## 3. Unverified assumptions and blockers

| Item | Status | Reason |
|---|---|---|
| SAM-specific still-image formats, dimensions, payload limits, output ceilings | UNVERIFIED | Generic file-handling limits are not SAM-specific (matrix) |
| Exact wire integration: Responses envelope/SSE handling, Base85 variant, decoder behavior in this repository, and live-sample conformance | UNVERIFIED | Primary docs now specify record-level text grammar and official parser/decoder interfaces; this repository has no stream assembler, decoder, or live sample. Offline evidence added: conservative envelope parser, caller-side adapter, and review/decision chain exist with synthetic-fixture tests (`sam/envelope.py`, `sam/frames.py`, `sam/chain.py`); wire schema and live conformance stay UNVERIFIED |
| Credit amount, model eligibility, allocation, expiry for this account | UNVERIFIED | Event page + pricing give no per-account entitlement |
| Account billing state, payment settings, spend exposure | UNVERIFIED | No account inspection performed |
| Per-request Standard routing + ZDR for this account/model | UNVERIFIED | ZDR needs qualified enablement; varies by model |
| User authorization + privacy-notice product flow | UNVERIFIED | Product has neither; env flags are not consent |
| Full Official Rules (eligibility, allowed integrations, deliverables) | UNVERIFIED | Rules document not accessible at review |
| Freshness of every link above | UNVERIFIED | Original assessment had no fresh fetch; Phase 4B rechecked the linked official SAM, billing, terms, and ZDR pages on 2026-10-28 (§9); links change over time, so recheck again before any live step |
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
- A provider integration remains REQUIRED: use of Meta's documented parser
  and decoder library is a candidate, not an implemented dependency or a
  verified result here. Base85 variant/decoder behavior, SSE completion and
  error framing, per-frame handling, and any mapping into internal structures
  still need offline contract evidence. The Phase 3B text parser covers record
  tokenization and shape validation only; the synthetic workflow makes no
  conformance claim (its docstrings forbid reading it as SAM-processed).
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

1. Close verification gaps: applicable Official Rules, credit entitlement/
   expiry, SAM-specific still-image limits, and account billing/privacy gates.
2. Add offline contract cases against the documented grammar and evaluate
   Meta's official parser/decoder interface without installing or guessing an
   encoding. Keep unknown alphabet/variant details UNVERIFIED.
3. Wire the privacy gate to the sender boundary; add the authorization and
   privacy-notice product flow; add cost controls and failure-injection tests.
4. Only after every gate and separate authorization, run one approved request
   on rights-cleared, non-personal test imagery, with retries disabled and
   pre/post billing checks. A fixed micro-budget cannot be guaranteed by a
   spend alert, because it is not a hard cap.
5. Only then consider real farmer imagery, still gated per request.

## 8. Go/no-go recommendation

**NO-GO for live SAM integration.** Reasons: (a) no local decoder or
transport/stream integration has been implemented and verified — text-shape
parsing alone cannot consume a live response; (b) no credit
entitlement, billing review, or spending cap is established; (c) the product
has no authorization or privacy-notice flow, so private images remain blocked
by standing policy; (d) SAM-specific limits and account/model ZDR status are
unknown. Proceeding now would require guessing the wire format, assuming
payment coverage, and moving private data without consent evidence — all
explicitly forbidden by repository rules. Revisit only after sequence steps
1–3 are complete with fresh official references.

## 9. Phase 4B official parser/decoder review (2026-10-28)

### Officially documented

- The API guide specifies model ID `sam-3.1`, `POST https://api.meta.ai/v1/responses`, a Bearer key, and a user message with `input_text` plus an `input_image` or `input_video`. For images, the SAM guide shows a public URL or base64 data URL. Streaming is recommended, but non-streaming is documented. [SAM overview](https://dev.meta.ai/docs/sam/overview), [segmenting with prompts](https://dev.meta.ai/docs/sam/segmenting)
- Output uses `output_text`, one line per emitted frame, with a frame marker and comma-separated object-id/box/mask records. For a single image, the frame marker is `<0f>`. Box dimensions and coordinates are source pixels. Masks use `x=0;y=0`, `data=<H>,<W>,<encoding><payload>`, and `H` then `W` are smaller than the source frame. Confidence is omitted unless requested; when requested, each box and mask carry the same 0..1 value. [Output grammar](https://dev.meta.ai/docs/sam/reading-segmentation)
- The payload is documented as Base85-encoded bytes, not Base64. The docs identify `~` as lossless and `!` as one_bit and say payload bytes may contain these and other printable characters. The docs do **not** specify a complete Base85 alphabet/variant, padding rules, comma/terminator escaping, or decoding pseudocode. [Output grammar](https://dev.meta.ai/docs/sam/reading-segmentation)
- Meta documents parser libraries and decoder functions: `decode_mask_to_raster`, `decode_mask_to_rle`, and `decode_mask_to_svg_path` in Python. The documented raster is row-major, length `H * W`, with 0/1 values; RLE is COCO-compatible with `[height, width]` size. This documents an official implementation interface, not that this repository has the package, a decoder, or verified decoded results. [Client libraries](https://dev.meta.ai/docs/sam/client-libraries), [output grammar](https://dev.meta.ai/docs/sam/reading-segmentation)
- The SAM guide provides video limits and object constraints but no SAM-specific still-image size/dimension or mask-payload ceiling. Generic file docs list file types and 50 MB inline / 1 GiB Files API limits; those are not established here as SAM-specific guarantees. [SAM limits](https://dev.meta.ai/docs/sam/segmenting), [generic file handling](https://dev.meta.ai/docs/file-handling)
- Published SAM pricing is $2.50/1,000 images and $0.20/1,000 video frames, with a 50-frame minimum for video; SAM is listed at 3,000 requests/minute per team. These facts do not establish this account's credits, expiry, eligibility, payment configuration, or maximum possible bill. Meta says spend-limit alerts are not hard caps. [Pricing and rate limits](https://dev.meta.ai/docs/pricing-rate-limits), [spend-limit alert](https://dev.meta.ai/help/billing/spend-limit-alert)
- Standard requests are not used to train Meta models, but terms allow content retention for service, legal, rights, safety/security, abuse, and policy purposes. ZDR requires separate organization enablement, is eligibility/model dependent, and has feature restrictions. Contributor services may use content for model improvement and prohibit personal information. [Terms](https://dev.meta.ai/legal/terms-of-service) §§4.4, 5.1, 6.1–6.2; [ZDR help](https://dev.meta.ai/help/policies-and-privacy/zero-data-retention)

### Local behavior and compatibility boundary

- `src/mydrak/sam/response_text.py` is a handwritten offline shape parser for one `<0f>` line. It does not assemble SSE events, implement a request, decode payloads, or establish live compatibility. Its tests use synthetic fixtures only. `src/mydrak/sam/output.py` validates a separate project-local mapping fixture and is not a wire parser.
- Local caps such as `SamLimits.max_mask_chars`, maximum object count, dimension cap, and whole-output cap are defensive project limits, not Meta service limits. The text parser also rejects commas in payloads and accepts a printable ASCII subset; that is a local parsing boundary. The service's exact Base85 alphabet and whether these constraints cover every valid Meta payload are **UNVERIFIED**.
- The marketing page lists `sam-3-1`, while current API docs use `sam-3.1`; retain the discrepancy as **UNVERIFIED** and do not configure from the marketing label. The offline request boundary enforces the documented `sam-3.1` as a request-format gate only, which establishes no eligibility, billing, compatibility, or live success. [SAM product page](https://dev.meta.ai/models/sam-3-1), [Models](https://dev.meta.ai/docs/models)
- The synthetic tests check that documented printable marker characters survive as opaque text and that a local payload cap accepts exactly its configured boundary. They do not validate Base85 encoding, decoding, API output, or masks.

## 10. Evidence checklist before any live call

Every item below is a gate. No API call is authorized by this checklist.

| Required evidence | Status | Evidence needed |
|---|---|---|
| Access to API model `sam-3.1` | **BLOCKED** | Account/team evidence of model access and resolved API model identifier; no credential test in this review |
| Applicable hackathon Official Rules and participant eligibility | **BLOCKED** | Obtain and review the complete rules/waiver and participant acceptance evidence; the accessible event page still says rules will be published before the Oct. 26 kickoff |
| Credit balance, eligible models/modes, and expiry | **BLOCKED** | Current account billing evidence; published prices do not prove credits cover a call |
| Payment method, payment threshold, and acceptance of card-charge exposure | **BLOCKED** | User-reviewed billing state and explicit acceptance of possible charges |
| One-request operational guard and disabled retries | **BLOCKED** | Reviewed caller-level one-call guard; smoke path must have retries disabled and stop after any response/error |
| Test-image rights, provenance, and approval | **BLOCKED** | A non-personal, rights-cleared image with documented provenance and explicit approval |
| Privacy notice, user authorization, Standard routing, and retention/ZDR | **BLOCKED** | Product notice and per-request authorization; evidence the actual request uses Standard/non-contributor mode; account/model retention decision and ZDR evidence where required |
| SAM-specific image constraints | **BLOCKED** | Official confirmation of still-image formats, dimensions, and payload limits applicable to the request |
| Parser/decoder compatibility | **BLOCKED** | Offline contract evidence against Meta's parser/decoder on synthetic documentation-derived cases, followed by an explicitly authorized sample before claiming live compatibility |
| Explicit authorization for live testing | **BLOCKED** | Separate direct user authorization after all preceding gates are supported |

**Spending limit warning:** Meta's spend-limit alert is not a hard cap. A one-request guard and disabled retries reduce operational exposure but cannot guarantee zero billing or a fixed maximum charge. Published per-image pricing is not proof of credit coverage or that card billing is impossible.

### Proposed one-request smoke plan (not authorized or executed)

After all gates and separate user authorization: issue exactly one non-streaming `sam-3.1` Responses request with one short concept prompt and one approved, non-personal image via inline data URL; do not use Files API upload, video, contributor routing, or background mode. Disable retries. Record only response status, request ID, usage/billing metadata, and a sanitized parse result. Compare the output with Meta's parser/decoder before accepting it. Stop on any error, unexpected format, billing event, or parser/decoder mismatch; do not retry or send another image. A successful single request would not establish broad live compatibility or crop-diagnosis quality.

**Phase 4B conclusion: NO-GO for live calls.** Offline preparation may continue with synthetic fixtures only. Reassess each blocked item using current evidence and obtain explicit live-test authorization only after all applicable gates are complete.
