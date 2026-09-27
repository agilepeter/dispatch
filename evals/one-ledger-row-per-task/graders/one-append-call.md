---
type: tool_used
tool: Bash
input_match: '"command":\s*"(?:(?:[^"\\]|\\.)*?(?:\\[nt]|[;&|(]))?\s*(?:(?:then|do|else)\s+)?(?:(?:command|exec|nohup|time)\s+)*(?:env(?:\s+-\S+)*\s+)?(?:\w+=(?:\\"[^"]*?\\"|\x27[^\x27]*\x27|[^\s"\x27\\]*)\s+)*(?:(?:ba|z|da)?sh\s+(?:-\S+\s+)*?-\w*c\s+(?:\\"|\x27)\s*(?:\w+=(?:\\"[^"]*?\\"|\x27[^\x27]*\x27|[^\s"\x27\\]*)\s+)*)?(?:python3?\s+)?(?:\\"(?:[^"\\]*/)?dispatch-ledger\\"|\x27(?:[^\x27"\\]*/)?dispatch-ledger\x27|(?:[^\s"\x27;&|\\]*/)?dispatch-ledger)\s+append\b'
min: 1
max: 1
---

One task run must log exactly one ledger row -- not zero, and not a duplicate from a retry
that forgot it already logged. `ledger-row-shape` counts the rows in the file, and is the
one to believe about whether a row was written; this counts the calls that wrote them.

The pattern is matched against the JSON form of the tool call, so it is anchored inside the
command's own string and requires `dispatch-ledger` to stand where a command stands: at the
start, or after a line break, `;`, `&`, `|` or `(`. In between it allows what may precede a
command word: `then`, `do` or `else`; `command`, `exec`, `nohup` or `time`; `env` and its
flags; `NAME=value` prefixes; and `sh -c` or `bash -c` with its opening quote. The command
word may be bare or a path, quoted or not (a quoted path may hold spaces), or run through
`python3`. An `echo`, a comment,
a `grep` for the phrase, or a description that mentions it does not count.

Known limit: a line of a here-document that begins with the phrase is text being written to
a file, and it is counted as a call. The pattern cannot tell the two apart without
following the shell's own grammar.
