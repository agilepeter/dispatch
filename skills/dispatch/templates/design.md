# Design: <plan name>

Written once, before task 1, for a multi-file plan -- never for a plan where every task
edits a single file and adds no interface another task uses. Read the relevant existing code before writing this; design
against the codebase that exists, not an imagined one.

## Files

<Every file created or changed, one line each on why it lives there.>

## Types & signatures

<Code blocks: types and function signatures, no implementation bodies. This section should be
readable in seconds -- a reader should be able to say "right" or "wrong" on each one without
reading prose.>

## Call stack

<For each main flow: what calls what, top to bottom.>

## Test plan

<Test case names and what each one asserts, written before any of them exist.>

## Least confident decisions

<Numbered list of the calls most worth challenging now, while changing them is free. This is
the list the user actually reads at approval time, alongside the signatures above.>

## Amendments

<Empty until a task proves something here wrong. When that happens: stop, add an entry below
with the date, what changed, and why, tell the user, and continue -- never let the code and
this document quietly drift apart.>
