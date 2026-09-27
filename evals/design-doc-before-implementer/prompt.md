---
max_turns: 25
timeout_seconds: 300
allowed_tools: [Skill, Agent, Read, Glob, Grep, TodoWrite, AskUserQuestion, Bash]
append_system_prompt: "Environment note: in this sandbox, a bare `git` command sometimes fails with an xcrun cache error such as `couldn't create cache file ... Operation not permitted`. If that happens, retry the exact same git command using the absolute path from `xcode-select -p` instead, e.g. `$(xcode-select -p)/usr/bin/git status --short`."
---

Here's my plan for the calc package, in plan.md. Let's get started.
