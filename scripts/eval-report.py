#!/usr/bin/env python3
"""Turn one eval run into the numbers this repository publishes.

    scripts/eval-report.py summarize <raw result.json>
        Write evals/reports/<version>/result.json from the file `claude plugin eval --json`
        produced. Refuses a run that is partial, has an error in any session, or skipped a
        paid grader: release numbers come from one complete run or from none.

    scripts/eval-report.py readme
        Rewrite the block between the eval-results markers in README.md from that report.

    scripts/eval-report.py check
        Exit 1 if README.md does not say what the report says. Changes nothing.

exit: 0 on success, 1 with one line on stderr, "eval-report: <what is wrong>".

The raw output of an eval run embeds the local paths of the machine it ran on and the full
text of every session, so it is never committed. The report keeps counts, scores, costs and
durations, and nothing a session said.

Stdlib only, like everything else a maintainer runs here.
"""
import json
import os
import re
import sys
import tempfile
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"
MANIFEST = ROOT / ".claude-plugin" / "plugin.json"

CASES_START, CASES_END = "<!-- eval-cases:start -->", "<!-- eval-cases:end -->"
RESULTS_START, RESULTS_END = "<!-- eval-results:start -->", "<!-- eval-results:end -->"

# Anything shaped like a location on somebody's machine. The report is checked against this
# after it is built, so a field added to the raw format later cannot carry one through.
LOCAL_PATH = re.compile(r"(?:/Users/|/home/|/private/|/tmp/|/var/folders/|[A-Za-z]:\\\\)")


class Refused(Exception):
    pass


def version():
    try:
        found = json.loads(MANIFEST.read_text(encoding="utf-8"))["version"]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise Refused(f"cannot read a version from .claude-plugin/plugin.json ({type(exc).__name__})")
    if not isinstance(found, str) or not found:
        raise Refused("cannot read a version from .claude-plugin/plugin.json (it is not a string)")
    return found


def report_path():
    return ROOT / "evals" / "reports" / version() / "result.json"


