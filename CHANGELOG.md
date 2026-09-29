# Changelog

## 0.1.0 - 2026-09-29

### Added

- dispatch skill: Build an approved plan of three or more checkbox tasks, one task at a time, with a fresh implementer, spec reviewer, quality reviewer, exit-code gate and ledger row per task.

- dispatch-resume skill: Continue an in-progress plan without retyping its path.

- dispatch-stats skill: Show the ledger's rolling health numbers.

- Six skill templates in skills/dispatch/templates/: plan.md (plan structure), design.md (program design pass), spec-review.md (spec compliance review), implementer-brief.md (task spec for implementer), quality-review.md (code quality review), final-review.md (final review gate).

- Three entry points: /dispatch <plan-path> (start or continue a plan), /dispatch-resume (continue without retyping path), /dispatch-stats (show health numbers).

- bin/dispatch-ledger: Append one row to the dispatch ledger. Guarantees: 13 columns (ts, plan_path, task_idx, task_text, impl_status, impl_loops, spec_review, spec_loops, quality_review, quality_loops, final_status, model_impl, notes); atomic creation via a hard-link barrier against races (fails loudly where hard links are unsupported); created with mode 0600 on POSIX; one-line error messages on stderr; row validation (impl_status and final_status are closed enums, required fields must be non-empty, notes are optional defaulting to "-", tabs and newlines sanitized to spaces).

- bin/dispatch-stats: Print rolling N-day stats from the ledger with optional --json flag. Guarantees: header validation (13 columns), row validation (field count matching header, timestamp parsing, non-negative loop counts), stable JSON output (fields: days, since, total_runs, avg_impl_loops, avg_spec_loops, avg_quality_loops, spec_fail_count, spec_fail_rate_pct, quality_critical_count, quality_critical_rate_pct, escalation_count, escalation_rate_pct, by_model, top_failing_plans, skipped_rows, optional message), blank lines silently ignored, malformed rows counted in skipped_rows and reported on stderr.

- .claude-plugin/plugin.json: Plugin manifest (name, version, description, author, license, homepage, repository).

- .claude-plugin/marketplace.json: Plugin marketplace entry.

- scripts/release-check.sh: Pre-release checklist. Checks version agreement among `.claude-plugin/plugin.json`, the latest `CHANGELOG.md` heading, and `.claude-plugin/marketplace.json`; runs `claude plugin validate --strict` on the plugin manifest and on the marketplace manifest, and a `claude plugin tag --dry-run`; and checks that the release tag (`<name>--v<version>`) does not already exist locally or on origin (`RELEASE_CHECK_OFFLINE=1` skips the origin check). Every check runs even after an earlier one fails, so one run reports everything that blocks the release. It only checks: it never creates or pushes a tag itself.

- scripts/eval-report.py: Turns one eval run into the numbers the repository publishes. `summarize` writes evals/reports/<version>/result.json (counts, scores, costs and durations; nothing a session said and no local path) and refuses a run that is partial, has an error in any session, or skipped a paid grader; `readme` rewrites the results block in README.md from that report; `check` exits 1 when the two disagree.

- Test suite: tests/test_ledger.py (tests for dispatch-ledger), tests/test_skill_references.py (validation of skill files, frontmatter, and references), tests/test_stats.py (tests for dispatch-stats), tests/test_release_check.py (tests for scripts/release-check.sh), tests/test_eval_graders.py (what each eval grader's pattern accepts and refuses), tests/test_eval_report.py (tests for scripts/eval-report.py, and the check that README.md and the committed report agree).

- evals/: A `claude plugin eval` suite of five cases, each against its own scaffolded fixture repo, run both with the plugin loaded and against a no-plugin baseline: design-doc-before-implementer (a design pass and one approval gate a plan before any implementer runs), spec-before-quality (spec review always precedes quality review), one-ledger-row-per-task (a task run logs exactly one well-formed ledger row), dirty-tree-blocks (an unrelated dirty tree stops the run cold, with no self-service git surgery), and reviewer-reads-code (spec review reads the code instead of trusting a claimed report). Release numbers live in evals/reports/0.1.0/.

- RELEASING.md: the release runbook, including the order of the first release and what users run to update or pin a version.

- CI: .github/workflows/ci.yml with matrix across Ubuntu, macOS, and Windows; Python 3.11; pytest suite on all three operating systems; plugin manifest validation on Ubuntu.
