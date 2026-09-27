"""Tests for scripts/eval-report.py.

The script runs against a temp copy of the repo and a raw result built here, so nothing in
these tests needs an eval run, the claude binary or the network. The raw result is invented
but shaped like the real thing, including the parts that must never reach the report: local
paths, the prompt, and what a grader said about a session.
"""
import copy
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = Path("scripts") / "eval-report.py"

CASES = [
    "design-doc-before-implementer",
    "dirty-tree-blocks",
    "one-ledger-row-per-task",
    "reviewer-reads-code",
    "spec-before-quality",
]

SECRET_PROMPT = "the prompt a session was given"
SECRET_VERDICT = "what a grader said about a session"


def _session(score, graders):
    return {
        "score": score,
        "passed": score == 1,
        "turns": 10,
        "costUsd": 0.2,
        "judgeCostUsd": 0.001,
        "durationSeconds": 50,
        "startedAt": "2026-01-01T00:00:00.000Z",
        "error": None,
        "tracePath": "/private/tmp/e-AbCdEf/out/trace.jsonl",
        "skippedPaidGraders": False,
        "graders": [
            {
                "name": name,
                "passed": passed,
                "scored": name != "skill-fired",
                "weight": 1,
                "withOnly": name == "skill-fired",
                "explanation": f"{SECRET_VERDICT} in /Users/someone/work",
            }
            for name, passed in graders
        ],
    }


def _raw():
    good = [("does-the-thing", True), ("never-pushes", True), ("skill-fired", True)]
    poor = [("does-the-thing", False), ("never-pushes", True)]
    return {
        "schemaVersion": 1,
        "claudeVersion": "9.9.9",
        "partial": False,
        "startedAt": "2026-01-01T00:00:00.000Z",
        "costUsd": 6.0,
        "durationSeconds": 725,
        "suite": {
            "root": "/Users/someone/work/plugin",
            "ablation": "with-without",
            "modelOverride": "sonnet",
            "judgeModel": "haiku",
            "threshold": 1,
            "concurrency": 4,
        },
        "cases": [
            {
                "name": name,
                "dir": f"/Users/someone/work/plugin/evals/{name}",
                "promptMarkdown": SECRET_PROMPT,
                "runsPerCase": 3,
                "arms": {
                    "with": [_session(1, good) for _ in range(3)],
                    "without": [_session(0.5, poor) for _ in range(3)],
                },
            }
            for name in CASES
        ],
    }


def _copy_repo(tmp_path) -> Path:
    dest = tmp_path / "repo"
    shutil.copytree(
        REPO_ROOT,
        dest,
        ignore=shutil.ignore_patterns(".git", ".dispatch", "results", "__pycache__", ".pytest_cache"),
    )
    return dest


def _run(repo, *args):
    return subprocess.run(
        [sys.executable, str(repo / SCRIPT), *args], capture_output=True, text=True
    )


def _summarize(repo, tmp_path, raw):
    path = tmp_path / "raw.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    return _run(repo, "summarize", str(path))


def _report(repo) -> Path:
    version = json.loads((repo / ".claude-plugin" / "plugin.json").read_text())["version"]
    return repo / "evals" / "reports" / version / "result.json"


def _assert_refused(result, *needles):
    assert result.returncode == 1
    lines = result.stderr.splitlines()
    assert len(lines) == 1
    assert lines[0].startswith("eval-report: ")
    for needle in needles:
        assert needle in lines[0]
    assert result.stdout == ""


def test_summarize_keeps_the_numbers_and_nothing_a_session_said(tmp_path):
    repo = _copy_repo(tmp_path)

    result = _summarize(repo, tmp_path, _raw())

    assert result.returncode == 0, result.stderr
    text = _report(repo).read_text(encoding="utf-8")
    for leak in ("/Users/", "/private/", "tracePath", SECRET_PROMPT, SECRET_VERDICT, "explanation"):
        assert leak not in text
    report = json.loads(text)
    assert report["sessions"] == 30
    assert report["claudeVersion"] == "9.9.9"
    assert report["concurrency"] == 4
    assert [c["name"] for c in report["cases"]] == CASES
    first = report["cases"][0]
    assert first["with"]["scores"] == [1, 1, 1]
    assert first["without"]["mean_score"] == 0.5
    assert first["delta"] == 0.5
    assert first["with"]["graders"]["skill-fired"] == {"passed": 3, "total": 3, "scored": False}
    assert first["without"]["graders"]["does-the-thing"] == {"passed": 0, "total": 3, "scored": True}


