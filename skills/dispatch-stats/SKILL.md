---
name: dispatch-stats
description: Show dispatch's rolling health numbers -- run counts, review-loop averages, and the escalation rate -- from the ledger.
---

Run the ledger's stats script and show its result as-is, unedited:

```
${CLAUDE_PLUGIN_ROOT}/bin/dispatch-stats --oneline
```

No runs logged yet: show the script's own message -- it handles a missing or empty ledger
without error, so there is nothing else to report or explain.

For the full breakdown instead of the one-line summary, run
`${CLAUDE_PLUGIN_ROOT}/bin/dispatch-stats` with no flags; for a different window, add
`--days N` to either form.
