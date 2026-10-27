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
- **DATA_POLICY gap:** `.env.example` previously defaulted to `public_test`, and no runtime code currently enforces this variable or model mode. This review changes the example default to `private` and adds a test. Future implementation should fail closed: require an explicit data classification; treat all real user/farmer photos as private unless provenance proves synthetic/public and licensed; map private only to Standard/non-contributor routes; reject a contributor model or a host with unknown data terms; never infer privacy class from a filename; and fail before upload if policy/model selection is unknown. Public-test mode must be opt-in and restricted to known public/synthetic test assets.
- No code currently produces a confirmed diagnosis or treatment advice, and there are no numeric-confidence reply templates. When added, preserve KB-only treatment text and the spec's uncertainty/safety-line requirement.
- The project has no API client, timeout/retry/fallback path, trace store, data-retention implementation, output-schema validator, or integration tests. These are future-phase gaps, not implemented failures, and should be addressed before any end-user integration.

## Test result

Command: `python3 -m pytest`

Result before review edits: **25 passed**, 0 failed, 0.03s, Python 3.12.0 / pytest 8.3.3.

Result after the DATA_POLICY example/test update: **26 passed** (see the session log and DAILY_LOG for the final command result). No live calls were made.

## Git identity and staging controls

- No local Git identity existed because the repository did not yet exist. A global Git identity was already configured; it was not changed or invented. The identity value is omitted from this report.
- `.gitattributes` keeps the source PDF and PNG as binary assets in Git diffs. `.gitignore` is tightened for env variants (while preserving `.env.example`), credential files, local Muse/Codex auth state, logs, local databases, private-data/upload/recording directories, media, caches, and evaluation outputs.
- The official spec PDF and supporting PNG are included as ordinary source documents. Generated evaluation data/results and secrets/private media are excluded.
- The staging review is documented in the session log; no secret-scan output contained values.