def test_the_total_cost_counts_the_judge_and_ignores_the_runs_own_total(tmp_path):
    repo = _copy_repo(tmp_path)

    assert _summarize(repo, tmp_path, _raw()).returncode == 0

    report = json.loads(_report(repo).read_text(encoding="utf-8"))
    assert report["totalCostUsd"] == pytest.approx(30 * (0.2 + 0.001))
    assert report["totalCostUsd"] != 6.0


def _partial(raw):
    raw["partial"] = True


def _errored(raw):
    raw["cases"][2]["arms"]["without"][1]["error"] = "rate limited"


def _skipped(raw):
    raw["cases"][1]["arms"]["with"][0]["skippedPaidGraders"] = True


def _one_arm(raw):
    raw["cases"][0]["arms"]["without"] = []


def _no_sessions(raw):
    for case in raw["cases"]:
        case["arms"] = {"with": [], "without": []}


def _no_cases(raw):
    raw["cases"] = []


@pytest.mark.parametrize(
    "spoil, needle",
    [
        (_partial, "partial"),
        (_errored, "error"),
        (_skipped, "skipped"),
        (_one_arm, "same number"),
        (_no_sessions, "no sessions"),
        (_no_cases, "no cases"),
    ],
    ids=["partial", "error", "skipped-paid-graders", "empty-arm", "no-sessions", "no-cases"],
)
def test_summarize_refuses_a_run_that_is_not_complete_and_writes_nothing(tmp_path, spoil, needle):
    repo = _copy_repo(tmp_path)
    before = _report(repo).read_bytes() if _report(repo).exists() else None
    raw = _raw()
    spoil(raw)

    result = _summarize(repo, tmp_path, raw)

    _assert_refused(result, needle)
    after = _report(repo).read_bytes() if _report(repo).exists() else None
    assert after == before
    assert not list(_report(repo).parent.glob(".eval-report-*"))


def test_summarize_refuses_a_file_that_is_not_json(tmp_path):
    repo = _copy_repo(tmp_path)
    path = tmp_path / "raw.json"
    path.write_text("{not json", encoding="utf-8")

    _assert_refused(_run(repo, "summarize", str(path)), "cannot read")


def test_readme_is_written_from_the_report_and_a_second_run_changes_nothing(tmp_path):
    repo = _copy_repo(tmp_path)
    assert _summarize(repo, tmp_path, _raw()).returncode == 0

    first = _run(repo, "readme")

    assert first.returncode == 0, first.stderr
    readme = (repo / "README.md").read_text(encoding="utf-8")
    assert "Release run, Claude Code 9.9.9, `--runs 3 --ablation with-without`:" in readme
    assert "| dirty-tree-blocks | 1.00 | 0.50 | +0.50 |" in readme
    prose = " ".join(readme.split())  # the summary is wrapped, so sentences span lines
    assert "Mean delta +0.50, from one complete run of 30 sessions: 12m05s wall clock at" in prose
    assert "concurrency 4, $6.03 at list price." in prose
    assert "All five cases scored 1.00 with the plugin loaded in all three repeats." in prose
    assert max(len(line) for line in readme[readme.index("Mean delta") :].split("\n\n")[0].splitlines()) <= 90
    assert _run(repo, "readme").returncode == 0
    assert (repo / "README.md").read_text(encoding="utf-8") == readme
    assert _run(repo, "check").returncode == 0


def test_the_table_follows_the_order_of_the_cases_in_the_readme(tmp_path):
    repo = _copy_repo(tmp_path)
    assert _summarize(repo, tmp_path, _raw()).returncode == 0
    assert _run(repo, "readme").returncode == 0

    readme = (repo / "README.md").read_text(encoding="utf-8")
    listed = [
        line.split("`")[1]
        for line in readme[readme.index("<!-- eval-cases:start -->") :].splitlines()
        if line.startswith("- `")
    ][: len(CASES)]
    rows = [
        line.split("|")[1].strip()
        for line in readme.splitlines()
        if line.startswith("| ") and line.split("|")[1].strip() in CASES
    ]
    assert sorted(listed) == CASES
    assert rows == listed


def test_a_case_that_fell_short_is_reported_as_measured(tmp_path):
    repo = _copy_repo(tmp_path)
    raw = _raw()
    raw["cases"][1]["arms"]["with"][2] = _session(
        0.5, [("does-the-thing", False), ("never-pushes", True), ("skill-fired", True)]
    )
    assert _summarize(repo, tmp_path, raw).returncode == 0

    assert _run(repo, "readme").returncode == 0

    readme = " ".join((repo / "README.md").read_text(encoding="utf-8").split())
    assert "| dirty-tree-blocks | 0.83 | 0.50 | +0.33 |" in readme
    assert "4 of 5 cases scored 1.00 with the plugin loaded in all three repeats" in readme
    assert "`dirty-tree-blocks` fell short in 1 of 3 repeats (failing: `does-the-thing`)" in readme
    assert "All five cases" not in readme


