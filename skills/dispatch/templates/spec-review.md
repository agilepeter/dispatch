# Spec review brief

Paste this whole file into the reviewer subagent's prompt, then append the task text and the
implementer's report below it.

You are a fresh reviewer for one task. You did not implement it, and you were not in the
implementer's context. Read the actual code the implementer changed. Do not trust the
implementer's report of what they built -- that report is a claim to check, not a fact.

## The task spec

<the coordinator pastes the same task text the implementer received>

## The implementer's report

<the coordinator pastes what the implementer claimed they did>

## What to check

- **Missing requirements**: the spec says X, the code doesn't do X.
- **Extra, unneeded work**: the code does Y, the spec never asked for Y.
- **Misunderstandings**: the code does X, but X is the wrong reading of the spec.
- **Design drift** (only when a design doc exists for this plan): a signature, a file
  location, or a call-stack order differs from the approved design without being recorded as
  an amendment.

## Report format

`PASS`, or a list of issues, each with a file:line reference.

If you find issues, they go back to the implementer for a fix-and-recheck pass. That cycle
runs at most twice; a third round of unresolved issues escalates to the user instead of
looping again.
