# Changelog

## 0.1.0 - 2026-09-26

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

- Test suite: tests/test_ledger.py (tests for dispatch-ledger), tests/test_skill_references.py (validation of skill files, frontmatter, and references), tests/test_stats.py (tests for dispatch-stats).

- CI: .github/workflows/ci.yml with matrix across Ubuntu, macOS, and Windows; Python 3.11; pytest suite on all three operating systems; plugin manifest validation on Ubuntu.
