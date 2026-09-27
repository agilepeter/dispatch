"""Tests for scripts/release-check.sh.

The script runs against a temp copy of the repo with a stub CLAUDE_BIN and
RELEASE_CHECK_OFFLINE=1, so nothing here needs the real claude binary, a git
remote, or the network.
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

# The script is a maintainer-side release tool run from a POSIX shell. The
# Windows leg cannot rely on python3 on PATH, an LF checkout (CRLF breaks
# `set -euo pipefail`), or POSIX paths handed to bash.
pytestmark = [
    pytest.mark.skipif(
        sys.platform == "win32",
        reason="release-check.sh is a POSIX-shell release tool; the Windows "
               "leg cannot rely on python3, LF checkout or POSIX paths",
    ),
    pytest.mark.skipif(shutil.which("bash") is None, reason="bash is not on PATH"),
]

needs_git = pytest.mark.skipif(shutil.which("git") is None, reason="git is not on PATH")


def _copy_repo(tmp_path, git_init=False) -> Path:
    """Copy the working tree without git metadata or ledger state; with
    git_init, make the copy the root of a fresh (empty) git repository."""
    dest = tmp_path / "repo"
    shutil.copytree(
        REPO_ROOT, dest, ignore=shutil.ignore_patterns(".git", ".dispatch")
    )
    if git_init:
        subprocess.run(["git", "init", "-q", str(dest)], check=True)
    return dest


def _stub_claude(tmp_path) -> Path:
    """A claude stand-in that accepts any arguments and succeeds."""
    stub = tmp_path / "claude-stub"
    stub.write_text("#!/bin/sh\nexit 0\n")
    stub.chmod(0o755)
    return stub


def _run(repo, tmp_path):
    env = dict(
        os.environ, CLAUDE_BIN=str(_stub_claude(tmp_path)), RELEASE_CHECK_OFFLINE="1"
    )
    return subprocess.run(
        ["bash", str(repo / "scripts" / "release-check.sh")],
        capture_output=True, text=True, env=env,
    )


def _plugin_version(repo) -> str:
    return json.loads((repo / ".claude-plugin" / "plugin.json").read_text())["version"]


def _assert_single_failure(result, *needles):
    assert result.returncode == 1
    lines = result.stderr.splitlines()
    assert len(lines) == 1
    assert lines[0].startswith("release-check: ")
    for needle in needles:
        assert needle in lines[0]


@needs_git
def test_wrong_changelog_version_fails(tmp_path):
    repo = _copy_repo(tmp_path, git_init=True)
    version = _plugin_version(repo)
    changelog = repo / "CHANGELOG.md"
    changelog.write_text(changelog.read_text().replace(version, "9.9.9", 1))

    result = _run(repo, tmp_path)

    _assert_single_failure(result, "CHANGELOG.md", "9.9.9", version)
    assert result.stdout == ""


@needs_git
def test_consistent_copy_passes(tmp_path):
    repo = _copy_repo(tmp_path, git_init=True)

    result = _run(repo, tmp_path)

    assert result.returncode == 0
    assert result.stderr == ""
    assert result.stdout.splitlines()[-1] == (
        f"release-check: dispatch {_plugin_version(repo)} ok"
    )


def test_not_a_git_repository_is_reported(tmp_path):
    repo = _copy_repo(tmp_path)

    result = _run(repo, tmp_path)

    _assert_single_failure(result, "not a git repository")


@needs_git
def test_marketplace_version_mismatch_fails(tmp_path):
    repo = _copy_repo(tmp_path, git_init=True)
    market = repo / ".claude-plugin" / "marketplace.json"
    data = json.loads(market.read_text())
    data["plugins"][0]["version"] = "9.9.9"
    market.write_text(json.dumps(data))

    result = _run(repo, tmp_path)

    _assert_single_failure(result, "marketplace.json", "9.9.9")


@needs_git
def test_malformed_marketplace_json_fails(tmp_path):
    repo = _copy_repo(tmp_path, git_init=True)
    (repo / ".claude-plugin" / "marketplace.json").write_text("{bad")

    result = _run(repo, tmp_path)

    _assert_single_failure(result, "marketplace.json")


@needs_git
def test_marketplace_plugins_not_a_list_fails(tmp_path):
    repo = _copy_repo(tmp_path, git_init=True)
    (repo / ".claude-plugin" / "marketplace.json").write_text('{"plugins": {}}')

    result = _run(repo, tmp_path)

    _assert_single_failure(result, "marketplace.json")


@needs_git
def test_marketplace_entry_without_version_is_ignored(tmp_path):
    repo = _copy_repo(tmp_path, git_init=True)
    data = json.loads((repo / ".claude-plugin" / "marketplace.json").read_text())
    assert "version" not in data["plugins"][0]

    result = _run(repo, tmp_path)

    assert result.returncode == 0
    assert result.stderr == ""


@needs_git
def test_copy_inside_another_repo_is_not_a_repo(tmp_path):
    # The enclosing directory is a repository; the copy itself is not, so its
    # tags must not be looked up in the parent.
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    repo = _copy_repo(tmp_path)

    result = _run(repo, tmp_path)

    _assert_single_failure(result, "not a git repository")
