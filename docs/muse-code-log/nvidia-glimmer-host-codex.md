# NVIDIA hosted Muse Glimmer 30B host selection — Codex

Date: 2026-11-04. Scope: offline implementation and mocked tests only.

## Changes

- `config/models.yaml`: NVIDIA selected through `glimmer_host.choice`; Together
  remains selectable. Host profiles carry endpoint, model ID, credential
  environment variable, and prices. Existing timeout, max input estimate,
  max output tokens, and sample count are preserved. NVIDIA's `0.35`/`1.50`
  prices are nonzero UNVERIFIED ledger placeholders, not NVIDIA billed prices.
- `src/mydrak/live/guard.py`: resolves and validates the selected Glimmer
  profile before the existing spend/authorization guard; accepts the old flat
  Together config shape for compatibility.
- `src/mydrak/live/clients.py`: Glimmer uses the selected credential variable,
  host model/endpoint and trace label. `src/mydrak/live/provider_contract.py`
  treats null final content as empty for downstream schema validation and reads
  only `message.content`; reasoning fields are not retained or traced.
- `scripts/smoke_glimmer.py`: description now refers to the configured host; it
  still delegates to the existing guarded shared smoke runner.
- `.env.example`: added only a blank `NVIDIA_API_KEY=` placeholder and comment.
- `README.md`, `scripts/README.md`, and this log describe NVIDIA selection,
  process-environment key handling, placeholder prices, privacy limits, and
  UNVERIFIED status. Added `docs/providers/nvidia_glimmer.md` from task-supplied
  information, explicitly labeling that information as not freshly verified.
- Tests cover default NVIDIA selection, Together selection, profile credential
  routing, guard refusals, missing NVIDIA key, empty/null content, reasoning
  suppression, and offline-only mocked transport behavior.

## Unverified

No external documentation was fetched and no live request was sent. NVIDIA's
image data-URL format, response usage/token fields, reasoning field behavior,
rate limits, retention/logging, free-tier terms, account eligibility, billing,
and compatibility remain UNVERIFIED. Do not send private farmer photos to
NVIDIA until its privacy and retention terms are reviewed. The Glimmer client
continues to require rights-cleared public-test image inputs. Spark, SAM, and
ledger behavior were not changed.

## Verification

- Focused: `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_config.py tests/test_live_guard.py tests/test_live_clients.py tests/test_live_smoke.py tests/test_live_smoke_diagnostics.py -q` — exit 0, **88 passed**.
- Full suite: `python3 -m pytest -q` — exit 1, **1285 passed, 11 failed**.
  All 11 failures are in `tests/test_telegram_http_transport.py`; the test
  server cannot bind `127.0.0.1` in this environment (`PermissionError: [Errno
  1] Operation not permitted`). These loopback tests therefore remain
  unverified here; this is not evidence of a provider/network request.
- Syntax: `PYTHONDONTWRITEBYTECODE=1 python3 -m compileall -q src tests eval` —
  exit 0.
- Config: `python3 -c 'import yaml; from pathlib import Path; p=Path("config/models.yaml"); d=yaml.safe_load(p.read_text()); assert d["glimmer_host"]["choice"] == "nvidia"; assert set(d["glimmer_host"]["profiles"]) == {"nvidia", "together"}; print("parsed config/models.yaml; selected=nvidia; profiles=nvidia,together")'`
  — exit 0; selected profile and both profiles parsed as expected.
- Whitespace: `git diff --check` — exit 0.
- Safe pattern scan over 14 task-related files — exit 0, one match at
  `tests/test_live_clients.py:29`; it is a synthetic test credential fixture,
  not a real credential. The matched text was suppressed. `.env` was excluded.

The smoke script uses the repository's fixed ignored ledger path and does not
accept a `--ledger` option. If the user separately authorizes a smoke test, the
command shape is:

```sh
export NVIDIA_API_KEY="<paste in your own terminal>"
MYDRAK_LIVE=1 python3 scripts/smoke_glimmer.py --live-authorized --max-spend-usd <CAP>
```

This command was not run. It still requires the user's separate live-test
authorization and the existing local spend ledger.
- No smoke script, live call, dependency install, staging, commit, or push was
  performed. `.env` was not read; the local spend ledger was not accessed.
