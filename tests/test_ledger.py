"""Tests for bin/dispatch-ledger.

Every test points DISPATCH_LEDGER (or, for the one default-path test, HOME)
at a pytest tmp_path. Nothing here reads or writes the real ~/.claude.
"""
import csv
import importlib.util
import os
import stat
import subprocess
import sys
import threading
from datetime import datetime, timedelta, timezone
from importlib.machinery import SourceFileLoader
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


def load_ledger_module():
    """Import bin/dispatch-ledger (no .py suffix, so it needs an explicit
    loader) so tests can call its internal functions directly, for the
    race simulation below where a deterministic call order matters more
    than a real black-box subprocess invocation would let us control."""
    loader = SourceFileLoader("dispatch_ledger_under_test", str(LEDGER_SCRIPT))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


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


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX executable-bit semantics don't apply on Windows")
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


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX file mode bits don't apply on Windows")
def test_ledger_created_with_mode_0600(tmp_path):
    ledger = tmp_path / "runs.tsv"
    run_ledger(BASE_APPEND_ARGS, ledger_path=ledger)
    mode = stat.S_IMODE(ledger.stat().st_mode)
    assert mode == 0o600, oct(mode)


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


def test_sanitize_replaces_lone_surrogate_with_replacement_char():
    """Direct, platform-independent unit test for the surrogateescape fix.
    A lone surrogate codepoint is exactly what sys.argv holds, on a POSIX
    mangled locale, for an argument byte that is not valid UTF-8; a strict
    .encode("utf-8") on that string raises UnicodeEncodeError. Constructed
    here as a literal so it runs identically on every OS, unlike a real
    subprocess argv injection -- see the skipped end-to-end test below for
    why that path is POSIX-only."""
    mod = load_ledger_module()
    result = mod.sanitize("caf\udce9 with an invalid byte")
    assert result == "caf� with an invalid byte"


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="Windows subprocess command-line building (list2cmdline) must "
           "decode every argv byte to build one command-line string before "
           "the child process even starts, so a raw invalid UTF-8 byte can't "
           "reach a child's argv the way a POSIX mangled locale allows; the "
           "platform-independent unit test above covers the same sanitize() "
           "fix directly.",
)
def test_invalid_utf8_argv_byte_is_replaced_not_crashed(tmp_path):
    """End-to-end: the same fix, exercised through a real subprocess with a
    genuinely invalid byte in one argv element, on the platforms where that
    is possible to construct at all."""
    ledger = tmp_path / "runs.tsv"
    argv = [sys.executable, str(LEDGER_SCRIPT)] + list(BASE_APPEND_ARGS) + ["--notes", "placeholder"]
    argv_bytes = [os.fsencode(a) if isinstance(a, str) else a for a in argv]
    argv_bytes[argv.index("--notes") + 1] = b"caf\xe9 with an invalid byte"

    env = dict(os.environ)
    env["DISPATCH_LEDGER"] = str(ledger)
    result = subprocess.run(argv_bytes, capture_output=True, env=env)
    assert result.returncode == 0, result.stderr

    content = ledger.read_text(encoding="utf-8")
    assert "caf� with an invalid byte" in content
    assert "\xe9" not in content  # the raw invalid byte must not survive as-is


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
    # Point the home directory at a temp dir and remove DISPATCH_LEDGER so
    # the default-path branch runs end to end without ever touching the
    # real ~/.claude. Path.home() reads HOME on POSIX but USERPROFILE on
    # Windows (ntpath.expanduser never looks at HOME), so both must be set
    # or this silently falls through to the real home directory instead.
    result = run_ledger(
        BASE_APPEND_ARGS,
        ledger_path=None,
        env_overrides={"HOME": str(tmp_path), "USERPROFILE": str(tmp_path)},
        unset=("DISPATCH_LEDGER",),
    )
    assert result.returncode == 0, result.stderr
    expected = tmp_path / ".claude" / "dispatch" / "runs.tsv"
    assert expected.exists()


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="On Windows, O_APPEND is emulated by the C runtime rather than "
           "guaranteed atomic by the OS, and a writer's view of the file's "
           "last byte can go stale against another process's append that "
           "just landed. Two writers that both read a stale non-newline "
           "last byte each prepend a newline to close a torn line, and the "
           "second one leaves a blank line (which dispatch-stats skips), so "
           "this 20-process stress test is not a meaningful check there. "
           "POSIX filesystems serialise a write against the reads around it, "
           "so the guard cannot misfire there. The header's own creation "
           "race is covered on every OS by the two tests that force it.",
)
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


