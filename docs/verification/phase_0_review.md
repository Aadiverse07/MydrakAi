# Phase 0 foundation review

**Review date:** 2026-10-27. Read-only code review plus the explicitly requested local test run. No model calls, smoke scripts, or data uploads were performed.

## Observed repository state

- Working directory: `/Users/aditya/Mydrak_Ai`.
- No Git repository existed at review start (`git rev-parse --is-inside-work-tree` failed with “not a git repository”). Git 2.55.0 is installed. This differs from the prior report only in that Git was actually checked here; it confirms its statement that no repository existed.
- Python 3.12.0; pytest 8.3.3; PyYAML 6.0.3; pypdf 5.0.1 were available. `pdftotext` was unavailable (`zsh: command not found: pdftotext`); the spec was read with pypdf without installing anything.
- Existing official spec and supporting image are project source materials and are retained for version control; they are not blindly ignored. Evaluation dev/test/results directories were empty at review time and are excluded by `.gitignore`.
- Secret-pattern scan reported no candidate-file matches. The scan did not inspect credential stores, `.env`, or the user's home authentication directories and cannot prove absence of every secret. No private farmer media or local `.env` file appeared in the project tree.

## Foundation and safety review

- `decider/signals.py`, `decider/policy.py`, `sam/severity.py`, and `reply/confidence.py` are pure local functions; no external calls exist. The Decider stays small and receives no network dependency.
- The confidence helper maps a number to three words and does not itself display a percentage. It does not validate its score or thresholds, and its plain-English output is not yet a reviewed bilingual reply template. No user-facing composer exists yet.
- `kb/cards/general_safety.yaml` is the only card and has no treatment guidance. `kb/loader.py` validates only a mapping and four safety fields; it does not yet validate a complete disease-card schema, sourcing, or safe-treatment constraints. There are no disease-specific treatment cards.
- `config/models.yaml` correctly marks IDs, endpoints, prices, and limits as `TODO(verify)`; this review does not change those runtime values. `config/thresholds.yaml` and `config/severity.yaml` explicitly label thresholds/bands unverified heuristics. No tuning or evaluation was done.
- **DATA_POLICY status before Phase 0.3:** `.env.example` defaulted to `private`, but no runtime code enforced the variable or model mode. Phase 0.3 adds `src/mydrak/privacy/data_policy.py` and unit tests. Private data now requires a verified Standard route, confirmed rights, explicit authorization, and an established privacy notice; Contributor is blocked. Public-test data requires `public_test`, independently verified provenance and rights, and a verified provider mode. The gate does not collect consent or independently verify route/evidence. There are still no outbound call sites, so no sender is currently wired to the gate; external processing remains absent and blocked.
- Official policy evidence: [Meta Contributor help](https://dev.meta.ai/help/policies-and-privacy/contributor-tier) explicitly prohibits sending personal information to Discounted/Contributor Services and directs such use cases to Standard Services. Meta [Terms](https://dev.meta.ai/legal/terms-of-service), §4.1, require necessary rights under applicable data-protection laws, §5.1 says Standard request content is not used to train Meta Models, and §4.4 permits specified retention. These statements do not themselves prove this product has user authorization, a privacy notice, route configuration, or account eligibility.
- No code currently produces a confirmed diagnosis or treatment advice, and there are no numeric-confidence reply templates. When added, preserve KB-only treatment text and the spec's uncertainty/safety-line requirement.
- The project has no API client, timeout/retry/fallback path, trace store, data-retention implementation, output-schema validator, or integration tests. These are future-phase gaps, not implemented failures, and should be addressed before any end-user integration.

## Test result

Command: `python3 -m pytest`

Result before review edits: **25 passed**, 0 failed, 0.03s, Python 3.12.0 / pytest 8.3.3.

Earlier baseline after the `.env.example` DATA_POLICY example/test update: **26 passed** (Phase 0.1 session log). Phase 0.3 adds the policy unit tests; the current run result is recorded in its session log and DAILY_LOG. No live calls were made.

## Phase 0.3 verification blockers

- **VERIFIED:** Muse Voice Transcribe documentation explicitly lists Hindi among 25 supported languages. This does not establish agricultural-vocabulary accuracy.
- **VERIFIED:** Contributor Services must not receive personal information; Meta directs personal-information use cases to Standard Services. Standard does not mean zero retention.
- **UNVERIFIED:** Complete official hackathon rules, event credit amount/allocation/expiry/model eligibility, account-specific billing state, ZDR for this account/model, Telegram OGG direct format support, and exact media limits.
- **Readiness:** NO-GO for live API testing. No official account credit entitlement was verified, full event rules were not accessible, this product has no privacy notice/authorization flow, and there is no sender integrated with the gate.

## Git identity and staging controls

- No local Git identity existed because the repository did not yet exist. A global Git identity was already configured; it was not changed or invented. The identity value is omitted from this report.
- `.gitattributes` keeps the source PDF and PNG as binary assets in Git diffs. `.gitignore` is tightened for env variants (while preserving `.env.example`), credential files, local Muse/Codex auth state, logs, local databases, private-data/upload/recording directories, media, caches, and evaluation outputs.
- The official spec PDF and supporting PNG are included as ordinary source documents. Generated evaluation data/results and secrets/private media are excluded.
- The staging review is documented in the session log; no secret-scan output contained values.
