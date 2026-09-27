---
type: tool_used
tool: Bash
input_match: 'dispatch-ledger append'
min: 1
max: 1
---

One task run must log exactly one ledger row -- not zero, and not a duplicate from a retry
that forgot it already logged.
