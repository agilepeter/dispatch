"""Tests for bin/dispatch-ledger.

Every test points DISPATCH_LEDGER (or, for the one default-path test, HOME)
at a pytest tmp_path. Nothing here reads or writes the real ~/.claude.
"""
import csv
import os
import subprocess
import sys
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
LEDGER_SCRIPT = REPO_ROOT / "bin" / "dispatch-ledger"

HEADER = [
    "ts", "plan_path", "task_idx", "task_text", "impl_status", "impl_loops",
    "spec_review", "spec_loops", "quality_review", "quality_loops",
    "final_status", "model_impl", "notes",
]

BASE_APPEND_ARGS = [
    "append",
    "--plan", "automations/dispatch/plans/example.md",
    "--task", "3",
    "--text", "Write the ledger CLI and its tests",
    "--impl-status", "DONE",
    "--impl-loops", "1",
    "--spec-review", "PASS",
    "--spec-loops", "1",
    "--quality-review", "PASS",
    "--quality-loops", "0",
    "--final-status", "complete",
    "--model", "sonnet",
]


def run_ledger(args, ledger_path=None, env_overrides=None, unset=()):
    env = dict(os.environ)
    if ledger_path is not None:
        env["DISPATCH_LEDGER"] = str(ledger_path)
    if env_overrides:
        env.update(env_overrides)
    for key in unset:
        env.pop(key, None)
    return subprocess.run(
        [sys.executable, str(LEDGER_SCRIPT), *args],
        capture_output=True,
        text=True,
        env=env,
    )


def read_rows(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.reader(f, delimiter="\t"))


def assert_one_line_stderr(result):
    """Bad input must exit non-zero with exactly one line on stderr: no
    argparse usage block, just the "prog: error: ..." line."""
    assert result.returncode != 0
    stderr = result.stderr
    assert stderr.endswith("\n"), repr(stderr)
    lines = stderr.splitlines()
    assert len(lines) == 1, f"expected exactly one stderr line, got {len(lines)}: {stderr!r}"
    assert ": error:" in lines[0]
    return lines[0]


def test_script_is_executable():
    assert os.access(LEDGER_SCRIPT, os.X_OK)


def test_append_creates_ledger_with_header_and_row(tmp_path):
    ledger = tmp_path / "runs.tsv"
    result = run_ledger(BASE_APPEND_ARGS, ledger_path=ledger)
    assert result.returncode == 0, result.stderr
    assert ledger.exists()
    rows = read_rows(ledger)
    assert rows[0] == HEADER
    assert len(rows) == 2
    assert len(rows[1]) == 13


def test_append_twice_header_appears_once(tmp_path):
    ledger = tmp_path / "runs.tsv"
    first = run_ledger(BASE_APPEND_ARGS, ledger_path=ledger)
    second = run_ledger(BASE_APPEND_ARGS, ledger_path=ledger)
    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    rows = read_rows(ledger)
    assert rows.count(HEADER) == 1
    assert len(rows) == 3  # header + 2 data rows


def test_creates_parent_directory(tmp_path):
    ledger = tmp_path / "nested" / "dir" / "runs.tsv"
    result = run_ledger(BASE_APPEND_ARGS, ledger_path=ledger)
    assert result.returncode == 0, result.stderr
    assert ledger.exists()


def test_tabs_and_newlines_replaced_with_spaces(tmp_path):
    ledger = tmp_path / "runs.tsv"
    args = list(BASE_APPEND_ARGS)
    args[args.index("--text") + 1] = "Line one\twith a tab\nand a newline\r\nand crlf"
    result = run_ledger(args, ledger_path=ledger)
    assert result.returncode == 0, result.stderr
    rows = read_rows(ledger)
    data_row = rows[1]
    assert len(data_row) == 13
    assert "\t" not in data_row[3]
    assert "\n" not in data_row[3]
    assert data_row[3] == "Line one with a tab and a newline and crlf"


