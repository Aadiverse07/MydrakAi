# eval — evaluation harness (deferred past Phase 0)

Planned (spec D1/D2): 30 labeled images (dev 20 / test 10), 3 strategies
(always-Spark, always-Glimmer, Mydrak routing), metrics JSON + markdown table +
accuracy-vs-coverage and cost/accuracy charts via `run_eval.py`.

Phase 0: no harness code, no images, no labels, no results. `data/dev/` and
`data/test/` intentionally empty; see `data/SOURCES.md` for sourcing rules.
