# Phase 2 planning readiness — SAM 3.1

**Date:** 2026-10-27 (Asia/Kolkata)
**Scope:** Approved documentation-only changes; SAM remains **NOT IMPLEMENTED**.

## Authorization boundary

Phase 2 planning and offline/mock parser work with synthetic fixtures only are
authorized. This update adds no application code and authorizes no API call,
media upload, credential test, or credit use. No private farmer images, audio,
or derived personal data may be used in offline fixtures or sent externally.
The existing privacy gate is not wired to an outbound sender. Any future send
must be denied before request construction reaches a network, upload, or SDK
unless route, rights/provenance, user authorization, privacy notice, and the
applicable external-processing policy are verified. `DATA_POLICY` is not
consent or evidence of provider eligibility.

## Official verification recorded

- [SAM overview](https://dev.meta.ai/docs/sam/overview) documents `sam-3.1` on
  `POST /v1/responses`, with a user message containing an `input_text` concept
  or box/point prompt and an `input_image` or `input_video`. It documents MP4
  and MOV video with H.264, H.265, or MPEG-4.
- [SAM output grammar](https://dev.meta.ai/docs/sam/reading-segmentation)
  describes special-token text in `output_text`, one record line for an image
  or per frame for video, with object IDs, boxes, and masks. Empty output is a
  valid zero-match result.
- [Generic file handling](https://dev.meta.ai/docs/file-handling) lists image
  MIME types and 50 MB inline / 1 GiB Files API size limits. These are generic
  API limits, not verified SAM-specific limits.
- [Pricing](https://dev.meta.ai/docs/pricing-rate-limits) lists $2.50 per 1,000
  SAM images and $0.20 per 1,000 video frames, with a 50-frame minimum per
  video request and 3,000 requests per minute per team. Price does not prove
  credit eligibility.
- The [hackathon page](https://dev.meta.ai/events/global-hackathon) mentions
  SAM 3.1 but does not establish this account's credit amount, model eligibility,
  allocation, or expiry.
- [Terms](https://dev.meta.ai/legal/terms-of-service) distinguish Standard
  no-training from retention allowed for defined purposes. [ZDR help](https://dev.meta.ai/help/policies-and-privacy/zero-data-retention) says ZDR
  requires qualified account enablement, may vary by model, and excludes some
  features.

## Explicit unresolved items

- SAM-specific still-image format, dimensions, and payload limits:
  **UNVERIFIED**.
- User/account eligibility, amount, allocation, and expiry of credits for SAM:
  **UNVERIFIED**.
- Whether ZDR is enabled for this account and supported for the intended SAM
  request; applicable account-/SAM-specific retention status:
  **UNVERIFIED**.
- No claim is made that Meta supports agricultural/Hindi concept prompts at a
  particular quality or that segmentation provides diagnosis/severity.

## Checks

Executed in this run:

- `python3 -m pytest`: **79 passed, 0 failed**.
- `python3 -m compileall -q src tests`: **passed**.
- Python `tomllib` parsing of `pyproject.toml`: **passed**.
- `yaml.safe_load` for all 3 `config/*.yaml` files: **passed**.
- `git check-ignore -q .env`: **passed**; `.env` is ignored.
- `git ls-files --error-unmatch .env`: did not match; `.env` is untracked.
  Its contents were not read or printed.
- Safe secret-pattern scan across the six changed documentation files:
  **passed**, no matches; no values were emitted.
- `git diff --check`: **passed**.

The source PDF exists, but this environment has neither the `pymupdf` Python
module nor `pdftotext`, so its content was not extracted in this run. No
application source or tests were modified.

No API calls, media uploads, credential tests, billing changes, or credit use
were made for this work.