def _drop_results_markers(text):
    return text.replace("<!-- eval-results:start -->", "").replace("<!-- eval-results:end -->", "")


def _double_results_markers(text):
    return text + "\n<!-- eval-results:start -->\n<!-- eval-results:end -->\n"


def _rename_a_case(text):
    return text.replace("- `dirty-tree-blocks` -- ", "- `dirty-tree-stops` -- ")


def _drop_a_case(text):
    start = text.index("- `dirty-tree-blocks` -- ")
    end = text.index("- `reviewer-reads-code` -- ")
    return text[:start] + text[end:]


@pytest.mark.parametrize(
    "spoil, needle",
    [
        (_drop_results_markers, "eval-results"),
        (_double_results_markers, "eval-results"),
        (_rename_a_case, "disagree"),
        (_drop_a_case, "disagree"),
    ],
    ids=["no-markers", "two-pairs-of-markers", "renamed-case", "missing-case"],
)
def test_readme_is_refused_and_left_alone_when_it_cannot_be_rewritten_safely(tmp_path, spoil, needle):
    repo = _copy_repo(tmp_path)
    assert _summarize(repo, tmp_path, _raw()).returncode == 0
    readme = repo / "README.md"
    readme.write_text(spoil(readme.read_text(encoding="utf-8")), encoding="utf-8")
    before = readme.read_bytes()

    result = _run(repo, "readme")

    _assert_refused(result, needle)
    assert readme.read_bytes() == before


def test_check_fails_when_the_readme_no_longer_says_what_the_report_says(tmp_path):
    repo = _copy_repo(tmp_path)
    assert _summarize(repo, tmp_path, _raw()).returncode == 0
    assert _run(repo, "readme").returncode == 0
    readme = repo / "README.md"
    text = readme.read_text(encoding="utf-8")
    readme.write_text(text.replace("| 1.00 | 0.50 | +0.50 |", "| 1.00 | 0.40 | +0.60 |", 1), encoding="utf-8")
    before = readme.read_bytes()

    result = _run(repo, "check")

    _assert_refused(result, "does not say what the report says")
    assert readme.read_bytes() == before


def test_a_readme_checked_out_with_windows_line_endings_still_checks(tmp_path):
    repo = _copy_repo(tmp_path)
    assert _summarize(repo, tmp_path, _raw()).returncode == 0
    assert _run(repo, "readme").returncode == 0
    readme = repo / "README.md"
    readme.write_bytes(readme.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))

    assert _run(repo, "check").returncode == 0


def test_an_unknown_command_is_refused_with_the_usage(tmp_path):
    repo = _copy_repo(tmp_path)

    _assert_refused(_run(repo, "publish"), "usage")


def test_this_repositorys_readme_says_what_its_committed_report_says():
    # The drift gate: whoever changes the numbers in one place has to change the other.
    result = _run(REPO_ROOT, "check")

    assert result.returncode == 0, result.stderr


def test_the_committed_report_carries_no_local_path_and_no_session_text():
    text = _report(REPO_ROOT).read_text(encoding="utf-8")

    for leak in ("/Users/", "/home/", "/private/", "/tmp/", "tracePath", "promptMarkdown", "explanation"):
        assert leak not in text
    report = json.loads(text)
    assert sorted(c["name"] for c in report["cases"]) == CASES
    assert report["sessions"] == sum(c["with"]["runs"] + c["without"]["runs"] for c in report["cases"])


def test_raw_results_are_never_tracked():
    ignored = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()

    assert "evals/results/" in ignored


def test_the_synthetic_run_is_not_changed_by_being_summarized(tmp_path):
    repo = _copy_repo(tmp_path)
    raw = _raw()
    untouched = copy.deepcopy(raw)

    assert _summarize(repo, tmp_path, raw).returncode == 0

    assert raw == untouched


def test_summarize_refuses_a_report_that_would_carry_a_local_path(tmp_path):
    repo = _copy_repo(tmp_path)
    before = _report(repo).read_bytes() if _report(repo).exists() else None
    raw = _raw()
    raw["claudeVersion"] = "9.9.9 (/Users/someone/ci-runner)"

    _assert_refused(_summarize(repo, tmp_path, raw), "local path")

    after = _report(repo).read_bytes() if _report(repo).exists() else None
    assert after == before


