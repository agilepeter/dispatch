---
max_turns: 40
timeout_seconds: 900
allowed_tools: [Skill, Agent, Read, Glob, Grep, TodoWrite, AskUserQuestion, Bash]
append_system_prompt: "Environment note: in this sandbox, a bare `git` command sometimes fails with an xcrun cache error such as `couldn't create cache file ... Operation not permitted`. If that happens, retry the exact same git command using the absolute path from `xcode-select -p` instead, e.g. `$(xcode-select -p)/usr/bin/git status --short`."
---

Here is my approved plan for the calc package, in plan.md, with its design doc already
reviewed. Build task 1 only for now -- I'll ask for the rest separately. Keep this run's
ledger at ./.dispatch/runs.tsv (set the DISPATCH_LEDGER environment variable to that path
before calling dispatch-ledger).