def test_first_write_race_header_stays_on_line_one(tmp_path):
    """Forces the actual race rather than simulating it with two sequential
    calls: patches os.link so the FIRST writer blocks, via a
    threading.Event, right after it has written its temp header but
    before it links that file into place. While it is blocked, a second
    append_row runs to completion on the main thread against the same
    path. Releasing the first writer then lets its os.link() discover the
    ledger already exists (FileExistsError) and fall through to appending
    its own row after the second writer's. This is the exact interleaving
    the mkstemp-plus-link design has to survive, and the one a purely
    sequential test (create, create-again, append, append) cannot exercise
    -- it would pass against the old create-and-write-together code just
    as easily as this one, which is why this version drives it with a
    real second thread instead.
    """
    mod = load_ledger_module()
    ledger = tmp_path / "runs.tsv"

    real_link = mod.os.link
    first_writer_paused = threading.Event()
    release_first_writer = threading.Event()
    link_call_count = [0]

    def blocking_link(src, dst):
        link_call_count[0] += 1
        if link_call_count[0] == 1:
            first_writer_paused.set()
            assert release_first_writer.wait(timeout=5), "test deadlocked waiting to be released"
        return real_link(src, dst)

    mod.os.link = blocking_link
    try:
        row_a = ["ts-a", "plan-a", "1", "text-a", "DONE", "1", "PASS", "1", "PASS", "0", "complete", "sonnet", "-"]
        row_b = ["ts-b", "plan-b", "2", "text-b", "DONE", "1", "PASS", "1", "PASS", "0", "complete", "sonnet", "-"]
        results = {}

        def first_writer():
            mod.append_row(ledger, row_a)
            results["a"] = "done"

        thread_a = threading.Thread(target=first_writer)
        thread_a.start()
        try:
            assert first_writer_paused.wait(timeout=5), "first writer never reached its os.link call"

            # Second writer, on the main thread, runs to completion while
            # the first is blocked mid-creation.
            mod.append_row(ledger, row_b)
            results["b"] = "done"
        finally:
            release_first_writer.set()
            thread_a.join(timeout=5)
        assert not thread_a.is_alive(), "first writer's thread did not finish"
        assert results == {"a": "done", "b": "done"}
    finally:
        mod.os.link = real_link

    lines = ledger.read_text(encoding="utf-8").splitlines()
    header = "\t".join(mod.HEADER)
    assert lines.count(header) == 1
    assert lines[0] == header
    data_lines = [line for line in lines if line != header]
    assert len(data_lines) == 2
    assert any(line.startswith("ts-a\t") for line in data_lines)
    assert any(line.startswith("ts-b\t") for line in data_lines)


def test_row_appended_the_moment_the_ledger_appears_survives(tmp_path):
    """The ledger must never become visible before its header is complete.
    Pauses the creator right AFTER its os.link() succeeds and lets a
    bystander append in that window: the bystander takes the fast path
    (the file exists) and appends at end of file. If the header were
    linked in empty and written afterwards through a non-append handle,
    that write would land at offset 0 and destroy the bystander's row;
    the pause before os.link in the test above cannot see that ordering.
    """
    mod = load_ledger_module()
    ledger = tmp_path / "runs.tsv"

    real_link = mod.os.link
    creator_linked = threading.Event()
    release_creator = threading.Event()
    link_call_count = [0]

    def link_then_pause(src, dst):
        result = real_link(src, dst)
        link_call_count[0] += 1
        if link_call_count[0] == 1:
            creator_linked.set()
            assert release_creator.wait(timeout=5), "test deadlocked waiting to be released"
        return result

    mod.os.link = link_then_pause
    try:
        row_a = ["ts-a", "plan-a", "1", "text-a", "DONE", "1", "PASS", "1", "PASS", "0", "complete", "sonnet", "-"]
        row_c = ["ts-c", "plan-c", "3", "text-c", "DONE", "1", "PASS", "1", "PASS", "0", "complete", "sonnet", "-"]
        results = {}

        def creator():
            mod.append_row(ledger, row_a)
            results["a"] = "done"

        thread_a = threading.Thread(target=creator)
        thread_a.start()
        try:
            assert creator_linked.wait(timeout=5), "creator never linked the ledger into place"
            mod.append_row(ledger, row_c)
            results["c"] = "done"
        finally:
            release_creator.set()
            thread_a.join(timeout=5)
        assert not thread_a.is_alive(), "creator's thread did not finish"
        assert results == {"a": "done", "c": "done"}
    finally:
        mod.os.link = real_link

    lines = ledger.read_text(encoding="utf-8").splitlines()
    header = "\t".join(mod.HEADER)
    assert lines[0] == header
    assert lines.count(header) == 1
    data_lines = [line for line in lines if line != header]
    assert len(data_lines) == 2
    assert any(line.startswith("ts-a\t") for line in data_lines)
    assert any(line.startswith("ts-c\t") for line in data_lines)


