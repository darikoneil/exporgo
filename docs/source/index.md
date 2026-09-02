# exporgo

**exporgo** organizes scientific studies. It describes what your data should look like,
validates that the data is actually there, and reports what's missing — it never runs your
analysis. Orchestration stays in your code or an LLM agent; exporgo brackets the ends.

The framework is layered, and you install only the layers you need:

- **logging**: a reusable {mod}`loguru`-based logging framework, in the base install.
  Parameterized console and rotating file/exception sinks, plus decorators that record
  calls, arguments, return values, and timing.
- **study**: the **Study & Identity** model, also in the base install. A study declares an
  identity coordinate system (one to three keys, default `Subject`), the resources it expects
  at each identity, and it validates their existence on disk. Declarations persist to
  `study.json` and reload with {meth}`~exporgo.study.Study.load`.
- **datastore** (`exporgo[datastore]`): fast, schema-enforced polars/Parquet component
  stores for a study's bulk data, Hive-partitioned on the identity keys, with lazy,
  partition-pruned retrieval.
- **monitoring** (`exporgo[monitor]`): progress *derived* from the filesystem, rendered into
  an agent-readable map. *Planned; not yet implemented.*

The identity keys are the hinge: they name a study's subjects and sessions, and they become
the datastore's partition keys. Declare them once, and the layers click together.

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
