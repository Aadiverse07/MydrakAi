# Git integration and GitHub publishing workflow

## Policy

Muse Code implements changes. Codex independently verifies the actual local changes. Only scoped, reviewed, safe changes that pass the applicable verification gate may enter `main` or be published there. Work happens when the user invokes integration; Codex does not monitor another session in the background.

## Before integrating a Muse Code batch

1. Confirm the repository root, clean/dirty state, current branch, recent commits, remotes, and remote `main` history. Do not assume local `main` is authoritative or that GitHub is empty.
2. Read the task acceptance criteria and relevant `AGENTS.md` and specification sections. Identify the exact files changed for this batch.
3. Inspect the complete unstaged diff and any untracked files. If implementation continues during review, preserve it and re-inspect the new diff before proceeding.
4. Reject unrelated files, generated noise, secrets, credentials, private farmer media/audio, personal data, local databases, caches, and unintended evaluation outputs. Run a secret scan that reports locations/types only, never values. Confirm `.gitignore` coverage.
5. Create or reuse `integration/<task-slug>` from the intended current `main` history. If local and remote histories diverge, inspect both. Do not reset, rebase shared history, force-push, or discard either side. For unrelated roots, pause unless the user explicitly authorizes a preserving merge.
6. Stage only intended files by explicit path. Inspect both `git diff` and `git diff --cached`; ensure the staged change matches the task.

## Verification gate

Run applicable checks before committing. At minimum:

```sh
git diff --cached --check
python3 -m pytest
python3 -m compileall -q src tests
```

Also run configured import, configuration, type-check, and lint checks where relevant. Do not invent checks or results. If a required check is unavailable or fails, stop the integration, preserve the work, and report the exact result. Never weaken tests just to pass the gate.

Review the staged code for specification compliance, regressions, unsafe behavior, guessed API interfaces, and privacy/data-policy violations. API details must come from verified official sources. No Git verification task may make a live API call, authenticate against the Meta API, upload media, or use API credits.

After checks pass, commit one scoped change batch with a descriptive message. Update `docs/DAILY_LOG.md` and write a factual session log in `docs/muse-code-log/`.

## Publish and integrate

1. Push the verified integration branch with a normal push, if authenticated and permitted. Never put credentials in a remote URL.
2. Use a pull request when repository policy requires one. Do not bypass branch protections or required reviews; report any human approval needed.
3. Merge into `main` only after the gate passes and the candidate branch is based on the current intended `main` history. For local fast-forward integration, verify both refs first and use a fast-forward-only merge.
4. Push `main` only with a normal fast-forward update that GitHub accepts. Never use `--force` or `--force-with-lease`.
5. Verify remote `main` and integration-branch refs after pushing, then report branch, commit hash, tests, push status, and remaining blockers.

## Current repository reconciliation

The initial local foundation commit and the pre-existing GitHub `main` license commit were unrelated roots. The user explicitly authorized combining them while preserving both histories. The reconciliation was made on `integration/git-workflow` as a merge commit; the existing local `master` and remote `main` commits remain intact. The policy change and subsequent publication still must pass the normal verification gate.
