"""Checks on the shipped skill files themselves, not on runtime behavior.

Three things matter about a file a plugin ships to every installer: every path it points at
under ${CLAUDE_PLUGIN_ROOT} has to actually exist in the repo, every SKILL.md's frontmatter has
to parse and carry the fields Claude Code requires, and none of these files may carry a local
path, an internal project name, a commit trailer, or a pinned model id out into the world.
"""
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO_ROOT / "skills"

# Every skill this plugin ships. Each is also an "entry point" -- something a user invokes
# directly -- so this one glob covers both "SKILL.md" and "the entry points" from the same walk.
SKILL_FILES = sorted(SKILLS_DIR.glob("*/SKILL.md"))

# Skills plus whatever they paste from (currently just skills/dispatch/templates/*.md).
SHIPPED_FILES = sorted(SKILLS_DIR.rglob("*.md"))

PLUGIN_ROOT_REF = re.compile(r"\$\{CLAUDE_PLUGIN_ROOT\}(/[^\s`\"'()\[\]]+)")

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
    """Minimal, stdlib-only reader for the flat `key: value` frontmatter this project's
    SKILL.md files use. Not a general YAML parser: it only has to confirm the two fields
    Claude Code requires are present, not validate every field this repo's skills happen
    to use.
    """
    assert text.startswith("---\n"), "SKILL.md must open with a --- frontmatter block"
    end = text.index("\n---", 4)
    block = text[4:end]
    fields = {}
    for line in block.splitlines():
        if not line.strip() or line[0] in " \t":
            continue  # blank line, or a continuation/nested line under the previous key
        key, sep, value = line.partition(":")
        if sep:
            fields[key.strip()] = value.strip()
    return fields


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
    for path in SHIPPED_FILES:
        text = read(path)
        for label, pattern in LEAK_PATTERNS.items():
            assert not pattern.search(text), f"{path}: contains {label}"
