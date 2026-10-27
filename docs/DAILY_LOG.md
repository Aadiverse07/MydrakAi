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
