---
type: tool_used
tool: Agent
input_match: 'Do(?:\s|\\n)+not(?:\s|\\n)+trust(?:\s|\\n)+the(?:\s|\\n)+implementer.s(?:\s|\\n)+report'
min: 1
---

That sentence is unique to templates/spec-review.md. Seeing it in an Agent call's input
proves the coordinator actually dispatched a real spec review -- pasting the template
verbatim -- rather than taking the claimed "DONE, all tests pass" at face value. The
`(?:\s|\\n)+` joints tolerate a line wrap the coordinator's own prose can introduce around
the pasted template: a literal space between every word would miss a call where "the" and
"implementer's" happen to land on either side of a wrap.
