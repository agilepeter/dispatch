"""Checks on the shipped skill files themselves, not on runtime behavior.

What matters about a file a plugin ships to every installer: every path it points at under
${CLAUDE_PLUGIN_ROOT} has to exist relative to the repo root, every path it points at under
${CLAUDE_SKILL_DIR} has to exist relative to that particular SKILL.md's own directory (the two
resolve differently, so mixing them up is a real way to ship a dangling reference), every
SKILL.md's frontmatter has to parse and carry the fields Claude Code requires, none of the
skills, templates, the README, or the plugin manifests may carry a local path, an internal
project name, a commit trailer, or a pinned model id out into the world, and the coordinator's
own instructions never tell it to push.

This module parses frontmatter with PyYAML instead of a hand-rolled splitter, because only a
real YAML parser reads it the same way Claude Code's own loader does: a value that merely
contains a colon looks identical to genuinely broken YAML to anything less. That is a
dependency this test suite alone takes on -- the plugin's shipped scripts, bin/dispatch-ledger
and bin/dispatch-stats, stay stdlib-only so any machine with a bare python3 can run them, and
nothing under skills/ needs a YAML library at runtime either.
"""
import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO_ROOT / "skills"

# Every skill this plugin ships. Each is also an "entry point" -- something a user invokes
# directly -- so this one glob covers both "SKILL.md" and "the entry points" from the same walk.
SKILL_FILES = sorted(SKILLS_DIR.glob("*/SKILL.md"))

# Skills plus whatever they paste from (currently just skills/dispatch/templates/*.md).
SHIPPED_FILES = sorted(SKILLS_DIR.rglob("*.md"))

# Everything a fresh install actually receives and everything a browser can load straight off
# the repo: the skills above, plus the README and the plugin manifests. The leak check runs
# over this wider set -- a stray local path or the wrong description can land in a manifest or
# the README just as easily as in a skill file.
LEAK_CHECK_FILES = (
    SHIPPED_FILES
    + [REPO_ROOT / "README.md"]
    + sorted((REPO_ROOT / ".claude-plugin").glob("*.json"))
)

# README.md links to the plugin's own product page for the "why a verifier" numbers this repo
# cannot keep current on its own. That is one deliberate, human-facing reference to the maker's
# own domain -- not the kind of accidental workspace leak the "staas" pattern below exists to
# catch -- so it is stripped out of the README's text before that check runs, and only from the
# README: a skill or template's own operational instructions must stay generic and never carry
# this or any other product link, so none of them get this allowance.
README_ALLOWED_REFERENCES = ["https://staas.fund/dispatch/"]

PLUGIN_ROOT_REF = re.compile(r"\$\{CLAUDE_PLUGIN_ROOT\}(/[^\s`\"'()\[\]]+)")
SKILL_DIR_REF = re.compile(r"\$\{CLAUDE_SKILL_DIR\}(/[^\s`\"'()\[\]]+)")

# The dispatch skill's Resume step treats a plan as pre-approved only once its header's
# `Approved:` line begins with a real date, so it can never mistake the plan template's own
# placeholder comment (which also starts with "Approved:") for an approval.
DATED_APPROVED_LINE = re.compile(r"^Approved: 20\d{2}-\d{2}-\d{2}")

LEAK_PATTERNS = {
    "an absolute /Users/ path": re.compile(r"/Users/"),
    "the word 'saarvis'": re.compile(r"saarvis", re.IGNORECASE),
    "the word 'staas'": re.compile(r"staas", re.IGNORECASE),
    "a Co-Authored-By trailer": re.compile(r"Co-Authored-By"),
    "a full model id": re.compile(r"claude-(opus|sonnet|haiku|fable)-\d"),
}


def read(path):
    return path.read_text(encoding="utf-8")


def parse_frontmatter(text):
    """Parse a SKILL.md's frontmatter block with a real YAML parser.

    A hand-rolled `key: value` splitter cannot tell a value that merely contains a colon from
    one that is genuinely broken YAML -- it would read
    `when_to_use: ... Example requests: "..."` as a fine key with a long string value, exactly
    where Claude Code's own loader reads that second colon as the start of a nested mapping and
    fails to parse the frontmatter at all (the skill then loads with no name, no description,
    nothing). Using the same kind of parser Claude Code uses is what catches that class of bug.
    """
    assert text.startswith("---\n"), "SKILL.md must open with a --- frontmatter block"
    end = text.index("\n---", 4)
    block = text[4:end]
    parsed = yaml.safe_load(block)
    assert isinstance(parsed, dict), f"frontmatter did not parse to a mapping: {parsed!r}"
    return parsed


