# Daily log

## 2026-10-30 — T04 offline image preprocessing measurements (Codex)

- What changed: after the user confirmed Pillow imports, added bounded Pillow decoding for local PNG/JPEG inputs, EXIF transpose, an explicitly UNVERIFIED long-edge cap, project-local JPEG normalization, and a SHA-256 hash of normalized bytes. Added measurement-only Laplacian variance, mean grayscale brightness, and a clearly UNVERIFIED green-hue pixel proxy for leaf coverage. Measurements can be stored in a dedicated trace table and are not mapped to S3, quality scores, or routing. Retake routing remains disabled. Pillow is approved for T04 only.
- Limits: resize cap (2048), JPEG quality (85), and green-pixel proxy parameters are project-local and UNVERIFIED, not calibrated criteria or provider constraints. Synthetic fixtures verify deterministic behavior only. No quality score, retake decision, B3 S3 signal, agronomic leaf segmentation, or real-image accuracy is claimed. T04 remains PARTIAL pending approved quality thresholds/mapping and workflow integration.
- Verification: focused preprocessing/trace/header tests **65 passed**; full suite **982 passed**. Follow-up compile/config/security/metadata/whitespace results are recorded in `docs/muse-code-log/t04-image-preprocessing.md`.
- No network/API calls, media uploads, credential access, `.env` reads, dependency installation, or Git history operations. Live SAM remains NO-GO.

## 2026-10-30 — T06 registry gap tier and test regression check (Codex)

- Compared `git diff e087e23 ef1aa7b -- tests/`. The title-verification parameter case was obsolete because `title_verified` is not in the revised registry contract; the PAU edition-year test was obsolete because `edition_year` is not in that contract. The `gap` citation parameter had been dropped solely because the enum omitted it; restored it as a non-citable tier and added an enum-acceptance test.
- JNKVV/RVSKVV is now `tier: gap`, with note “No package was found; source not retrieved.” Both `gap` and `cross-check` citations are rejected. T06 remains PARTIAL.
- Verification: focused schema/registry tests **58 passed**; full suite **962 passed**; compileall passed; all `kb/` YAML parsed; safe secret scan returned 0 matches; `.env` checks used Git metadata only; whitespace and diff checks clean. Exact results are in `docs/muse-code-log/t06-kb-registry-codex.md`.
- No network/API calls, `.env` access, dependency changes, or live tests. Live SAM remains NO-GO.

## 2026-10-30 — Phase 4 T06 registry contract correction (Codex)

- What changed: aligned the source registry with the latest owner-supplied titles and fields, removing `title_verified` and `edition_year`; citations now require `retrieved: true`, and verified cards additionally require `verified_by_user: true`. The requested tier enum omits `gap`; JNKVV/RVSKVV is recorded as `cross-check` only to remain non-citable, with its source-gap status explained in notes and the content plan. The prior Phase 4 entry remains historical; its registry snapshot is marked superseded in the plan.
- Codex permission remains stated by the user; official wording/link is not recorded, so status remains UNVERIFIED. No source excerpts exist locally; no production disease cards were drafted. Hindi remains UNREVIEWED and the proposed crops remain unconfirmed. T06 stays PARTIAL.
- Verification: correction-pass disease-card schema/registry tests **56 passed**; full suite **960 passed**; compileall exit 0; both `kb/` YAML files parsed; secret scan, metadata-only `.env` checks, and final whitespace/diff checks are recorded in `docs/muse-code-log/t06-kb-registry-codex.md`.
- No network/API calls, dependency changes, `.env` access, or live tests. Live SAM remains NO-GO.

## 2026-10-30 — Phase 4 T06 KB schema, source registry, and validator (Codex)

- What changed: added the project-local `kb/sources.yaml` registry with only the eight owner-supplied candidate entries, all retrieval/title/user-verification flags false; extended the disease-card validator with explicit card status, region tags, per-claim source locators, per-language review metadata, citation eligibility, and conservative dosage/mixing pattern checks; preserved the general safety-card loader. Added one `SYNTHETIC_TEST` fixture under tests that production loading rejects. Recorded the Codex permission statement as user-stated but UNVERIFIED.
- Content boundary: proposed MP-first region and tomato/potato/soybean crops are not confirmed. No `docs/kb/source_excerpts/` directory or source excerpts were present, so no production disease cards or agricultural claims were drafted. Hindi remains UNREVIEWED. T06 stays PARTIAL.
- Verification: disease-card schema/registry tests **59 passed**; full suite **963 passed**; `python3 -m compileall -q src tests eval` exit 0; both `kb/` YAML files parsed; safe secret-pattern scan 0 matches; `.env` ignored and untracked per Git metadata only; `git diff --check` clean. Exact commands/statuses are in `docs/muse-code-log/t06-kb-registry-codex.md`.
- No network, dependency installation, `.env` read, credentials, media, live provider calls, or credits. Live SAM remains NO-GO.


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

## 2026-10-28 — Phase 4B: offline SAM compatibility and safety gates

- What changed: added synthetic coverage that preserves documented printable payload marker characters as opaque data and accepts a payload exactly at its configured local cap; updated SAM readiness and Meta API matrix with the current official grammar/parser/decoder documentation, distinguishing official facts from local limits and unresolved Base85 variant details; added a pre-live evidence checklist and one-request plan explicitly marked unauthorized. Updated the existing Phase 3 session log with this follow-up.
- What remains broken/unverified: no SAM client, SSE assembler, decoder, live compatibility evidence, account model access/credits/expiry/payment state, hard spend cap, SAM-specific still-image limits, or completed privacy/authorization/retention gates. Live calls remain NO-GO. A spend alert is not a hard cap; one-call guard cannot guarantee zero billing.
- Checks: response-text tests **75 passed**; synthetic parser tests **71 passed**; full suite **323 passed, 0 failed**; compileall and TOML/three-YAML parsing passed; `git diff --check` passed; added-line whitespace scan found 0; safe secret-pattern scan found 0; `.env` ignore/untracked state confirmed using Git metadata only.
- What is next: continue offline compatibility work with synthetic fixtures and official parser interfaces only. Gather redacted account, billing, privacy, image-rights, and model-access evidence before seeking separate live-test authorization. No API calls, uploads, credentials, credits, dependency changes, or Git mutations.

## 2026-10-28 — Phase 4B.1: readiness freshness-note correction

