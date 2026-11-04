# Guarded SAM 3.1 client and smoke CLI — Codex

Date: 2026-11-04. Offline implementation and mocked tests only.

## Changes

- `config/models.yaml` SAM section now carries the configured `META_API_KEY`
  environment-variable name, request path `/responses` (SDK-convention
  inference, UNVERIFIED), and a 2 MiB project-local response-byte cap. Existing
  model, base endpoint, price, timeout, and input-token bound were preserved.
- `src/mydrak/sam/live_client.py` constructs the specified one-message,
  `input_text`/`input_image`, `stream: true` request; makes a JPEG data URL;
  incrementally collects SSE `response.output_text.delta` text; bounds bytes;
  reports fixed failure categories; reserves the per-image estimate via the
  shared spend ledger; and requires the existing durable SAM campaign guard as
  well as the shared CLI/env/key/cap/ledger gates. No retries or fallback.
- `src/mydrak/sam/http_transport.py` is the explicit stdlib `urllib` streaming
  transport, with redirects disabled so bearer credentials are not forwarded
  to a redirect target. It is not imported by or selected from `sam.transport`'s
  fake default. `run_scan()` and `FakeSamTransport` were not changed.
- `scripts/smoke_sam.py` creates a small synthetic red-square JPEG in memory,
  sends one guarded call, and prints only status metadata. `--show-structure`
  prints structural types/keys/list/string lengths without raw output text.
- `src/mydrak/live/guard.py` gained a fixed estimated-cost reservation helper
  sharing the existing live gates and SQLite ledger; token-priced behavior
  remains unchanged. Tests cover its checks and accumulation.
- `tests/test_sam_live_client.py` covers request shape, data URL, split/multiple
  SSE deltas, ignored fields, `[DONE]`, error/empty/malformed/oversize streams,
  parser failure, failure redaction, shared and campaign guard refusals, config
  validation, exact reservation, and structure-only output.
- README/script docs describe the client while retaining SAM NO-GO.

## Parser boundary and unresolved items

SSE delta content is passed directly to `parse_response_text`, which expects the
single-image special-token grammar: `<0f>` followed by records of unsigned
object ID, `<|box;x1=...;y1=...;x2=...;y2=...;w=...;h=...;c=...|>` (confidence
optional), then `<|mask;x=0;y=0;c=...;data=<H>,<W>,<enc>payload|>` (confidence
optional); mask payload remains opaque. No `SamFrame` is treated as a decoded
mask or severity result. `parse_response_envelope` handles non-stream JSON
envelopes, not already-extracted SSE deltas; `parse_sam_output` handles the
project-local synthetic JSON fixture grammar, not provider output. Applying
either here would guess a format, so neither was used. A mismatch is a typed
`parse_invalid` failure.

The supplied provider note itself marks the `/responses` path, Bearer auth,
inline data-URL image input, terminal event names, event error schema, and live
response compatibility UNVERIFIED. Account eligibility, billing behavior,
image constraints, retention/privacy, Base85 decoding, and decoder compatibility
also remain UNVERIFIED. The smoke requires an already-authorized persistent SAM
campaign (`sam-live-smoke`, scope `synthetic-red-square-smoke`) in addition to
the standard CLI/environment/cap/ledger gates; no helper or authorization was
created here.

## Verification

- Baseline before Part A: `python3 -m pytest -q` — **1296 passed**.
- Focused: `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_sam_live_client.py tests/test_sam_client.py tests/test_live_guard.py tests/test_sam_live_guard.py -q` — **260 passed**.
- Part A full suite: `python3 -m pytest -q` — **1328 passed**.
- No smoke script or provider call was run. No `.env` or credentials were read; no dependency, ledger, or Git staging/history operation occurred.
