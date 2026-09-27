#!/usr/bin/env bash
# Pre-release gate: version agreement, plugin validation, tag availability.
#
# env:  CLAUDE_BIN (default: claude)   RELEASE_CHECK_OFFLINE=1 skips ls-remote
# exit: 0 -> one stdout line "release-check: dispatch <version> ok"
#       1 -> one stderr line per failure, "release-check: <what is wrong>"
#
# Every check runs even after an earlier one fails, so a single run reports
# everything that blocks the release. No failure may be multi-line: command
# output is folded to its first non-empty line before it is reported.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

CLAUDE_BIN="${CLAUDE_BIN:-claude}"
failures=0

fail() {
  printf 'release-check: %s\n' "$1" >&2
  failures=$((failures + 1))
}

first_line() {
  printf '%s\n' "$1" | awk 'NF { sub(/^[ \t]+/, ""); print; exit }'
}

plugin_version() {
  python3 -c 'import json;print(json.load(open(".claude-plugin/plugin.json"))["version"])'
}

plugin_name() {
  python3 -c 'import json;print(json.load(open(".claude-plugin/plugin.json"))["name"])'
}

# Prints the marketplace entry's version for the named plugin, or nothing when
# the file, the entry, or its version is absent (nothing to compare). An
# unparseable file or a non-list "plugins" exits 2 with a one-line reason on
# stdout, so that condition cannot be mistaken for "nothing to compare".
marketplace_version() {
  python3 - "$1" <<'PY'
import json, sys
try:
    with open(".claude-plugin/marketplace.json") as f:
        data = json.load(f)
except FileNotFoundError:
    sys.exit(0)
except (OSError, ValueError) as exc:
    print("cannot parse it (%s)" % type(exc).__name__)
    sys.exit(2)
plugins = data.get("plugins", []) if isinstance(data, dict) else None
if not isinstance(plugins, list):
    print('"plugins" is not a list')
    sys.exit(2)
for entry in plugins:
    if isinstance(entry, dict) and entry.get("name") == sys.argv[1] and entry.get("version"):
        print(entry["version"])
PY
}

if ! version="$(plugin_version 2>/dev/null)" || [ -z "$version" ]; then
  fail "cannot read a version from .claude-plugin/plugin.json"
  exit 1
fi
if ! name="$(plugin_name 2>/dev/null)" || [ -z "$name" ]; then
  fail "cannot read a name from .claude-plugin/plugin.json"
  exit 1
fi

changelog_version="$(awk '/^## / { print $2; exit }' CHANGELOG.md 2>/dev/null || true)"
if [ -z "$changelog_version" ]; then
  fail "CHANGELOG.md has no '## ' version heading"
elif [ "$changelog_version" != "$version" ]; then
  fail "CHANGELOG.md version $changelog_version does not match plugin.json version $version"
fi

if ! market_version="$(marketplace_version "$name" 2>/dev/null)"; then
  fail "marketplace.json is unusable: $(first_line "$market_version")"
elif [ -n "$market_version" ] && [ "$market_version" != "$version" ]; then
  fail "marketplace.json version $market_version does not match plugin.json version $version"
fi

if ! command -v "$CLAUDE_BIN" >/dev/null 2>&1; then
  fail "$CLAUDE_BIN not found on PATH (set CLAUDE_BIN)"
else
  # Two targets, because they check different things: the repository root is
  # validated as a marketplace manifest and nothing under it is read, while the
  # plugin's own manifest brings its skills and their frontmatter with it.
  for target in .claude-plugin/plugin.json .; do
    if out="$("$CLAUDE_BIN" plugin validate --strict "$target" 2>&1)"; then
      :
    else
      status=$?
      fail "claude plugin validate --strict $target failed (exit $status): $(first_line "$out")"
    fi
  done

  if out="$("$CLAUDE_BIN" plugin tag --dry-run . 2>&1)"; then
    if [ -n "$out" ]; then printf '%s\n' "$out"; fi
  else
    status=$?
    fail "claude plugin tag --dry-run failed (exit $status): $(first_line "$out")"
  fi
fi

# The tag checks need this directory to be the root of its own git work tree;
# git searches upward, so a copy nested in another repo must not borrow that
# repo's tags. Physical paths keep symlinked prefixes (macOS /tmp) from
# causing false mismatches. Without a repo the check cannot say anything
# about existing tags, which is itself a failure.
tag="${name}--v${version}"
toplevel="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [ -z "$toplevel" ] || [ "$(cd "$toplevel" && pwd -P)" != "$(pwd -P)" ]; then
  fail "not a git repository, cannot check for an existing tag"
else
  if git rev-parse -q --verify "refs/tags/$tag" >/dev/null 2>&1; then
    fail "tag $tag already exists locally"
  fi
  if [ "${RELEASE_CHECK_OFFLINE:-}" != "1" ]; then
    if remote="$(git ls-remote --tags origin "refs/tags/$tag" 2>&1)"; then
      if [ -n "$remote" ]; then
        fail "tag $tag already exists on origin"
      fi
    else
      fail "git ls-remote --tags origin failed: $(first_line "$remote")"
    fi
  fi
fi

if [ "$failures" -gt 0 ]; then
  exit 1
fi
echo "release-check: $name $version ok"
