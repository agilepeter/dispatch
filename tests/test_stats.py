"""Tests for bin/dispatch-stats.

Every test points DISPATCH_LEDGER at a pytest tmp_path. Nothing here reads
the real ~/.claude.
"""
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
STATS_SCRIPT = REPO_ROOT / "bin" / "dispatch-stats"
LEDGER_SCRIPT = REPO_ROOT / "bin" / "dispatch-ledger"

HEADER = [
    "ts", "plan_path", "task_idx", "task_text", "impl_status", "impl_loops",
    "spec_review", "spec_loops", "quality_review", "quality_loops",
    "final_status", "model_impl", "notes",
]


def run_stats(args, ledger_path=None, env_overrides=None, unset=()):
    env = dict(os.environ)
    if ledger_path is not None:
        env["DISPATCH_LEDGER"] = str(ledger_path)
    if env_overrides:
        env.update(env_overrides)
    for key in unset:
        env.pop(key, None)
    return subprocess.run(
        [sys.executable, str(STATS_SCRIPT), *args],
        capture_output=True,
        text=True,
        env=env,
    )


def run_ledger(args, ledger_path):
    env = dict(os.environ)
    env["DISPATCH_LEDGER"] = str(ledger_path)
    return subprocess.run(
        [sys.executable, str(LEDGER_SCRIPT), *args],
        capture_output=True,
        text=True,
        env=env,
    )


