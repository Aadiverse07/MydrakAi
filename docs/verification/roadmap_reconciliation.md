# Master-spec roadmap reconciliation

**Basis:** `docs/MydrakDeepseekreformed.pdf`, especially B1/B3/B5–B12, C1–C2,
D1–D2. The PDF C2 list contains **19 tasks (T01–T19)**. Task acceptance text
below follows C2; B-section requirements are included where they determine
whether an implementation is complete. Repository code/tests are evidence;
historical logs are context only. Statuses describe the checked-in working tree
at this reconciliation, not live-service readiness.

`COMPLETE` means the specified offline behavior and its relevant tests exist;
provider/live completion is not implied. `PARTIAL` means some specified
behavior exists but a C2 or B-section requirement remains. `BLOCKED` means a
concrete missing prerequisite prevents safe completion under the current
authorization. `NOT STARTED` means no meaningful implementation was found.

| Task; C2 acceptance | Implementation and test evidence | Status | Missing behavior / dependency | Prior blocker and whether changed |
|---|---|---|---|---|
| **T01 Repo scaffold, config loader, `.env.example`;** pytest/config loads; MVP | `pyproject.toml`, `src/mydrak/util/config.py`, `config/*.yaml`, `.env.example`; `tests/test_config.py` | **COMPLETE** (foundation/config scope) | None for C2. Later integrations still need verified settings. | Foundation task; no relevant blocker. |
| **T02 Smoke scripts per Meta endpoint;** each prints valid response; MVP | `scripts/README.md`; no endpoint smoke scripts found | **BLOCKED** | Requires live endpoint calls, credentials, eligible account, confirmed billing/privacy gates and explicit live authorization. | Previously withheld under no-live-call rule; unchanged. |
| **T03 Telegram bot skeleton/state machine;** photo triggers handler and `/start` works; MVP | `src/mydrak/bot/adapter.py`; `tests/test_bot_adapter.py`; synthetic updates only | **PARTIAL** | No Telegram SDK/client, real update adapter, `/start` delivery, persistent user state, or outbound send path. | Offline adapter work changed the local prerequisite; real Telegram behavior remains unverified and unauthorized. |
| **T04 Preprocess and quality check;** blurry/dark/good image tests; MVP | `src/mydrak/vision/source.py` validates PNG/JPEG headers; `tests/test_vision_source.py` and `tests/test_image_eval.py` | **BLOCKED** | No decode, EXIF orientation, resize, or measurable blur/brightness/coverage checks. Pillow/OpenCV is not declared; specification lacks approved numeric thresholds/output settings. | Header-only work exists; dependency and product thresholds remain unavailable. |
| **T05 Diagnosis client/schema validation/repair retry;** invalid JSON falls back unknown; MVP | `src/mydrak/vision/diagnosis.py`; `tests/test_diagnosis_contract.py`; injected provider and B8 validator, one repair | **PARTIAL** | Concrete authorized model client and provider response contract are absent; Hindi/error/retry end-to-end behavior is not established. | Offline schema/repair work changed the local blocker; provider access and integration remain unavailable. |
| **T06 KB loader/matcher/general safety card;** all cards validate; MVP | `src/mydrak/kb/loader.py`; `tests/test_disease_card_schema.py`; only `kb/cards/general_safety.yaml` is production content | **PARTIAL** | No curated 12–16 source-backed disease cards across selected three crops; no B3 symptom-overlap/normalization/denominator/score mapping. | Schema validation is implemented; absent crop selection, reviewed content, and matching contract remain unchanged blockers. |
| **T07 Reply composer hi/en templates;** snapshots for answer/ask/refer/retake; MVP | `src/mydrak/reply/composer.py`, `templates.py`; `tests/test_reply_composer.py`; English templates | **PARTIAL** | Hindi templates/review and source-backed answer flow are absent; current safe outputs are limited. | English composer added; bilingual reviewed content remains unavailable. |
| **T08 SAM client/severity/overlay;** known mask fixture gives expected percent; MVP | `src/mydrak/sam/client.py`, `transport.py`, `response_text.py`, `adapter.py`, `severity.py`; client/grid/parser/severity tests | **PARTIAL** | Serializer/default transport are offline/mock-only; no documented provider mask decoder or image overlay renderer; live response compatibility is unverified. | Synthetic grid severity changed the offline state; decoder/overlay/provider blockers remain. |
| **T09 Trace and cost accounting;** every case writes steps and totals; MVP | `src/mydrak/trace/store.py`; `src/mydrak/decider/extraction.py` optionally records `route_signals()` decisions against an existing case; `src/mydrak/recovery/history.py` adds B9 scan rows; coordinator integration in `src/mydrak/workflow/coordinator.py`; `tests/test_trace_store.py`, `tests/test_decider_extraction.py`, `tests/test_workflow_coordinator.py`, `tests/test_recovery_history.py`, `tests/test_offline_replay.py` | **PARTIAL** | Case/step/scan/cache/signals SQLite persistence covers accepted offline coordinator/recovery records and explicitly traced Decider calls. Full app/event trace integration, per-step `started_at`, B9 `eval_runs`, token traces, and verified prices are absent. | Trace was previously an empty stub; T09 coordinator cases, T11 optional B9 signal rows, T17 scan persistence, and the T15 cache table now share one store. Model pricing remains `TODO(verify)`. |
| **T10 Audio pipeline;** sample OGG becomes transcript; MVP | `src/mydrak/audio/__init__.py` only; no audio tests or transcription pipeline found | **BLOCKED** | No OGG decode/transcription path or approved offline fixture/client; live transcription would require authorization and provider configuration. | No prerequisite has become available. |
| **T11 Decider signals/policy;** table tests every B3 branch; MVP | `src/mydrak/decider/extraction.py`, `signals.py`, `policy.py`; `tests/test_decider_extraction.py`, `tests/test_decider.py`; optional B9 persistence via `TraceStore.record_signals()` | **PARTIAL** | S2 symptom overlap and S3 quality measurements are unavailable; confidence-band mapping/thresholds and full B3 route coverage remain incomplete. Tracing requires an existing T09 case ID and store; unavailable values remain NULL. | S1/S4 structural extraction, fail-closed routing, and optional T09 signal trace now exist; missing upstream measurements/approved thresholds are unchanged. |
| **T12 Glimmer sampling/escalation;** disagreement triggers exactly one escalation; MVP | `src/mydrak/vision/sampling.py`; `tests/test_glimmer_sampling.py`; two validated injected Glimmer results and one bounded injected Spark escalation | **PARTIAL** | No concrete Glimmer/Spark providers; state is caller-carried; Spark result cannot be B3 re-scored because S2/S3 and approved thresholds are unavailable. | Offline sampling contract changed the purely missing state; provider and re-score blockers remain. |
| **T13 Eval harness;** metrics JSON for 3 strategies plus cost/accuracy chart; MVP | `eval/metrics.py`, `eval/chart.py`, `eval/run_eval.py`; `tests/test_eval_metrics.py`, `tests/test_eval_chart.py`; synthetic fixtures under `tests/fixtures/eval/`; `eval/image_report.py` remains header-only | **PARTIAL** (offline core); **BLOCKED** (real-data evaluation) | Offline metrics, test-only reporting, CSV/JSON input validation, JSON/Markdown/SVG output, and dev-only descriptive curves are implemented and tested. D1 escalation includes recorded Spark escalation or expert referral; score curves count coverage only when a scored row has a prediction. Still no 30 licensed/labeled cases (20 dev/10 test), actual outcomes for the three required strategies, verified token/latency traces or prices, or approved frozen thresholds. The 10 images in `eval/data/dev` remain header inventory only and were not used. | T13 offline core exists; this gap check corrected two metric interpretations and exposed D2's `--strategy all` CLI spelling. The real-data and measurement blocker is unchanged. No test-set tuning or real performance claim is made. |
| **T14 Dashboard;** traces, routes, eval page/chart; MVP | `dashboard/README.md` placeholder; no dashboard implementation/tests | **BLOCKED** | Depends on complete trace/event coverage and valid T13 results; no UI/routes/charts. | No material prerequisite change; T09 provides only a partial offline data store. |
| **T15 Replay mode + backup;** replay runs network-disabled; MVP | `src/mydrak/bot/adapter.py` handles `/replay <fixture_id>` through `run_registered_cached_replay`; only `synthetic-referral-01` is registered; `src/mydrak/replay/replay.py` validates cache read and serves fixed synthetic text; `src/mydrak/trace/store.py` implements B9 `cache(key,response_json,ts)` and records cache-read activity as a privacy-safe case/step; `src/mydrak/util/config.py` validates replay mode and rejects live; `tests/test_bot_adapter.py`, `tests/test_offline_replay.py` | **PARTIAL** | Caller integration works only for the single registered synthetic fixture and a pre-populated valid local cache. No complete D3 demo-case inventory or real Telegram wire adapter exists, and no image-hash lookup is defined. `DEMO_MODE=live` is deliberately disabled; no provider response or live compatibility is claimed. Replay-read traces record status and a fixed step only; they do not store user text or the cache key. | The prior cache-only helper is now connected to the existing normalized bot command entry point. The D3 all-demo-cases gap and live/provider gates remain unchanged. |
| **T16 Follow-up loop;** maximum two enforced; Should-have | `src/mydrak/workflow/followup.py`; coordinator bridge; `tests/test_followup.py`, `tests/test_workflow_coordinator.py` | **COMPLETE** for C2 bounded-loop behavior | Full Telegram lifecycle, persistent state, and KB-selected question integration are not complete; those are broader workflow gaps. | The offline C2 behavior and its tests exist; app integration remains separate. |
| **T17 Recovery tracking;** delta/margin logic tests; Should-have | `src/mydrak/recovery/history.py` uses `TraceStore.scans` and `recovery_trend`; `tests/test_recovery_history.py`; coordinator optionally persists validated hashes in T09 cases | **PARTIAL** | Offline persistence/comparison is implemented. No real rescan/user flow supplies validated severity; no localized user-facing caveat is wired; scan retention is unspecified. T04/T08 real severity inputs remain unavailable. | T09 SQLite now supports the B9 `scans` table; this unblocks offline persistence tests. It does not unblock valid real scan data or deployment retention policy. |
| **T18 Failure injection suite;** one test per B11 row; Should-have | Failure cases distributed across intake, diagnosis, sampling, SAM guard/transport, bot, and workflow tests | **PARTIAL** | No demonstrated test for every B11 row as a complete system, notably transcription, Telegram delivery retry/trace, full Spark fallback and provider timeout/retry. | Offline component cases exist; external client paths remain absent. |
| **T19 README/architecture/demo assets;** fresh clone works per README; MVP | `README.md`, `docs/architecture.md`; setup instructions; no demo assets/fresh-clone verification found | **PARTIAL** | README is stale (Phase 0 claims no bot/SAM/dashboard implementation); no judge-ready demo assets or verified clean-clone run. | Several offline features were added since README status text; documentation/demo gap has grown. |

