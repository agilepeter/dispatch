"""Tests for scripts/release-check.sh.

The script runs against a temp copy of the repo with a stub CLAUDE_BIN and
RELEASE_CHECK_OFFLINE=1, so nothing here needs the real claude binary, a git
remote, or the network.
"""
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

pytestmark = pytest.mark.skipif(
    shutil.which("bash") is None, reason="bash is not on PATH"
)


def _copy_repo(tmp_path) -> Path:
    """Copy the working tree without git metadata or ledger state."""
    dest = tmp_path / "repo"
    shutil.copytree(
        REPO_ROOT, dest, ignore=shutil.ignore_patterns(".git", ".dispatch")
    )
    return dest


def _stub_claude(tmp_path) -> Path:
    """A claude stand-in that accepts any arguments and succeeds."""
    stub = tmp_path / "claude-stub"
    stub.write_text("#!/bin/sh\nexit 0\n")
    stub.chmod(0o755)
    return stub


def _run(repo, stub):
    env = dict(os.environ, CLAUDE_BIN=str(stub), RELEASE_CHECK_OFFLINE="1")
    return subprocess.run(
        ["bash", str(repo / "scripts" / "release-check.sh")],
        capture_output=True, text=True, env=env,
    )


def test_wrong_changelog_version_fails(tmp_path):
    repo = _copy_repo(tmp_path)
    plugin = json.loads((repo / ".claude-plugin" / "plugin.json").read_text())
    changelog = repo / "CHANGELOG.md"
    text = changelog.read_text()
    changelog.write_text(text.replace(plugin["version"], "9.9.9", 1))

    result = _run(repo, _stub_claude(tmp_path))

    assert result.returncode == 1
    lines = result.stderr.splitlines()
    assert lines and all(line.startswith("release-check: ") for line in lines)
    assert any(
        "9.9.9" in line and plugin["version"] in line and "CHANGELOG.md" in line
        for line in lines
    )
    assert result.stdout == ""
