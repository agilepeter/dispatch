#!/usr/bin/env bash
# Fixture: a tiny stdlib-only package plus a CLI dispatcher on top of it, with an
# unapproved, genuinely multi-file plan (each task touches the ops module, the package's
# exports, AND the CLI's dispatch table).
set -euo pipefail

git init -q
git config user.name "Dispatch Eval Fixture"
git config user.email "dispatch-eval@example.invalid"

mkdir -p calc tests
cat > calc/ops.py <<'EOF'
def add(a, b):
    raise NotImplementedError


def sub(a, b):
    return a - b


def mul(a, b):
    return a * b
EOF

cat > calc/__init__.py <<'EOF'
from .ops import sub, mul
EOF

cat > cli.py <<'EOF'
import sys

from calc import sub, mul

OPS = {
    "sub": sub,
    "mul": mul,
}


def _parse(token):
    return float(token) if "." in token else int(token)


def main(argv):
    if not argv or argv[0] not in OPS:
        print(f"usage: cli.py <{'|'.join(OPS)}> <a> [b]", file=sys.stderr)
        return 1
    op = OPS[argv[0]]
    args = [_parse(x) for x in argv[1:]]
    print(op(*args))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
EOF

: > tests/__init__.py

cat > tests/test_add.py <<'EOF'
import unittest
from calc import add


class TestAdd(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(add(2, 3), 5)

    def test_default_b(self):
        self.assertEqual(add(5), 5)


if __name__ == "__main__":
    unittest.main()
EOF

cat > tests/test_sub.py <<'EOF'
import unittest
from calc import sub


class TestSub(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(sub(5, 2), 3)
        self.assertEqual(sub(0, 5), -5)


if __name__ == "__main__":
    unittest.main()
EOF

cat > tests/test_mul.py <<'EOF'
import unittest
from calc import mul


class TestMul(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(mul(3, 4), 12)
        self.assertEqual(mul(-2, 3), -6)


if __name__ == "__main__":
    unittest.main()
EOF

cat > tests/test_cli.py <<'EOF'
import subprocess
import sys
import unittest


class TestCli(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, "cli.py", *args], capture_output=True, text=True
        )

    def test_add(self):
        result = self.run_cli("add", "2", "3")
        self.assertEqual(result.stdout.strip(), "5")

    def test_sub(self):
        result = self.run_cli("sub", "5", "2")
        self.assertEqual(result.stdout.strip(), "3")


if __name__ == "__main__":
    unittest.main()
EOF

cat > README.md <<'EOF'
# calc

A tiny arithmetic package with a small CLI dispatcher on top of it.
EOF

cat > plan.md <<'EOF'
# Plan: calc ops CLI

Approved: <!-- left blank until the coordinator writes it -- during the design pass for a
multi-file plan, or during the one Gates: question below for a plan that skips the design
pass. This placeholder comment does not count as approval by itself -- the coordinator fills
the line in with the date first, then the user's own words, e.g. "2026-09-26: yes, ship it".
Only once the line begins "Approved: 20" followed by a date does a plan count as pre-approved
(together with its design doc, for a plan that needed one): it then skips straight to the
first unfinished task, no second approval question, in this session or a later one. -->

Gates:
<!-- One verification command per line, nothing else in this block. The dispatch skill runs
exactly these commands, in order, after every task, and stops at the first one that fails. -->

## Tasks

- [ ] 1. Implement add(a, b=0) in calc/ops.py so it returns a + b, with b defaulting to 0
      when the caller omits it. Export add from calc/__init__.py. Add an "add" entry to
      cli.py's OPS dispatch table, following the same pattern as "sub" and "mul", so
      `python3 cli.py add 2 3` and `python3 cli.py add 5` both work. Tests already exist in
      tests/test_add.py and tests/test_cli.py and currently fail; make them pass without
      modifying the tests.
- [ ] 2. Add a "describe" subcommand to cli.py that prints a one-line human-readable
      description of what an op does (e.g. `python3 cli.py describe sub` prints
      "sub: returns a - b"), backed by a docstring on each function in calc/ops.py.
- [ ] 3. Add a --version flag to cli.py that prints the package version from a new
      calc.__version__ string, without requiring an op argument.
EOF

git add -A
git commit -q -m "Initial fixture: calc package, CLI dispatcher, one failing task, unapproved plan"
