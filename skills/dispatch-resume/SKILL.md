---
name: dispatch-resume
description: Resume an in-progress dispatch run without retyping the plan's path -- finds it from this repo's saved plans and the ledger, then continues from the first task with no complete row.
when_to_use: Use when the user wants to continue a dispatch run without naming the plan again. Example requests: "resume the dispatch run", "continue where dispatch left off".
argument-hint: "[plan-path]"
---

Continues a dispatch run already in progress, so the user does not have to remember or retype
the plan's path. If `$ARGUMENTS` is given, it is that path directly -- skip straight to "Then"
below with it.

## Find the plan

1. If this is a git repo, list `<repo>/.dispatch/plans/*.md`. Read each one that looks like a
   dispatch plan (a `Gates:` line and `- [ ]` boxes) and keep any with at least one unticked
   box.
2. For each candidate, cross-check its checkboxes against the ledger the same way the
   `dispatch` skill's own Resume step does, so a box that is unticked in the file but already
   logged `complete` there is not reported as still open.
3. No git repo, or nothing under `.dispatch/plans/`: there is nothing here to search. Say so,
   and ask for the plan's path directly, or point at `/dispatch <plan-path>`, which runs the
   same resume check given one explicitly -- this covers a plan that was given by an explicit
   path rather than saved under `.dispatch/`.

Exactly one candidate still has unfinished tasks: use it. More than one: list each with how
many tasks remain and ask which to resume. None: say there is nothing to resume.

## Then

Follow this plugin's `dispatch` skill (`${CLAUDE_PLUGIN_ROOT}/skills/dispatch/SKILL.md`)
exactly, starting at its Resume step, using the plan found above (or given in `$ARGUMENTS`) as
its plan path. This is the same process as `/dispatch <plan-path>`, entered without having to
name the plan first -- not a second, different one.