- What changed: corrected one stale table row in `docs/verification/sam_live_integration_readiness.md` (§3, link-freshness entry) to record that Phase 4B rechecked the linked official pages on 2026-10-28 (§9) and that links must be rechecked again before any live step. Status stays UNVERIFIED; no claim that every link or detail is independently verified. No parser, test, or other documentation changes.
- Checks: `git diff --check` clean; response-text tests **75 passed**; synthetic parser tests **71 passed**; full suite **323 passed, 0 failed**; compileall, TOML/YAML parse, secret-pattern count scan (0), `.env` ignored/untracked (metadata only) all observed. No API calls, uploads, credentials, credits, deps, staging, or commits. **Live SAM remains NO-GO.**

## 2026-10-28 — Phase 4C: offline guard, mock transport, test log

- What changed: added `src/mydrak/sam/guard.py` (default-off 5-attempt campaign guard, breaker trips on 5th, explicit reset + re-authorization, token never stored; cannot enforce billing) and `src/mydrak/sam/transport.py` (request/response types without image bytes, deterministic fake, default-is-fake, no live client, validate → count → dispatch-once → parse, timeouts to manual review, never retried) with `tests/test_sam_live_guard.py` (14 tests); created `docs/testing/phase-4c-test-log.jsonl` (schema + non-executed example only, zero executed/live records, no invented costs); added `docs/verification/phase-4c-privacy-notice-questions.md` (unresolved recipients/storage/retention/access/consent, no ZDR or deletion claims, notice not approved). Recorded in `docs/muse-code-log/phase-4c-offline-implementation.md`.
- Checks: new file **14 passed** first run; full suite **337 passed, 0 failed**; `compileall`, TOML/YAML parse, `git diff --check`, untracked whitespace scan clean; secret-pattern count scan 0 in new files / 0 on added doc lines; `.env` ignored + untracked (metadata only). No API calls, uploads, credentials, credits, deps, staging, or commits. **Live SAM remains NO-GO.**

## 2026-10-28 — Phase 4C.1: safety-gate hardening

- What changed: durable file-backed guard budget (XDG-local JSON state, atomic writes, lock-mutex, fail-closed corruption/write failures, restart/recreation sharing, 8-thread contention tested); explicit local operator-gate authorization (single-use token fingerprints, campaign+scope binding, expiry, reuse/mismatch rejection; reset verifies distinctness, authorize records use — one self-found ordering defect fixed); `run_scan` accepts exactly `FakeSamTransport` (fabricated-flag subclasses rejected pre-send, pre-count); `MockScanResult` provenance wrapper enforced in constructor; cost-log schema disambiguated (null = unknown, 0 = verified zero only). Recorded in `docs/muse-code-log/phase-4c-1-safety-gate-hardening.md`.
- Checks: guard/transport file **31 passed** (3 first-run failures investigated and fixed); full suite **354 passed, 0 failed**; `compileall`, TOML/YAML parse, `git diff --check`, untracked whitespace scan clean; secret-pattern count scan 0; `.env` ignored + untracked (metadata only). No API calls, uploads, credentials, credits, deps, staging, or commits. **Live SAM: NO-GO.**

## 2026-10-28 — Phase 4C.2: safety-gate hardening follow-up

- What changed: in-process loss/rollback tripwire (deleted/replaced state rejected while the process lives; explicit reset recovers missing state with history re-seeded, budget not recovered); realpath state-dir normalization; stale-lock/orphan-temp fail-closed behavior pinned by tests; forged-reply validation (type, `fake-<n>` ID, string payload, flag) with in-process limits documented; provenance-forgery negatives; cross-process contention test (exactly 5 across 3 processes). One self-found reset/authorize ordering defect fixed; one editing accident (dropped test def) repaired and re-verified. JSONL unchanged, zero executed records. Recorded in `docs/muse-code-log/phase-4c-2-safety-gate-hardening.md`.
- Checks: guard/transport file **43 passed** (1 first-run failure investigated: snapshot-restore hits history-rollback before the token check — restructured test to assert each layer); full suite **366 passed, 0 failed**; bytecode/cache-disabled pytest, no-write compile pass, TOML/YAML parse, JSONL validation, `git diff --check`, untracked whitespace scan clean; secret-pattern count scan 0; `.env` ignored + untracked (metadata only). No API calls, uploads, credentials, credits, deps, staging, or commits. Tested vs reasoned-about limits recorded in the session log. **Live SAM: NO-GO.**

## 2026-10-28 — Phase 4C.3: two defect fixes + narrowed claims

- What changed: `MockScanResult` now requires a `SamFrame` instance (`frame=None` etc. rejected); `_write()` cleanup guarded so mkdir failure surfaces `LiveGuardError`, not `UnboundLocalError`; docstrings narrowed (shape checks/marker are conventional, forgeable markers — not authenticity proof) with a boundary test proving a shape-valid forgery parses. Recorded in `docs/muse-code-log/phase-4c-3-defect-fixes.md`.
- Checks: focused file **46 passed**; full suite **369 passed, 0 failed**; in-memory compile (48 files), TOML/YAML parse, JSONL validation (0 executed records), `git diff --check`, untracked whitespace scan clean; secret-pattern count scan 0; `.env` metadata-only (ignored/untracked, never read). No API calls, uploads, credentials, installs, staging, commits, or pushes. Strictly offline. Same-process forgery, cross-restart rollback, and billing remain UNVERIFIED/unenforced. **Live SAM remains NO-GO.**

## 2026-10-28 — Phase 4D.1: offline integration contract review

- What changed: created `docs/verification/phase-4d-integration-contract.md` (implementation-vs-boundary, 20-row evidence table with VERIFIED IN REPO / OFFICIAL SOURCE RECORDED / PROJECT-LOCAL ASSUMPTION / UNVERIFIED / BLOCKED labels, 8 unanswered contract questions, privacy/cost blockers, no-go checklist; authorizes nothing) from repository evidence only, no network. No additional contract test: every offline-testable invariant is already pinned by the suite; inventing schema is forbidden. Recorded in `docs/muse-code-log/phase-4d-1-integration-contract.md`.
- Checks: focused SAM files **192 passed** (75 + 71 + 46); full suite **369 passed, 0 failed**; in-memory compile (48 files), TOML/YAML parse, JSONL validation (0 executed records), `git diff --check`, untracked whitespace scan clean; secret-pattern count scan 0; `.env` metadata-only (ignored/untracked, never read). No network/API calls, uploads, credentials, installs, staging, commits, or pushes. Blockers stand. **Live SAM remains NO-GO.**

## 2026-10-28 — Phase 4D.1 corrections (Codex 4D.2 audit)

