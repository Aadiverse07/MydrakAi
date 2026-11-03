# KB card inventory and source-intake rules

## Current inventory

- Batch 1 disease-card drafts integrated: **10**.
- Verified/approved farmer-facing disease cards: **0**.
- `general_safety.yaml` is the existing general safety card, not a disease card.
- `tests/fixtures/kb/SYNTHETIC_TEST.yaml` is a test-only placeholder and is never
  production content.
- The master specification calls for 12–16 disease cards across three crops.
  Proposed crop scope remains unconfirmed. The supplied batch contains tomato,
  potato, and soybean drafts, but that does not itself approve the deployment
  crop scope or make the cards ready for use.

The integrated Batch 1 cards remain `draft`; structural validation is not
agronomic or language approval. Printed-page locators below are transcribed from
the supplied `INTEGRATION_NOTES.md`. The four Batch 1 title/year values below
were confirmed by the project owner on 2026-11-03; Codex did not inspect the
owner-held PDFs.

| Card ID | Source ID(s) | Printed page references |
|---|---|---|
| `tomato_early_blight` | `icar_tomato_hort_ecourse` | 111, 112 |
| `tomato_septoria_leaf_spot` | `icar_tomato_hort_ecourse` | 112, 113 |
| `tomato_leaf_curl` | `icar_tomato_hort_ecourse`; `icar_iivr_viruses_tb75` | e-course 116; TB75 2, 43 |
| `tomato_bacterial_wilt` | `icar_tomato_hort_ecourse` | 113, 114 |
| `tomato_fusarium_wilt` | `icar_tomato_hort_ecourse` | 110, 111 |
| `potato_late_blight` | `icar_cpri_gap_bulletin_108` | 127, 128, 160 (Annexure 12) |
| `potato_early_blight` | `icar_cpri_gap_bulletin_108` | 128, 128-129, 129, 160 (Annexure 12) |
| `soybean_charcoal_rot` | `icar_iisr_soybean_bulletin_17` | 38, 40, 41 (Table 9, referral only) |
| `soybean_yellow_mosaic` | `icar_iisr_soybean_bulletin_17` | 39 |
| `soybean_rust` | `icar_iisr_soybean_bulletin_17` | 40, 41 (Table 9, referral only) |

## Owner-confirmed Batch 1 source titles and years

| Source ID | Confirmed title | Edition year |
|---|---|---:|
| `icar_cpri_gap_bulletin_108` | Good Agricultural Practices (GAP) for Production of Potato Crop (Technical Bulletin No. 108) | 2020 |
| `icar_iisr_soybean_bulletin_17` | Improved Practices & Methods for Soybean Production and Technical Recommendations (Extension Bulletin 17, Revised Edition 2022) | 2022 |
| `icar_iivr_viruses_tb75` | Viruses of Vegetable Crops: Symptomatology, Diagnostics and Management (Technical Bulletin No. 75) | 2017 |
| `icar_tomato_hort_ecourse` | Disease of Horticultural Crops & their Management (ICAR e-Course for B.Sc (Agriculture) and B.Tech (Agriculture)) | 2020 |

These four records have `verified_by_user: true`; the other six registry
records remain false. User confirmation of title/year does not resolve the
soybean cover/title Bulletin 17 versus “Correct Citation” Bulletin No. 16
discrepancy, verify card claims/page mappings, or approve any card.

## Required card shape and citations

Use the exact validated contract in `src/mydrak/kb/loader.py`. A disease card
contains `id`, `crop`, bilingual `names`, `symptoms`, `confusable_with`, bilingual
`follow_up_questions` (`id`, `en`, `hi`), bilingual `low_risk_steps`,
`chemical_options`, `when_to_refer`, `sources`, `reviewed_by`, `status`,
`region_tags`, `claim_sources`, `review_status`, and `language_reviewers`.

Each claim needs a `claim_sources` entry with exactly `claim`, `source_id`,
`page`, and `section`; every source ID must resolve in `kb/sources.yaml`.
Preserve the printed page number and document/section wording from the supplied
source. Do not normalize away discrepancies between a printed page and a
bibliographic record. Registry eligibility gates still apply, including retrieval
and title verification; `cross-check` and `gap` sources are not citable.

New cards must remain `status: draft`; English and Hindi must each remain
`UNREVIEWED`, with reviewer fields unset until actual review occurs. Keep
`chemical_options: []` unless a separately reviewed and properly sourced change
is authorized. Schema validation does not establish factual accuracy, source
quality, agronomic safety, or approval for farmer-facing use. Do not infer a
virus species from visual symptoms alone.

## Bibliographic and provenance questions to preserve

- **Soybean bulletin number:** the project has been alerted to a Bulletin 17/16
  discrepancy. The supplied notes say the cover/title page says Extension
  Bulletin 17 (Revised Edition 2022), while its “Correct Citation” says
  Extension Bulletin No. 16. The user confirmed the title/year above, but this
  numbering discrepancy remains unresolved.
  Preserve the printed locators and both bibliographic statements; do not
  silently select one number.
- **Supplementary tomato e-course:** project-provided provenance notes that it
  is hosted on the RVSKVV website. Hosting alone does not establish RVSKVV
  authorship. The patch registry attributes it to “ICAR e-Course”; this remains
  user-supplied and unverified, with no author/year stated in the notes.

The title/year metadata above is owner-confirmed; claim support, page mappings,
agronomic content, and translations were not independently checked by Codex.
The cards remain draft, their English and Hindi statuses remain `UNREVIEWED`,
and reviewer fields remain null. Agronomy and native-speaker Hindi review are pending.
`confusable_with` is empty pending agronomist input; `chemical_options` remains
empty. There is no production caller that selects these disease cards for a
reply; any such path must require `status: verified` and reviewed languages.
**Phase 4 is NOT FULLY CLOSED.**