def test_at_least_the_three_expected_skills_exist():
    names = {p.parent.name for p in SKILL_FILES}
    assert {"dispatch", "dispatch-resume", "dispatch-stats"} <= names


def test_every_claude_plugin_root_reference_resolves_in_repo():
    checked = 0
    for path in SHIPPED_FILES:
        text = read(path)
        for match in PLUGIN_ROOT_REF.finditer(text):
            rel = match.group(1).rstrip(".,;:").lstrip("/")
            target = REPO_ROOT / rel
            assert target.exists(), f"{path}: ${{CLAUDE_PLUGIN_ROOT}}/{rel} does not exist"
            checked += 1
    assert checked > 0, "expected at least one ${CLAUDE_PLUGIN_ROOT}/... reference to check"


def test_every_claude_skill_dir_reference_resolves_relative_to_its_own_skill():
    """${CLAUDE_SKILL_DIR} resolves to the directory holding the SKILL.md that references it,
    not the repo root and not any other skill's directory -- so each SKILL.md's own references
    have to be checked against its own parent directory, one skill at a time. A bare relative
    path (no variable at all, e.g. "templates/foo.md") would silently skip this check entirely,
    which is exactly the gap that let a typo'd template name pass unnoticed before; every
    template reference in this repo is now spelled with ${CLAUDE_SKILL_DIR} so this check
    actually sees it.
    """
    checked = 0
    for path in SKILL_FILES:
        text = read(path)
        skill_dir = path.parent
        for match in SKILL_DIR_REF.finditer(text):
            rel = match.group(1).rstrip(".,;:").lstrip("/")
            target = skill_dir / rel
            assert target.exists(), (
                f"{path}: ${{CLAUDE_SKILL_DIR}}/{rel} does not exist under {skill_dir}"
            )
            checked += 1
    assert checked > 0, "expected at least one ${CLAUDE_SKILL_DIR}/... reference to check"


def test_skill_frontmatter_parses_with_name_and_description():
    assert SKILL_FILES, "expected at least one skills/*/SKILL.md"
    for path in SKILL_FILES:
        fields = parse_frontmatter(read(path))
        assert fields.get("name"), f"{path}: frontmatter missing name"
        assert fields.get("description"), f"{path}: frontmatter missing description"


def test_skill_name_matches_its_directory():
    for path in SKILL_FILES:
        fields = parse_frontmatter(read(path))
        assert fields["name"] == path.parent.name, (
            f"{path}: frontmatter name {fields['name']!r} does not match "
            f"directory {path.parent.name!r}"
        )


def test_no_owner_specific_or_disallowed_strings():
    for path in LEAK_CHECK_FILES:
        text = read(path)
        if path.name == "README.md":
            for allowed in README_ALLOWED_REFERENCES:
                text = text.replace(allowed, "", 1)  # one blessed occurrence, never a repeat
        for label, pattern in LEAK_PATTERNS.items():
            assert not pattern.search(text), f"{path}: contains {label}"


def test_plan_template_approved_placeholder_is_not_a_dated_approval():
    """The plan template ships an `Approved:` placeholder comment so a user can see where the
    line goes. That placeholder must never itself satisfy the dated-approval rule the dispatch
    skill's Resume step checks -- otherwise every fresh plan made from this template would read
    as already approved the instant its design doc exists, skipping the one approval gate the
    whole workflow depends on.
    """
    plan_template = read(SKILLS_DIR / "dispatch" / "templates" / "plan.md")
    approved_line = next(
        line for line in plan_template.splitlines() if line.startswith("Approved:")
    )
    assert not DATED_APPROVED_LINE.match(approved_line), (
        f"template's placeholder line matches the dated-approval form: {approved_line!r}"
    )
    # Positive control: a real approved line must still match, so a change that broke the
    # regex into never matching anything would not slip this test by vacuous success.
    assert DATED_APPROVED_LINE.match("Approved: 2026-09-26: yes, ship it")


