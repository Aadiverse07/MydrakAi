# Credit protection and billing limitations

**Accessed:** 2026-10-27 (Asia/Kolkata). No API call or account billing page was accessed. Billing dashboard values below are user-reported and not independently verified.

**Rechecked:** 2026-10-27. The official event page and current pricing documentation were revisited. The amount, eligibility by model/mode, allocation, and expiry of any participant credits remain **UNVERIFIED**; the current accessible event page does not provide these details.

## Phase 2 / SAM 3.1 planning status

SAM 3.1 is **NOT IMPLEMENTED**. Phase 2 planning and offline/mock parser work
with synthetic fixtures only are authorized; no API call, upload, credential
test, or credit use is authorized. The official pricing page lists SAM at
$2.50 per 1,000 images and $0.20 per 1,000 video frames, with a 50-frame
minimum for a video request. The official event page mentions SAM 3.1 among
the hackathon models but does not state the user's account credit balance,
SAM eligibility, allocation, or expiry. Therefore account-level credit
eligibility for SAM remains **UNVERIFIED**. Published price is not an estimate
of this user's out-of-pocket cost and does not establish credit coverage.

SAM-specific still-image media limits and account-/SAM-specific retention or
ZDR status are also **UNVERIFIED**. Generic Meta file limits are not assumed to
apply to SAM. Standard mode's no-training term is not a zero-retention promise;
ZDR requires separate organization-level enablement and may vary by model.
Before any separately approved external test, verify the account's exact credit
terms, charges/payment settings, model route, rights and privacy disclosures.
The spend-limit alert remains a notification, not a hard cap. This planning
authorization does not authorize that future test.

## Reported account observations

- User reports the Meta Model API dashboard showed **$149.65 in free credits** and **₹0.00 recorded spend**.
- User reports a payment method was displayed and a **₹1,000 payment trigger** appeared.
- These observations are not verified account facts. We did not use credentials, query an API, sign in to a browser, or change billing settings.

## What official sources establish

