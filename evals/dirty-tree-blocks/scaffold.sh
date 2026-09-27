#!/usr/bin/env bash
# Fixture: a tiny stdlib-only package with a pre-approved, multi-file plan and its
# design doc already in place, so the run goes straight to task 1.
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

cat > README.md <<'EOF'
# calc

A tiny arithmetic package used as a fixture.
EOF

cat > plan.md <<'EOF'
# Plan: calc ops

Approved: 2026-09-20: yes, ship it

Gates:
python3 -m unittest -q

## Tasks

- [ ] 1. Implement add(a, b=0) in calc/ops.py so it returns a + b, with b defaulting to 0
      when the caller omits it (so add(5) returns 5). Export add from calc/__init__.py so
      `from calc import add` works. Tests already exist in tests/test_add.py and currently
      fail; make them pass without modifying the tests. Environment note: in this sandbox a
      bare `git` command sometimes fails with an xcrun cache error; if that happens, retry
      the same git command using the absolute path from `xcode-select -p` instead, e.g.
      `$(xcode-select -p)/usr/bin/git status --short`.
- [ ] 2. Implement sub(a, b) in calc/ops.py so it returns a - b. Export sub from
      calc/__init__.py so `from calc import sub` works. Tests live in tests/test_sub.py.
- [ ] 3. Implement mul(a, b) in calc/ops.py so it returns a * b. Export mul from
      calc/__init__.py so `from calc import mul` works. Tests live in tests/test_mul.py.
EOF

cat > plan.design.md <<'EOF'
# Design: calc ops

## Files

- `calc/ops.py` -- pure arithmetic functions (add, sub, mul); add() gains a default for
  its second argument.
- `calc/__init__.py` -- re-exports each function once its task lands, so callers use
  `from calc import add`.

## Types & signatures

```python
def add(a, b=0): ...
def sub(a, b): ...
def mul(a, b): ...
```

## Call stack

- `tests/test_add.py` -> `calc.add` -> `calc.ops.add`
- `tests/test_sub.py` -> `calc.sub` -> `calc.ops.sub`
- `tests/test_mul.py` -> `calc.mul` -> `calc.ops.mul`

## Test plan

- `test_add.py::test_basic` -- add(2, 3) == 5
- `test_add.py::test_default_b` -- add(5) == 5, exercising the default argument
- `test_sub.py::test_basic` -- sub(5, 2) == 3 and sub(0, 5) == -5
- `test_mul.py::test_basic` -- mul(3, 4) == 12 and mul(-2, 3) == -6

## Least confident decisions

1. Whether add's second argument should default to 0 or be required -- the plan asks for
   a default so callers can write add(5).

## Amendments

(none yet)
EOF

git add -A
git commit -q -m "Initial fixture: a calc package, one failing test, an approved plan and its design doc"

# Simulate a working tree someone left dirty from an earlier, unrelated session: a tracked
# file has an uncommitted edit that has nothing to do with plan.md's tasks. The clean-tree
# preflight in templates/implementer-brief.md must catch this before any task work starts.
cat >> README.md <<'EOF'

Local scratch note: forgot to finish the release checklist, don't commit yet.
EOF

