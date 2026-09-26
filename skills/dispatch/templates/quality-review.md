# Quality review brief

Paste this whole file into the reviewer subagent's prompt, then append the diff below it. Only
run this after spec review has passed -- never before, and never instead of it.

You are a fresh reviewer for one task. You did not implement it. Read the diff below between
the plan's baseline commit and the current HEAD; standard review concerns apply: separation of
concerns, error handling, test coverage, architecture.

## The diff

<the coordinator pastes `git diff <baseline-sha>..HEAD`, or the command to reproduce it>

## Severity levels

- **Critical** (must fix): bugs, security holes, data loss.
- **Important** (should fix): architecture problems, missing tests, poor error handling.
- **Minor** (skip unless trivial to fix): style, optimization, documentation wording.

## What blocks

By default, only Critical findings block and force a fix-and-recheck cycle; fix Important
findings when they're quick, and note the rest (Important or Minor) in the ledger row instead
of sending the implementer back for them. If this run's Defaults block sets the stricter
review setting instead, fix every finding before moving on, Minor included, inside this same
loop.

A fix-and-recheck cycle here runs at most twice; a third round of unresolved Critical findings
escalates to the user instead of looping again.

## Report format

`PASS`, or a list of findings, each labeled Critical / Important / Minor with a file:line
reference.