- The current [official event page](https://dev.meta.ai/events/global-hackathon), rechecked on 2026-10-27, does not state a per-account credit amount, model/mode eligibility, allocation, or expiry. Meta Model API Terms §13.3 ([Terms](https://dev.meta.ai/legal/terms-of-service)) say promotional credits may be provided to accounts and may expire as specified in the account or Supplemental Managed Account Terms; this does not identify hackathon credits or the user's entitlement. No user account was accessed. Treat the previously reported $149.65 as account-specific and **UNVERIFIED** until confirmed in the official account interface and applicable terms.
- Meta's [pricing page](https://dev.meta.ai/docs/pricing-rate-limits) describes pay-as-you-go costs: Spark Standard $1.25/1M input tokens, $0.15/1M cached input, $4.25/1M output; SAM 3.1 $2.50/1,000 images and $0.20/1,000 video frames (50-frame video minimum); Voice Transcribe $0.18/audio hour. These are current listed prices, not a guarantee about credits or the final amount charged for a particular request.
- [Billing help](https://dev.meta.ai/help/billing/api-bill) says charges accrue with use and the payment method can be charged when the payment threshold is reached or on the monthly bill date.
- [Spend-limit help](https://dev.meta.ai/help/billing/spend-limit-alert) explicitly says a spend-limit alert is **not a hard cap**; usage can exceed it and the user remains responsible for charges.
- The exact dashboard item described as a ₹1,000 “payment trigger” cannot be independently identified. Official help distinguishes an automatic **payment threshold** from a monthly **spend-limit alert**. Without seeing the exact label/settings, whether this account's ₹1,000 is a threshold or something else is **UNVERIFIED**. It must not be treated as a hard spending cap.
- [Muse Code subscriptions](https://dev.meta.ai/docs/muse-code/subscriptions) describes two separate paths: per-token pay-as-you-go through Model API/API keys, and optional flat-rate Muse Code subscriptions. The subscription applies only to Muse Code's connected credential; additional API keys remain pay-as-you-go. No paid subscription was purchased or changed.
- Muse Glimmer is open-weight and not billed by Meta Model API; a hosted inference provider may charge independently. Provider credits/policies are not confirmed here.

## Data mode and credit implications

Meta's [pricing and rate limits](https://dev.meta.ai/docs/pricing-rate-limits) say Contributor mode allows submitted content to be used to train future Meta models for discounted rates; Standard mode does not use content to train Meta models. Meta's [Terms of Service](https://dev.meta.ai/legal/terms-of-service) still allow retention for service provision, legal compliance, safety/security, abuse and policy review. Zero Data Retention is separately enabled for qualified organizations and may have model/feature limits. For private farmer images, the project rule requires Standard/non-contributor mode; do not use Contributor mode even if it is cheaper or credits apply.

| Exact question | Official source and passage | Status | Practical consequence |
|---|---|---|---|
| Does Standard mode mean zero retention? | [Terms](https://dev.meta.ai/legal/terms-of-service), §5.1 says Standard request content is not used to train Meta Models; §4.4 separately allows retention for service, legal compliance, rights, safety/security/abuse, and policy review/improvements. | **VERIFIED** (distinction); exact retention time **UNVERIFIED** | Do not promise deletion by Meta or describe Standard as ZDR. |
| Is ZDR active for this account and model? | [ZDR help](https://dev.meta.ai/help/policies-and-privacy/zero-data-retention) describes eligibility/enablement and model or feature limitations. No account inspection was done. | **UNVERIFIED** | Treat ordinary Standard retention terms as applicable. |
| Does the project have official confirmation that the user-reported $149.65 covers each intended model or mode? | [Hackathon page](https://dev.meta.ai/events/global-hackathon) and [pricing docs](https://dev.meta.ai/docs/pricing-rate-limits) do not establish the user's account entitlement. | **UNVERIFIED** | No test request; account entitlements must be confirmed separately before a future approved test. |
| Do the user's event credits cover SAM 3.1, and what are the amount and expiry? | The [official event page](https://dev.meta.ai/events/global-hackathon) names SAM 3.1 but gives no account-specific amount, SAM eligibility, allocation, or expiry; the [pricing page](https://dev.meta.ai/docs/pricing-rate-limits) states prices, not an entitlement. | **UNVERIFIED** | Do not infer credit coverage from the event page or reported dashboard balance. No SAM request or credential check. |
| Are SAM-specific image limits and ZDR/retention status established? | [SAM overview](https://dev.meta.ai/docs/sam/overview) does not state still-image payload limits. [Terms](https://dev.meta.ai/legal/terms-of-service), §§4.4 and 5.1, permit retention for defined purposes while excluding Standard data from training. [ZDR help](https://dev.meta.ai/help/policies-and-privacy/zero-data-retention) requires separately enabled qualified-account status and says model support may vary. | **UNVERIFIED** (SAM limits and account-/SAM-specific status) | Do not pass private media externally or claim ZDR; generic file limits are not SAM-specific evidence. |
| What controls promotional-credit amount and expiry? | Meta Model API Terms §13.3 ([Terms](https://dev.meta.ai/legal/terms-of-service)): promotional credits may be provided to Accounts; unused credits may expire within a set period stated in the Account or Supplemental Managed Account Terms. No account terms were accessed. | **VERIFIED** (general mechanism); user/event-specific amount, coverage, and expiry **UNVERIFIED** | Check the exact account entitlement before any separately approved test; do not infer it from the generic terms. |

## Conservative manual budget-check procedure before any future approved test

1. In the signed-in dashboard, record the account/team, free-credit balance, credit expiry and eligible services/models from the official UI/terms. Do not assume all listed models or partner hosts are included.
2. Identify the exact ₹1,000 setting by its dashboard label: payment threshold, spend-limit alert, or other. Treat any alert as notification only unless official billing terms say otherwise; current help says spend alerts are not hard caps.
3. Review billing method, current balance, current cycle, usage page and any unpaid amount. This review report does not change any setting.
4. Before a later, separately approved test, define a tiny fixed request count and maximum input/output/media size; use synthetic/public non-personal data, Standard mode, no retries, and no background or multi-step calls. Estimate using official prices and record the estimate.
5. Immediately before the test, recheck credits and spend. Immediately after the approved test, recheck requests/tokens/model usage, credits, balance and payment activity; compare actual usage with the estimate. Stop on any discrepancy.
6. Keep all future model calls disabled until the user explicitly approves a separate smoke-test task. This task made no live call.

## Sources

All accessed 2026-10-27:

- [Meta hackathon event](https://dev.meta.ai/events/global-hackathon)
- [Model API pricing and rate limits](https://dev.meta.ai/docs/pricing-rate-limits)
- [How am I billed for Model API?](https://dev.meta.ai/help/billing/api-bill)
- [How do I set a spend limit alert?](https://dev.meta.ai/help/billing/spend-limit-alert)
- [Muse Code subscriptions](https://dev.meta.ai/docs/muse-code/subscriptions)
- [Meta Model API Terms](https://dev.meta.ai/legal/terms-of-service)
- [Zero Data Retention](https://dev.meta.ai/help/policies-and-privacy/zero-data-retention)
