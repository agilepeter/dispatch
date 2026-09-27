# dispatch

Dispatch runs an approved, multi-task plan one task at a time instead of handing
the whole plan to a single subagent. Each task gets a fresh implementer subagent
and then a fresh reviewer subagent that checks the actual code, not the
implementer's own report of it. Every task's outcome, including an escalation,
is logged to a local ledger so loop counts and escalation rates are visible
over time instead of living only in chat history.

This repo packages that as a Claude Code plugin: three skills plus two small
stdlib scripts for the ledger.

## Status

Shipped: the plugin manifest and marketplace entry, the ledger and stats
scripts (concurrent-safe ledger creation, validated stats parsing, a stable
`--json` shape), and the `dispatch`, `dispatch-resume`, and `dispatch-stats`
skills are all in this repo. CI runs the test suite on Linux, macOS, and
Windows on every push.

## Install

```
claude plugin marketplace add agilepeter/dispatch
claude plugin install dispatch@agilepeter
```

Works out of the box on macOS and Linux. On Windows, use WSL or Git Bash with
`python3` on PATH -- both ledger scripts are plain Python 3 files.

## What it does

1. Read an approved plan's tasks (a program design pass first, for multi-file
   work, with one approval).
2. For each task, in order: dispatch a fresh implementer subagent, then a
   fresh spec-compliance reviewer, then a fresh code-quality reviewer.
3. Send issues back to the implementer and re-review; by default only a
   Critical quality finding blocks, and each stage escalates to the user
   instead of starting a third review pass, i.e. after two fix cycles. (A
   stricter setting is available: fix every finding, Minor included, in the
   same loop.)
4. Gate on runnable evidence -- the commands named in the plan's own `Gates:`
   block -- not on the implementer's claim of a green run, before marking a
   task complete.
5. Log the outcome (status, loop counts, reviews, model used) to the ledger.
6. Move to the next task; stop and ask the user on a blocker or repeated
   review failures.

## Entry points

| Invocation | Does |
|---|---|
| `/dispatch <plan-path>` | Start a plan, or continue one already in progress. |
| `/dispatch-resume` | Continue an in-progress plan without retyping its path. |
| `/dispatch-stats` | Show the ledger's rolling health numbers. |

Each also auto-activates: `dispatch` runs on an approved plan of three or more
checkbox tasks without being invoked by name.

## The plan file

A plan is a Markdown file with a `Gates:` block (the verification commands
this run checks after every task) and a list of checkbox tasks, each carrying
its own full spec text. See `skills/dispatch/templates/plan.md` for the full
template; a minimal one looks like this:

```markdown
# Plan: add a health endpoint

Approved: 2026-09-26: yes, ship it

Gates:
pytest -q
python3 -m py_compile app.py

## Tasks

- [ ] 1. Add a GET /health route that returns {"status": "ok"} with a 200 status code.
- [ ] 2. Add a test that requests /health and asserts the status code and body.
- [ ] 3. Wire /health into the existing router and document it in README.md.
```

## Why a verifier

The loop is only as good as the thing that checks it. Here that's a fresh
reviewer that reads the actual code instead of trusting a report, and an
exit-code gate that runs real commands instead of trusting a claim. As of
2026-09-26, before this plugin's own tasks were logged to a ledger of their
own, one real dataset run this way stood at 121 tasks across 13 plans: 120
completed, 1 escalated to a human, and a fresh reviewer found something to
fix in 51 of them (42%) after the implementer had already reported done.
The [maker's own product page](https://staas.fund/dispatch/) carries this
dataset's current numbers, refreshed on every publish.

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
| `spec_review` | `PASS` / `FAIL`, or a free-form outcome such as `FAIL->PASS` or `n/a (...)` |
| `spec_loops` | number of spec-review fix-and-recheck cycles |
| `quality_review` | `PASS` / `CRITICAL` / `IMPORTANT` / `SKIPPED`, or a free-form outcome |
| `quality_loops` | number of quality-review fix-and-recheck cycles |
| `final_status` | `complete` / `escalated` / `user` |
| `model_impl` | model tier(s) the implementer ran on, e.g. `sonnet`, `opus`, `haiku+sonnet` |
| `notes` | free text, `-` if empty |

Location: `$DISPATCH_LEDGER` if set, otherwise `~/.claude/dispatch/runs.tsv`.
The file and its header are created on first use, safely under concurrent
first writers on every OS. Appending a row is atomic against another
dispatch-ledger process on Linux and macOS. On Windows, two sessions
appending at the same instant can overwrite or split a row; everywhere else,
each append is atomic.

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

`--json` always returns the same keys, whether or not the window has any
runs: zeros and empty lists rather than a shorter payload.

```json
{
  "days": 30,
  "since": "2026-08-27",
  "total_runs": 2,
  "avg_impl_loops": 1.0,
  "avg_spec_loops": 1.0,
  "avg_quality_loops": 0.0,
  "spec_fail_count": 0,
  "spec_fail_rate_pct": 0,
  "quality_critical_count": 0,
  "quality_critical_rate_pct": 0,
  "escalation_count": 0,
  "escalation_rate_pct": 0,
  "by_model": [
    {"model": "sonnet", "runs": 2, "escalated": 0, "escalation_rate_pct": 0}
  ],
  "top_failing_plans": [],
  "skipped_rows": 0
}
```

- `days` / `since`: the requested window and the UTC date it starts from.
- `total_runs` / `skipped_rows`: rows counted vs. rows read but discarded
  (wrong column count, an unparseable timestamp, or a bad loop-count value).
- `avg_impl_loops` / `avg_spec_loops` / `avg_quality_loops`,
  `spec_fail_count` / `spec_fail_rate_pct`, `quality_critical_count` /
  `quality_critical_rate_pct`, `escalation_count` / `escalation_rate_pct`:
  aggregate stats over `total_runs`.
- `by_model`: one entry per model tier seen -- `haiku`, `sonnet`, `opus`, or
  `other` for anything else `model_impl` names -- each with its own run
  count, escalation count, and escalation rate. A compound `model_impl` such
  as `sonnet+opus` counts its row under both tiers it names.
- `top_failing_plans`: up to 5 plans ranked by escalation count, each with
  its own escalation and run counts.
- `message`: present only when `total_runs` is 0, alongside the same
  zeroed-out keys above rather than in place of them.

Both scripts are stdlib-only Python 3 and need nothing installed.
