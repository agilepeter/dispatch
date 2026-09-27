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

To install from a local checkout instead, add the directory itself:
`claude plugin marketplace add /path/to/dispatch`, then install as above.

Installed, the plugin adds about 290 tokens to every session and about 4,600 each
time the `dispatch` skill fires. Both are estimates; `claude plugin details dispatch`
prints the current ones.

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

## Evals

The plugin ships its own eval suite (`evals/`), scored with `claude plugin eval` and run
both with the plugin loaded and against a no-plugin baseline, so a score says what the
plugin changed rather than what Claude would have done anyway. Five cases, each against a
tiny scaffolded fixture repo:

<!-- eval-cases:start -->
- `design-doc-before-implementer` -- a multi-file plan that nobody has approved yet gets a
  design doc and one approval question before any implementer runs.
- `spec-before-quality` -- once a plan is approved with its design doc in place, the spec
  reviewer runs before the quality reviewer, and the task gets ticked.
- `one-ledger-row-per-task` -- a single task run logs exactly one well-formed, 13-column
  ledger row.
- `dirty-tree-blocks` -- an unrelated uncommitted change stops the run cold, with no edits
  and no git surgery to make it disappear.
- `reviewer-reads-code` -- an implementer's commit and its "all tests pass" report do not
  survive spec review, which reads the code and finds what is missing.
<!-- eval-cases:end -->

<!-- eval-results:start -->
Release run, Claude Code 2.1.283, `--runs 3 --ablation with-without`:

| Case | With plugin | Without | Delta |
|---|---|---|---|
| design-doc-before-implementer | 1.00 | 0.67 | +0.33 |
| spec-before-quality | 1.00 | 0.56 | +0.44 |
| one-ledger-row-per-task | 1.00 | 0.33 | +0.67 |
| dirty-tree-blocks | 1.00 | 0.63 | +0.37 |
| reviewer-reads-code | 1.00 | 0.56 | +0.44 |

Mean delta +0.45, from one complete run of 30 sessions: 17m53s wall clock at concurrency
4, $8.95 at list price. All five cases scored 1.00 with the plugin loaded in all three
repeats. Per-grader pass counts for both arms are in `evals/reports/0.1.0/result.json`.
<!-- eval-results:end -->

<!-- eval-caveat:start -->
How much this proves: three repeats per arm is a small sample, and the plugin and the
suite were both revised between runs until this one, so these are the scores of the final
suite against the final plugin, not of a first attempt. The baseline moves from run to
run. Four complete runs were made on the day of this release, each after the suite had
been corrected, so they do not measure quite the same thing: their mean deltas were +0.42,
+0.46, +0.41 and +0.45, and every case scored 1.00 with the plugin loaded in all four. The
five cases were written by the plugin's author to show what the plugin is for. They say
that it does those five things reliably, not how it will do on a plan of yours.
<!-- eval-caveat:end -->

Building and re-running this suite changed the plugin four times, each time from a run
that showed the problem:

- The coordinator noticed someone's uncommitted, unrelated edit during its own setup and
  quietly stashed it to get a clean tree, instead of stopping to ask. The clean-tree rule
  now binds the coordinator as well as the implementer.
- Whether a plan got a design pass depended on how simple its tasks looked to the
  coordinator, and the same plan went both ways in different runs. The design pass is now
  chosen by counting files and interfaces.
- A coordinator sometimes handed a reviewer a paraphrase of its template, which loses the
  exact wording that tells the reviewer not to trust the report. Every subagent is now
  handed the template's actual text.
- The skill did not always trigger for someone who wanted to start on a plan that was not
  approved yet, although the approval happens inside it. Its trigger text now says so.

The suite needed as much correcting as the plugin did, and its graders were the larger
part of it:

- One grader searched the whole trace for words such as "blocked" and "dirty". The skill's
  own text contains those words and is part of the trace once the skill loads, so that
  grader passed on every run in which the skill fired, whatever the run then did. It now
  reads the run's last message.
