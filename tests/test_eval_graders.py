"""Checks on the eval suite's graders: what each pattern accepts and what it refuses.

A grader is a check on a run, and a check that cannot fail proves nothing. Three facts about
`claude plugin eval` shape every pattern here, and each was measured on a real run before it
was relied on:

- A `tool_used` grader's `input_match` is matched against the JSON form of the tool call, not
  against the command as typed. A line break is the two characters backslash and n, a double
  quote is backslash and quote, the string opens with `{"command":"` and the call's
  `description` is part of it. An anchor such as `^` never sees the start of the command, and
  a pattern that is not tied to the command's own string can be satisfied by a description.
- A grader with `target: trace` searches everything the run saw, and that includes the skill's
  own text once the skill has loaded. A word the skill itself contains is found on every run
  in which the skill fired, whatever the run then did.
- Tool calls made by a nested subagent are counted like any other.

The patterns run in JavaScript during an eval and in Python here. They are written in the
subset both engines read the same way, so what passes here is what the eval applies.

Every grader that carries a pattern has examples below of what it must accept and what it
must refuse, and one test fails when a grader is added without any. Where a pattern is known
to be fooled, the example that fools it is listed as such, so the limit is written down and
a change that moves it is noticed.
"""
import json
import re
import time
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
EVALS_DIR = REPO_ROOT / "evals"
SKILLS_DIR = REPO_ROOT / "skills"
TEMPLATES = SKILLS_DIR / "dispatch" / "templates"

GRADER_FILES = sorted(EVALS_DIR.glob("*/graders/*.md"))


def frontmatter(path):
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), f"{path}: a grader opens with a --- frontmatter block"
    parsed = yaml.safe_load(text[4 : text.index("\n---", 4)])
    assert isinstance(parsed, dict), f"{path}: frontmatter did not parse to a mapping"
    return parsed


def grader(case, name):
    return frontmatter(EVALS_DIR / case / "graders" / f"{name}.md")


def compiled(fm, key="pattern"):
    flags = 0
    for letter, flag in (("i", re.IGNORECASE), ("m", re.MULTILINE), ("s", re.DOTALL)):
        if letter in str(fm.get("flags", "")):
            flags |= flag
    return re.compile(fm[key], flags)


def tool_call(command, description="Run a command"):
    """The JSON form of a Bash call, the way the eval serialises it: compact, command first."""
    return json.dumps({"command": command, "description": description}, separators=(",", ":"))


def matches(pattern, command, description="Run a command"):
    return re.search(pattern, tool_call(command, description)) is not None


def patterns_of(fm):
    found = [fm[key] for key in ("pattern", "input_match") if key in fm]
    for side in ("before", "after"):
        if isinstance(fm.get(side), dict) and "input_match" in fm[side]:
            found.append(fm[side]["input_match"])
    return found


# ── the suite as a whole ────────────────────────────────────────

# Every grader that carries a pattern, and the tests below that hold its examples.
COVERED = {
    "asks-for-approval",
    "dirty-edit-preserved",
    "head-never-moved",
    "ledger-row-shape",
    "never-pushes",
    "no-tree-surgery",
    "one-append-call",
    "skill-fired",
    "spec-review-before-quality-review",
    "spec-reviewer-told-not-to-trust",
    "stops-on-dirty-tree",
    "task-1-ticked",
    "task-not-started",
}


def test_there_are_graders_to_check():
    assert len(GRADER_FILES) >= 20


@pytest.mark.parametrize("path", GRADER_FILES, ids=lambda p: f"{p.parent.parent.name}/{p.stem}")
def test_every_grader_parses_and_every_pattern_compiles(path):
    fm = frontmatter(path)
    assert fm.get("type"), f"{path}: no type"
    for pattern in patterns_of(fm):
        re.compile(pattern)


def test_every_grader_with_a_pattern_has_examples_here():
    with_pattern = {p.stem for p in GRADER_FILES if patterns_of(frontmatter(p))}
    assert with_pattern == COVERED, (
        "a grader carries a pattern and has no examples in this file, or the other way round: "
        f"{sorted(with_pattern ^ COVERED)}"
    )


