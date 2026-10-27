# Daily log

## 2026-10-27 — Phase 0: repository foundation

- What changed: created minimum scaffold (AGENTS.md, README.md, pyproject.toml,
  .gitignore, .env.example, config/*.yaml with UNVERIFIED placeholders,
  src/mydrak package with pure foundation modules, kb/cards/general_safety.yaml,
  tests/, eval/ + dashboard/ + scripts/ placeholders, docs/architecture.md).
- What is broken: nothing executable yet beyond foundation functions; all
  integrations UNVERIFIED (no smoke tests run — forbidden in Phase 0).
- What is next: single next task per spec is T02 (smoke scripts per Meta
  endpoint) — requires user approval + API keys; do NOT start in Phase 0.

## 2026-10-27 — Phase 0.1: security and official verification

- What changed: hardened `.gitignore`; changed `.env.example` DATA_POLICY default from `public_test` to fail-closed `private`; added a regression test; added official Meta API, hackathon rules, credit protection, and Phase 0 review reports under `docs/verification/`; recorded this session in `docs/muse-code-log/`.
- What is broken/unverified: full hackathon Official Rules document was not available from official pages; credit allocation/expiry and account eligibility remain unknown; exact ₹1,000 billing setting is account-specific and unverified; max payload/output constraints and Hindi-specific voice support need confirmation. No integrations exist.
- What is next: obtain/read the complete Official Rules and confirm the dashboard credit/threshold labels manually; implement a fail-closed policy gate and structured card validation before any integration. Do not run a live API test until separately approved.

## 2026-10-27 — Phase 0.2: verified Git integration policy

- What changed: documented Muse Code implementation/Codex verification gates in `AGENTS.md`; added `docs/verification/git_workflow.md`; reconciled the local foundation root and GitHub's independent LICENSE root on `integration/git-workflow`, preserving both commits; published the verified branch and fast-forwarded GitHub `main` to the verified result.
- What is broken/unverified: no Git workflow blockers remain after the verified push. Meta API and hackathon verification blockers from Phase 0.1 remain unchanged; no live integration is authorized.
- What is next: continue with the remaining official rules/credit verification and fail-closed data-policy work before planning any live API test.

## 2026-10-27 — Phase 0.3: verification blockers and fail-closed data policy

- What changed: rechecked official Meta terms, Contributor restrictions, speech-to-text documentation, and the event page; verified Hindi listing for Voice Transcribe and documented Standard/Contributor data handling. Added a pure, no-network policy gate for private/public-test classifications with explicit route, rights, provenance, authorization, and notice checks. Added unit tests and updated the existing verification reports and Phase 0 review.
- What is broken/unverified: no outbound client exists or is wired to the gate. Full hackathon Official Rules, participant credit eligibility/expiry, account-specific billing/ZDR status, and Telegram OGG support/media limits remain unresolved. The product has no privacy notice or user authorization flow, so private processing remains blocked in practice.
- Checks: recorded in `docs/muse-code-log/phase-0.3-verification-and-data-policy.md` after the local verification run. No Meta API calls, uploads, credentials, billing changes, or credit usage.
- What is next: review the full official rules and credit terms when available; build any future sender only with a pre-transmission gate and verified route, legal rights, and user-facing privacy disclosures. No live API testing until blockers and product readiness are resolved.
