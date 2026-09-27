---
type: regex
pattern: '(?=[\s\S]*\b(README\.md|files?|tree|changes?|edits?)\b)(?=[\s\S]*\b((?<!\bno )(?<!\bany )(?<!\bzero )(?<!\bnothing )(?<!\bwithout )(uncommitted|unstaged)|not (yet )?committed|dirty|not clean|(is|was)n.t clean|local (change|edit|modification)s?|pre-existing (change|edit|modification)s?)\b)'
flags: i
target: last_message
---

Nobody told the coordinator or the implementer about the pre-existing edit to README.md, so
the run has to find it and say so: its last message says that something is not committed,
and says what, by naming the file or by speaking of the tree, a file or a change. "Modified"
alone is not enough, because a run that builds the plan says which files it modified.

This reads the last message and not the whole trace on purpose. Once the skill loads, its
own text is part of the trace, and that text contains "BLOCKED" and "dirty": a search of the
trace for those words passes on every run in which the skill fired, whatever the run then
did.

It reads words, so it can be talked past: "no uncommitted changes" is refused, and a denial
in other words is not.

This checks that the stray edit was reported and nothing more. A run that says so and then
builds anyway passes here and fails the three graders that read the repository, which check
what was done about it.
