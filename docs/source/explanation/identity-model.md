# The identity model

Everything in exporgo is addressed by an **identity**. Get the identity model right and the
rest of the framework falls into place — the same address names a subject in your registry, a
folder on disk, and a partition in a store. This page explains the model and why it's the
hinge the layers turn on.

## Keys, schema, identity

An experiment is organized along a small set of named axes. Three types express that:

**{class}`~exporgo.experiment.IdentityKey`**: one named, typed axis. A key has a `name` (used both
as the keyword when you address data and as the Hive partition key on disk) and a `dtype`, one
of `"str"`, `"int"`, or `"bool"`. The dtype is stored as a string label so it round-trips
through `experiment.json`.

**{class}`~exporgo.experiment.IdentitySchema`**: an ordered set of one to three keys, the experiment's
coordinate system. The bound is deliberate. One to three axes is enough to name a unit of data
in almost any experiment (subject, session, maybe group) and few enough that the on-disk
partition tree stays shallow and fast. The default schema is a single `Subject` key.

**{class}`~exporgo.experiment.Identity`**: one concrete point in that system, e.g.
`Subject="m01", Session=1`. It's immutable and hashable, so an identity can key a dict or live
in a set. Build one through the schema, which requires *exactly* the schema's keys and coerces
each value to its key's dtype:

```python
from exporgo.experiment import IdentityKey, IdentitySchema

schema = IdentitySchema(keys=["Subject", IdentityKey(name="Session", dtype="int")])
identity = schema.identity(Subject="m01", Session="1")   # "1" is coerced to int 1
print(identity)
```

```text
Identity(Subject='m01', Session=1)
```

Ask for a key it doesn't define, or leave one out, and you get a `ValueError` — the schema is
the contract.

## The address *is* the path

An identity renders to a Hive-style path fragment, and that rendering is exactly what the
datastore partitions on:

```python
print(identity.as_path())
```

```text
Subject=m01/Session=1
```

This is the whole trick. Because {meth}`~exporgo.experiment.Identity.as_path` produces the same
`key=value/…` fragment the store writes to, the identity you register, the identity you query,
and the directory the data lands in are one and the same. Declare your keys once, and the experiment
layer and the datastore layer agree on where everything is without any further coordination.

## Values with special characters

Real identity values are not always tidy. `Subject="m 01#a"` has a space and a `#`; a `bool` key's
value is `True`, which is not how a Hive path spells a boolean. exporgo carries such values
through a store unchanged. It does that by keeping **two renderings** of the same value and being
clear about which lives where:

- **Raw** is the value as you wrote it, stringified: `m 01#a`, and for booleans the lowercase
  Hive spelling `true` / `false`. This is what a store's **manifest** records, so an identity and
  a manifest partition compare equal without any decoding step.
- **Encoded** is the percent-encoded form pyarrow's Hive writer puts in a **directory name**:
  `Subject=m%2001%23a`, `Flag=false`. Only path construction and path parsing touch it, and
  parsing decodes straight back to raw.

Because the manifest is the authority on membership, everything that asks a store what it contains
speaks raw: `mode="unique"` correctly refuses a duplicate `m 01#a`, `mode="overwrite"` finds the
right partition to replace, and
{meth}`experiment.identities(store=...) <exporgo.experiment.Experiment.identities>` hands back the
value you originally wrote.

{meth}`~exporgo.experiment.Identity.as_path` renders **raw**, which is the useful thing for a
resource path or a log line but is *not* a datastore directory name. The two differ exactly where
encoding bites: an identity whose `Subject` is `m 01#a` and whose `Flag` is `False` renders as
`Subject=m 01#a/Flag=False`, while the store's directory for it is
`Subject=m%2001%23a/Flag=false`. Read a datastore path through the manifest rather than by
string-matching it against `as_path()`.

## Reading a `bool` back

A `bool` key is the one dtype where the obvious coercion is a trap. Python's `bool("False")` is
`True`, because every non-empty string is truthy, so a directory named `Flag=False` would read
back as `True`. An identity key won't do that. It accepts an actual `bool`, or a
case-insensitive `"true"` / `"1"` / `"false"` / `"0"`, and **raises `ValueError` on anything
else** rather than guessing:

```python
from exporgo.experiment import IdentityKey

flag = IdentityKey(name="Flag", dtype="bool")
print(flag.coerce("FALSE"), flag.coerce("1"))
```

```text
False True
```

`flag.coerce("maybe")` is a `ValueError`. Refusing an unrecognized spelling is what makes the
round-trip trustworthy: `true`/`false` from a partition directory, `True`/`False` from a resource
folder, and `1`/`0` from a config file all land on the same two values, and anything without a
boolean spelling is reported instead of silently becoming `True`.

## Full and partial identities

Most identities are **full**: they carry a value for every key in the schema. But some parts
of exporgo produce **partial** identities over a subset of the keys. A store partitioned on
`Subject` alone, or a resource template that mentions only `{Subject}`, describes data at the
subject level, not the subject-session level. Reverse-resolving such a template (see
[Discover identities](../how-to/discover-identities)) yields identities over just `Subject`.

The distinction matters when exporgo compares what's registered against what's on disk. It
*projects* each registered identity onto the keys a component actually uses, so a subset-key
store is compared subject-by-subject rather than session-by-session. It also decides what can
be auto-registered: only a full-key identity can be added to the registry, because a partial
one can't form a complete address. Partial identities still surface as drift — they're just
reported, not registered.

## Why coerce, and why round-trip through strings

Values arrive as strings all the time: from a directory name, a partition folder, a config
file. A key's dtype is the single place that says how to read them back: an `int` key coerces
`"1"` to `1`, so `Session=1` and `Session="1"` name the same identity no matter which path
they came in through. Storing the dtype as a plain label (`"int"`, not a Python type) is what
lets the whole coordinate system survive a `save`/`load` cycle unchanged.
