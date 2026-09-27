---
type: regex
pattern: '(?:[^.!?\n]|\.(?!\s|$))*\b(approv\w*|design|does this look right|sound good|ready to (proceed|start|build)|shall I (proceed|start|build))\b(?:[^.!?\n]|\.(?!\s|$))*\?'
flags: i
target: last_message
---

Requires an actual question mark in the same clause as the keyword, not just the bare word --
a message that mentions "approve" while declining to (or a design note with no question
attached) must not satisfy this the way a real "does this look right?" does. A plain
`[^.!?]*` clause boundary is too strict for real messages, though: a filename like
`plan.md` carries a period that isn't a sentence end, and treating it as one can sever the
keyword from a question mark two words later in the same sentence. `\.(?!\s|$)` -- a period
not followed by whitespace or the end of the message -- is treated as part of a word, not a
clause break; only a period followed by whitespace (or nothing) counts as one.
