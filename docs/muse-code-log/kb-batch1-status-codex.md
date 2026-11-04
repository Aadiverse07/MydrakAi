# KB Batch 1 status clarification — Codex

Date: 2026-11-03

Updated `kb/cards/README.md` with the Batch 1 status supplied for this work. The
ten drafts cite printed pages across four ICAR PDFs according to the supplied
provenance; Codex did not inspect the owner-held PDFs. All cards remain drafts
and both languages remain unreviewed; agronomy and native Hindi review are
pending.

Recorded checks actually run: `load_disease_card()` accepted all ten cards;
`PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider
tests/test_disease_card_schema.py tests/test_kb_loader.py
tests/test_disease_cards_batch1.py -q` passed 136 tests; the later full suite
`PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider -q` passed
1274 tests. These checks establish structural/test behavior, not agricultural
accuracy or PDF claim support.

The repository now has an explicit default-off, English-only draft-preview
mode. It uses the exact draft banner, refuses synthetic fixtures, and is
refused in public mode. The Telegram photo-consent implementation is also
default-off, requires a shown current notice and active per-user consent, and
does not change any card or registry fields. Hindi content remains unreviewed;
the consent notice Hindi slot is UNREVIEWED and not served. The notice still
states that this build uses synthetic/mock SAM locally because the repository
does not verify transmission to a live SAM service.