- What changed (docs only, no code/tests): reconciled the contract confidence row with the matrix Phase 4B grammar bullet (0..1 range = recorded citation, not fresh verification; synthetic score stays project-local); documented the zero-area box parser difference (`response_text.py` accepts, `output.py` rejects; official semantics UNVERIFIED); narrowed retry scope (zero retries for any future authorized smoke test, B11 ≤2 policy stands project-level, provider semantics UNVERIFIED, authorizes nothing). Recorded in `docs/muse-code-log/phase-4d-1-integration-contract.md`.
- Checks: `git diff --check` clean; untracked whitespace scan clean; read-back of all three edited documents confirmed; secret-pattern count scan 0 (counts only); `.env` metadata-only (ignored/untracked, never read). Full suite not re-run: documentation-only change, audit already reported 369 passing, no code or tests touched. No network/API calls, uploads, credentials, installs, staging, commits, or pushes. **Live SAM remains NO-GO.**

## 2026-10-28 — Phase 4D.3: privacy/eligibility/cost readiness review

- What changed: created `docs/verification/phase-4d-readiness-review.md` (17-row evidence table, blockers, owner decisions, go/no-go checklist at 0 of 10) from repository evidence only, no network. Nothing resolved: privacy notice still draft/unapproved; credits, billing, ZDR, consent flow, media limits, decoder, and live compatibility all remain UNVERIFIED/BLOCKED. Recorded in `docs/muse-code-log/phase-4d-3-readiness-review.md`.
- Checks: `git diff --check` clean; untracked whitespace scan clean; read-back confirmed; secret-pattern count scan 0 (counts only); `.env` metadata-only (ignored/untracked, never read). Full suite not re-run (docs-only; 369 passing per audit). No network/API calls, uploads, credentials, installs, staging, commits, or pushes. **Live SAM remains NO-GO.**

## 2026-10-28 — Phase 4D.3 audit corrections (Codex 4D.2 follow-up)

- What changed (docs only, 3 files): review row 3 no longer claims credential absence (UNVERIFIED, nothing inspected); row 9 limited to reviewed documents; conclusion separates recorded-but-not-freshly-verified official claims from UNVERIFIED/BLOCKED account conditions; threat-model approval removed as a mandatory gate (unsupported by §10/§E; notice gate kept); "0 of 10" preserved for still-blocked §E/§10 rows. Recorded in `docs/muse-code-log/phase-4d-3-readiness-review.md`.
- Checks: `git diff --check` clean; untracked whitespace scan clean; read-back of all three documents confirmed; secret-pattern count scan 0 (counts only); `.env` metadata-only (ignored/untracked, never read). Full suite not re-run (docs-only change, no code/tests touched). No network/API calls, uploads, credentials, installs, staging, commits, or pushes. **Live SAM remains NO-GO.**

## 2026-10-28 — Offline SAM mask-to-severity subtask (limited T08)

- What changed: added pure `mask_severity_pct(leaf, lesion)` in `src/mydrak/sam/severity.py` (reuses `intersection()`; `SegmentationEvalError` on type/shape mismatch; unrounded percent, `None` on empty leaf, `0.0` on zero overlap, outside-leaf lesion ignored) with 5 tests in `tests/test_severity.py` (4×4: 10 leaf / 3 overlap / 1 outside → `30.0`) and 1 grid-converter integration test in `tests/test_sam_grid.py` (→ `50.0`). All fixtures synthetic; grid-based project-local math only. Recorded in `docs/muse-code-log/phase-2-task-10-grid-adapter.md` (follow-up section).
- Checks: grid + severity files pass; full suite passes; `compileall`, TOML/YAML parse, `git diff --check` clean; secret-pattern count scan 0; `.env` ignored + untracked (metadata only). No API calls, uploads, credentials, installs, staging, commits, or pushes.
- Status (explicit): Phase 4 is **NOT FULLY CLOSED** and this task does not close it; T08's client and overlay scope remains incomplete; live SAM remains **NO-GO** (no live test authorized); no API credits were intentionally used.

## 2026-10-28 — Offline SAM client/configuration boundary

- What changed: added `src/mydrak/sam/client.py` (explicit validated config with no defaults, per-call credential resolution from injected env mapping or process env, credential-free metadata envelope, injected session protocol, validate → resolve → invoke-once dispatch, no retries, no network, no provider JSON invented) with `tests/test_sam_client.py` (36 tests: valid/mapping/placeholder/invalid config, zero calls on failure, credential exclusion, metadata-only receipt, no-network scan, default-still-fake). `config/models.yaml` untouched; model-ID discrepancy unresolved; `.env` autoload not claimed. Recorded in `docs/muse-code-log/sam-client-boundary.md`.
- Checks: new file **36 passed** first run; full suite **411 passed, 0 failed** (375 + 36); `compileall`, TOML/YAML parse, `git diff --check`, untracked whitespace scan clean; secret-pattern count scan 0; `.env` ignored + untracked (metadata only). No API calls, uploads, credentials, installs, staging, commits, or pushes. Provider JSON, media limits, retry semantics, and billing remain UNVERIFIED/BLOCKED. Live execution disabled and unauthorized.

## 2026-10-28 — Offline SAM request serialization

- What changed: pure deterministic serializer in `src/mydrak/sam/client.py` (exact `model`/`input`/message/`input_text`+`input_image`/`stream:false` body per supplied findings; URL + base64-data-URL validation, no invented media limits; canonical `https://api.meta.ai/v1` + `/responses` built once, others rejected; key in `Authorization` header metadata only; raw reply returned unparsed) with 28 new tests in `tests/test_sam_client.py` (exact structure, malformed inputs, determinism, credential exclusion, exact dispatch metadata, pre-session failure). `run_scan`, default fake, and `models.yaml` untouched. Recorded in `docs/muse-code-log/sam-request-serialization.md`.
- Checks: client file **64 passed** (36 carried + 28 new; 4 first-run failures fixed: 3 test-side kwargs, 1 docstring tripping the token scan); full suite **439 passed, 0 failed**; `compileall`, TOML/YAML parse, `git diff --check`, untracked whitespace scan clean; secret-pattern count scan 0; `.env` ignored + untracked (metadata only). No API calls, uploads, credentials, installs, staging, commits, or pushes. SAM media limits, envelope parsing, retry semantics, billing UNVERIFIED/BLOCKED; Phase 4 open. Live execution disabled and unauthorized.

## 2026-10-29 — SAM request/dispatch hardening (Codex audit follow-up)

