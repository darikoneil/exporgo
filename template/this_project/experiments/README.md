# Experiments

One folder per experiment. Each is a self-contained, documented unit an agent can read on its own.

## Start a new experiment

Copy `_TEMPLATE/` to a new folder named for the experiment (a short slug, e.g. `grid-remap-v1`):

```
experiments/
  _TEMPLATE/          <- the blank set; don't edit, copy it
  grid-remap-v1/
    experiment.md     scientific description: aim, hypothesis, design
    protocol.md       how the data is produced (one or more protocols)
    analysis.md       how raw data becomes a result (the pipeline)
    resources.md      where the code and data live (repos, server paths)
```

## Why four files, not one

Each file has one job, so an agent opens only what the task needs — `analysis.md` for an analysis
question, `resources.md` to find the data — instead of loading the whole experiment. That keeps
context small, the same reason `context.md` at the project root is deliberately short.

## Relationship to `plans/`

`plans/` is what you intend to do; `experiments/` is what you are doing or have done. When an idea
in `plans/` becomes real, copy `_TEMPLATE/` into a new experiment folder and move the relevant
notes over.
