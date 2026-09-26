# Plan: <name>

Approved: <!-- left blank until the coordinator writes it -- during the design pass for a
multi-file plan, or during the one Gates: question below for a plan that skips the design
pass. This placeholder comment does not count as approval by itself -- the coordinator fills
the line in with the date first, then the user's own words, e.g. "2026-09-26: yes, ship it".
Only once the line begins "Approved: 20" followed by a date does a plan count as pre-approved
(together with its design doc, for a plan that needed one): it then skips straight to the
first unfinished task, no second approval question, in this session or a later one. -->

Gates:
<!-- One verification command per line, nothing else in this block. The dispatch skill runs
exactly these commands, in order, after every task, and stops at the first one that fails.
Order them from cheapest and most certain to most expensive: a syntax or static check first
(imports, lint, a type-check), then a runtime check (unit tests, a startup smoke test), then
a system check (integration or end-to-end) if this plan touches more than one component.

Leave this block empty and the coordinator fills it in before task 1: during the design pass
for a multi-file plan, it proposes commands from the repo's own manifests (package.json
scripts, pytest or pyproject config, Cargo, a Makefile) and confirms them in that same
approval; for a plan that skips the design pass, it asks once before task 1 and writes the
answer here. Either way, filling this block is never a second approval stop. -->

## Tasks

<!-- Full spec text for each task, not a title or a pointer elsewhere -- an implementer never
reads this file directly; the coordinator pastes each task's text into that task's own
subagent prompt, so nothing here can say "see above" or "as discussed". -->

- [ ] 1. <first task>
- [ ] 2. <second task>
- [ ] 3. <third task>
