---
type: tool_order
before: { tool: Agent, input_match: "Misunderstandings" }
after: { tool: Agent, input_match: "architecture" }
---

"Misunderstandings" is a word templates/spec-review.md's checklist uses and no other
template does; "architecture" is one templates/quality-review.md's opening paragraph uses
(final review shares it too, but this run only ever reaches task 1, so final review never
fires here). Since the coordinator pastes each template's full text verbatim into its
subagent's prompt, seeing these two words in this order proves a spec review was
dispatched before the quality review, never the other way round. Single, unbroken words
are used on purpose: a multi-word phrase can straddle a line wrap the coordinator's own
prose introduces around the pasted template, which would make a literal-space match miss
a real, correctly-ordered call.
