# Daily log

## 2026-10-27 — Phase 0: repository foundation

- What changed: created minimum scaffold (AGENTS.md, README.md, pyproject.toml,
  .gitignore, .env.example, config/*.yaml with UNVERIFIED placeholders,
  src/mydrak package with pure foundation modules, kb/cards/general_safety.yaml,
  tests/, eval/ + dashboard/ + scripts/ placeholders, docs/architecture.md).
- What is broken: nothing executable yet beyond foundation functions; all
  integrations UNVERIFIED (no smoke tests run — forbidden in Phase 0).
- What is next: single next task per spec is T02 (smoke scripts per Meta
  endpoint) — requires user approval + API keys; do NOT start in Phase 0.

## 2026-10-27 — Phase 0.1: security and official verification

- What changed: hardened `.gitignore`; changed `.env.example` DATA_POLICY default from `public_test` to fail-closed `private`; added a regression test; added official Meta API, hackathon rules, credit protection, and Phase 0 review reports under `docs/verification/`; recorded this session in `docs/muse-code-log/`.
- What is broken/unverified: full hackathon Official Rules document was not available from official pages; credit allocation/expiry and account eligibility remain unknown; exact ₹1,000 billing setting is account-specific and unverified; max payload/output constraints and Hindi-specific voice support need confirmation. No integrations exist.
- What is next: obtain/read the complete Official Rules and confirm the dashboard credit/threshold labels manually; implement a fail-closed policy gate and structured card validation before any integration. Do not run a live API test until separately approved.

## 2026-10-27 — Phase 0.2: verified Git integration policy

- What changed: documented Muse Code implementation/Codex verification gates in `AGENTS.md`; added `docs/verification/git_workflow.md`; reconciled the local foundation root and GitHub's independent LICENSE root on `integration/git-workflow`, preserving both commits; published the verified branch and fast-forwarded GitHub `main` to the verified result.
- What is broken/unverified: no Git workflow blockers remain after the verified push. Meta API and hackathon verification blockers from Phase 0.1 remain unchanged; no live integration is authorized.
- What is next: continue with the remaining official rules/credit verification and fail-closed data-policy work before planning any live API test.

## 2026-10-27 — Phase 0.3: verification blockers and fail-closed data policy

- What changed: rechecked official Meta terms, Contributor restrictions, speech-to-text documentation, and the event page; verified Hindi listing for Voice Transcribe and documented Standard/Contributor data handling. Added a pure, no-network policy gate for private/public-test classifications with explicit route, rights, provenance, authorization, and notice checks. Added unit tests and updated the existing verification reports and Phase 0 review.
- What is broken/unverified: no outbound client exists or is wired to the gate. Full hackathon Official Rules, participant credit eligibility/expiry, account-specific billing/ZDR status, and Telegram OGG support/media limits remain unresolved. The product has no privacy notice or user authorization flow, so private processing remains blocked in practice.
- Checks: recorded in `docs/muse-code-log/phase-0.3-verification-and-data-policy.md` after the local verification run. No Meta API calls, uploads, credentials, billing changes, or credit usage.
- What is next: review the full official rules and credit terms when available; build any future sender only with a pre-transmission gate and verified route, legal rights, and user-facing privacy disclosures. No live API testing until blockers and product readiness are resolved.

## 2026-10-27 — Phase 1: mock-only intake with privacy gate

- What changed: added `src/mydrak/intake/adapter.py` (validate -> privacy gate -> deterministic mock diagnosis -> privacy-safe trace; optional `sender` hook invoked at most once, only when the gate allows, metadata only) and `tests/test_mock_intake.py` (valid/invalid/oversized input, determinism, missing/invalid policy, private-without-authorization, unverified route, Contributor-with-private, provenance, blocked-means-zero-sender-calls, trace/byte safety, no-network guard). Verified the Phase 0.3 gate is still unwired to any sender (no network imports anywhere in `src/`); `.env` stays ignored and untracked; `.env` names are not auto-loaded (no dotenv dependency).
- Checks: full suite **72 passed, 0 failed**; `compileall` clean; config parse OK; secret-pattern scan clean; `git diff --cached --check` clean. No live API calls, uploads, auth tests, or credit usage.
- What is broken/unverified: Telegram intake, model/SAM clients, production senders, trace store, and dashboard remain NOT implemented. Official Rules, credit entitlement, ZDR, and media-limit blockers from Phase 0.3 are unchanged.
- What is next: commit/push of this batch per the git workflow; then continue verification blockers before any live integration.

## 2026-10-27 — Independent review of Phase 1 mock intake

- What changed: independently reviewed the published Phase 1 commit and found trace/input-boundary defects: caller-controlled `source` entered traces, descriptor mappings accepted extra fields, unsupported-format errors echoed untrusted input, and malformed classification could raise `AttributeError`. Applied a local, uncommitted remediation in the intake adapter with regression tests; added exact-limit tests for the local dimensions/size bounds.
- What is broken/unverified: the `sender` remains an arbitrary injected callback; repository code provides no production sender, network transport, Telegram SDK, or model SDK. Do not connect an external sender without the verified timeout/retry/fallback and privacy controls.
- Checks: full suite **79 passed, 0 failed**; `compileall`, TOML/config YAML parsing, `.env` ignore/untracked checks, changed-file secret-pattern scan, AST import scan, and diff whitespace check all passed. `.env` exists but was not read.
- Git ancestry: Phase 1 descends from Phase 0.3 and `main`; the merge ancestry preserves the original foundation and LICENSE root commits. The initial review ended with local remediation uncommitted; its later commit/push status is recorded in the follow-up handoff.
- What is next: open a PR from the verified Phase 1 integration branch to `main` and follow required review/protection rules. Do not begin another feature phase or any live API work.

## 2026-10-27 — Phase 2 planning authorization and SAM verification

- What changed: documentation-only update to `AGENTS.md`, `docs/architecture.md`, the official verification matrix, and credit-protection report. Phase 2 planning and offline/mock parser work with synthetic fixtures only are authorized. SAM 3.1 is explicitly **NOT IMPLEMENTED**. Recorded the documented Responses API interface, prompt/input and output shape, listed video formats, and published pricing/rate limit with official Meta links. Generic file limits are clearly distinguished from SAM-specific guarantees. Added `docs/muse-code-log/phase-2-planning-readiness.md`.
- What remains broken/unverified: SAM-specific still-image formats/dimensions/payload limits, event credit eligibility/amount/expiry for this account, and account-/SAM-specific retention/ZDR remain **UNVERIFIED**. No outbound client or production parser exists; the privacy gate is not wired to an outbound sender. Private farmer data remains blocked from external processing absent verified route, rights, user authorization, privacy notice, and separately authorized processing.
- Checks: `python3 -m pytest` **79 passed**; `python3 -m compileall -q src tests`, TOML/YAML configuration parsing, `.env` ignore/untracked checks, safe changed-document secret-pattern scan, and `git diff --check` **passed**. `.env` contents were not read or printed. See `docs/muse-code-log/phase-2-planning-readiness.md`. No API calls, media uploads, credential tests, billing changes, or credits used.
- What is next: review this documentation diff. Do not implement SAM or make external requests; proceed only with offline/mock parser work using synthetic fixtures under a separate scoped task.

## 2026-10-27 — Phase 2, Task 1: offline SAM output parser

- What changed: added `src/mydrak/sam/output.py` (offline-only validator mapping a synthetic fixture grammar onto frozen `SamSegmentation` dataclasses: object IDs, source-pixel boxes, mask dims, opaque mask payload, optional score, zero-match support; strict fail-closed validation, no mask decoding, no untrusted echo) and `tests/test_sam_output.py` (65 synthetic-fixture tests). Recorded this session in `docs/muse-code-log/phase-2-task-1-sam-parser.md`. Left uncommitted per task instructions.
- Checks: new file 65 passed; full suite **144 passed, 0 failed**; `compileall`, config parse, secret-pattern scan, `git diff --check` all clean. No network, SDK, upload, credential, billing, or credit activity.
- Limitations: fixture grammar is project-local, not Meta wire text; mask encoding specifics, SAM-specific image/payload limits, credit eligibility, and ZDR remain UNVERIFIED; no SAM client exists and none is authorized.
- What is next: independent review of the uncommitted batch; wire-text mapping and mask decoding stay out of scope until separately authorized with verified documentation.

## 2026-10-27 — Phase 2, Task 1 fix pass (Codex defects)

- What changed: in `src/mydrak/sam/output.py`, explicit `"score": None` is now rejected (omitted score still yields `None`); all int→float conversions go through `_safe_float`, and `_is_number` no longer converts ints, so huge integers normalize to `SamOutputError` instead of leaking `OverflowError`. Added 6 regression tests in `tests/test_sam_output.py`. Updated the Task 1 session log. Still uncommitted per instructions; planning docs untouched.
- Checks: full suite **150 passed, 0 failed**; `compileall`, config parse, secret-pattern scan, `.env` ignore/untracked, `git diff --check` all clean. No API, upload, credential, billing, credit, commit, push, or merge activity.

## 2026-10-27 — Phase 2, Task 2: offline local image-header reader

- What changed: added `src/mydrak/vision/source.py` (`read_local_image`: size pre-check, PNG signature + first-chunk IHDR length-13 dimension parse with no CRC validation, SOI-anchored JPEG marker walk with structural SOF rule length == 8 + 3*Nf, precision 8/12, Nf 1-4; header-only scope documented) and `tests/test_vision_source.py` (synthetic byte fixtures in tmp_path; malformed/size/dimension rejections; SOF-structure, SOS/EOI-before-SOF, orphan-SOF cases; payload-garbage-passes control; descriptor → gate blocked-by-default-private and allowed-with-documented-synthetic-evidence integration tests). Recorded in `docs/muse-code-log/phase-2-task-2-local-reader.md`.
- Checks: full suite **171 passed, 0 failed** (150 prior + 21 new); `compileall`, `git diff --check`, secret-pattern scan clean. One segment-advance bug found by the suite and fixed before green. No network, API, upload, credential, billing, credit, or Git activity.
- Fix pass (Codex findings): nested-SOI rejection, OSError normalization to generic IntakeError without path/OS text, and single-open bounded read (MAX_IMAGE_BYTES + 1) independent of the stat pre-check; added nested-SOI, stat/read-failure, and bounded-read regression tests. Full suite **175 passed, 0 failed**; `compileall`, `git diff --check`, secret scan clean.
- Refinement pass: nested-SOI fixture now provably discriminating (verified it fails with the check temporarily removed, then restored); OSError chains use `from None` with traceback-leak assertions on message, path, and OS text; bounded-read test instruments the handle to assert exactly one open and a read of exactly MAX_IMAGE_BYTES + 1. Full suite **175 passed, 0 failed**; `compileall`, `git diff --check`, secret scan clean.

## 2026-10-27 — Phase 2, Task 3: offline image workflow integration

- What changed: added `src/mydrak/workflow/offline.py` (`run_offline_image_workflow`: real-file header read via existing reader, controlled-fixture parse via existing SAM parser, frozen `OfflineResult` with `validated_local_metadata` vs `supplied_fixture` provenance labels, per-stage timings; no network, model, sender, or new dependency) and `tests/test_offline_workflow.py` (14 synthetic-fixture tests: success, zero-match, frame independence, format/malformed/missing/unreadable/oversize/dimension failures without path leaks, malformed/oversized segmentation, existing-limit regressions, no-network guard). Recorded in `docs/muse-code-log/phase-2-task-3-offline-workflow.md`.
- Checks: new file 14 passed first run; full suite **189 passed, 0 failed**; `compileall`, `git diff --check`, secret scan clean. No network, API, uploads, credentials, credits, or Git activity. Not a diagnosis; fixtures are synthetic, not real SAM output.

## 2026-10-27 — Phase 2, Task 4: real crop-image readiness (blocker documented)

- What changed: searched the full repo tree for genuine crop-image samples; the only image file is the `docs/MydrakDeep.png` infographic poster (viewed in Phase 0 — not a crop photograph, explicitly disqualified as a sample). No code or test changes; suite not re-run (recorded 189 passed). Recorded in `docs/muse-code-log/phase-2-task-4-readiness.md`.
- Outcome: condition 2 — no authorized genuine crop-image file available; no real-data validation claimed, none fabricated. Needed from user: one genuine crop/leaf photo (JPEG/PNG) as an explicit local path with read permission. No network, API, uploads, credentials, credits, staging, or commits.

## 2026-10-27 — Phase 2, Task 5: SAM live-integration readiness (assessment only)

- What changed: added `docs/verification/sam_live_integration_readiness.md` (8-section assessment: verified facts with official references, unverified blockers, parser/adapter compatibility boundary, privacy and credit risks, required offline tests, implementation sequence, NO-GO recommendation). Recorded in `docs/muse-code-log/phase-2-task-5-readiness.md`.
- Outcome: NO-GO for live SAM integration — no verified wire schema/encoding, no credit entitlement or billing review, no authorization/notice flow, unknown SAM limits and ZDR status. No fresh official pages fetched; assessment rests on the 2026-10-27 in-repo verification. No code changes; no API, uploads, credentials, credits, staging, or commits.

## 2026-10-28 — Phase 2, Task 6: real crop-image validation

- What changed: ran the existing `read_local_image` on 10 user-supplied files in `eval/data/dev/` (offline, read-only, metadata only). Result: 6 accepted as genuine JPEG with parsed dimensions (Crop_1 1158x1700, Crop_3 3071x1999, crop_04 400x533, crop_07 346x280 as JPEG despite .png name, crop_09 440x454, crop_10 1024x683); 4 rejected as unsupported format — root cause verified by magic bytes as valid WebP (RIFF/VP8) files misnamed .jpg/.png, correctly rejected per the PNG/JPEG-only contract, not corrupt. Recorded in `docs/muse-code-log/phase-2-task-6-real-images.md`.
- Outcome: real-file header validation ESTABLISHED for 6 JPEGs; WebP support is out of scope (needs SAM-format verification first — reported, not implemented). This proves header inspection only, not decoding, segmentation, or diagnosis. Photos stay local and out of Git. No code changes; no API, uploads, credentials, credits, staging, or commits.

## 2026-10-28 — Phase 2, Task 7: reproducible image-evaluation pipeline

- What changed: added `eval/image_report.py` (stdlib-only CLI: sorted discovery, existing reader as verdict source, per-file format/dims/size/status/reason, totals, deterministic sorted-keys JSON to `eval/results/dev_image_headers.json`, missing-dir exit 2, no timestamps/absolute paths/contents) and `tests/test_image_eval.py` (5 portable tests via importlib loading: ordering, totals, rejections, missing/empty dirs, byte-identical reruns, no-path/no-content assertions). Generated the real report: inspected=10 accepted=6 rejected=4 unsupported=4, matching Task 6; rerun byte-identical. Recorded in `docs/muse-code-log/phase-2-task-7-eval-pipeline.md`.
- Checks: new file 5 passed (one fixture format-string bug found and fixed); full suite **194 passed, 0 failed**; `compileall`, `git diff --check`, secret scan clean. Photos and report verified gitignored. No code-reader changes, deps, network, API, uploads, credentials, credits, staging, or commits. Header validation proves nothing about decoding, SAM segmentation, or diagnosis.

## 2026-10-28 — Phase 2, Task 8: mock-first segmentation evaluation

- What changed: added `src/mydrak/sam/scores.py` (explicit synthetic `BinaryMask` grids; IoU/Dice with documented empty-mask conventions; strict validation, shape-mismatch rejection without silent resize; `evaluate_case` valid/skipped records, `mark_invalid`, deterministic `summarize` with valid-only aggregates, null when none valid) and `tests/test_sam_scores.py` (20 synthetic tests: perfect/partial/no-overlap with hand-computed values, empty conventions, invalid values, shape mismatch, missing sides, bad ids, aggregates, determinism). Recorded in `docs/muse-code-log/phase-2-task-8-seg-eval.md`.
- Checks: new file 20 passed first run; full suite **214 passed, 0 failed**; `compileall`, `git diff --check`, secret scan clean. Opaque SAM-parser payloads cannot feed this contract — boundary documented; a decoding adapter is future work. No network, API, uploads, credentials, credits, deps, staging, or commits. Mechanism only; not SAM accuracy, diagnosis, or treatment evidence.

## 2026-10-28 — Phase 2, Task 9: adapter contract check (STOPPED per §2)

- What changed: no code, tests, or config changes. Inspected `SamMask` vs `BinaryMask` and found the contract insufficient for any truthful adapter (details in `docs/muse-code-log/phase-2-task-9-adapter-blocker.md`). Recorded the precise incompatibility and the smallest clarification proposal instead of guessing a decoder.
- Checks: `git diff --check` clean; worktree otherwise untouched. No network, API, uploads, credentials, credits, deps, staging, or commits.

## 2026-10-28 — Phase 2, Task 10: synthetic-grid-v1 adapter

- What changed: added `src/mydrak/sam/adapter.py` (`GRID_ENCODING = "synthetic-grid-v1"`; `grid_mask_to_binary` converts only that exact encoding — newline-separated 0/1 rows, count == height, width-exact rows, trailing newline rejected, dims rechecked, size pre-bounded by existing `max_mask_chars`; all other encodings rejected, never decoded; no merging, no box rasterization) and `tests/test_sam_grid.py` (initial 28 tests covering valid/all-zero/all-one grids, malformed rows, encodings, dimensions, size, orientation, scoring acceptance, non-merge, and error-value secrecy). Recorded in `docs/muse-code-log/phase-2-task-10-grid-adapter.md`.
- Codex-confirmed fix pass: adapter now enforces `SamLimits.max_dimension` for width and height and rejects non-string data with a controlled `SegmentationEvalError` before string operations; added over-cap width/height and bytes/int/None payload regressions. No coercion, decoding, or grammar changes.
- Checks after fix: `python3 -m pytest tests/test_sam_grid.py` **33 passed**; parser/scoring tests **91 passed**; full suite **247 passed, 0 failed**; compileall and `git diff --check` passed. Synthetic fixture contract only — not SAM wire decoding, accuracy, or diagnosis. No network, API, uploads, credentials, credits, deps, staging, or commits.

## 2026-10-28 — Phase 2, Task 11: integration validation and review

- What changed: inspected full state, ran the battery (focused 221, full suite **247 passed, 0 failed**, compileall, diff --check, eval CLI 10/6/4/4 with byte-identical rerun), and wrote `docs/verification/phase_2_integration_review.md`. Finding: the Codex fix-pass files are self-documented in the Task 10 log entry — reviewed and benign. Verdict: READY TO CLOSE (OFFLINE SCOPE ONLY).
- Checks observed; no network/API activity, uploads, credentials, credit use, staging, commits, or Git mutations occurred during the review.


## 2026-10-28 — Phase 2, Task 11 review corrections

- What changed: `eval/image_report.py` now serializes absolute input directories as `absolute-input` and reports missing directories without echoing their paths; exit code 2 is preserved. Added an absolute temporary-directory regression test. Updated the Task 11 review with the exact 221-test focused command, the automated/manual image-validation distinction, and historical worktree-snapshot wording.
- Checks: focused command **222 passed** after adding the regression; full suite **248 passed, 0 failed**; compileall and `git diff --check` passed. Two reporter runs to temporary output paths produced `inspected=10 accepted=6 rejected=4 unsupported=4` and byte-identical JSON. The ignored default report and development images were preserved. No `.env` or credentials read; no API/network calls or Git mutations.

## 2026-10-28 — Phase 3B: offline SAM output-text parser

- What changed: added `src/mydrak/sam/response_text.py` (offline parser for the documented single-image `output_text` shape: `<0f>` frame, integer IDs, pixel boxes vs caller-supplied expected dims, `~`/`!` opaque Base85 payloads never decoded, box/mask confidence agreement, fail-closed `SamResponseError` without echoing untrusted output; no video/client/network/decoding) and `tests/test_sam_response_text.py` (53 synthetic documentation fixtures). Fixed two implementation defects found by the new tests (comma-split vs `data=H,W,…`; stale `body` passed to the mask `y` parser). `src/mydrak/sam/output.py` unchanged. Updated the SAM matrix (Phase 3B note with 2026-10-28 sources) and the readiness doc (two-parser distinction, NO-GO intact, model-ID discrepancy still unresolved). Recorded in `docs/muse-code-log/phase-3b-response-text-parser.md`.
- Checks: focused parser files **124 passed**; full suite **301 passed, 0 failed**; `compileall`, TOML/YAML parse, `git diff --check` clean; secret-pattern count scan clean (doc wording only, no values); `.env` ignored + untracked (metadata only). Pre-existing `docs/architecture.md` clarification preserved. No API calls, uploads, credentials, credits, deps, staging, or commits. Shape parsing only — not decoding, live compatibility, or diagnosis.

## 2026-10-28 — Phase 3C: Codex-confirmed parser fixes

- What changed (all in `src/mydrak/sam/response_text.py` + `tests/test_sam_response_text.py`; `output.py` and `docs/architecture.md` untouched): (A) ASCII-only `[0-9]` numerics, unsigned digit-capped object IDs, every untrusted `int()`/`float()` wrapped to `SamResponseError`, bool/non-int `max_chars` rejected; (B) mask origin fixed at `x=0;y=0`, mask dims strictly smaller than source, confidence both-absent or both-present-and-equal; (C) strict frame syntax — bare `<0f>`, trailing/leading separators rejected, only empty output is a zero-match (Phase 3B leading-comma tolerance withdrawn); (D) bounded boundary-regex record scan replacing `re.split`, stopping past the object limit. Tests grew 53 → 69. Matrix Phase 3C note + readiness corrections record source tiers (Codex-confirmed rules vs snippet corroboration vs local defenses); model-ID discrepancy, credits/billing, still-image limits, ZDR, live compat stay UNVERIFIED. Recorded in `docs/muse-code-log/phase-3b-response-text-parser.md` (Phase 3C section; Phase 3B text is historical).
- Checks: focused parser files **140 passed**; full suite **317 passed, 0 failed**; `compileall`, TOML/YAML parse, `git diff --check` clean; secret-pattern count scan clean; `.env` ignored + untracked (metadata only). No API calls, uploads, credentials, credits, deps, staging, or commits.

## 2026-10-28 — Phase 3D: residual parser fixes

- What changed: only `""` is now a zero-match (whitespace-only input rejected, no silent normalization); readiness doc reports current counts (73 response-text + 71 synthetic tests; task brief cited pre-fix 69); mask `data` parsing uses bounded `partition` delimiter scans instead of splitting comma-heavy payloads (grammar unchanged, Base85 variant still UNVERIFIED). `output.py` and `docs/architecture.md` untouched. Recorded in `docs/muse-code-log/phase-3b-response-text-parser.md` (Phase 3D section; earlier text historical).
- Checks: new file **73 passed**; synthetic file **71 passed**; full suite **321 passed, 0 failed**; `compileall`, TOML/YAML parse, `git diff --check` clean; secret-pattern count scan clean; `.env` ignored + untracked (metadata only). No API calls, uploads, credentials, credits, deps, staging, or commits.

## 2026-10-28 — Phase 3D.1: mask-payload limit regression test

- What changed: added `test_mask_payload_limit_enforced` (9-char valid payload accepted under default limits, rejected with `SamLimits(max_mask_chars=8)`; payload not echoed). No parser change needed. Readiness counts updated to 74/71. Recorded in `docs/muse-code-log/phase-3b-response-text-parser.md` (Phase 3D.1 section).
- Checks: new file **74 passed**; synthetic file **71 passed**; full suite **322 passed, 0 failed**; `compileall`, TOML/YAML parse, `git diff --check` clean; secret-pattern count scan clean; `.env` ignored + untracked (metadata only). No API calls, uploads, credentials, credits, deps, staging, or commits.