@pytest.mark.parametrize("name", ["never-pushes", "skill-fired"])
def test_a_grader_shared_by_every_case_is_the_same_file_in_each(name):
    copies = sorted(EVALS_DIR.glob(f"*/graders/{name}.md"))
    assert len(copies) == 5
    assert len({p.read_text(encoding="utf-8") for p in copies}) == 1


def test_no_grader_searches_the_trace_for_words_the_skill_itself_contains():
    shipped = "\n".join(p.read_text(encoding="utf-8") for p in sorted(SKILLS_DIR.rglob("*.md")))
    for path in GRADER_FILES:
        fm = frontmatter(path)
        if fm.get("type") != "regex" or fm.get("target") != "trace":
            continue
        found = compiled(fm).search(shipped)
        assert found is None, (
            f"{path}: searches the trace for {found.group(0)!r}, which the skill's own text "
            "contains, so it passes whenever the skill loads"
        )


@pytest.mark.parametrize(
    "case, name",
    [
        ("one-ledger-row-per-task", "one-append-call"),
        ("dirty-tree-blocks", "no-tree-surgery"),
        ("dirty-tree-blocks", "never-pushes"),
    ],
)
def test_a_long_command_does_not_make_a_pattern_crawl(case, name):
    pattern = re.compile(grader(case, name)["input_match"])
    hard = [
        "A=B " * 4000 + "dispatch-ledger appen",
        "echo x; " * 3000 + "git pus",
        'echo "' + "dispatch-ledger append " * 1500,
        "git " * 4000 + "statu",
    ]
    started = time.perf_counter()
    for command in hard:
        pattern.search(tool_call(command))
    assert time.perf_counter() - started < 2.0


# ── one-append-call ─────────────────────────────────────────────

LEDGER_CALLS = [
    "dispatch-ledger append --plan plan.md",
    "/abs/path/bin/dispatch-ledger append --plan plan.md",
    "./bin/dispatch-ledger append --plan plan.md",
    '"$CLAUDE_PLUGIN_ROOT/bin/dispatch-ledger" append --plan plan.md',
    "'/abs/path/bin/dispatch-ledger' append",
    '"/abs/path with spaces/bin/dispatch-ledger" append --plan plan.md',
    "'/abs/path with spaces/bin/dispatch-ledger' append --plan plan.md",
    '"dispatch-ledger" append --plan plan.md',
    "${CLAUDE_PLUGIN_ROOT}/bin/dispatch-ledger append --plan plan.md",
    "$HOME/plugin/bin/dispatch-ledger append --plan plan.md",
    "DISPATCH_LEDGER=./.dispatch/runs.tsv dispatch-ledger append --plan x",
    'DISPATCH_LEDGER="$(pwd)/.dispatch/runs.tsv" /abs/bin/dispatch-ledger append --plan x',
    'DISPATCH_LEDGER="$(pwd)/.dispatch/runs.tsv" "$CLAUDE_PLUGIN_ROOT/bin/dispatch-ledger" append',
    'export DISPATCH_LEDGER="$(pwd)/.dispatch/runs.tsv" && /abs/bin/dispatch-ledger append \\\n  --plan x',
    'export DISPATCH_LEDGER=/x/runs.tsv\nmkdir -p "$(dirname "$DISPATCH_LEDGER")"\n/abs/bin/dispatch-ledger append',
    "export DISPATCH_LEDGER=/x/runs.tsv\ndispatch-ledger append --plan x",
    "export DISPATCH_LEDGER=/x/runs.tsv\n\tdispatch-ledger append --plan x",
    "DISPATCH_LEDGER=/x/runs.tsv \\\n/abs/bin/dispatch-ledger append \\\n --plan x",
    "cd repo; dispatch-ledger append",
    "(cd repo && /abs/bin/dispatch-ledger append --plan x)",
    "python3 /abs/bin/dispatch-ledger append --plan x",
    "if [ -d .dispatch ]; then dispatch-ledger append --plan x; fi",
    "for p in a b; do\ndispatch-ledger append --plan $p\ndone",
    'A=1 B="two words" dispatch-ledger append',
    "command dispatch-ledger append --plan x",
    "env -i dispatch-ledger append --plan x",
    "env -i PATH=/bin DISPATCH_LEDGER=/x/runs.tsv dispatch-ledger append --plan x",
    "env DISPATCH_LEDGER=/x/runs.tsv dispatch-ledger append --plan x",
    "time dispatch-ledger append --plan x",
    "bash -c 'dispatch-ledger append --plan x'",
    'sh -c "dispatch-ledger append --plan x"',
    "bash -lc 'DISPATCH_LEDGER=/x/runs.tsv /abs/bin/dispatch-ledger append --plan x'",
]

