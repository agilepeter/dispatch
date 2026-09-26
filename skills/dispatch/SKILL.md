---
name: dispatch
description: Build an approved plan of three or more checkbox tasks, one task at a time, with a fresh implementer, a spec reviewer, a quality reviewer, an exit-code gate and a ledger row per task.
user-invocable: true
argument-hint: "[plan-path]"
---

Dispatch runs an approved, multi-task plan one task at a time instead of handing the whole
plan to a single subagent. `$ARGUMENTS` is the plan's path, given by the user or by whatever
approved the plan in this conversation.

## When this runs

Automatically, when all of these are true: a plan exists with three or more checkbox tasks
(`- [ ]`), the user has approved it (said "do it", "build it", "ship it", "go", or similar),
and the tasks involve code changes. Also runs directly as `/dispatch <plan-path>`.

Do not run it for: a one- or two-task plan (just do those directly); a research or exploration
plan (no code for a reviewer to check); a plan the user has not approved yet.

## Where things live

Edit this block, and only this block, to move any of these:

- A plan given by path stays where it is; its design doc is `<slug>.design.md` next to it.
- A plan that exists only in this conversation is saved to `<repo>/.dispatch/plans/<slug>.md`.
  Before the first write under `.dispatch/`, make sure it is excluded from git without
  touching the repo's own `.gitignore`:
  ```sh
  exclude_file="$(git rev-parse --git-path info/exclude)"
  mkdir -p "$(dirname "$exclude_file")"
  touch "$exclude_file"
  grep -qxF '/.dispatch/' "$exclude_file" || echo '/.dispatch/' >> "$exclude_file"
  ```
  This is idempotent and keeps a plan out of `git status`, out of an implementer's clean-tree
  pre-flight, and out of an implementer's `git add -A`. Outside a git repo, just write the
  folder.
- The ledger is written only through `${CLAUDE_PLUGIN_ROOT}/bin/dispatch-ledger append ...`,
  never a hand-built line. Always pass the plan's **absolute** path as `--plan` so a later
  resume, possibly in a different session, matches its rows exactly.

## Entry points

- `/dispatch <plan-path>` (this skill): start a plan, or continue one already in progress.
- `/dispatch-resume`: continue an in-progress plan without retyping its path.
- `/dispatch-stats`: show the ledger's rolling health numbers.

## Defaults

Edit these to change how a run behaves; nothing else in this skill should be treated as a
tunable.

- Implementer model: `sonnet`. Use `haiku` instead for a single-file, mechanical task.
- Reviewer model, both spec and quality review: `sonnet`.
- Model for a `BLOCKED` retry, or a judgment call about architecture: `opus`.
- Review strictness, default: block only on a Critical quality finding, fix an Important one
  when it's quick, note a Minor one in the ledger row instead of looping on it.
  Stricter setting: fix every finding before moving on, Minor included, inside the same loop.

Use a tier name (`haiku`, `sonnet`, `opus`) when dispatching or recording `model_impl` --
never a full model id, which changes over time and varies by provider.

## Call stack

```
/dispatch <plan-path>
  -> resume check: the plan's ticked boxes, cross-checked against ledger rows for this plan
  -> setup: read the plan once, record the baseline commit, read its Gates: block
  -> design pass (multi-file plans only): write <slug>.design.md, get ONE approval
  -> per task, in order:
       implementer subagent   <- templates/implementer-brief.md + task text + design slice
       -> spec reviewer       <- templates/spec-review.md          (max 2 loops, then escalate)
       -> quality reviewer    <- templates/quality-review.md, diff baseline..HEAD (max 2 loops)
       -> DoD gate: run the plan's Gates: commands; record each command and its exit status
       -> tick the task's checkbox in the plan
       -> dispatch-ledger append ...   (always -- including on escalation)
  -> final cross-task review -> report to the user + dispatch-stats --oneline
```

## Setup

1. Read the plan file once. Extract every task with its full text.
2. Track the tasks in the harness's own to-do tool, if it has one, for visibility during the
   run -- but the plan's checkboxes are the durable record, not that tool's list.
3. If this is a git repo, note the current commit as this run's baseline (used later for the
   quality reviewer's diff).
4. Run the program design pass below, unless every task is single-file or mechanical.

## Resume (before Setup, every time)

A run can span sessions. Before doing anything else:

1. Find the plan: the path given, or `<repo>/.dispatch/plans/<slug>.md` if it was saved there.
   Read it, and its sibling `<slug>.design.md` if one exists.
2. Cross-check its checkboxes against the ledger: a task is done when its box is ticked, or
   when a ledger row for this plan's absolute path has `final_status` = `complete` for it,
   whichever a plain, portable read finds --
   `awk -F'\t' -v p="$PLAN_ABS_PATH" '$2==p && $11=="complete" {print $3}' \
   "${DISPATCH_LEDGER:-$HOME/.claude/dispatch/runs.tsv}"` -- lists that plan's completed task
   indices.
3. Resume from the first task with neither. Never silently re-run a task that already has one,
   unless the user asks or a design amendment invalidated it.
4. A plan whose header already has an `Approved:` line, with its design doc present, needs no
   second approval question -- proceed straight to the first unfinished task. This is what
   lets a run resume in a new session, and what lets a non-interactive run proceed on a
   pre-approved plan.

On a pause or an escalation, before handing back: make sure the plan and the design doc (not
this conversation) capture everything decided. Nothing important may exist only in chat.

## Program design pass (before task 1, multi-file plans only)

Read the relevant existing code first -- design against the codebase that exists, never an
imagined one. Then write `<slug>.design.md` from `templates/design.md`.