def write_atomically(path, text):
    """Beside the target, then moved over it, so a run that dies part-way changes nothing."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".eval-report-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        if path.exists():
            os.chmod(tmp, path.stat().st_mode & 0o777)
        else:
            os.chmod(tmp, 0o644)
        os.replace(tmp, str(path))
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def session_cost(run):
    return (run.get("costUsd") or 0) + (run.get("judgeCostUsd") or 0)


def grader_counts(runs):
    counts = {}
    for run in runs:
        for g in run.get("graders") or []:
            entry = counts.setdefault(g["name"], {"passed": 0, "total": 0, "scored": True})
            entry["total"] += 1
            entry["passed"] += 1 if g.get("passed") else 0
            if g.get("scored") is False:
                entry["scored"] = False
    return {name: counts[name] for name in sorted(counts)}


def score_of(run, where):
    """A session's score, which is a number from 0 to 1 or is not a score.

    A score that is missing must not be read as 0: that is what a session that failed every
    check looks like.
    """
    score = run.get("score")
    if isinstance(score, bool) or not isinstance(score, (int, float)) or not 0 <= score <= 1:
        raise Refused(f"{where} has a session whose score is not a number from 0 to 1")
    return score


def arm_summary(runs, where):
    scores = [score_of(run, where) for run in runs]
    return {
        "runs": len(runs),
        # Counted before anything is rounded: a score a hair under one is not full marks.
        "full_marks": sum(1 for s in scores if s >= 1),
        "scores": [round(s, 3) for s in scores],
        "mean_score": round(sum(scores) / len(scores), 3),
        "cost_usd": round(sum(session_cost(run) for run in runs), 4),
        "duration_seconds": round(sum(run.get("durationSeconds") or 0 for run in runs), 1),
        "mean_turns": round(sum(run.get("turns") or 0 for run in runs) / len(runs), 1),
        "graders": grader_counts(runs),
    }


def summarize(raw):
    if raw.get("partial"):
        raise Refused("the run is partial, and a partial run is never quoted")
    cases = raw.get("cases") or []
    if not cases:
        raise Refused("the run has no cases")
    sizes = {len((case.get("arms") or {}).get(arm) or []) for case in cases for arm in ("with", "without")}
    if len(sizes) != 1:
        raise Refused("the arms do not all have the same number of sessions, so their means do not compare")
    out_cases = []
    for case in cases:
        arms = case.get("arms") or {}
        name = case.get("name")
        if not isinstance(name, str) or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name):
            raise Refused(f"a case has a name that is not lower-case words joined by hyphens: {name!r}"[:120])
        for arm in ("with", "without"):
            runs = arms.get(arm) or []
            if not runs:
                raise Refused(f"{name} has no sessions in the {arm} arm")
            for run in runs:
                if run.get("error"):
                    raise Refused(f"{name} has a session that ended in an error ({arm} arm)")
                if run.get("skippedPaidGraders"):
                    raise Refused(f"{name} has a session whose paid graders were skipped ({arm} arm)")
        with_arm = arm_summary(arms["with"], f"{name} (with arm)")
        without_arm = arm_summary(arms["without"], f"{name} (without arm)")
        out_cases.append(
            {
                "name": name,
                "delta": round(with_arm["mean_score"] - without_arm["mean_score"], 3),
                "with": with_arm,
                "without": without_arm,
            }
        )
    suite = raw.get("suite") or {}
    sessions = [run for case in cases for runs in case["arms"].values() for run in runs]
    report = {
        "schemaVersion": 3,
        "pluginVersion": version(),
        "claudeVersion": raw.get("claudeVersion"),
        "startedAt": raw.get("startedAt"),
        "model": suite.get("modelOverride"),
        "judgeModel": suite.get("judgeModel"),
        "ablation": suite.get("ablation"),
        "concurrency": suite.get("concurrency"),
        "sessions": len(sessions),
        "durationSeconds": raw.get("durationSeconds"),
        # Every session plus every judge call. The run's own top-level figure leaves the
        # judge out, so it is not the one quoted.
        "totalCostUsd": round(sum(session_cost(run) for run in sessions), 4),
        "meanDelta": round(sum(c["delta"] for c in out_cases) / len(out_cases), 3),
        "cases": sorted(out_cases, key=lambda c: c["name"]),
    }
    text = json.dumps(report, indent=1, sort_keys=False) + "\n"
    found = LOCAL_PATH.search(text)
    if found:
        raise Refused(f"the report would carry a local path ({found.group(0)}...)")
    return text


def between(text, start, end, what):
    if text.count(start) != 1 or text.count(end) != 1:
        raise Refused(f"README.md needs exactly one pair of {what} markers")
    a, b = text.index(start), text.index(end)
    if b < a:
        raise Refused(f"README.md has its {what} markers in the wrong order")
    return a + len(start), b


def case_order(readme):
    a, b = between(readme, CASES_START, CASES_END, "eval-cases")
    names = re.findall(r"^- `([a-z0-9-]+)` -- ", readme[a:b], re.M)
    if not names:
        raise Refused("README.md lists no cases between its eval-cases markers")
    if len(set(names)) != len(names):
        raise Refused("README.md lists a case twice")
    return names


def plural(n, word):
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


NUMBER_WORDS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"]


def in_words(n):
    return NUMBER_WORDS[n] if 0 <= n < len(NUMBER_WORDS) else str(n)


def two_places(number):
    """Rounded the way a reader would do it by hand: a half goes up."""
    return Decimal(str(number)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def wrap(text, width=90):
    lines, line = [], ""
    for word in text.split():
        if line and len(line) + 1 + len(word) > width:
            lines.append(line)
            line = word
        else:
            line = f"{line} {word}" if line else word
    if line:
        lines.append(line)
    return "\n".join(lines)


def render(report, order):
    by_name = {c["name"]: c for c in report["cases"]}
    if set(order) != set(by_name):
        missing = sorted(set(by_name) - set(order))
        extra = sorted(set(order) - set(by_name))
        raise Refused(
            "README.md and the report disagree about the cases"
            + (f"; not in README.md: {', '.join(missing)}" if missing else "")
            + (f"; not in the report: {', '.join(extra)}" if extra else "")
        )
    repeats = {c["with"]["runs"] for c in report["cases"]} | {c["without"]["runs"] for c in report["cases"]}
    if len(repeats) != 1:
        raise Refused("the report's arms do not all have the same number of sessions")
    n = repeats.pop()

    # Every figure in the block is worked out from the figures shown beside it, so a row adds
    # up at the precision it is printed at and the mean is the mean of the column above it.
    rows, deltas = [], []
    for name in order:
        c = by_name[name]
        with_plugin, without = two_places(c["with"]["mean_score"]), two_places(c["without"]["mean_score"])
        deltas.append(with_plugin - without)
        rows.append(f"| {name} | {with_plugin} | {without} | {deltas[-1]:+} |")
    mean_delta = two_places(sum(deltas) / len(deltas))

    clean = [name for name in order if by_name[name]["with"]["full_marks"] == by_name[name]["with"]["runs"]]
    if len(clean) == len(order):
        held = (
            f"All {in_words(len(order))} cases scored 1.00 with the plugin loaded in all "
            f"{in_words(n)} repeats."
        )
    else:
        parts = []
        for name in order:
            if name in clean:
                continue
            c = by_name[name]["with"]
            short = c["runs"] - c["full_marks"]
            failing = sorted(
                g for g, v in c["graders"].items() if v["scored"] and v["passed"] < v["total"]
            )
            parts.append(
                f"`{name}` fell short in {short} of {n} repeats (failing: "
                + ", ".join(f"`{g}`" for g in failing)
                + ")"
            )
        held = (
            f"{len(clean)} of {len(order)} cases scored 1.00 with the plugin loaded in all "
            f"{in_words(n)} repeats; " + "; ".join(parts) + ". Those are reported as measured."
        )

    seconds = int(report["durationSeconds"])
    summary = wrap(
        f"Mean delta {mean_delta:+}, from one complete run of "
        f"{plural(report['sessions'], 'session')}: {seconds // 60}m{seconds % 60:02d}s wall clock at "
        f"concurrency {report['concurrency']}, ${report['totalCostUsd']:.2f} at list price. {held} "
        f"Per-grader pass counts for both arms are in "
        f"`evals/reports/{report['pluginVersion']}/result.json`."
    )
    return (
        f"Release run, Claude Code {report['claudeVersion']}, "
        f"`--runs {n} --ablation {report['ablation']}`:\n\n"
        "| Case | With plugin | Without | Delta |\n"
        "|---|---|---|---|\n" + "\n".join(rows) + "\n\n" + summary
    )


def read_text(path):
    return path.read_text(encoding="utf-8").replace("\r\n", "\n")


def load_report():
    path = report_path()
    if not path.exists():
        raise Refused(f"there is no report at evals/reports/{version()}/result.json; run summarize first")
    try:
        report = json.loads(read_text(path))
    except (OSError, ValueError) as exc:
        raise Refused(f"cannot read the report ({type(exc).__name__}); run summarize again")
    if not isinstance(report, dict) or not isinstance(report.get("cases"), list):
        raise Refused("the report is not the one this script writes; run summarize again")
    if report.get("schemaVersion") != 3:
        raise Refused("the report was written by an older version of this script; run summarize again")
    return report


def readme_with_block(readme, block):
    a, b = between(readme, RESULTS_START, RESULTS_END, "eval-results")
    return readme[:a] + "\n" + block + "\n" + readme[b:]


def main(argv):
    if len(argv) == 3 and argv[1] == "summarize":
        try:
            raw = json.loads(Path(argv[2]).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise Refused(f"cannot read {argv[2]} ({type(exc).__name__})")
        write_atomically(report_path(), summarize(raw))
        print(f"eval-report: wrote evals/reports/{version()}/result.json")
        return 0
    if len(argv) == 2 and argv[1] in ("readme", "check"):
        readme = read_text(README)
        updated = readme_with_block(readme, render(load_report(), case_order(readme)))
        if argv[1] == "check":
            if updated != readme:
                raise Refused("README.md does not say what the report says; run readme")
            print("eval-report: README.md agrees with the report")
            return 0
        if updated != readme:
            write_atomically(README, updated)
        print("eval-report: README.md is up to date")
        return 0
    raise Refused("usage: eval-report.py summarize <raw result.json> | readme | check")


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except Refused as refusal:
        print(f"eval-report: {refusal}", file=sys.stderr)
        sys.exit(1)
