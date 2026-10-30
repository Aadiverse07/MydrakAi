# T08 offline synthetic mask severity and overlay

Date: 2026-10-30
Tool: Codex

## Scope and implementation

Master B4 (PDF p. 7) defines severity as lesion pixels intersecting leaf pixels
divided by leaf area, with bands from `config/severity.yaml`; it explicitly
labels those bands configurable heuristics, not validated agronomic thresholds.
B4 requires a semi-transparent lesion-mask overlay plus outline, and no severity
or overlay when masks fail or are empty. C2 T08 asks for a known-mask fixture
with the expected percent.

Added `src/mydrak/sam/overlay.py`. It accepts only `SamSegmentation` values
from the offline synthetic JSON parser, then only mask payloads tagged
`synthetic-grid-v1` validated by the existing grid adapter. Caller-supplied
object IDs select leaf and lesion roles; IDs and boxes are not interpreted as
semantic labels. Boolean grids are converted to `BinaryMask` and scored through
the existing `mask_severity_pct()` helper. Bands use the existing `band()`
helper and values in `config/severity.yaml`.

The renderer nearest-neighbor scales the lesion grid to the preprocessed image
size, applies translucent red fill with a contrasting outline, and writes a
PNG to memory. This entry point accepts only `synthetic-fixture` provenance
and draws `SYNTHETIC FIXTURE` on the image. Missing/ambiguous objects, unsupported
encodings, empty masks, size mismatch, invalid severity config, and image/render
failures return stable reason codes with no numeric severity or overlay. The
Pillow dependency was already declared for T04; `pyproject.toml` now notes its
T08 overlay use, with no new dependency added.

The existing response-text parser remains unchanged and its mask payloads stay
opaque. No Base85 decoder, provider-specific mask format, SAM client, API call,
or live compatibility claim was introduced. T08 remains PARTIAL and live SAM
remains NO-GO.

## Acceptance tests

`tests/test_sam_overlay.py` covers boolean-grid decoding, a 4x4 synthetic mask
with 10 leaf cells, 3 intersecting lesion cells and 1 outside-leaf cell
(`30.0%`), outside-only lesion cells, empty leaf/lesion, mask size mismatch,
severity-band boundaries, image-sized PNG output, lesion fill/outline, visible
watermark, unsupported encoding, and failure results without severity/overlay.

## Verification

- `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_sam_overlay.py tests/test_severity.py tests/test_sam_grid.py -q` — exit 0, **57 passed**.
- `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider -q` — exit 0, **997 passed**.
- `python3 -m compileall -q src tests eval` — exit 0.
- TOML/YAML parsing — exit 0; `pyproject.toml` and **7 YAML files** parsed under `config/`, `kb/`, and `tests/fixtures/`.
- Safe secret scan — exit 0; **530 changed/addition lines scanned, 0 matches**; matched content is suppressed.
- `git check-ignore -v .env` — exit 0; ignored by `.gitignore:2`.
- `git ls-files -- .env` — exit 0; no tracked path output.
- `git status --short --ignored -- .env` — exit 0; `!! .env`. Contents were not read.
- `git diff --check` — exit 0. Untracked-file whitespace check — exit 0; **3 files checked, 0 issues**.

No network/API calls, media uploads, credentials, `.env` reads, dependency
installations, or credits were used.