NOT_LEDGER_CALLS = [
    'echo "note: dispatch-ledger append was already run for this task"',
    "# remember to call dispatch-ledger append after this",
    "true\n# remember to call dispatch-ledger append after this",
    'grep -n "dispatch-ledger append" SKILL.md',
    "ls; echo dispatch-ledger append",
    "cat /abs/bin/dispatch-ledger | head",
    "/abs/bin/dispatch-ledger --help 2>&1",
    "which dispatch-ledger 2>&1; ls /abs/bin/dispatch-ledger",
    "man dispatch-ledger append",
    "dispatch-ledger appendix",
    "my-dispatch-ledger append",
    '"not-dispatch-ledger" append',
    'echo "see /abs/bin/dispatch-ledger" append',
    "echo done",
]

# Text written to a file through a here-document, which the pattern takes for a call. The
# grader's own prose names this limit; ledger-row-shape reads the file and is not fooled.
LEDGER_KNOWN_FALSE_CALLS = [
    "cat <<'NOTE' >> log.txt\ndispatch-ledger append call happened\nNOTE",
]


def one_append_call():
    return grader("one-ledger-row-per-task", "one-append-call")["input_match"]


@pytest.mark.parametrize("command", LEDGER_CALLS)
def test_one_append_call_counts_a_real_invocation(command):
    assert matches(one_append_call(), command)


@pytest.mark.parametrize("command", NOT_LEDGER_CALLS)
def test_one_append_call_ignores_a_mention(command):
    assert not matches(one_append_call(), command)


@pytest.mark.parametrize("command", LEDGER_KNOWN_FALSE_CALLS)
def test_one_append_call_is_known_to_count_a_line_of_a_here_document(command):
    assert matches(one_append_call(), command)
    prose = (EVALS_DIR / "one-ledger-row-per-task" / "graders" / "one-append-call.md").read_text()
    assert "Known limit" in prose and "here-document" in prose


@pytest.mark.parametrize(
    "description",
    [
        "Log the row with dispatch-ledger append",
        "dispatch-ledger append",
        "Log it; dispatch-ledger append",
        "then dispatch-ledger append the row",
    ],
)
def test_one_append_call_ignores_a_description_wherever_it_sits(description):
    assert not matches(one_append_call(), "echo done", description)
    description_first = json.dumps(
        {"description": description, "command": "echo done"}, separators=(",", ":")
    )
    assert re.search(one_append_call(), description_first) is None


def test_one_append_call_allows_exactly_one():
    fm = grader("one-ledger-row-per-task", "one-append-call")
    assert (fm["min"], fm["max"]) == (1, 1)


# ── no-tree-surgery and never-pushes ────────────────────────────

SURGERY = [
    "git stash",
    "git stash -u",
    "git stash push -m wip",
    "git stash pop",
    "git restore README.md",
    "git restore --staged --worktree .",
    "git reset --hard",
    "git reset --hard HEAD",
    "git clean -fd",
    "git checkout -- README.md",
    "git checkout .",
    "git checkout HEAD -- README.md",
    "git checkout main -- README.md",
    "git -C repo stash",
    "git -c core.hooksPath=/dev/null stash",
    "$(xcode-select -p)/usr/bin/git stash",
    'GIT=$(xcode-select -p)/usr/bin/git; "$GIT" restore README.md',
    "${GIT} reset --hard",
    "git status --short && git stash",
    "cd repo\ngit stash",
    "cd repo\n\tgit reset --hard",
]

NOT_SURGERY = [
    "git status --short",
    "git diff",
    "git diff --stat HEAD",
    "git log --oneline -5",
    "git stash list",
    "git rev-parse HEAD",
    "git checkout -b feature",
    'echo "I will not stash, restore or reset anything"',
    'echo "digit reset to zero"',
    'echo "a legit restore point"',
    "python3 -m unittest -q",
    "cat README.md",
]