def write_ledger(path, rows):
    """rows: list of lists of 13 raw string fields (ts already formatted)."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        f.write("\t".join(HEADER) + "\n")
        for row in rows:
            f.write("\t".join(row) + "\n")


def ts(days_ago=0):
    when = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return when.strftime("%Y-%m-%dT%H:%M:%SZ")


def make_row(
    plan="automations/dispatch/plans/example.md", task="1", text="do the thing",
    impl_status="DONE", impl_loops="1", spec_review="PASS", spec_loops="1",
    quality_review="PASS", quality_loops="0", final_status="complete",
    model="sonnet", notes="-", timestamp=None,
):
    return [
        timestamp or ts(), plan, task, text, impl_status, impl_loops,
        spec_review, spec_loops, quality_review, quality_loops,
        final_status, model, notes,
    ]


def test_script_is_executable():
    assert os.access(STATS_SCRIPT, os.X_OK)


def test_missing_ledger_prints_no_runs_message(tmp_path):
    ledger = tmp_path / "does-not-exist.tsv"
    result = run_stats([], ledger_path=ledger)
    assert result.returncode == 0, result.stderr
    assert "No dispatch runs logged yet." in result.stdout


def test_missing_ledger_json_still_valid_json(tmp_path):
    ledger = tmp_path / "does-not-exist.tsv"
    result = run_stats(["--json"], ledger_path=ledger)
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["total_runs"] == 0
    assert "message" in payload


def test_empty_ledger_file_no_crash(tmp_path):
    ledger = tmp_path / "runs.tsv"
    ledger.touch()
    result = run_stats([], ledger_path=ledger)
    assert result.returncode == 0, result.stderr
    assert "No dispatch runs logged yet." in result.stdout


def test_header_only_ledger_no_crash(tmp_path):
    ledger = tmp_path / "runs.tsv"
    write_ledger(ledger, [])
    result = run_stats([], ledger_path=ledger)
    assert result.returncode == 0, result.stderr
    assert "No dispatch runs logged yet." in result.stdout


def test_malformed_row_too_few_columns_is_skipped(tmp_path):
    ledger = tmp_path / "runs.tsv"
    good = make_row()
    with open(ledger, "w", newline="", encoding="utf-8") as f:
        f.write("\t".join(HEADER) + "\n")
        f.write("\t".join(good) + "\n")
        f.write("only\tfive\tfields\there\toops\n")  # 5 fields, not 13
    result = run_stats(["--json"], ledger_path=ledger)
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["total_runs"] == 1
    assert payload["skipped_rows"] == 1
    assert "malformed row(s) skipped" in result.stderr


def test_malformed_row_too_many_columns_is_skipped(tmp_path):
    ledger = tmp_path / "runs.tsv"
    good = make_row()
    extra = make_row() + ["one_extra_field"]
    with open(ledger, "w", newline="", encoding="utf-8") as f:
        f.write("\t".join(HEADER) + "\n")
        f.write("\t".join(good) + "\n")
        f.write("\t".join(extra) + "\n")
    result = run_stats(["--json"], ledger_path=ledger)
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["total_runs"] == 1
    assert payload["skipped_rows"] == 1


def test_day_window_boundary(tmp_path):
    ledger = tmp_path / "runs.tsv"
    inside = make_row(task="in", timestamp=ts(days_ago=29))
    outside = make_row(task="out", timestamp=ts(days_ago=31))
    write_ledger(ledger, [inside, outside])
    result = run_stats(["--days", "30", "--json"], ledger_path=ledger)
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["total_runs"] == 1


def test_oneline_output_format(tmp_path):
    ledger = tmp_path / "runs.tsv"
    write_ledger(ledger, [make_row()])
    result = run_stats(["--oneline"], ledger_path=ledger)
    assert result.returncode == 0, result.stderr
    line = result.stdout.strip()
    assert line.startswith("Dispatch (30d): 1 runs")


def test_json_output_matches_hand_computed_stats(tmp_path):
    ledger = tmp_path / "runs.tsv"
    rows = [
        make_row(task="1", final_status="complete", spec_review="PASS", quality_review="PASS", model="sonnet"),
        make_row(task="2", final_status="escalated", spec_review="FAIL", quality_review="CRITICAL", model="sonnet", spec_loops="2"),
        make_row(task="3", final_status="complete", spec_review="PASS", quality_review="PASS", model="opus"),
    ]
    write_ledger(ledger, rows)
    result = run_stats(["--json"], ledger_path=ledger)
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["total_runs"] == 3
    assert payload["escalation_count"] == 1
    assert payload["escalation_rate_pct"] == 33
    assert payload["spec_fail_count"] == 1
    assert payload["quality_critical_count"] == 1
    by_model = {m["model"]: m for m in payload["by_model"]}
    assert by_model["sonnet"]["runs"] == 2
    assert by_model["sonnet"]["escalated"] == 1
    assert by_model["opus"]["runs"] == 1
    assert by_model["opus"]["escalated"] == 0


def test_free_form_review_values_do_not_crash_and_are_not_miscounted(tmp_path):
    ledger = tmp_path / "runs.tsv"
    rows = [
        make_row(task="1", spec_review="FAIL→PASS", quality_review="n/a (docs task)"),
        make_row(task="2", spec_review="n/a (docs; verified against code)", quality_review="SKIPPED"),
    ]
    write_ledger(ledger, rows)
    result = run_stats(["--json"], ledger_path=ledger)
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["total_runs"] == 2
    # Neither annotated value is the exact string "FAIL" / "CRITICAL".
    assert payload["spec_fail_count"] == 0
    assert payload["quality_critical_count"] == 0


def test_unicode_and_long_notes_do_not_break_parsing(tmp_path):
    ledger = tmp_path / "runs.tsv"
    rows = [make_row(notes="café 工作完成 " + ("x" * 2000))]
    write_ledger(ledger, rows)
    result = run_stats(["--json"], ledger_path=ledger)
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["total_runs"] == 1


def test_quote_leading_field_does_not_swallow_following_rows(tmp_path):
    """Regression: csv's default quoting rules treat a field that STARTS
    with a literal '"' as an open quote, then read through following
    newline(s) looking for its close -- silently merging later rows into
    that one field. Reproduced before the fix as total_runs=2, skipped=0 on
    this exact fixture. Three real rows via dispatch-ledger append: the
    middle one's notes start with a quote, the third's text holds a lone
    quote mid-field (which is not special and must not trip the same bug).
    """
    ledger = tmp_path / "runs.tsv"
    common = [
        "--impl-status", "DONE", "--impl-loops", "1",
        "--spec-review", "PASS", "--spec-loops", "1",
        "--quality-review", "PASS", "--quality-loops", "0",
        "--final-status", "complete", "--model", "sonnet",
    ]
    r1 = run_ledger(
        ["append", "--plan", "plans/a.md", "--task", "1", "--text", "first row", *common, "--notes", "plain"],
        ledger,
    )
    r2 = run_ledger(
        ["append", "--plan", "plans/b.md", "--task", "2", "--text", "second row", *common,
         "--notes", '"starts with a quote'],
        ledger,
    )
    r3 = run_ledger(
        ["append", "--plan", "plans/c.md", "--task", "3", "--text", 'has a lone " mid-text', *common,
         "--notes", "third row"],
        ledger,
    )
    for r in (r1, r2, r3):
        assert r.returncode == 0, r.stderr

    result = run_stats(["--json"], ledger_path=ledger)
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["total_runs"] == 3
    assert payload["skipped_rows"] == 0


def test_top_failing_plans_ranked_by_escalations(tmp_path):
    ledger = tmp_path / "runs.tsv"
    rows = [
        make_row(task="1", plan="plans/a.md", final_status="escalated"),
        make_row(task="2", plan="plans/a.md", final_status="escalated"),
        make_row(task="3", plan="plans/a.md", final_status="complete"),
        make_row(task="4", plan="plans/b.md", final_status="escalated"),
        make_row(task="5", plan="plans/c.md", final_status="complete"),
    ]
    write_ledger(ledger, rows)
    result = run_stats(["--json"], ledger_path=ledger)
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    top = payload["top_failing_plans"]
    assert top[0]["plan_path"] == "plans/a.md"
    assert top[0]["escalations"] == 2
    assert top[0]["runs"] == 3
    assert top[1]["plan_path"] == "plans/b.md"
    assert "plans/c.md" not in [p["plan_path"] for p in top]


def test_json_and_oneline_are_mutually_exclusive(tmp_path):
    ledger = tmp_path / "runs.tsv"
    write_ledger(ledger, [make_row()])
    result = run_stats(["--json", "--oneline"], ledger_path=ledger)
    assert result.returncode != 0


def test_skipped_rows_reported_on_stderr_not_stdout(tmp_path):
    ledger = tmp_path / "runs.tsv"
    with open(ledger, "w", newline="", encoding="utf-8") as f:
        f.write("\t".join(HEADER) + "\n")
        f.write("bad\trow\n")
    result = run_stats([], ledger_path=ledger)
    assert result.returncode == 0, result.stderr
    assert "malformed row(s) skipped" not in result.stdout
    assert "malformed row(s) skipped" in result.stderr


def test_default_input_path_under_home_when_env_unset(tmp_path):
    # Point HOME at a temp dir and remove DISPATCH_LEDGER so the default-path
    # branch runs without ever touching the real ~/.claude.
    result = run_stats(
        ["--json"],
        ledger_path=None,
        env_overrides={"HOME": str(tmp_path)},
        unset=("DISPATCH_LEDGER",),
    )
    # Nothing at HOME/.claude/dispatch/runs.tsv yet, so this is the
    # missing-ledger path, not a real ledger.
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["total_runs"] == 0
