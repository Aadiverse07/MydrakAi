# Default-off KB draft preview — Codex

Date: 2026-11-03

Added `config/reply.yaml` with `demo_draft_preview: false`. Ordinary
`compose_reply()` and `begin_followup()` retain the strict gate: the card must
be verified and both language review states must be `REVIEWED`. With explicit
preview enabled in non-public mode, only an unchanged, structurally valid draft
loaded from `kb/cards/` can be rendered for English `answer` or `ask`, with the
exact `DEMO DRAFT: not reviewed by an agronomist. Do not use for real farming
decisions.` banner on its own first line. The synthetic fixture and altered
card mappings are rejected. Hindi remains unavailable/unreviewed. Public mode
refuses preview both at reply/follow-up boundaries and in Telegram runner
startup. Referral and retake safety-card rendering remains unchanged.

To enable locally, edit only the local demo setting `config/reply.yaml` to
`demo_draft_preview: true`, then pass the source path when rendering a draft:

```python
card_path = "kb/cards/tomato_early_blight.yaml"
card = load_disease_card(card_path)
reply = compose_reply(
    "answer", card=card, card_path=card_path, safety_card=safety_card,
    confidence="not sure",
)
```

Do not enable preview in public mode. This switch does not change card YAML,
registry records, review state, or reviewer metadata. Preview is for demo only;
it does not approve agricultural claims. Phase 4 is **NOT FULLY CLOSED**;
agronomy and native-speaker Hindi review remain pending.

Verification:

- Focused: `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_reply_preview.py tests/test_reply_composer.py tests/test_followup.py tests/test_telegram_runner.py tests/test_workflow_coordinator.py -q` — exit 0, **84 passed**.
- Full suite: `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider -q` — exit 0, **1283 passed**.
- `git diff --check` — exit 0.
