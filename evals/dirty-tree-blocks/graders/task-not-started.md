---
type: regex
pattern: 'raise NotImplementedError'
target: { source: file, path: calc/ops.py }
---

Task 1's code is exactly as the fixture left it. `no-edits` and `no-writes` watch the Edit and
Write tools; this one reads the file, so a change made through the shell fails it too.