def test_git_push_appears_only_in_the_no_self_push_constraint():
    """The coordinator itself must never run `git push` -- only an implementer does, on a
    task's own instruction. The one place "git push" may appear anywhere in a shipped skill
    or template is the Constraints line stating that rule; a second occurrence anywhere else
    would be the coordinator's own instructions telling it to push.
    """
    occurrences = [
        (path, lineno, line)
        for path in SHIPPED_FILES
        for lineno, line in enumerate(read(path).splitlines(), start=1)
        if "git push" in line
    ]
    assert len(occurrences) == 1, f"expected exactly one 'git push' mention, found {occurrences}"
    path, lineno, line = occurrences[0]
    assert "Never runs `git push` itself" in line, (
        f"the one 'git push' mention is not the no-self-push constraint: {path}:{lineno}: {line!r}"
    )


def test_dispatch_git_exclude_step_runs_in_setup_and_resume():
    """A run that needs `.dispatch/` for a design doc or an amendment -- not only for saving a
    plan that lives only in this conversation -- still has to keep that folder out of git
    before writing to it, or the next implementer's own clean-tree pre-flight sees the
    coordinator's working files and stops cold. That has to hold whether a run is starting
    fresh (Setup) or picking back up in a later session (Resume), since either one can be the
    first to write under that folder.
    """
    text = read(SKILLS_DIR / "dispatch" / "SKILL.md")
    marker = "0. Exclude `.dispatch/` from git"
    setup = text[text.index("\n## Setup") : text.index("\n## Resume")]
    resume = text[text.index("\n## Resume") : text.index("\n## Design pass and approval")]
    assert marker in setup, "Setup has no step 0 opening with the git-exclude step"
    assert marker in resume, "Resume has no step 0 opening with the git-exclude step"


def test_implementer_owns_its_commit_in_skill_and_brief():
    """Only the implementer that did the work may commit it. A coordinator that commits on an
    implementer's behalf -- even just so the next reviewer has something to look at -- breaks
    the link between the commit history and who actually wrote and checked the change. The
    per-task loop and the brief handed to every implementer must say this the same way, so one
    can never quietly drift from the other.
    """
    phrase = "The implementer commits its own work"
    assert phrase in read(SKILLS_DIR / "dispatch" / "SKILL.md")
    assert phrase in read(SKILLS_DIR / "dispatch" / "templates" / "implementer-brief.md")


def test_plan_template_documents_a_gate_a_later_task_creates():
    """A gate can check something that does not exist until a later task creates it -- a
    generated script, a config file. The template has to show how to mark that gate so the
    coordinator never tries to run it before it can possibly pass, and never mistakes its
    absence on the baseline for a broken plan.
    """
    plan_template = read(SKILLS_DIR / "dispatch" / "templates" / "plan.md")
    assert "# from task" in plan_template


def test_coordinator_post_cap_fix_exception_is_stated_in_both_stages():
    """Only the implementer commits its own work, with exactly one exception: a small fix the
    coordinator makes itself after a review loop-cap escalation. Stage 1 states the general
    rule and has to name that exception rather than silently contradict it, and Stage 2 is
    where the exception is spelled out in full. If either one drops the word "exception", the
    two rules can drift back into contradicting each other the way they once did.
    """
    text = read(SKILLS_DIR / "dispatch" / "SKILL.md")
    marker = "the sole exception"
    stage1 = text[text.index("**Stage 1") : text.index("**Stage 2")]
    stage2 = text[text.index("**Stage 2") : text.index("**Stage 3")]
    assert marker in stage1, "Stage 1 never names the post-cap fix as an exception"
    assert marker in stage2, "Stage 2 never names the post-cap fix as an exception"


def test_design_pass_is_chosen_by_counting_files_not_by_judging_difficulty():
    """Whether a plan gets a design pass must not depend on how simple its tasks look to
    whoever is reading it: the same plan has to take the same path every time."""
    skill = (Path(__file__).resolve().parent.parent / "skills" / "dispatch" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    assert "Count files and interfaces, not difficulty" in skill
    assert "Single-file or mechanical plans" not in skill


def test_every_pasted_template_is_read_fresh_including_the_final_review():
    """The rule that a template is pasted as written, never paraphrased, has to reach every
    subagent that is handed one. The final review sits under its own heading, outside the
    per-task loop, so it carries the rule itself."""
    skill = (Path(__file__).resolve().parent.parent / "skills" / "dispatch" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    loop = skill[skill.index("## Per-task loop") : skill.index("## After the last task")]
    final = skill[skill.index("## After the last task") : skill.index("## Constraints")]
    for name, section in (("the per-task loop", loop), ("the final review", final)):
        flat = " ".join(section.split())
        assert "read fresh" in flat, f"{name} never says its template is read fresh"
        assert "actual text" in flat, f"{name} never says to paste the template's actual text"
