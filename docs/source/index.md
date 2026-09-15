# exporgo

**exporgo** organizes scientific experiments. It describes what your data should look like,
validates that the data is actually there, and reports what's missing. It never runs your
analysis. Orchestration stays in your code or an LLM agent; exporgo brackets the ends.

The framework is layered, and you install only the layers you need:

- **logging**: a reusable `loguru`-based logging framework, in the base install.
  Parameterized console and rotating file/exception sinks, plus decorators that record
  calls, arguments, return values, and timing.
- **experiment**: the **Experiment & Identity** model, also in the base install. An experiment
  declares an identity coordinate system (one to three keys, default `Subject`) and the resources
  it expects at each identity, then validates their existence on disk. Declarations persist to
  `experiment.json` and reload with {meth}`~exporgo.experiment.Experiment.load`.
- **datastore** (`exporgo[datastore]`): fast, schema-enforced polars/Parquet component
  stores for an experiment's bulk data, Hive-partitioned on the identity keys, with lazy,
  partition-pruned retrieval.
- **monitoring** (`exporgo[monitor]`): progress *derived* from the filesystem, rendered into
  an agent-readable map. *Planned; not yet implemented.*

The identity keys are the hinge: they name an experiment's subjects and sessions, and they become
the datastore's partition keys. Declare them once, and the layers click together.

## The workspace CLI

The exporgo repository also ships a **Rust command-line tool** that stamps and maintains project
*workspaces* (the documentation side of a project, one folder per experiment). The two halves meet
at the data root: an {class}`~exporgo.experiment.Experiment` is the data-side unit that lives *at*
that root, while a workspace's `experiments/<name>/` folder is prose that points at it. This site
documents the Python package; the CLI's commands and installation live in the
[repository README](https://github.com/darikoneil/exporgo#workspace-cli-rust), and the contract
between the two is spelled out in
[Architecture](explanation/architecture.md#the-workspace-cli-and-the-data-root).

## Where to start

- **New to exporgo?** Start with the [Tutorials](tutorials/index).
- **Have a specific task?** See the [How-to guides](how-to/index).
- **Want the concepts?** Read [Explanation](explanation/index).
- **Need the API?** Go to the [Reference](reference/index).

```{toctree}
:hidden:
:maxdepth: 2

installation
tutorials/index
how-to/index
explanation/index
reference/index
```
