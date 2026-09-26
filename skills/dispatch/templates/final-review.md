# Final review brief

Paste this whole file into the reviewer subagent's prompt, then append the diff below it. Run
this once, after every task in the plan has reached Stage 4 -- never as a substitute for any
single task's own spec or quality review.

You are a fresh reviewer looking at the whole plan's work at once. You did not implement any
task in it. Read the diff below between the plan's baseline commit and the current HEAD --
every task's changes together, not one task's diff in isolation.

## The diff

<the coordinator pastes `git diff <baseline-sha>..HEAD`, or the command to reproduce it>

## What to check

Cross-task integration, not any single task's correctness again:

- Do the pieces from different tasks actually fit together -- a function one task added is
  called correctly by another, a shared type or format is used consistently throughout?
- Any duplicated work, dead code, or an approach an earlier task took that a later task
  superseded without cleaning up?
- Do the plan's own `Gates:` commands still pass against the finished whole, not just what
  each task checked in isolation?

## Severity levels

Same as quality review: **Critical** (must fix): bugs, security holes, data loss. **Important**
(should fix): architecture problems, missing tests, poor error handling. **Minor** (skip unless
trivial to fix): style, optimization, documentation wording.

## Report format

`PASS`, or a list of findings, each labeled Critical / Important / Minor with a file:line
reference.