Show the user only its "Types & signatures" and "Least confident decisions" sections, and ask:
"Design look right, or what changes?" Wait for an answer before dispatching task 1. When they
approve, write an `Approved:` line into the plan header with the date and their own words (see
`templates/plan.md`). This is the one approval gate in the whole workflow -- never add another.

If a plan has no `Gates:` block filled in yet, propose commands from the repo's own manifests
(package.json scripts, pytest/pyproject config, Cargo, a Makefile) in this same approval step.
A plan that skips the design pass instead asks once, before task 1, and writes the answer into
the plan's `Gates:` block. Either way, this never becomes a second approval stop.

If a later task proves the design wrong: stop, update `<slug>.design.md` under a new
"Amendments" entry, tell the user what changed and why, and continue. Never let the code and
the design doc quietly drift apart.

## Per-task loop

Initialize before Stage 1: `impl_loops = 1`, `spec_loops = 1`, `quality_loops = 0`,
`model_impl` = the tier dispatched (record the highest tier reached if a task escalates tiers).

**Stage 1 -- Implement.** Spawn a fresh implementer subagent on the model from Defaults. Paste
`templates/implementer-brief.md`, then the task's full text, then the design slice it
implements (the file entries, signatures, and call-stack lines that apply) -- never make the
subagent go read the plan or the design doc itself. Include the working directory, relevant
file paths, and enough scene-setting that the subagent understands what the task is part of.

Handle its report:
- `DONE` -> Stage 2.
- `DONE_WITH_CONCERNS` -> read the concerns; if they don't block, proceed to Stage 2, otherwise
  fix first.
- `NEEDS_CONTEXT` -> supply the missing context, re-dispatch, increment `impl_loops`.
- `BLOCKED` -> re-dispatch with more context (increment `impl_loops`), move to `opus`, or split
  the task smaller. Still blocked after that: pause and ask the user.

If the previous attempt at this task ended in an agent error rather than a status report,
run `git status --short` and `git diff --stat` yourself before re-dispatching, and tell the
next implementer about that partial diff so they adopt and verify it -- never discard it
silently, never assume it is complete.

**Stage 2 -- Spec review.** Only after Stage 1 reports `DONE` or an accepted
`DONE_WITH_CONCERNS`. Spawn a fresh reviewer on the reviewer model. Paste
`templates/spec-review.md`, then the same task text, then the implementer's report. `PASS`
moves on; issues go back to the same implementer to fix, then re-review, incrementing
`spec_loops` each cycle, up to 2 loops before escalating to the user.

**Stage 3 -- Quality review.** Only after Stage 2 passes, never before. Spawn a fresh reviewer
on the reviewer model. Paste `templates/quality-review.md`, then `git diff <baseline>..HEAD`.
Only a Critical finding blocks and forces a fix-and-recheck cycle (increment `quality_loops`
each time), up to 2 loops before escalating; handle Important and Minor per the Defaults
review-strictness setting.

**DoD gate.** Spec and quality review confirm the code is *right*; this confirms it is
*verified* -- a task is never "complete" on the strength of a report alone. Run the plan's
`Gates:` commands in order, stopping at the first failure. Record each command and its actual
output in this stage's ledger `notes` -- never the implementer's claim of a green run. Red
gate: escalate rather than marking the task complete. No gate commands exist for this task: it
is `DONE_WITH_CONCERNS`, not `complete`, with the missing verification noted.

**Stage 4 -- Mark complete.** Tick the task's checkbox in the plan file. Move to the next task.

**Stage 5 -- Log.** Always runs, including on escalation:
```
${CLAUDE_PLUGIN_ROOT}/bin/dispatch-ledger append \
  --plan "<plan's absolute path>" --task "<index, e.g. 3, 17b, or 13+14>" \
  --text "<task spec text or a summary of it>" \
  --impl-status <DONE|DONE_WITH_CONCERNS|NEEDS_CONTEXT|BLOCKED> --impl-loops <N> \
  --spec-review <PASS|FAIL|...> --spec-loops <N> \
  --quality-review <PASS|CRITICAL|IMPORTANT|SKIPPED|...> --quality-loops <N> \
  --final-status <complete|escalated|user> --model <sonnet|opus|haiku|...> \
  [--notes "<free text, including the DoD gate's recorded output>"]
```

## Hard-won lessons

1. **Clean-tree pre-flight.** Every implementer brief opens with `git status --short` must be
   empty, or the implementer stops and reports `BLOCKED`. This is what catches the next lesson
   before it compounds.
2. **A dead or errored agent can leave work behind.** After any agent error, read `git status`
   and `git diff --stat` before re-dispatching, and hand the next implementer that partial diff
   to adopt and verify against the spec -- never discard it silently, never assume it's done.
3. **Put the shape of the code in the brief, not in the review.** When you already know a
   convention this task must follow -- where a string is rendered, how test-only code is
   gated, what every fixture must assert -- state it in the implementer brief. A brief that
   names the shape up front saves a whole review loop.

## After the last task

Dispatch one final, fresh reviewer across the entire diff: does the whole thing hang together,
any cross-task integration issues, are all gates still green. Report to the user with a
summary of what was built, then run and show `${CLAUDE_PLUGIN_ROOT}/bin/dispatch-stats
--oneline` so they see this run's effect on the rolling numbers immediately.

## Constraints

- Sequential implementers only -- never two in parallel; they will conflict on files.
- Full task text and design slice pasted into every prompt -- never "go read the plan."
- One design pass, one approval, ever -- never a second approval gate.
- Spec review before quality review, never reversed.
- A fresh subagent for every stage, every time -- a reviewer that reuses the implementer's
  context is not a review.
- Every task logs to the ledger, even on escalation.