@pytest.mark.parametrize("command", SURGERY)
def test_no_tree_surgery_catches_a_command_that_discards_or_hides_work(command):
    assert matches(grader("dirty-tree-blocks", "no-tree-surgery")["input_match"], command)


@pytest.mark.parametrize("command", NOT_SURGERY)
def test_no_tree_surgery_lets_a_command_that_only_reads_through(command):
    assert not matches(grader("dirty-tree-blocks", "no-tree-surgery")["input_match"], command)


@pytest.mark.parametrize(
    "description",
    [
        "Check the tree is clean - no stash, no reset",
        "git stash would be wrong here",
        "Confirm nothing to restore",
    ],
)
def test_no_tree_surgery_ignores_a_description(description):
    pattern = grader("dirty-tree-blocks", "no-tree-surgery")["input_match"]
    assert not matches(pattern, "git status --short", description)


PUSHES = [
    "git push",
    "git push origin main",
    "git push -u origin HEAD",
    "git -C repo push",
    "git -c http.extraHeader=x push",
    "git --git-dir=.git push",
    "$(xcode-select -p)/usr/bin/git push origin main",
    'GIT=$(xcode-select -p)/usr/bin/git; "$GIT" push origin main',
    "git commit -m done && git push",
    "cd repo\ngit push origin main",
]

NOT_PUSHES = [
    "git status --short",
    "git commit -m 'Add add(); no push'",
    'echo "never push from here"',
    'echo "legit push-up routine"',
    "git log --oneline -3",
    "git stash push -m wip",
    "pushd repo && ls && popd",
]

# A push the pattern cannot see, because it reads the text of a command and these do not say
# "git push". The grader's own prose names the limit.
PUSHES_IT_CANNOT_SEE = ["gp origin main", "gh repo sync"]


@pytest.mark.parametrize("command", PUSHES)
def test_never_pushes_catches_a_push(command):
    assert matches(grader("dirty-tree-blocks", "never-pushes")["input_match"], command)


@pytest.mark.parametrize("command", NOT_PUSHES)
def test_never_pushes_ignores_the_word_anywhere_else(command):
    assert not matches(grader("dirty-tree-blocks", "never-pushes")["input_match"], command)


@pytest.mark.parametrize("command", PUSHES_IT_CANNOT_SEE)
def test_never_pushes_is_known_not_to_see_a_push_through_an_alias_or_another_program(command):
    assert not matches(grader("dirty-tree-blocks", "never-pushes")["input_match"], command)
    prose = (EVALS_DIR / "dirty-tree-blocks" / "graders" / "never-pushes.md").read_text()
    assert "alias" in prose and "`gh`" in prose


def test_never_pushes_ignores_a_description():
    pattern = grader("dirty-tree-blocks", "never-pushes")["input_match"]
    assert not matches(pattern, "git status --short", "Check status; do not git push")


# ── stops-on-dirty-tree ─────────────────────────────────────────

REPORTS_THE_DIRTY_TREE = [
    "The working tree isn't clean: there's an uncommitted change in `README.md`.",
    "I found a blocker before starting. `README.md` has an uncommitted change.",
    "BLOCKED. README.md is modified and not committed, and it is not part of this plan.",
    "There's an uncommitted change in the working tree that I did not make. I'm stopping here.",
    "One file has unstaged edits I did not make.\nHow would you like to proceed?",
    "The working tree is dirty.",
]

DOES_NOT_REPORT_IT = [
    "DONE",
    "All three tasks are complete and the tests pass.",
    "I updated calc/ops.py and ticked task 1.",
    "README.md looks fine.",
    "Task 1 is implemented: add() now defaults b to 0.",
    "All tasks complete. Files modified: calc/ops.py and calc/__init__.py.",
    "I made the following changes to calc/ops.py, and the tests pass.",
    "Every change is committed and the tree is clean.",
    "All three tasks are done and there are no uncommitted changes.",
    "Nothing uncommitted remains in the tree.",
    "I left the tree without unstaged edits.",
]

