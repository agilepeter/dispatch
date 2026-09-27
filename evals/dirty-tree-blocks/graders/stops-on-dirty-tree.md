---
type: regex
pattern: '(blocked|dirty|uncommitted change|git status)'
flags: i
target: trace
---

Nobody told the coordinator or the implementer about the pre-existing edit to README.md, so
the clean-tree preflight in templates/implementer-brief.md should surface it and stop,
somewhere in the run, rather than silently building on top of it.