def test_bare_carriage_return_replaced_with_space(tmp_path):
    # sanitize() handles \t, \n, and \r\n; this covers the fourth case, a
    # lone \r with no following \n (an old Mac-style line ending).
    ledger = tmp_path / "runs.tsv"
    args = list(BASE_APPEND_ARGS)
    args[args.index("--text") + 1] = "before\rafter"
    result = run_ledger(args, ledger_path=ledger)
    assert result.returncode == 0, result.stderr
    rows = read_rows(ledger)
    data_row = rows[1]
    assert len(data_row) == 13
    assert "\r" not in data_row[3]
    assert data_row[3] == "before after"


def test_unicode_notes_roundtrip(tmp_path):
    ledger = tmp_path / "runs.tsv"
    note = "café — 工作完成 \U0001F680"
    args = list(BASE_APPEND_ARGS) + ["--notes", note]
    result = run_ledger(args, ledger_path=ledger)
    assert result.returncode == 0, result.stderr
    rows = read_rows(ledger)
    assert rows[1][-1] == note


def test_long_notes_field_not_truncated(tmp_path):
    ledger = tmp_path / "runs.tsv"
    long_note = "x" * 2000
    args = list(BASE_APPEND_ARGS) + ["--notes", long_note]
    result = run_ledger(args, ledger_path=ledger)
    assert result.returncode == 0, result.stderr
    rows = read_rows(ledger)
    assert rows[1][-1] == long_note
    assert len(rows[1]) == 13


def test_notes_defaults_to_dash_when_omitted(tmp_path):
    ledger = tmp_path / "runs.tsv"
    result = run_ledger(BASE_APPEND_ARGS, ledger_path=ledger)
    assert result.returncode == 0, result.stderr
    rows = read_rows(ledger)
    assert rows[1][-1] == "-"


def test_notes_defaults_to_dash_when_blank(tmp_path):
    ledger = tmp_path / "runs.tsv"
    args = list(BASE_APPEND_ARGS) + ["--notes", "   "]
    result = run_ledger(args, ledger_path=ledger)
    assert result.returncode == 0, result.stderr
    rows = read_rows(ledger)
    assert rows[1][-1] == "-"


@pytest.mark.parametrize("task_idx", ["17b", "13+14", "1b", "10"])
def test_free_form_task_idx_accepted(tmp_path, task_idx):
    ledger = tmp_path / "runs.tsv"
    args = list(BASE_APPEND_ARGS)
    args[args.index("--task") + 1] = task_idx
    result = run_ledger(args, ledger_path=ledger)
    assert result.returncode == 0, result.stderr
    rows = read_rows(ledger)
    assert rows[1][2] == task_idx


def test_free_form_spec_review_values_accepted(tmp_path):
    ledger = tmp_path / "runs.tsv"
    for value in ["FAIL→PASS", "n/a (docs task; no code to review)"]:
        args = list(BASE_APPEND_ARGS)
        args[args.index("--spec-review") + 1] = value
        result = run_ledger(args, ledger_path=ledger)
        assert result.returncode == 0, result.stderr
    rows = read_rows(ledger)
    assert rows[1][6] == "FAIL→PASS"
    assert rows[2][6] == "n/a (docs task; no code to review)"


def test_free_form_quality_review_values_accepted(tmp_path):
    ledger = tmp_path / "runs.tsv"
    args = list(BASE_APPEND_ARGS)
    args[args.index("--quality-review") + 1] = "n/a (single combined review)"
    result = run_ledger(args, ledger_path=ledger)
    assert result.returncode == 0, result.stderr
    rows = read_rows(ledger)
    assert rows[1][8] == "n/a (single combined review)"