def test_append_to_existing_ledger_creates_no_temp_file(tmp_path):
    """ensure_ledger_header()'s fast path (the ledger already exists) must
    skip the temp-file-and-link dance entirely, not just skip the link
    itself -- listing the directory before and after an append to an
    already-created ledger must show no new file of any kind."""
    mod = load_ledger_module()
    ledger = tmp_path / "runs.tsv"
    mod.ensure_ledger_header(ledger)

    before = set(os.listdir(tmp_path))
    mod.append_row(ledger, ["ts-a", "plan-a", "1", "text-a", "DONE", "1", "PASS", "1", "PASS", "0", "complete", "sonnet", "-"])
    after = set(os.listdir(tmp_path))

    assert after - before == set(), f"unexpected new file(s) in the ledger directory: {after - before}"


def test_ensure_ledger_header_fails_loudly_when_hard_links_unsupported(tmp_path, monkeypatch, capsys):
    """When os.link fails for a reason OTHER than the destination already
    existing (no hard-link support on this filesystem), the only safe move
    is to fail: any fallback that creates the file and then writes the
    header as a second, separate step reintroduces the very race this
    module exists to close (a concurrent row can land in the empty file
    between the create and the header write, then be overwritten when the
    header lands at offset 0). This must surface as the same one-line
    stderr contract as any other write failure, and must leave no
    half-created ledger behind. Tested in-process (like the race test
    above) so os.link itself can be monkeypatched; main() reads its ledger
    path from the environment, same as a real invocation would.
    """
    mod = load_ledger_module()
    ledger = tmp_path / "runs.tsv"

    def fake_link(src, dst):
        raise OSError(1, "Operation not permitted (simulated: no hard link support)")

    monkeypatch.setattr(mod.os, "link", fake_link)
    monkeypatch.setenv("DISPATCH_LEDGER", str(ledger))

    argv = [
        "append", "--plan", "plans/a.md", "--task", "1", "--text", "hi",
        "--impl-status", "DONE", "--impl-loops", "1",
        "--spec-review", "PASS", "--spec-loops", "1",
        "--quality-review", "PASS", "--quality-loops", "0",
        "--final-status", "complete", "--model", "sonnet",
    ]
    exit_code = mod.main(argv)
    captured = capsys.readouterr()

    assert exit_code == 1
    lines = captured.err.splitlines()
    assert len(lines) == 1, f"expected exactly one stderr line, got: {captured.err!r}"
    assert "cannot create it safely" in lines[0]
    assert "no hard links" in lines[0]
    assert not ledger.exists()
    assert not any(p.name.startswith(".dispatch-ledger-tmp-") for p in tmp_path.iterdir())


def test_torn_last_line_does_not_corrupt_next_append(tmp_path):
    """A ledger whose last line has no trailing newline (a previous short
    write) must not swallow the next append into the same line: the guard
    detects the missing newline and inserts one first, so the new row
    lands intact on its own line and dispatch-stats counts it."""
    mod = load_ledger_module()
    ledger = tmp_path / "runs.tsv"
    mod.ensure_ledger_header(ledger)
    with open(ledger, "a", encoding="utf-8") as f:
        f.write("torn-ts\tplan\t1\ttext\tDONE\t1\tPASS\t1\tPASS\t0\tcomplete\tsonnet\t-")  # no trailing \n

    new_ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    mod.append_row(ledger, [new_ts, "plan-new", "2", "text-new", "DONE", "1", "PASS", "1", "PASS", "0", "complete", "sonnet", "-"])

    lines = ledger.read_text(encoding="utf-8").splitlines()
    assert any(line.startswith("torn-ts\t") for line in lines)
    new_line = next(line for line in lines if line.startswith(new_ts + "\t"))
    assert new_line.count("\t") == 12  # 13 fields, intact and not glued to the torn line

    stats_script = REPO_ROOT / "bin" / "dispatch-stats"
    env = dict(os.environ)
    env["DISPATCH_LEDGER"] = str(ledger)
    result = subprocess.run([sys.executable, str(stats_script), "--json"], capture_output=True, text=True, env=env)
    assert result.returncode == 0, result.stderr
    import json
    payload = json.loads(result.stdout)
    assert payload["total_runs"] == 1  # only the new, well-formed row
    assert payload["skipped_rows"] == 1  # the torn line (bad "ts" value), counted, not crashed
