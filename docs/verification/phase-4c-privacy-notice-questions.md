# Privacy-notice implementation questions (Phase 4C, 2026-10-28)

Status: working notes only. There is no published privacy notice, and
nothing here is legally approved. The codebase tracks a
`privacy_notice_present` evidence flag (`ProcessingEvidence` in
`src/mydrak/privacy/data_policy.py`) that a future product flow must set
from a real, user-visible notice — the flag itself is not a notice and
proves nothing.

Unresolved implementation questions (all must be answered before any
external image processing):

1. **Recipients.** Which services receive image data and prompts (model
   endpoint, logging/monitoring, error-reporting, hosting provider)?
   No recipient list has been fixed.
2. **Storage.** Are any images, prompts, or responses stored, and where
   (provider side, application traces, evaluation artifacts, backups)?
   Unknown for every future recipient.
3. **Retention and deletion.** What retention periods apply, who can
   delete what, and on what timeline? Nothing verified; do not promise
   deletion or any retention bound. ZDR status is UNVERIFIED for this
   account and every relevant model.
4. **Access controls.** Who can view submitted images and derived data
   (operators, reviewers, annotators)? No access model exists.
5. **Consent and privacy requirements.** What authorization and notice
   wording is required, when is it shown, and how is per-request consent
   recorded? The product has no authorization or notice flow; environment
   flags are not consent.

Explicit non-claims: ZDR is NOT enabled by anything in this repository;
no deletion/retention behavior is promised; private farmer photos remain
blocked by the fail-closed gate until per-request evidence exists.
