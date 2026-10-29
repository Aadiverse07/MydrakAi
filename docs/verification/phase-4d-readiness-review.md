# Phase 4D readiness review: privacy, eligibility, and cost (offline)

**Date:** 2026-10-28. **Scope:** evidence review ONLY, from repository
records. No network access was used; no page was re-fetched. This
document authorizes no live test. Live SAM remains **NO-GO**.

Labels: **VERIFIED IN REPO** (current code/tests), **OFFICIAL SOURCE
RECORDED** (repository already records a specific official source),
**PROJECT-LOCAL ASSUMPTION** (internal design choice), **UNVERIFIED**
(not established), **BLOCKED** (must resolve before a live test).

## Evidence table

| # | Item | Label | Supporting evidence | Evidence needed to resolve |
|---|---|---|---|---|
| 1 | SAM model eligibility for this account/team | UNVERIFIED | No account evidence anywhere in repo (matrix, readiness §3) | Account/team record of `sam-3.1` access |
| 2 | Resolved model identifier (`sam-3.1` vs `sam-3-1`) | UNVERIFIED | Discrepancy recorded, unresolved (matrix, readiness §2/§9) | Official confirmation of the API model ID |
| 3 | API access prerequisites (key provisioning, request shape) | OFFICIAL SOURCE RECORDED (interface) / UNVERIFIED (this account) | Matrix/readiness cite Overview + auth docs for Bearer scheme and `POST /v1/responses`; no credential was inspected or tested during this offline review; actual credential existence and account usability are UNVERIFIED | Provisioned key handling procedure + access proof |
| 4 | Credential handling rule (env-only, never logged/committed) | VERIFIED IN REPO | `AGENTS.md` safety rules; gate/tests keep secrets out of errors/traces; `.env` ignored + untracked | None (rule in force) |
| 5 | Credit availability, expiry, model coverage | UNVERIFIED | Event page gives no per-account entitlement (matrix); reported balances are user-reported only | Current account billing evidence |
| 6 | Billing exposure and spend controls | BLOCKED | Published prices recorded, but alerts are not hard caps (readiness §9); guard cannot enforce spend (guard docstring); no cap mechanism exists | Reviewed billing state + explicit charge acceptance + a real cap (none exists today) |
| 7 | Rate limits (3000 RPM/team) | OFFICIAL SOURCE RECORDED | Pricing page as recorded (readiness §2) | None for the fact itself; account-specific standing UNVERIFIED |
| 8 | Still-image formats, dimensions, payload ceilings for SAM | UNVERIFIED | SAM guide gives video limits only (matrix Phase 4B, readiness §9); generic file limits not established as SAM-specific | Official SAM-specific confirmation |
| 9 | Test-image authorization (rights, provenance, approval) | UNVERIFIED | No image-approval record was found in the documents reviewed; synthetic fixtures carry no rights burden; rights and approval status stay UNVERIFIED | Rights-cleared non-personal image + documented approval |
| 10 | Image handling: who receives images/prompts, what is stored where | UNVERIFIED | No recipients fixed (privacy-questions doc §§1–2) | Named recipient + storage inventory |
| 11 | Retention, deletion, ZDR eligibility/status | UNVERIFIED | Standard terms allow defined retention (recorded); ZDR needs qualified enablement, never inspected | Account/model ZDR evidence + retention schedule |
| 12 | Privacy notice and user consent flow | UNVERIFIED | No notice published or approved; no product flow; env flags are not consent (gate docs, readiness §3) | Shipped notice + per-request authorization mechanism |
| 13 | Image rights and third-party-processing disclosure | UNVERIFIED | Same gap as 9, 12; contributor route prohibited for personal data (recorded terms) | Rights evidence + disclosure wording |
| 14 | Provider errors, timeouts, ambiguous outcomes | PROJECT-LOCAL ASSUMPTION (offline behavior) / UNVERIFIED (provider) | Timeouts → counted attempt + manual review, no retries: VERIFIED IN REPO (`transport.py` + tests). Provider-side shapes: no evidence | Official error/timeout contract + authorized live observation |
| 15 | Retry policy and cost implications | PROJECT-LOCAL ASSUMPTION (policy) / UNVERIFIED (provider) | Zero-retry smoke rule + B11 ≤2 policy recorded (contract §C as narrowed); provider semantics unknown | Official retry/failure/cost semantics |
| 16 | Mock/live separation at every layer | VERIFIED IN REPO (offline layers) | Exact-fake gate, reply-contract checks, enforced provenance marker, no live client (code + 46 tests) | Live-layer proof impossible before a live path exists |
| 17 | Conditions for authorizing any live test | BLOCKED | Contract §E checklist + readiness §10 gates: every item unsatisfied | Satisfy each gate with evidence, then separate direct authorization |

## Remaining blockers (all must clear)

Account access + resolved model ID; rules review; credits/expiry/eligibility + billing exposure acceptance; rights-cleared image + approval; notice + per-request authorization on a verified Standard route with a retention/ZDR decision; SAM media limits; offline-validated decoder adapter; one-call guard with retries disabled; separate direct authorization. No partial credit: a single open blocker keeps the decision NO-GO.

## Required decisions (owner)

- Approve or rewrite the (still draft, unapproved) privacy notice before any external data flow (existing §10 gate).
- Designate who may issue campaign approval tokens and how charge acceptance is recorded.

## Go/no-go checklist

- [ ] All §E/§10 gates evidenced (currently 0 of 10 satisfied)
- [ ] Privacy-notice wording approved (existing §10 gate)
- [ ] Separate direct live-test authorization recorded

**Decision: NO-GO.** Documentation completeness does not constitute
readiness; every live path remains unbuilt. Official-source claims
previously recorded in project documentation were not freshly verified
in this review, and all account-specific external conditions remain
UNVERIFIED or BLOCKED.
