# The identity model

Everything in exporgo is addressed by an **identity**. Get the identity model right and the
rest of the framework falls into place — the same address names a subject in your registry, a
folder on disk, and a partition in a store. This page explains the model and why it's the
hinge the layers turn on.

## Keys, schema, identity

A study is organized along a small set of named axes. Three types express that:

**{class}`~exporgo.study.IdentityKey`**: one named, typed axis. A key has a `name` (used both
as the keyword when you address data and as the Hive partition key on disk) and a `dtype`, one
of `"str"`, `"int"`, or `"bool"`. The dtype is stored as a string label so it round-trips
through `study.json`.

**{class}`~exporgo.study.IdentitySchema`**: an ordered set of one to three keys, the study's
coordinate system. The bound is deliberate. One to three axes is enough to name a unit of data
in almost any study (subject, session, maybe group) and few enough that the on-disk
partition tree stays shallow and fast. The default schema is a single `Subject` key.

**{class}`~exporgo.study.Identity`**: one concrete point in that system, e.g.
`Subject="m01", Session=1`. It's immutable and hashable, so an identity can key a dict or live
in a set. Build one through the schema, which requires *exactly* the schema's keys and coerces
each value to its key's dtype:

```python
from exporgo.study import IdentityKey, IdentitySchema

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

This is the whole trick. Because {meth}`~exporgo.study.Identity.as_path` produces the same
`key=value/…` fragment the store writes to, the identity you register, the identity you query,
and the directory the data lands in are one and the same. Declare your keys once, and the study
layer and the datastore layer agree on where everything is without any further coordination.

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