- Patterns written for a command as typed were being matched against the JSON form of the
  tool call, where a line break and a quote are escaped and the description is part of the
  text. One could be satisfied by an `echo` that mentioned the command and could not see a
  quoted path; another would have failed a run for a description containing the word
  "push". Each is now anchored inside the command's own string.
- Checks that watch for particular tools or commands cannot see a file changed through the
  shell, a `git restore`, or a commit of someone else's unfinished edit. `dirty-tree-blocks`
  gained three checks that read the repository when the run ends: the uncommitted edit is
  still there, the task's code is untouched, the history never moved.
- The fixtures were corrected in two ways: the design doc now carries the file name the
  skill looks for, in the four cases that ship one, and the work under review in
  `reviewer-reads-code` is a real commit instead of a claim in the prompt.

Every grader that carries a pattern now has examples in `tests/test_eval_graders.py` of
what it must accept and what it must refuse, and a test fails when a grader is added
without any. The graders written or rewritten for this release were also run against
deliberate misbehaviour in a real eval before they were trusted: a stash, a restore, a
commit of the stray edit, a change made through the shell, a run that loads the skill and
does nothing.

Two limits are known, and each is written into the grader that has it. A line of a
here-document that begins with the ledger command is counted as a call to it; the grader
that counts the rows in the ledger file is the one to believe. A push reached through a
shell alias or another program is not seen, because the grader reads the text of a command.

Reproduce with Claude Code 2.1.283 or later:

```
claude plugin eval . --model sonnet --judge-model haiku --ablation with-without \
  --runs 3 -j 4 --scaffold --trust-plugin --no-publish \
  --allow-tools Bash Write Edit --json result.json
scripts/eval-report.py summarize result.json
scripts/eval-report.py readme
```

Add `--max-cost-usd <n>` if you want a ceiling: it is a guard against a runaway run, not a
budget the suite needs, and a run that hits it is partial. `eval-report.py` refuses a
partial run, a run with an error in any session, and a run whose paid graders were skipped.
The raw `--json` and `--report` output embeds the local paths of the machine it ran on and
the full text of every session, so it is never committed; the report keeps the counts,
scores, costs and durations, and `evals/results/` is ignored.

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
dispatch-ledger process on every OS, by different means depending on the
platform: on Linux and macOS the kernel guarantees that a single write to
an `O_APPEND`-opened file lands at the true end of file and is never
interleaved with another process's write; on Windows, where `O_APPEND` is
only emulated by the C runtime, a byte-range lock held for the whole of
each append serializes it against every other dispatch-ledger process
instead.

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

## Releases

`scripts/release-check.sh` is the pre-release checklist. It verifies that the
version agrees among `.claude-plugin/plugin.json`, `CHANGELOG.md` and
`.claude-plugin/marketplace.json`, runs `claude plugin validate --strict` on
both manifests and `claude plugin tag --dry-run`, and checks that the tag does
not already exist locally or on origin (set `RELEASE_CHECK_OFFLINE=1` to skip
the origin check). The script only checks; it does not create or push tags.
After it passes, create the release tag with `claude plugin tag` (form
`dispatch--v<version>`). The [CHANGELOG](CHANGELOG.md) is the record, and
[RELEASING.md](RELEASING.md) is the full runbook.

A release is a version number: Claude Code gives an installed user a new copy
only when `version` in `.claude-plugin/plugin.json` changes. To update, run
`claude plugin update dispatch@agilepeter`; automatic updates are off until you
turn them on under Marketplaces in `/plugin`. To stay on one version, add the
marketplace at a tag: `agilepeter/dispatch#dispatch--v0.1.0`.

One limit: claude.ai's organization sync rejects a plugin with a top-level
`bin/` directory, which this plugin has. Installing through a marketplace, as
above, is unaffected.
