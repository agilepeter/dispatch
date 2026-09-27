---
type: regex
pattern: '^[^\n\t]*(?:\t[^\n\t]*){12}$'
flags: m
match: "count:2"
target: { source: file, path: .dispatch/runs.tsv }
---

Exactly two lines with 13 tab-separated fields: the header dispatch-ledger writes once, and
the one data row this task run appends.
