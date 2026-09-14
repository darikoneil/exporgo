---
name: <skill-slug>
description: <One or two sentences, written to trigger. Say plainly WHAT the skill does and
  WHEN to use it, including the words a future prompt would contain — "Use when the user asks
  to …". This description is the only thing Claude sees when deciding whether to load the
  skill, so make it specific.>
---

# <Skill Title>

<One paragraph: what this skill is for and the situation that calls for it. Motivation before
mechanism — say what it accomplishes, then how.>

## When to use

- <concrete trigger — the kind of request that should load this>
- <concrete trigger>
- Not for: <the adjacent case this skill should NOT handle, so it doesn't over-fire>

## Inputs / assumptions

- <what must be true or supplied before this runs — a dataset path, a repo, an env>
- <units, shapes, conventions the skill assumes>

## Procedure

1. <first step — specific and checkable>
2. <next step>
3. <…>

## Conventions

- <the fixed choices that make the output consistent every time — tools, style, naming,
  export settings, statistical defaults>

## Output

- <what the skill produces and where it goes>

## Verify

- <how to check the result is correct before calling it done>

---

> Authoring notes (delete before saving):
> - Keep the skill self-contained: everything Claude needs to do the task the same way twice.
> - Prefer one concrete example over three abstract ones; give real values and units.
> - Put reusable reference material (long tables, style specs, voice profiles) in a
>   `references/` subfolder beside the skill and point to it, rather than bloating the body.
> - A skill is a procedure, not a script. If it's code, it belongs in a repo — link to it.
> - Register the finished skill in `.claude/skills/README.md` so it's discoverable.