- What changed: hardened `src/mydrak/sam/client.py` (stdlib `re` only, no `urllib` per the no-network token scan): full-body revalidation at construction and dispatch (unexpected keys/malformed nesting rejected, model/endpoint/timeout consistency enforced pre-session); nested-mutation bypass closed (session receives a deep copy); injected-session exceptions sanitized to fixed `SAM session call failed` (`from None`); strict HTTP(S) URL syntax (host/port/userinfo, no reachability claim); data-URL mediatype restricted to `image/*` with no invented SAM format limits; docstring distinguishes documented `sam-3.1` from UNVERIFIED eligibility/billing/live-compat. `run_scan`, default fake, `models.yaml`, `architecture.md` untouched. Recorded in `docs/muse-code-log/sam-request-hardening.md`.
- Checks: client file **104 passed** (64 carried + 40 new; one first-run failure was this task's own `urllib` import tripping the token scan, fixed by hand-rolled parsing); full suite **479 passed, 0 failed**; `compileall`, TOML/YAML/JSONL parse, `git diff --check` clean; secret-pattern scan benign-only; `.env` ignored + untracked (metadata only, never read). No API calls, uploads, credentials, installs, staging, commits, or pushes. Envelope parsing, retry semantics, media limits, eligibility, billing UNVERIFIED/BLOCKED; Phase 4 open. Live execution disabled and unauthorized.

## 2026-10-29 — SAM dispatch hardening, round 2 (Codex audit follow-up)

- What changed: `src/mydrak/sam/client.py` (stdlib only): every injected-session failure — including `SamConfigError` — sanitized to fixed `SAM session call failed` (`from None`); construction sha256 snapshot rejects any post-construction body mutation at dispatch while `body` stays a plain readable dict; strict base64 length/padding rules; bracketed hosts validated via `ipaddress.IPv6Address` (no network/reachability claim); message `type` omitted or `"message"` accepted, others rejected. Matrix line 44 corrected (offline boundary recorded; `sam-3.1` vs eligibility/billing/compat distinguished; URL checks syntax-only). `run_scan`, default fake, `models.yaml`, `architecture.md` untouched. Recorded in `docs/muse-code-log/sam-request-hardening-2.md`.
- Checks: client file **135 passed** (104 carried + 31 new, first run green); full suite **510 passed, 0 failed** (bytecode/cache disabled); in-memory compile of 50 files OK; TOML/3×YAML/JSONL parse OK (0 executed records); `git diff --check` clean; secret scan benign-only (value-safe literal check, 0 real secrets); `.env` ignored + untracked (metadata only, never read); no-network token scan 0. No API calls, uploads, credentials, installs, staging, commits, or pushes. Envelope parsing, retry semantics, media limits, eligibility, billing UNVERIFIED/BLOCKED; Phase 4 open. Live execution disabled and unauthorized.

## 2026-10-29 — SAM dispatch hardening, round 3 (Codex audit follow-up)

- What changed: `src/mydrak/sam/client.py` (stdlib only): sanitized dispatch error now raised outside the handler via flag, severing `__context__` and `__cause__`; digest-based mutation detection preserved (no immutability claimed, read compat kept, nested-mutation rejection tested); `sam-3.1` enforced at the HTTP boundary (`serialize_sam_body` + `dispatch_http`, incl. rejecting `sam-3-1`) while the generic config layer stays model-agnostic by design; matrix lines 30/44 and readiness row 39 corrected (offline format gate only, no live use/eligibility/billing/compat). `run_scan`, default fake, `models.yaml`, `architecture.md`, round-2 log untouched. Recorded in `docs/muse-code-log/sam-request-hardening-3.md`.
- Checks: client file **144 passed** (135 carried + 9 new, first run green); full suite **519 passed, 0 failed** (bytecode/cache disabled); in-memory compile of 50 files OK; TOML/3×YAML/JSONL parse OK (0 executed records); `git diff --check` clean; secret scan benign-only (0 real secrets); `.env` ignored + untracked (metadata only, never opened); no-network token scan 0. No API calls, uploads, credentials, installs, staging, commits, or pushes. Envelope parsing, retry semantics, media limits, eligibility, billing UNVERIFIED/BLOCKED; Phase 4 open. Live execution disabled and unauthorized.

## 2026-10-29 — SAM model-ID documentation consistency (Codex audit follow-up, docs-only)

- What changed (3 sentences, 2 files): matrix line 44 states `sam-3.1` as the documented API model ID enforced by the SAM-specific request boundary, with UNVERIFIED extended to eligibility, billing/credits, media limits, response compatibility, retention/ZDR, live compat; matrix line 50 restates the discrepancy as UNVERIFIED live API-side resolution; readiness line 175 notes offline enforcement as format-gate-only. Inspected and left unchanged: `client.py` docstring, readiness row 39, round-2 log (historical), all readiness gates and NO-GO conclusions. Recorded in `docs/muse-code-log/sam-model-id-docs.md`.
- Checks: focused client file **144 passed**; full suite **519 passed, 0 failed** (bytecode/cache disabled); `git diff --check` clean; read-back of edits confirmed; secret-pattern counts benign; `.env` ignored + untracked (metadata only, never opened). No code/test/config changes; no API calls, uploads, credentials, installs, staging, commits, or pushes. Phase 4 open. Live execution disabled and unauthorized.

## 2026-10-29 — Offline SAM response-envelope parsing (Phase 4 product task)

- What changed: new `src/mydrak/sam/envelope.py` (stdlib only) with conservative `parse_response_envelope` (two explicitly labeled shapes, UNVERIFIED envelope schema; fixed value-free errors; empty/missing/error replies fail closed; texts returned unparsed, separate from the synthetic fixture grammar) plus `tests/test_sam_envelope.py` (17 tests, synthetic fixtures labeled UNVERIFIED). No changes to client, transport, existing parsers, `models.yaml`, gates, or historical logs. Recorded in `docs/muse-code-log/sam-envelope-parsing.md`.
- Checks: envelope + output + response-text + client files **307 passed** (17 new, first-run token-assertion fix as logged); in-memory compile of new files OK; `git diff --check` clean. Full suite deferred to next phase boundary (no shared file modified, nothing existing imports the new module). No API calls, uploads, credentials, installs, staging, commits, or pushes. Envelope schema, live compat, eligibility, billing UNVERIFIED. Phase 4 open. Live SAM remains NO-GO.

## 2026-10-29 — Caller-side envelope-to-frames adapter (Phase 4 task 2/3)

- What changed: new `src/mydrak/sam/frames.py` (`adapt_envelope` parses each envelope text against caller-supplied dimensions; `""` → zero-match frame, zero texts or rejected text → manual-review outcome with value-free detail, only non-envelope input raises) plus `tests/test_sam_frames.py` (11 tests, synthetic fixtures). Grid adapter untouched; no changes to envelope/parsers, client, transport, `models.yaml`, gates, or historical logs. Recorded in `docs/muse-code-log/sam-frames-adapter.md`.
- Checks: frames + envelope + output + response-text files **173 passed** (11 new, first run green); in-memory compile of new files OK; `git diff --check` clean. Full suite deferred to next phase boundary (no shared file modified, nothing existing imports the new module). No API calls, uploads, credentials, installs, staging, commits, or pushes. Provider behavior UNVERIFIED. Phase 4 open. Live SAM remains NO-GO.

## 2026-10-29 — Offline integration chain (Phase 4 final offline task)

- What changed: new `src/mydrak/sam/chain.py` (`run_offline_chain`: envelope → frames → explicit decision; `no-findings` only for parsed zero-match, everything else `manual-review`, `severity_pct` always `None` offline since wire masks stay opaque) plus `tests/test_sam_chain.py` (11 tests, severity-never-fabricated asserted); readiness row 58 evidence note appended (label stays UNVERIFIED, gates intact). No changes to parsers, client, transport, `models.yaml`, `architecture.md`, or historical logs. Recorded in `docs/muse-code-log/sam-offline-chain.md`.
- Checks: chain + affected SAM files **227 passed** (11 new; 2 first-run token-assertion fixes as logged); full suite **556 passed, 0 failed** (bytecode/cache disabled); in-memory compile OK; TOML/3×YAML/JSONL parse OK (0 executed records); `git diff --check` clean; secret scan 0 real secrets; `.env` ignored + untracked (metadata only, never opened). No API calls, uploads, credentials, installs, staging, commits, or pushes. No checks deferred. Phase 4 offline scope validated; live SAM remains NO-GO (mask decoding, eligibility, billing, retention, authorization BLOCKED).

## 2026-10-29 — Offline English-first reply composer (T07 slice)

- What changed: added `src/mydrak/reply/composer.py` and `templates.py` for deterministic English answer/ask/refer/retake rendering from supplied structured data and KB text; answer requires the fixed confidence vocabulary and safety line, optional severity is labeled as a one-photo estimate, ask selects a KB question, and missing/unavailable content fails closed. Added `tests/test_reply_composer.py` with synthetic-only disease-card fixtures plus actual safety-card referral/retake checks. Recorded in `docs/muse-code-log/offline-reply-composer.md`.
- Checks: focused reply/KB tests **30 passed**; full suite **583 passed, 0 failed**; both pytest runs disabled bytecode/cache generation. No network, API, credentials, uploads, or credits.
- What remains: T07 is partial. No native-reviewed Hindi templates, disease cards, Telegram delivery, or diagnosis logic were added; Hindi output remains unavailable. Synthetic fixtures establish rendering only, not diagnosis or agronomic accuracy.

## 2026-10-29 — Offline bounded follow-up loop (T16 slice)

- What changed: added `src/mydrak/workflow/followup.py` to reuse the reply composer and KB question/referral text for a bounded follow-up conversation. It requires one answer before another ask, stops after two questions, then refers; answer contents are not retained. Added `tests/test_followup.py` with synthetic card text, terminal/refusal/error cases, and the repository safety-card referral. Recorded in `docs/muse-code-log/offline-bounded-followup.md`.
- Focused tests: `tests/test_followup.py`, `tests/test_reply_composer.py`, and `tests/test_kb_loader.py` — **45 passed**.
- Full suite: **599 passed, 0 failed** with bytecode/cache generation disabled.
- What remains: this is not a Telegram handler and does not interpret answers or choose questions; a future caller must select the next question from approved KB/model evidence. It makes no diagnosis and performs no external processing.

## 2026-10-29 — Offline workflow coordinator

- What changed: added `src/mydrak/workflow/coordinator.py` to reuse `process_intake`'s data-policy gate, the offline SAM chain, referral composition, and bounded follow-up state. Policy denial stops parsing. Only explicitly labeled synthetic SAM fixtures are accepted; the intake MOCK finding is discarded; zero detections refer without implying plant health, and other outcomes require manual review/referral with no severity. Added `tests/test_workflow_coordinator.py` for normal, blocked, malformed, unsupported-language, and follow-up paths. Recorded in `docs/muse-code-log/offline-workflow-coordinator.md`.
- Focused cross-module suite: `tests/test_workflow_coordinator.py tests/test_followup.py tests/test_reply_composer.py tests/test_mock_intake.py tests/test_sam_chain.py` — **101 passed**.
- Full suite: **606 passed, 0 failed** with bytecode/cache generation disabled.
- What remains: no diagnosis source selects the next KB question; the caller must select it from approved evidence. Telegram delivery, disease-card coverage, and live SAM remain separate and incomplete.

## 2026-10-29 — T06 fail-closed disease-card schema validation

- What changed: added an additive disease-card validator and YAML loader in `src/mydrak/kb/loader.py`, preserving the existing general safety-card path. Added synthetic-only structure tests in `tests/test_disease_card_schema.py`; no disease content or treatment advice was authored. Recorded details in `docs/muse-code-log/t06-disease-card-schema-validation.md`.
- Checks: focused KB tests **35 passed**; full suite **639 passed, 0 failed** (`PYTHONDONTWRITEBYTECODE=1`, pytest cache disabled); `git diff --check` clean. No API calls, uploads, credentials, dependencies, or Git mutations.
- What remains: B6 content sourcing, card authoring/review, native Hindi review, and chemical citation/safety verification are not established by schema validation. Live SAM remains NO-GO.

## 2026-10-29 — T03 offline-first Telegram adapter and state flow

- What changed: added a normalized synthetic-update boundary in `src/mydrak/bot/adapter.py` with B7 conversation states, `/start`, `/language`, `/help`, `/rescan`, photo/voice handling, policy-gated photo deferral, and trusted-only workflow state transitions. Default delivery is disabled; the only supported transport is an in-memory fake. Added `tests/test_bot_adapter.py`. No Telegram SDK, wire-format assumption, media bytes, or live integration.
- Checks: focused adapter/intake/coordinator/follow-up tests **85 passed**; full suite **660 passed, 0 failed** (`PYTHONDONTWRITEBYTECODE=1`, pytest cache disabled); syntax/config and `git diff --check` clean.
- What remains: photo preprocessing and diagnosis (T04/T05), voice transcription (T10), scan history for `/rescan` (T09), disease-driven follow-up selection/interpretation, Hindi replies, and live Telegram delivery are unavailable. Live SAM remains NO-GO.

## 2026-10-29 — T04 image preprocessing assessment (blocked)

- What changed: no code changed. Existing `read_local_image()` performs bounded PNG/JPEG header inspection only; it does not decode pixels, apply EXIF orientation, resize/recompress, or measure image quality. T04 preprocessing is blocked pending approval for an image-decoding dependency and decisions on unspecified numeric thresholds/resize settings. Recorded in `docs/muse-code-log/t04-preprocessing-blocker.md`.
- Existing checks: focused image/workflow/T03 tests **66 passed**; full suite **660 passed, 0 failed** (bytecode/cache disabled). These verify existing behavior, not T04 completion.
- What remains: no new dependency was installed or added, and no thresholds were invented. Live SAM remains NO-GO.

## 2026-10-29 — T11 offline signal extraction and Decider integration

- What changed: added `src/mydrak/decider/extraction.py` with B3 S1 extraction from two structured samples, numeric S4 extraction, explicit unavailable S2/S3 cases, and safe referral when signal evidence is incomplete or invalid. Hardened `combine()` and `decide()` for finite/ranged values, valid weights, and consistent escalation/follow-up state. Added synthetic-only `tests/test_decider_extraction.py`. No workflow coordinator integration because it has no model samples, KB-overlap result, T04 quality metrics, or model confidence input.
- Checks: focused Decider tests **79 passed**; full suite **726 passed, 0 failed** (`PYTHONDONTWRITEBYTECODE=1`, pytest cache disabled); syntax/config parsing and `git diff --check` clean.
- What remains: S2 symptom overlap/tokenization, S3 image-quality measurements, S4 band mapping, model-output validation (T05), and calibrated production thresholds remain unresolved. Synthetic tests do not establish model accuracy or agronomic safety. Live SAM remains NO-GO.

## 2026-10-29 — T05 offline diagnosis output contract

- What changed: added `src/mydrak/vision/diagnosis.py` with strict B8 eight-field JSON validation, trusted crop/disease allowlists, duplicate-key and extra-field rejection, separate valid/unknown/unavailable results, an injected provider protocol, and exactly one repair attempt for invalid structured output. Numeric confidence aligns with T11 S4; no provider/model or workflow route is created. Added synthetic-only `tests/test_diagnosis_contract.py`.
- Checks: focused diagnosis/Decider tests **121 passed**; full suite **768 passed, 0 failed** (`PYTHONDONTWRITEBYTECODE=1`, pytest cache disabled); syntax/config parsing and `git diff --check` clean.
- What remains: complete confidence-band vocabulary, curated T06 allowlists, request/prompt contract, T04 image input, T12 sampling/escalation, and live provider compatibility remain unresolved. B11 API-error backoff is not implemented in this offline validator; no live provider exists. Live SAM remains NO-GO.

## 2026-10-29 — T06 KB matching readiness follow-up

- What changed: no matcher or disease content added. Reviewed B6/T06 against the KB files, T05 allowlist inputs, and T11 S2 extraction. The only repository card is general safety; disease cards and trusted crop/ID vocabularies are absent. Existing no-card S2=0 behavior remains; matching-card symptom overlap remains unavailable until its contract is defined. Recorded the content and policy decisions needed in `docs/muse-code-log/t06-kb-matching-readiness.md`.
- Checks: read-only source/config inspection and `git diff --check`; no tests rerun because code and tests were unchanged.
- What remains: choose the three crops from the farmer region, curate/review 12–16 source-backed cards and bilingual content, derive trusted T05 allowlists, and approve the symptom-overlap/tokenization rule before implementing a matcher. Live SAM remains NO-GO.

## 2026-10-29 — T12 offline Glimmer sampling and escalation contract

- What changed: added `src/mydrak/vision/sampling.py` and synthetic-only tests for two B8-validated Glimmer samples, B3 S1 agreement, one Spark invocation on valid disagreement, and caller-carried per-case escalation state. Existing B8 validation/one-repair behavior and T11 S1 extraction are reused. Recorded in `docs/muse-code-log/t12-glimmer-sampling-escalation.md`.
- What remains unverified/incomplete: no provider or request format, SAM crop input, score-driven B3 escalation, re-score, or final policy decision was introduced. S2/S3 and production thresholds remain unavailable/placeholders; state is transient and caller-carried. No provider compatibility is claimed.
- Verification: focused T12/B8/B3 tests **124 passed**; full suite **784 passed, 0 failed** with bytecode and pytest cache disabled; compileall and TOML/YAML parsing passed; safe secret-pattern scan found 0 matches; `.env` ignored/untracked confirmed via Git metadata; `git diff --check` and new-file whitespace scan clean.
- Live SAM remains NO-GO; no live call is authorized or performed.

## 2026-10-29 — T13 evaluation harness readiness (blocked)

- What changed: no code or tests changed. Compared C2 T13 and D1/D2/D8 requirements with the existing header-only image report, evaluation data inventory, diagnosis/Decider/sampling interfaces, model configuration, and trace availability. Recorded the evidence blocker in `docs/muse-code-log/t13-evaluation-harness-readiness.md`.
- What blocks implementation: no 30 labeled licensed images or dev/test split, no per-strategy prediction/route outcomes, no token/cost/latency traces, model IDs/prices remain placeholders, and D1's deferral/coverage denominator needs clarification. Generating metrics or charts now would require invented inputs or unsupported figures.
- Checks: existing header-report tests **6 passed**; full suite **784 passed, 0 failed**; compileall and TOML/YAML parsing passed; secret-pattern scan found 0 matches; `.env` ignored/untracked confirmed through Git metadata; `git diff --check` and new-log whitespace check clean. No metrics were generated.
- No APIs, network, uploads, credentials, credits, dependency installs, or Git history operations. Live SAM remains NO-GO.

## 2026-10-29 — T04 image preprocessing follow-up (blocked)

- What changed: no code or tests changed. Rechecked T04 B1/B3/C2 against the bounded PNG/JPEG header reader, its synthetic tests, `config/thresholds.yaml`, and declared dependencies. Recorded the current blocker and required decisions in `docs/muse-code-log/t04-image-preprocessing.md`; preserved the prior T04 blocker log.
- What blocks implementation: no approved image decoder dependency is installed or declared, and B1/B3/C2 do not define resize/encoding parameters, blur/brightness/leaf-coverage thresholds, or measurement-to-S3 mapping. `quality_min: 0.4` remains a placeholder; local intake bounds are not quality thresholds.
- Verification: existing image-header/workflow/adapter tests **66 passed**; full suite **784 passed, 0 failed**; compileall and TOML/YAML parsing passed; safe secret-pattern scan found 0 matches; `.env` ignored/untracked confirmed via Git metadata; `git diff --check` and new-log whitespace scan clean. These checks do not establish pixel decoding or quality-gate behavior.
- No live services, media uploads, credentials, credits, dependency installs, or Git history operations. Live SAM remains NO-GO.

## 2026-10-29 — T06 disease-card content planning and readiness

- What changed: no disease cards, code, or tests added. Created `docs/verification/t06-disease-card-content-plan.md` with B6 fields/content rules, source/review traceability plan, allowlist derivation, S2 blocker, and owner decisions. Recorded in `docs/muse-code-log/t06-disease-card-content-planning.md`.
- What blocks content/matching: no intended farmer region or approved crop selection; no sourced/reviewed disease content or production cards; no authoritative-source hierarchy/reviewers recorded; and B3 S2 normalization, overlap denominator, bilingual tokenization, and score handling remain unspecified.
- Checks: existing KB schema tests and full suite, compile/config, secret-pattern, `.env` metadata, and whitespace/diff checks are reported in this task completion response. Synthetic schema fixtures remain test-only and are not agricultural evidence.
- No live services, network, media uploads, credentials, credits, dependency installs, or Git history operations. Live SAM remains NO-GO.

## 2026-10-29 — T09 offline trace and cost-accounting slice

- What changed: added `src/mydrak/trace/store.py` with an atomic SQLite `cases`/`steps` writer, bounded trace validation, latency totals, and per-million-token cost estimation. Missing or `TODO(verify)` prices yield unknown (`NULL`) cost. Integrated sanitized persistence for accepted offline coordinator outcomes, including policy blocks; records contain only fixed stage labels/outcomes and no image bytes, user text, synthetic SAM text, or mock findings. Added synthetic offline tests and created `docs/verification/roadmap_reconciliation.md` for all 19 C2 tasks.
- Status: T09 is **PARTIAL**, not complete: provider token/price traces, remaining B9 tables, and whole-application coverage do not exist. Live SAM remains **NO-GO**. No code or documentation asserts live compatibility or real costs.
- Checks: focused trace/coordinator tests **18 passed**; full suite **795 passed**; `compileall`, TOML/YAML/JSONL parsing, `git diff --check`, and scoped whitespace check passed; secret-pattern scan found 0 matches; `.env` ignore/untracked state confirmed by Git metadata only. Details in `docs/muse-code-log/t09-trace-cost-accounting.md`.
- What is next: implement B5/T17 recovery-history persistence with its specified hashed user ID, plant label, timestamp, severity, and image hash, reusing the existing trend helper. Use synthetic records and define retention before deployment; no live integration or live test is authorized.

## 2026-10-29 — T17 recovery-history persistence

- What changed: extended the existing T09 SQLite store with B9 `scans` persistence and added `src/mydrak/recovery/history.py`. Records require a 64-character lowercase SHA-256 user hash and image hash, a timezone-qualified timestamp, exact farmer-selected plant label, finite 0–100 severity, and a linked T09 case for the same hash. Re-scans match exact `(user_hash, plant_label)`, require a strictly later timestamp, compute percentage-point delta, and reuse `recovery_trend` with B5's 3pp default and caller-configurable margin. No image bytes or raw user IDs are accepted or stored.
- Status: offline recovery-history persistence and comparison are implemented. T17 remains **PARTIAL**: current workflow does not produce validated real scan severity or deliver a localized B5 caveat; scan-record retention is not specified and must be resolved before deployment. No improvement is attributed to treatment.
- Checks: focused recovery/T09/coordinator tests **48 passed**; full suite **825 passed**; compileall, TOML/YAML/JSONL parsing, `git diff --check`, scoped whitespace, safe secret scan, and `.env` metadata checks passed. Exact commands are in `docs/muse-code-log/t17-recovery-history-persistence.md`.
- No network/API calls, uploads, credentials, credits, dependency installs, or Git history operations. Live SAM remains **NO-GO**.

## 2026-10-29 — T15 offline replay and trace backup

- What changed: added `src/mydrak/replay/replay.py`, which re-runs only an explicitly labeled in-memory synthetic fixture through the existing offline coordinator, and `TraceStore.backup_to()` for non-overwriting local SQLite backups. Tests block socket creation, check replay outcomes and privacy-safe tracing, verify backup contents, and ensure existing destinations are preserved.
- Status: T15 is **PARTIAL**. B10's `DEMO_MODE=replay` serving of cached responses is not implemented; this slice does not cache arbitrary response text or claim live replay behavior.
- Verification: focused replay/T09/coordinator tests **28 passed**; full suite **834 passed**; compileall, TOML/YAML/JSONL parsing, `git diff --check`, scoped whitespace and secret scans passed; `.env` metadata checks confirmed ignored/untracked without reading contents. Exact commands are in `docs/muse-code-log/t15-offline-replay-and-backup.md`.
- No live calls, network access, uploads, credentials, credit use, dependency installs, or Git history operations. Live SAM remains **NO-GO**.

## 2026-10-29 — T15 validated offline cached replay

- What changed: extended the existing SQLite store with the B9 `cache(key,response_json,ts)` table and a strict cache payload allowlist; added validated `DEMO_MODE` loading and cached replay helpers. Replay accepts only a trace-backed synthetic offline outcome, stores only fixed schema/provenance/status/response-code fields, and renders fixed English demo text. Cache keys are SHA-256 digests of bounded project fixture IDs. Duplicate keys do not overwrite, corrupt/missing rows fail closed, and there is no provider/network fallback. SQLite backups include cache rows. Recorded details in `docs/muse-code-log/t15-cached-replay-mode.md`.
- Scope/status: T15 remains **PARTIAL**. This supports three explicitly synthetic response outcomes only; it is not connected to Telegram/app lookup, has no full approved demo-case inventory, and does not enable `DEMO_MODE=live`. No provider outputs or real diagnoses are cached.
- Verification: focused replay/trace tests **55 passed**; full suite **870 passed, 0 failed**; `python3 -m compileall -q src tests eval` passed; `pyproject.toml`, all three config YAML files, and JSONL test-log records parsed (2 records; 0 executed); `git diff --check` passed; scoped whitespace scan found 0 trailing-whitespace lines; safe secret-pattern scan found 0 matches; `.env` ignore/untracked state confirmed with Git metadata only.
- No APIs, network requests, uploads, credentials, credits, dependency installs, or Git history operations. Live SAM remains **NO-GO**.

## 2026-10-29 — T15 replay caller integration

- What changed: connected the normalized offline Telegram adapter command `/replay synthetic-referral-01` to the existing validated cache path. The adapter only accepts a registered fixture ID, serves the fixed cached synthetic response, leaves conversation state unchanged, and records a privacy-safe `replay_cache_read` case/step in the existing trace store before returning it. Missing, invalid, unknown, or live-mode requests fail closed; delivery remains disabled by default. Recorded in `docs/muse-code-log/t15-replay-caller-integration.md`.
- Scope/status: T15 remains **PARTIAL**. Only the already-supported synthetic referral fixture is registered; the full D3 inventory is not defined/available, and there is no real Telegram wire adapter or image-hash lookup. Live/provider replay remains disabled.
- Verification: focused bot/replay/trace tests **84 passed**; full suite **878 passed, 0 failed**; `python3 -m compileall -q src tests eval` passed; TOML, three YAML files, and JSONL parsed (2 records; 0 executed); `git diff --check` passed; safe secret scan found 0 matches; scoped whitespace scan found 0 issues; `.env` metadata confirms ignored/untracked.
- No network/API calls, uploads, credentials, credits, dependency installs, or Git history operations. Live SAM remains **NO-GO**.

## 2026-10-29 — T09/T11 B9 Decider signal tracing

- What changed: added the specification-listed B9 `signals` table and strict insert/read APIs to the existing SQLite trace store. `route_signals()` can optionally persist its routed B3 signal values and decision against an existing trace case. Unavailable or malformed measurements are stored as `NULL`; signal reasons, source text, and user data are not stored. Tests cover normalized values, boundaries, nulls, invalid inputs, duplicate/missing cases, decision routing, and SQLite backup preservation. Recorded in `docs/muse-code-log/t09-b9-signal-persistence.md`.
- Scope/status: T09 remains **PARTIAL** because `eval_runs`, per-step `started_at`, complete app event coverage, provider token traces, and verified prices are absent. T11 remains **PARTIAL** because T04 S3, matching-card S2, confidence-band mapping, and live diagnosis inputs are unavailable. The coordinator does not fabricate these values.
- Verification: focused trace/Decider/replay tests **145 passed**; full suite **893 passed, 0 failed**; `python3 -m compileall -q src tests eval` passed; TOML, three YAML files, and JSONL parsed (2 records; 0 executed); `git diff --check` passed; safe secret scan found 0 matches; scoped whitespace scan found 0 issues; `.env` metadata confirms ignored/untracked.
- No live APIs, network, uploads, credentials, dependency installs, credit use, or Git history operations. Live SAM remains **NO-GO**.

## 2026-10-29 — T13 offline evaluation core

- What changed: added a standard-library-only metrics module, hand-written SVG charts, and an offline CLI that joins labels CSV to recorded predictions JSON and emits test-split JSON/Markdown/SVG reports. Added clearly synthetic fixtures and focused regression tests. Updated `eval/README.md` and the roadmap matrix; T13 core is **PARTIAL**, while real licensed labels, actual strategy outcomes, verified costs/latencies, and frozen threshold evidence remain blocked. The ten existing `eval/data/dev` images were not opened or used.
- Metric conventions: deferrals/retakes count incorrect in all-case accuracy; coverage means answered/all; escalation uses the explicit recorded flag; missing price/token data yields unknown cost. These are stated project-local conventions, not new master-spec definitions. Scores only produce descriptive curves; no threshold is selected or tuned on test data.
- Verification: focused tests **23 passed** (`python3 -m pytest tests/test_eval_metrics.py tests/test_eval_chart.py -q`); full suite **916 passed** (`python3 -m pytest -q`); `python3 -m compileall -q src tests eval` and `git diff --check` passed. Additional secret-pattern, `.env` metadata, and untracked-whitespace results are in `docs/muse-code-log/t13-eval-core-codex.md`.
- No network/API calls, credentials, media, credits, dependency installs, or Git history operations. Live SAM remains **NO-GO**.

## 2026-10-29 — T13 evaluation gap check

- What changed: corrected escalation rate to count both the recorded escalation flag and expert referrals; corrected score-curve coverage to require a prediction while retaining score-bearing cases in the denominator; exposed `--strategy all` in the offline CLI. Updated metric/CLI docs and the T13 roadmap status. `eval/chart.py` was not changed.
- Regression coverage: tests now cover expert referral with the escalation flag false, deferred/no-prediction curve rows, all-deferred zero coverage, missing each required cost input, and the explicit all-strategy CLI invocation.
- Verification: focused metrics/chart tests **30 passed**; full suite **923 passed**; compileall and `git diff --check` passed. Configuration parsing, safe secret scan, `.env` metadata checks, and new-file whitespace results are recorded in `docs/muse-code-log/t13-eval-gap-check-codex.md`.
- Status: T13 offline core remains **PARTIAL**; real-data evaluation remains **BLOCKED** pending licensed/labeled cases, recorded outcomes and verified measurement evidence. No data images were accessed or relabeled. No live evaluation or SAM test was performed.

## 2026-10-29 — T11 S2 phrase overlap and coordinator bridge

- What changed: added pure S2 phrase matching over distinct observed symptoms: lowercase/casefold, trim, collapse whitespace, and replace punctuation with word boundaries before exact phrase comparison. The denominator is distinct normalized observations; extra card phrases do not reduce the score; no observations are unavailable. This formula is the user-approved project-local decision, not detail supplied by B3.
- Integration: added `coordinate_mock_tier1_results()` to pass two schema-valid synthetic Tier-1 results through the existing `route_signals()`. S1 comes from the two samples; S2 uses their agreed crop/issue and first result's observed symptoms. S3 and S4 aggregation remain unavailable; the route therefore returns a fail-closed referral. No provider, threshold, or weight tuning was added.
- Regression coverage: table-driven S2 cases cover no observations, duplicates, case/space/punctuation variants, extra card symptoms, no matching card, and an empty matching-card symptom list. Coordinator tests verify the routed S1/S2 values, unavailable S3, referral fallback, and rejection of a non-validated result. Corrected the roadmap reference from nonexistent `tests/test_decider.py` to the actual policy, signal, extraction, and coordinator test modules.
- Verification: focused Decider/coordinator tests **107 passed**; full suite **937 passed**; compileall passed. Static/config/security results are recorded in `docs/muse-code-log/t11-s2-coordinator-codex.md`.
- Status: T11 remains **PARTIAL**. S3 quality measurements, confidence aggregation, approved production disease cards, and real provider inputs remain unavailable. Live SAM remains **NO-GO**.
