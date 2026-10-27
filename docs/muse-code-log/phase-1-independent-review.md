# Independent review — Muse Phase 1 mock intake

**Date:** 2026-10-27 (Asia/Kolkata)
**Reviewed branch/commit:** `integration/phase-1-mock-intake` / `bae906d7260abec4f054e20973af15eba0f6169f`
**Review worktree after local remediation:** same branch, uncommitted changes in the intake adapter, its tests, and this review record/DAILY_LOG.

## Repository and ancestry

- Initial review state: clean worktree; local and remote Phase 1 refs both at `bae906d`; remote `main` both at `00f98f7`.
- `bae906d` is a direct descendant of Phase 0.3 commit `c987605`, itself a descendant of `main` at `00f98f7`.
- The preserved history contains merge commit `86dc8e7` with both original parent histories: foundation `4b360ae` and remote LICENSE root `c9b49ff`. Both are ancestors of the Phase 1 branch. The prior Phase 0.3 and Phase 1 remote branch refs remain present.
- A `git show-ref --remotes` inventory attempt failed because this Git version does not accept `--remotes`; no files or refs changed. The inventory was rerun successfully with `git for-each-ref` and `git ls-remote`.
- `.env` is present locally, ignored by `.gitignore`, and not tracked. Its contents were not read.

## Review findings and local remediation

The implementation accepts descriptor fields (`format`, `width`, `height`, `size_bytes`) and contains no actual media, but before remediation it silently ignored additional mapping keys, copied arbitrary caller-supplied `source` strings into trace output, echoed unsupported format text in errors, and raised `AttributeError` for a malformed `data_class`.

Local uncommitted fix:

- Require mappings to contain exactly the four descriptor fields; never accept extra raw-media fields.
- Remove caller-controlled source text from trace and response metadata.
- Do not echo an unsupported format value.
- Reject malformed data-class and evidence objects with `IntakeError` before any sender invocation.
- Add regression tests for these cases and exact/over-boundary validation.

The sender is an injected arbitrary callable. The repository does not provide a production sender or any network/model SDK. Policy-blocked requests return before the hook; tests use a local `Mock` and assert it is not called. A future caller could supply a callable with side effects, so this seam is not itself a guarantee that arbitrary callbacks are offline. Do not wire a real sender without the project's verified external-call controls.

## Checks actually run

- Baseline before remediation: `python3 -m pytest` — **72 passed**.
- After remediation: `python3 -m pytest` — **79 passed**, 0 failed.
- `python3 -m compileall -q src tests` — passed (exit 0).
- Python `tomllib` parse of `pyproject.toml` and PyYAML parse of all three `config/*.yaml` files — passed.
- `.env` ignored (`git check-ignore -q .env`) and not tracked (`git ls-files --error-unmatch .env` did not resolve); `.env` contents were not accessed.
- Read-only secret-pattern scan of branch-changed files — no candidate matches; values withheld.
- AST scan of imports under `src/` — no network, Telegram, model SDK, or subprocess imports found.
- `git diff --check` — passed.
- The initial one-off repro command without `PYTHONPATH=src` failed with `ModuleNotFoundError`; rerunning with `PYTHONPATH=src` reproduced the findings. This was only a local import-path issue.

No Meta or Telegram calls, uploads, authentication tests, billing changes, or credit use occurred. At the end of the original review turn, no merge, commit, push, PR, or update to `main` had been made. The later continuation outcome is reported in the current handoff.

## Handoff

At the end of the original review turn, remediation was uncommitted on `integration/phase-1-mock-intake` in `src/mydrak/intake/adapter.py`, `tests/test_mock_intake.py`, `docs/DAILY_LOG.md`, and this review record. This follow-up performs the user-authorized scoped commit and normal branch push. The ancestry already combines Phase 0.3 with the preserved foundation and LICENSE histories; avoid replaying or recreating those commits.
