# Offline English-first reply composer

Date: 2026-10-29

## Task and source

Implemented the next offline slice of master-spec T07, the reply composer
(Part B7/C2). The roadmap explicitly says “English first”; reply outcomes are
answer, ask, refer, and retake. The existing safety card supplies referral,
retake, and safety text, but has no disease card or reviewed Hindi text.

## Acceptance and result

- Render deterministic English answer/ask/refer/retake messages from supplied
  structured data and card text; use selected KB follow-up questions and
  low-risk steps only.
- Require the fixed confidence vocabulary; include the safety line in answer
  replies; label supplied severity as an estimate from one photo without
  calculating or rounding it.
- Reject missing or malformed fields and unavailable Hindi templates without
  returning placeholder or unreviewed text.
- No diagnosis, treatment, translation, provider behavior, or real-world
  accuracy is inferred. Tests use explicitly synthetic KB fixtures; the
  repository's actual general-safety card is exercised for referral and retake.

## Files

- Added `src/mydrak/reply/composer.py` and `templates.py`.
- Added `tests/test_reply_composer.py`.
- Updated `docs/DAILY_LOG.md`.

## Verification

- Focused reply/KB tests: 30 passed.
- Full suite: 583 passed.
- Both pytest runs used `PYTHONDONTWRITEBYTECODE=1` and disabled pytest's cache.

## Remaining work

T07 is not complete: reviewed Hindi templates, disease-card content, and
end-to-end bot delivery are absent. Hindi rendering fails closed. No API,
network, credential, upload, or credit activity occurred.
