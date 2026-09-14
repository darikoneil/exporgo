# Analysis / pipeline: <experiment name>

How raw data becomes a result. Describe the pipeline an agent should follow or reproduce — the
shape and the decisions, not the code itself (code lives in the repo, see `resources.md`).

- **Pipeline shape:** raw → <preprocessing> → <core analysis> → <figures/stats>
- **Inputs:** <what the pipeline starts from, and where — point to `resources.md`>
- **Outputs:** <what it produces, and where they land>

## Steps

1. **<stage>** — <what it does; key parameters and units; the entry point in the repo>
2. **<stage>** — <…>

## Statistical conventions

- **Tests:** <the test(s) and why they fit the design>
- **Multiple comparisons:** <correction method, family definition>
- **Effect sizes:** <what is reported alongside p-values>
- **Reproducibility:** <seeds, config files, what pins a result>

## Assumptions & caveats

<What the analysis assumes about the data (even sampling, stationarity, n ≥ …), and where it would
mislead if those fail.>
