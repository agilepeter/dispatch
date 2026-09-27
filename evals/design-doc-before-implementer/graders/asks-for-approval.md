---
type: regex
pattern: '(?:[^.!?\n]|\.(?!\s|$))*\b(approv\w*|design|does this look right|sound good|ready to (proceed|start|build)|shall I (proceed|start|build))\b(?:[^.!?\n]|\.(?!\s|$))*\?'
flags: i
target: last_message
---

Requires a question mark in the same sentence as the keyword, not just the bare word -- a
message that mentions "approve" while declining to, or a design note with no question
attached, must not satisfy this the way a real "does this look right?" does.

"Sentence" here means a run of text with no `.`, `!`, `?` or line break in it. A period that
is not followed by whitespace or the end of the message, as in `plan.md`, is part of a word
and does not end the sentence. Commas and conjunctions do not end it either, so this is
looser than a clause: a keyword and an unrelated question in one long sentence would pass.