@pytest.mark.parametrize("manifest", ["{not json", '{"name": "dispatch"}', ""], ids=["broken", "no-version", "empty"])
def test_a_manifest_it_cannot_read_is_one_line_not_a_traceback(tmp_path, manifest):
    repo = _copy_repo(tmp_path)
    (repo / ".claude-plugin" / "plugin.json").write_text(manifest, encoding="utf-8")

    for args in (("readme",), ("check",)):
        _assert_refused(_run(repo, *args), "plugin.json")
    path = tmp_path / "raw.json"
    path.write_text(json.dumps(_raw()), encoding="utf-8")
    _assert_refused(_run(repo, "summarize", str(path)), "plugin.json")


def _uneven_arms(raw):
    raw["cases"][0]["arms"]["with"].pop()


def _uneven_cases(raw):
    for arm in raw["cases"][3]["arms"].values():
        arm.pop()


@pytest.mark.parametrize("spoil", [_uneven_arms, _uneven_cases], ids=["one-arm-short", "one-case-short"])
def test_summarize_refuses_a_run_whose_arms_are_not_all_the_same_size(tmp_path, spoil):
    repo = _copy_repo(tmp_path)
    before = _report(repo).read_bytes() if _report(repo).exists() else None
    raw = _raw()
    spoil(raw)

    _assert_refused(_summarize(repo, tmp_path, raw), "same number")

    after = _report(repo).read_bytes() if _report(repo).exists() else None
    assert after == before


def test_a_score_a_hair_under_one_is_not_a_clean_run(tmp_path):
    repo = _copy_repo(tmp_path)
    raw = _raw()
    raw["cases"][4]["arms"]["with"][0] = _session(
        0.9999, [("does-the-thing", False), ("never-pushes", True), ("skill-fired", True)]
    )
    assert _summarize(repo, tmp_path, raw).returncode == 0

    assert _run(repo, "readme").returncode == 0

    readme = " ".join((repo / "README.md").read_text(encoding="utf-8").split())
    assert "All five cases" not in readme
    assert "`spec-before-quality` fell short in 1 of 3 repeats" in readme


def test_every_row_adds_up_at_the_precision_it_is_shown_at(tmp_path):
    # Means of 0.996 and 0.664 differ by 0.332. Shown to two places that is 1.00, 0.66 and
    # +0.33, which a reader with a pencil takes for a mistake. The row is worked out from
    # the figures it shows.
    repo = _copy_repo(tmp_path)
    raw = _raw()
    case = raw["cases"][0]
    good = [("does-the-thing", True), ("never-pushes", True), ("skill-fired", True)]
    poor = [("does-the-thing", False), ("never-pushes", True)]
    case["arms"]["with"] = [_session(s, good) for s in (1, 1, 0.988)]
    case["arms"]["without"] = [_session(s, poor) for s in (0.664, 0.664, 0.664)]
    assert _summarize(repo, tmp_path, raw).returncode == 0

    assert _run(repo, "readme").returncode == 0

    readme = (repo / "README.md").read_text(encoding="utf-8")
    assert "| design-doc-before-implementer | 1.00 | 0.66 | +0.34 |" in readme
    rows = [
        [cell.strip() for cell in line.split("|")[1:5]]
        for line in readme.splitlines()
        if line.startswith("| ") and line.split("|")[1].strip() in CASES
    ]
    assert len(rows) == 5
    for name, with_plugin, without, delta in rows:
        assert round(float(with_plugin) - float(without), 2) == float(delta), name
    shown = sum(float(row[3]) for row in rows) / len(rows)
    prose = " ".join(readme.split())
    assert f"Mean delta {shown:+.2f}, from one complete run" in prose


def test_a_half_is_rounded_up_the_way_a_reader_would(tmp_path):
    repo = _copy_repo(tmp_path)
    raw = _raw()
    poor = [("does-the-thing", False), ("never-pushes", True)]
    # 0.665 is the figure on which rounding a half up and rounding it to the even digit part.
    raw["cases"][0]["arms"]["without"] = [_session(s, poor) for s in (0.665, 0.665, 0.665)]
    assert _summarize(repo, tmp_path, raw).returncode == 0

    assert _run(repo, "readme").returncode == 0

    assert "| design-doc-before-implementer | 1.00 | 0.67 | +0.33 |" in (repo / "README.md").read_text(
        encoding="utf-8"
    )
