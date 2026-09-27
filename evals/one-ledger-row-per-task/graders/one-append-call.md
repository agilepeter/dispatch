---
type: tool_used
tool: Bash
input_match: '(^|[/\s])dispatch-ledger append\b'
min: 1
max: 1
---

One task run must log exactly one ledger row -- not zero, and not a duplicate from a retry
that forgot it already logged. Anchored so a command that merely mentions the phrase in
passing -- an echo, a comment -- can't satisfy this the way a real invocation, bare or by its
full path, does.
