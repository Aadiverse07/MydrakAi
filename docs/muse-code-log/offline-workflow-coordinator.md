# Offline workflow coordinator

Date: 2026-10-29

## Specification basis and selection

Implemented a minimal coordinator for the existing offline components. The
master spec B1/B3/B7 calls for a guarded case flow, honest uncertain/referral
paths, and bounded KB follow-up; T16 caps follow-up at two turns. Inspection
found no existing module connecting intake, the offline SAM chain, replies, and
the follow-up state. The current SAM chain cannot establish a diagnosis, so
its outcomes must not produce a disease answer.

## Behavior and acceptance

- Reuse `process_intake`; a blocked policy result stops before parsing the SAM
  fixture and returns no farmer reply.
- Accept only a labeled synthetic SAM fixture. The intake mock finding is
  discarded. Zero detections route to referral; all other parser outcomes
  route to manual review with referral text. Severity is always `None`.
- Reuse the existing follow-up transitions for a caller-selected KB question;
  answer contents are not retained or interpreted.
- Unsupported language, invalid descriptor/provenance, and missing reply data
  fail closed. No sender, API, media, credentials, or external processing is
  exposed or invoked.

## Files

- Added `src/mydrak/workflow/coordinator.py` and
  `tests/test_workflow_coordinator.py`.
- Updated `docs/DAILY_LOG.md`.

## Verification

- Focused coordinator/intake/SAM/reply/follow-up tests: 101 passed.
- Full suite: 606 passed with bytecode and pytest cache generation disabled.
