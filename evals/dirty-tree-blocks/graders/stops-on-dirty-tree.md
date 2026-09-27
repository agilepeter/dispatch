---
type: regex
pattern: '(blocked|dirty|uncommitted change)'
flags: i
target: trace
---

Nobody told the coordinator or the implementer about the pre-existing edit to README.md, so
the clean-tree preflight in templates/implementer-brief.md should surface it and stop,
somewhere in the run, rather than silently building on top of it. "git status" itself is not
in this list: every run's own routine pre-flight prints that phrase whether or not it finds
anything wrong, so it never discriminates a real finding from business as usual.