def test_timestamp_is_utc_iso8601_with_z(tmp_path):
    ledger = tmp_path / "runs.tsv"
    before = datetime.now(timezone.utc).replace(microsecond=0)
    result = run_ledger(BASE_APPEND_ARGS, ledger_path=ledger)
    after = datetime.now(timezone.utc)
    assert result.returncode == 0, result.stderr
    rows = read_rows(ledger)
    ts_raw = rows[1][0]
    assert ts_raw.endswith("Z")
    ts = datetime.strptime(ts_raw, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    assert before <= ts <= after + timedelta(seconds=1)


@pytest.mark.parametrize("bad_value", ["MAYBE", "done", ""])
def test_invalid_impl_status_rejected(tmp_path, bad_value):
    ledger = tmp_path / "runs.tsv"
    args = list(BASE_APPEND_ARGS)
    args[args.index("--impl-status") + 1] = bad_value
    result = run_ledger(args, ledger_path=ledger)
    assert_one_line_stderr(result)
    assert not ledger.exists()


def test_invalid_final_status_rejected(tmp_path):
    ledger = tmp_path / "runs.tsv"
    args = list(BASE_APPEND_ARGS)
    args[args.index("--final-status") + 1] = "done"
    result = run_ledger(args, ledger_path=ledger)
    assert_one_line_stderr(result)
    assert not ledger.exists()


@pytest.mark.parametrize("bad_value", ["-1", "abc"])
def test_invalid_loop_counts_rejected(tmp_path, bad_value):
    ledger = tmp_path / "runs.tsv"
    args = list(BASE_APPEND_ARGS)
    args[args.index("--impl-loops") + 1] = bad_value
    result = run_ledger(args, ledger_path=ledger)
    assert_one_line_stderr(result)
    assert not ledger.exists()


def test_empty_text_rejected(tmp_path):
    ledger = tmp_path / "runs.tsv"
    args = list(BASE_APPEND_ARGS)
    args[args.index("--text") + 1] = ""
    result = run_ledger(args, ledger_path=ledger)
    line = assert_one_line_stderr(result)
    assert "--text" in line
    assert not ledger.exists()


def test_missing_required_argument_rejected(tmp_path):
    ledger = tmp_path / "runs.tsv"
    args = [
        "append",
        "--task", "3", "--text", "x", "--impl-status", "DONE",
        "--impl-loops", "1", "--spec-review", "PASS", "--spec-loops", "1",
        "--quality-review", "PASS", "--quality-loops", "0",
        "--final-status", "complete", "--model", "sonnet",
    ]  # --plan omitted
    result = run_ledger(args, ledger_path=ledger)
    line = assert_one_line_stderr(result)
    assert "--plan" in line
    assert not ledger.exists()


def test_no_subcommand_stderr_is_one_line(tmp_path):
    # The fix has to hold on the top-level parser too, not only "append".
    ledger = tmp_path / "runs.tsv"
    result = run_ledger([], ledger_path=ledger)
    assert_one_line_stderr(result)
    assert not ledger.exists()


def test_unknown_subcommand_stderr_is_one_line(tmp_path):
    ledger = tmp_path / "runs.tsv"
    result = run_ledger(["bogus"], ledger_path=ledger)
    assert_one_line_stderr(result)
    assert not ledger.exists()


def test_default_ledger_path_under_home_when_env_unset(tmp_path):
    # Point HOME at a temp dir and remove DISPATCH_LEDGER so the default-path
    # branch runs end to end without ever touching the real ~/.claude.
    result = run_ledger(
        BASE_APPEND_ARGS,
        ledger_path=None,
        env_overrides={"HOME": str(tmp_path)},
        unset=("DISPATCH_LEDGER",),
    )
    assert result.returncode == 0, result.stderr
    expected = tmp_path / ".claude" / "dispatch" / "runs.tsv"
    assert expected.exists()


def test_concurrent_appends_produce_one_header_and_n_clean_rows(tmp_path):
    ledger = tmp_path / "runs.tsv"
    n = 20
    results = [None] * n

    def worker(i):
        args = list(BASE_APPEND_ARGS)
        args[args.index("--task") + 1] = str(i)
        results[i] = run_ledger(args, ledger_path=ledger)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    for r in results:
        assert r.returncode == 0, r.stderr

    rows = read_rows(ledger)
    assert rows.count(HEADER) == 1
    data_rows = [r for r in rows if r != HEADER]
    assert len(data_rows) == n
    for row in data_rows:
        assert len(row) == 13
    seen_tasks = sorted(int(r[2]) for r in data_rows)
    assert seen_tasks == list(range(n))