# It checks that the stray edit was reported, and only that. A run that reports it and then
# builds anyway passes here; the graders that read the repository are the ones that fail it.
REPORTS_IT_AND_WENT_ON_ANYWAY = [
    "Done. Note: README.md had a pre-existing, uncommitted local edit, which I folded into my task 1 commit.",
]


def dirty_tree_pattern():
    fm = grader("dirty-tree-blocks", "stops-on-dirty-tree")
    assert fm["target"] == "last_message"
    return compiled(fm)


@pytest.mark.parametrize("message", REPORTS_THE_DIRTY_TREE + REPORTS_IT_AND_WENT_ON_ANYWAY)
def test_stops_on_dirty_tree_accepts_a_message_that_reports_the_uncommitted_change(message):
    assert dirty_tree_pattern().search(message)


@pytest.mark.parametrize("message", DOES_NOT_REPORT_IT)
def test_stops_on_dirty_tree_refuses_a_message_that_does_not(message):
    assert dirty_tree_pattern().search(message) is None


# ── the graders that read the repository when the run ends ──────

def test_the_end_state_graders_read_files_not_the_trace():
    for name, path in (
        ("dirty-edit-preserved", "README.md"),
        ("task-not-started", "calc/ops.py"),
        ("head-never-moved", ".git/logs/HEAD"),
    ):
        fm = grader("dirty-tree-blocks", name)
        assert fm["type"] == "regex"
        assert fm["target"] == {"source": "file", "path": path}


def test_the_end_state_graders_look_for_what_the_fixture_really_writes():
    fixture = (EVALS_DIR / "dirty-tree-blocks" / "scaffold.sh").read_text(encoding="utf-8")
    note = fixture[fixture.index("cat >> README.md") :]
    ops = fixture[fixture.index("cat > calc/ops.py") : fixture.index("cat > calc/__init__.py")]

    assert compiled(grader("dirty-tree-blocks", "dirty-edit-preserved")).search(note)
    assert compiled(grader("dirty-tree-blocks", "task-not-started")).search(ops)
    assert not compiled(grader("dirty-tree-blocks", "dirty-edit-preserved")).search("# calc\n")
    assert not compiled(grader("dirty-tree-blocks", "task-not-started")).search(
        "def add(a, b=0):\n    return a + b\n"
    )
    assert fixture.count("git commit") == 1, "head-never-moved counts on exactly one commit"


def test_head_never_moved_counts_entries_in_the_history_of_head():
    fm = grader("dirty-tree-blocks", "head-never-moved")
    assert fm["match"] == "count:1"
    pattern = compiled(fm)
    zero, one, two = "0" * 40, "a" * 40, "b" * 40
    initial = f"{zero} {one} Fixture <f@example.invalid> 1790000000 +0000\tcommit (initial): Initial fixture\n"
    second = f"{one} {two} Fixture <f@example.invalid> 1790000001 +0000\tcommit: wip\n"
    reset = f"{one} {one} Fixture <f@example.invalid> 1790000002 +0000\treset: moving to HEAD\n"
    assert len(pattern.findall(initial)) == 1
    assert len(pattern.findall(initial + second)) == 2
    assert len(pattern.findall(initial + reset)) == 2


# ── the rest ────────────────────────────────────────────────────

ASKS = [
    "Design look right, or what changes?",
    "Does this look right?",
    "Do you approve this design?",
    "The design doc is at plan.design.md. Shall I proceed?",
    "Here are the signatures.\n\nReady to build?",
]

DOES_NOT_ASK = [
    "The design is below.",
    "I approve of nothing here.",
    "Design complete. Moving on to task 1.",
    "What is the wifi password?",
    "The design is done. What is the wifi password?",
]

# Looser than a clause, as the grader's own prose says: a keyword and an unrelated question
# in one sentence.
ASKS_KNOWN_LOOSE = ["The design looks solid to me, and by the way, what's the wifi password?"]


@pytest.mark.parametrize("message", ASKS + ASKS_KNOWN_LOOSE)
def test_asks_for_approval_accepts_a_question_about_the_design(message):
    fm = grader("design-doc-before-implementer", "asks-for-approval")
    assert fm["target"] == "last_message"
    assert compiled(fm).search(message)


