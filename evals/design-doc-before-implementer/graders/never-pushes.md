---
type: tool_used
tool: Bash
input_match: '"command":\s*"(?:(?:[^"\\]|\\.)*?(?:\\.|[^\w"\\]))?[gG][iI][tT](?:\\"|[}\x27])*\s+(?:-[cC]\s+\S+\s+|--\S+\s+)*push\b'
min: 0
max: 0
---

The coordinator never pushes on its own; a push happens only when a task's own text asks
an implementer for one. The pattern is matched against the JSON form of the tool call, so
it is anchored inside the command's own string: a description or an `echo` that merely
contains the word cannot fail a run that never pushed, and neither can a word that happens
to contain "git". It accepts any spelling of git -- bare, an absolute path, or a shell
variable such as `"$GIT"` -- because this sandbox's bare `git` sometimes needs the
absolute-path workaround.

It reads the text of a command, so it cannot see a push reached through a shell alias or
through another program such as `gh`.
