# dispatch

Dispatch runs an approved, multi-task plan one task at a time instead of handing
the whole plan to a single subagent. Each task gets a fresh implementer subagent
and then a fresh reviewer subagent that checks the actual code, not the
implementer's own report of it. Every task's outcome, including an escalation,
is logged to a local ledger so loop counts and escalation rates are visible
over time instead of living only in chat history.

This repo packages that as a Claude Code plugin: a skill plus two small
stdlib scripts for the ledger.

## Install

```
claude plugin marketplace add agilepeter/dispatch
claude plugin install dispatch@agilepeter
```

## What it does

1. Read an approved plan's tasks (a program design pass first, for multi-file work).
2. For each task, in order: dispatch an implementer subagent, then a fresh
   spec-compliance reviewer, then a fresh code-quality reviewer.
3. Send issues back to the implementer and re-review; only Critical quality
   issues block, and there is a cap on review loops before escalating.
4. Gate on runnable evidence (tests/lint/a smoke run), not on the
   implementer's claim of a green run, before marking a task complete.
5. Log the outcome (status, loop counts, reviews, model used) to the ledger.
6. Move to the next task; stop and ask the user on a blocker or repeated
   review failures.

(Placeholder: the skill itself, which drives this loop, ships in the next
piece of work on this repo and will be linked from here.)

## The ledger

Every task run appends one TSV row:

| Column | Meaning |
|---|---|
| `ts` | UTC timestamp, ISO-8601 with a trailing `Z`, e.g. `2026-09-26T14:03:00Z` |
| `plan_path` | path to the plan file the task came from (or a sentinel like `inline:<slug>`) |
| `task_idx` | the task's position in the plan, e.g. `3`, `17b`, `13+14` |
| `task_text` | the task's spec text, or a summary of it |
| `impl_status` | `DONE` / `DONE_WITH_CONCERNS` / `NEEDS_CONTEXT` / `BLOCKED` |
| `impl_loops` | number of times the implementer was (re-)dispatched |
| `spec_review` | `PASS` / `FAIL`, or a free-form outcome such as `FAIL→PASS` or `n/a (...)` |
| `spec_loops` | number of spec-review fix-and-recheck cycles |
| `quality_review` | `PASS` / `CRITICAL` / `IMPORTANT` / `SKIPPED`, or a free-form outcome |
| `quality_loops` | number of quality-review fix-and-recheck cycles |
| `final_status` | `complete` / `escalated` / `user` |
| `model_impl` | model tier(s) the implementer ran on, e.g. `sonnet`, `opus`, `sonnet+haiku` |
| `notes` | free text, `-` if empty |

Location: `$DISPATCH_LEDGER` if set, otherwise `~/.claude/dispatch/runs.tsv`.
The file and its header are created on first use.

Append a row directly:

```
bin/dispatch-ledger append --plan PATH --task N --text TEXT \
  --impl-status S --impl-loops N \
  --spec-review S --spec-loops N \
  --quality-review S --quality-loops N \
  --final-status S --model M [--notes TEXT]
```

Read stats back out:

```
bin/dispatch-stats                # human-readable, last 30 days
bin/dispatch-stats --oneline       # one-line summary
bin/dispatch-stats --json          # machine-readable
bin/dispatch-stats --days 7 --input /path/to/runs.tsv
```

Both scripts are stdlib-only Python 3 and need nothing installed.

## Status

In development. This repo currently holds the plugin skeleton and the ledger
tooling; the skill that actually drives the dispatch loop in a Claude Code
session is not in this repo yet.