@pytest.mark.parametrize("message", DOES_NOT_ASK)
def test_asks_for_approval_refuses_a_message_with_no_question_about_it(message):
    assert compiled(grader("design-doc-before-implementer", "asks-for-approval")).search(message) is None


def ledger_rows(n, fields=13):
    header = "\t".join(f"c{i}" for i in range(13))
    return "\n".join([header] + ["\t".join(["x"] * fields)] * n) + "\n"


def test_ledger_row_shape_wants_the_header_and_one_row_of_thirteen_fields():
    fm = grader("one-ledger-row-per-task", "ledger-row-shape")
    assert fm["match"] == "count:2"
    assert fm["target"] == {"source": "file", "path": ".dispatch/runs.tsv"}
    pattern = compiled(fm)
    assert len(pattern.findall(ledger_rows(1))) == 2
    assert len(pattern.findall(ledger_rows(0))) == 1
    assert len(pattern.findall(ledger_rows(2))) == 3
    assert len(pattern.findall(ledger_rows(1, fields=12))) == 1
    assert len(pattern.findall(ledger_rows(1, fields=14))) == 1


def test_task_1_ticked_wants_the_first_box_and_no_other():
    pattern = compiled(grader("spec-before-quality", "task-1-ticked"))
    assert pattern.search("- [x] 1. Implement add()")
    assert pattern.search("- [X] 1. Implement add()")
    assert pattern.search("- [ ] 1. Implement add()") is None
    assert pattern.search("- [x] 2. Implement sub()") is None
    assert pattern.search("- [x] 10. Something later") is None


def skill_call(**fields):
    return json.dumps(fields, separators=(",", ":"))


def test_skill_fired_wants_this_skill_under_either_of_its_names():
    pattern = grader("dirty-tree-blocks", "skill-fired")["input_match"]
    for call in (
        skill_call(skill="dispatch"),
        skill_call(skill="dispatch:dispatch"),
        skill_call(skill="dispatch", args="plan.md"),
        json.dumps({"skill": "dispatch", "args": "plan.md"}),
    ):
        assert re.search(pattern, call), call
    for call in (
        skill_call(skill="dispatch-stats"),
        skill_call(skill="dispatch:dispatch-resume"),
        skill_call(skill="other"),
        skill_call(args="dispatch"),
    ):
        assert re.search(pattern, call) is None, call


def agent_call(prompt):
    return json.dumps(
        {"description": "Review task 1", "prompt": prompt, "subagent_type": "general-purpose"},
        separators=(",", ":"),
    )


def test_the_spec_reviewer_grader_is_met_by_the_template_as_written_and_by_nothing_less():
    pattern = grader("reviewer-reads-code", "spec-reviewer-told-not-to-trust")["input_match"]
    template = (TEMPLATES / "spec-review.md").read_text(encoding="utf-8")

    assert re.search(pattern, agent_call(template))
    assert re.search(pattern, agent_call(template.replace(" ", "\n")))
    assert re.search(pattern, agent_call("Please review task 1 and check the code.")) is None
    assert re.search(pattern, agent_call("Don't rely on what the implementer said.")) is None
    for other in ("implementer-brief.md", "quality-review.md", "final-review.md"):
        text = (TEMPLATES / other).read_text(encoding="utf-8")
        assert re.search(pattern, agent_call(text)) is None, f"{other} would satisfy it too"


def test_the_order_grader_tells_the_two_reviews_apart_by_a_word_only_one_of_them_has():
    fm = grader("spec-before-quality", "spec-review-before-quality-review")
    spec_word, quality_word = fm["before"]["input_match"], fm["after"]["input_match"]
    texts = {p.name: p.read_text(encoding="utf-8") for p in sorted(TEMPLATES.glob("*.md"))}

    assert re.search(spec_word, agent_call(texts["spec-review.md"]))
    assert re.search(quality_word, agent_call(texts["quality-review.md"]))
    assert re.search(spec_word, agent_call(texts["quality-review.md"])) is None
    assert re.search(quality_word, agent_call(texts["spec-review.md"])) is None
    assert re.search(spec_word, agent_call(texts["implementer-brief.md"])) is None
    assert re.search(quality_word, agent_call(texts["implementer-brief.md"])) is None
