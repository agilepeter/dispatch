# Releasing dispatch

A release is a version number users can receive. Claude Code gives a user a new copy of a
plugin only when its version changes, and it reads that version from
`.claude-plugin/plugin.json`. Commits pushed without a version bump reach nobody who has
already installed.

## Every release

1. Bump `version` in `.claude-plugin/plugin.json`. Leave the marketplace entry without a
   `version`: two version fields are one too many, and the validator reports a mismatch.
2. Add a section for that version at the top of `CHANGELOG.md`, dated the day you tag.
   Every line must be true of the code.
3. Run the eval suite if the skill, a template or a grader changed (see "Evals" in the
   README), and update the numbers there and in `evals/reports/<version>/` from that one run.
4. Run the checks:

   ```
   python -m pytest -q
   claude plugin validate --strict .claude-plugin/plugin.json
   claude plugin validate --strict .
   scripts/release-check.sh
   ```

   `release-check.sh` confirms the version agrees everywhere, runs both validations and a
   dry run of the tag, and refuses if the tag already exists. It only checks; it never
   tags. The two validations are not the same check twice: the first reads the plugin's
   manifest and its skills, the second reads the marketplace manifest only.

   Neither validation proves that a skill's frontmatter is valid YAML. Claude Code 2.1.283
   accepts a value with an unquoted colon in it; 2.1.210 rejects the same file and loads
   the skill with its metadata dropped. The test suite parses every skill's frontmatter
   strictly, which is why `pytest` is first on this list and cannot be skipped.
5. Commit, push, and wait for CI to pass on all three operating systems.
6. Tag and push the tag:

   ```
   claude plugin tag --push .
   ```

   The tag is `dispatch--v<version>`.
7. Confirm from a fresh profile that the release installs:

   ```
   export CLAUDE_CONFIG_DIR="$(mktemp -d)"
   claude plugin marketplace add agilepeter/dispatch
   claude plugin install dispatch@agilepeter
   claude plugin list
   claude plugin details dispatch
   ```

## The first release only

The repository is private until 0.1.0 ships, and two pages link to each other: this README
links the product page, and the product page links this repository. Do these in order so
neither link is broken for longer than a minute:

1. Run "Every release" steps 1 to 5 above.
2. Publish the product page first, then wait until it answers:

   ```
   curl -sI https://staas.fund/dispatch/ | head -1
   ```

3. Make the repository public. This is the one step that cannot be taken back:

   ```
   gh repo edit agilepeter/dispatch --visibility public --accept-visibility-change-consequences
   ```

4. Tag (step 6) and confirm the install from a fresh profile (step 7).

## What users do

- Update: `claude plugin update dispatch@agilepeter` in a shell, or
  `/plugin marketplace update agilepeter` in a session. Automatic updates are off until a
  user turns them on under Marketplaces in `/plugin`.
- Stay on one version: add the marketplace at a tag, `agilepeter/dispatch#dispatch--v0.1.0`.

## Known limit

claude.ai's organization sync rejects a plugin with a top-level `bin/` directory, which this
plugin has (its two scripts live there so they are on the path in a session). Installing
through a marketplace, as above, is unaffected.