## Dependency order and current next steps

The master’s C1 MVP priorities include Telegram, voice/transcription, SAM
overlay/severity, Glimmer + Decider + Spark escalation, KB-grounded steps,
refusal, dashboard/evaluation/replay. Dependencies visible in the spec and
repository are: T04/T06/T08 measurements and content → T11/T12 safe decision
flow → T07 replies; T03 provides user interaction; T09 supplies case/step data
to T13/T14/T15/T17; T10 supplies voice transcripts. These dependencies do not
grant live-service authorization.

**T09/T11/T17 progress:** the shared SQLite store supports case/step traces,
B9 scan/cache/signal rows, and T11 can persist a routed decision with nullable
unavailable values when attached to an existing case. This does not create
model measurements or tune thresholds. T09 remains PARTIAL because
whole-application event traces, B9 `eval_runs`, per-step `started_at`, token
accounting, and verified prices are absent. T17 remains PARTIAL until validated
scan severity is supplied by a supported workflow, the required measurement
caveat is delivered in the user's language, and retention is resolved for
deployment.

**Current T15 status:** the local cached-response path is connected to the
normalized bot adapter's `/replay <fixture_id>` command for the single
registered synthetic fixture `synthetic-referral-01`. It validates the cache,
records a fixed replay-read case/step without the cache key or user text, and
returns a fixed synthetic response. Cache rows remain included in SQLite
backups. The full offline D3 demo-case inventory and a real Telegram wire
adapter remain absent. No caller falls through to a provider/network path;
arbitrary model or user response text stays outside the cache contract.
`DEMO_MODE=live` and provider replay remain disabled and unverified.

## Global unresolved gates

Live SAM remains **NO-GO**. Account eligibility, actual credits/expiry,
payment method and billing behavior, privacy notice/authorization approval,
retention/ZDR, accepted image constraints, provider decoder behavior, and live
compatibility have not been established by this repository state. No T02/T10
live calls or media uploads are authorized. `config/models.yaml` prices,
endpoints, IDs and limits remain explicit placeholders; an estimated cost must
remain unknown where its required price is unknown.
