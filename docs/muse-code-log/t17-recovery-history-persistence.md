# T17 — Recovery-history persistence

## Specification basis

The master specification's B5 (PDF p. 8) says to store each scan with farmer
hash, farmer-chosen plant label, timestamp, `severity_pct`, and image hash; on
a re-scan of the same plant label compute the severity delta in percentage
points. It defines `spreading` above the positive margin, `improving` below the
negative margin, otherwise `no_clear_change`, with a configurable 3pp default.
It requires a caveat that angle, light, and distance change measurements and
forbids claiming treatment worked (“the photo suggests improvement”). C2 T17
(PDF p. 13) acceptance is delta and margin logic tests. B9 defines the SQLite
`scans` fields and hashed-ID/raw-image storage boundary. It gives no scan
retention period.

## Implementation

- Extended the existing `TraceStore` SQLite database with B9's `scans` table;
  there is no parallel database. Inserts use `BEGIN IMMEDIATE`, require an
  existing case with the same hashed user ID, and return the previous scan
  atomically.
- Added `src/mydrak/recovery/history.py` and package exports. Each record
  accepts only lowercase SHA-256-shaped user/image digests, exact farmer-chosen
  label, timezone-qualified timestamp, finite 0–100 severity, scan ID, and
  linked case ID. Raw images and raw user IDs are not accepted by this API.
- Re-scans compare exact `(user_hash, plant_label)` pairs. UTC-normalized
  timestamps must strictly increase; duplicate scan IDs and out-of-order or
  same-time scans fail closed. The default 3pp and caller-supplied margins use
  the existing `sam.severity.recovery_trend()` helper.
- The assessment exposes a stable required-caveat key and
  `treatment_effect_claim_allowed=False`. It does not compose or send user-facing
  recovery text: no reviewed localized caveat template exists, and the current
  offline coordinator has no validated real severity source.

These are local defensive details where B5 does not specify representation:
lowercase 64-character SHA-256 hex is the accepted digest format; timestamps
must carry a timezone and are normalized to UTC; plant labels are stored
verbatim, matched exactly, and limited to 256 characters. No retention period
or automatic deletion policy was invented. Persistence remains a deployment
privacy decision because B5 does not specify how long scan rows are retained.

## Tests and verification

- `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_recovery_history.py tests/test_trace_store.py tests/test_workflow_coordinator.py` — **48 passed**.
- `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider` — **825 passed**.
- `python3 -m compileall -q src tests eval` — exit 0.
- TOML/YAML/JSONL parsing and `git diff --check` — exit 0; 1 TOML, 4 YAML,
  and 1 JSONL files parsed.
- Scoped safe secret scan — 0 matches, values suppressed; scoped whitespace
  scan — 0 findings. `.env` is ignored and untracked by Git metadata only; it
  was never read.

No APIs, network, uploads, credentials, credits, dependency installation,
staging, commits, pushes, or history operations occurred.

## Status and remaining work

T17 is **PARTIAL**, not complete. Persistence and delta/margin calculation
are available through the shared SQLite store. A workflow must still supply
validated severity from a supported image/SAM path, carry scan history into a
farmer rescan interaction, and deliver the required caveat through reviewed
localized templates. The scan-row retention policy must be decided before
deployment. Live SAM remains **NO-GO**.
