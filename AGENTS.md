# Mydrak AI v3 — agent rules (Phase 0)

Source of truth: `docs/MydrakDeepseekreformed.pdf` (Final Master Specification).
Supporting reference: `docs/MydrakDeep.png`. If code and spec disagree,
ask or propose a spec change. Current phase: **Phase 0 (foundation only)**.

## Orientation

Read `AGENTS.md`, `docs/architecture.md`, `docs/DAILY_LOG.md`, and the
relevant spec section before starting. State the task, the files you will
touch, and the acceptance test before editing.

## Process

- Small tasks. One task, one commit, a clear message.
- Add or update tests with each change. Run the test suite before declaring done.
- No unrelated refactors. No new dependency without stating why and noting it
  in `pyproject.toml`.
- Export or save the session log to `docs/muse-code-log/` at the end of each session.
- Update `docs/DAILY_LOG.md`: what changed, what is broken, what is next.
- If blocked for more than 20 minutes, stop and report the blocker with two options.
- Phase 0 only: do not start the Telegram bot, model integrations, SAM
  integration, or dashboard implementation.

## Correctness and honesty

- Never invent API parameters, model IDs, or prices. Read the docs or run the
  smoke script. If unknown, add `TODO(verify)` and tell the user.
- Model IDs and prices live only in `config/models.yaml`.
- Never generate treatment, dosage, chemical, or mixing advice from model output
  or memory. Treatment text comes only from `kb/cards/*.yaml`.
- Never write code that reports a model guess as a confirmed diagnosis. Every
  reply carries an uncertainty statement and the safety line.
- Never tune thresholds on `eval/data/test`. Use dev only.
- Never fabricate evaluation numbers, test results, screenshots, or logs.
- Mark every unverified detail as `UNVERIFIED`.
- Do not hardcode Hindi strings in logic; user-visible text lives in `reply/`
  templates with Hindi and English side by side.

## Safety and secrets

- Secrets only in `.env`. Never commit keys, tokens, or farmer images.
- Respect `DATA_POLICY`: private photos go only to the non-contributor model variant.
- Never make a live model call or consume API credits during Phase 0.
- Do not send private farmer photographs to a model before verifying its
  applicable data policy and model variant.
- Every external call has a timeout, at most 2 retries, and a defined fallback (B11).
- Log a trace for every case. No raw personal data in logs.

## Code quality

- Python 3.11+, type hints, small modules, no file over about 300 lines.
- `decider` stays small and readable (about 150 lines) with pure functions for
  signals and policy. It must stay independent of network calls and testable.
- Validate all model outputs against schemas before use.
- Prefer plain functions and dataclasses over frameworks.

## Session bootstrap prompt

```text
You are building Mydrak AI, a Hindi voice-first crop health assistant on Telegram, for the
Meta Global AI Developer Hackathon (Indie track, Theme 1). Read AGENTS.md, docs/architecture.md
and the Mydrak master spec first. Today's task: <TASK ID AND TITLE>. Acceptance test: <TEST>.
Follow AGENTS.md strictly. Do not invent API details; verify with docs or smoke scripts.
Treatment advice comes only from the knowledge base. Keep changes small, add tests, update
DAILY_LOG.md, and save the session log to docs/muse-code-log/.
```

## Git integration and publishing

- Muse Code implements project changes; Codex independently reviews and verifies them. Do not rely on an implementation summary instead of inspecting the actual diff.
- Do not claim to monitor Muse Code in the background. Run this workflow when the user asks to integrate a completed batch.
- Before integration, inspect `git status`, branch and remote history, then review the complete unstaged and staged diffs. Preserve all existing local and remote changes.
- Use a dedicated `integration/<task-slug>` branch based on the intended current `main`. Stage only the intended files. Do not use `git add -A` for routine change batches.
- Scan candidate and staged files for secrets without printing values. Reject credentials, `.env`, agent authentication state, private farmer data, local databases, caches, and unintended generated evaluation outputs. Recheck `.gitignore` coverage.
- Run the existing test suite and applicable syntax, import, configuration, type-check, and lint commands. Report commands and actual results; an unavailable required check is blocked, not passed.
- Review the staged diff independently. Commit only scoped changes that pass the verification gate and comply with this file and the master specification. Update `docs/DAILY_LOG.md` and save a factual session log under `docs/muse-code-log/`.
- Publish the verified integration branch first when remote access permits. Merge into `main` only after verification. Prefer the repository's pull-request flow. If branch protection requires a pull request or approval, stop for that human action.
- Push `main` only when its current remote history is safely reconciled and the update is a normal fast-forward permitted by repository rules. Verify remote refs after every successful push.
- Never force-push, rewrite shared history, bypass protections, discard uncommitted work, or put credentials in remote URLs. If histories diverge or have unrelated roots, inspect both sides and stop for a safe reconciliation decision unless the user has explicitly authorized a preserving merge.
- Never make live Meta API calls, run live smoke tests, upload farmer media, change billing, or consume API credits as part of Git verification.
