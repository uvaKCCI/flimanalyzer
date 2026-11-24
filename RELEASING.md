# Releasing FLIMAnalyzer

For maintainers. Go through the list from the top when a release is planned, not when
it is due: the preflight finds what would block a later step. Each step builds on the
one before it; nothing is published from a branch or by hand.

Two kinds of release:

- **A release `X.Y.0`:** `dev` into `main`, tagged on `main`. Development for it
  happens on `dev` (`feature/*`, `fix/*`, `docs/*`, `ci/*` from `dev` back into `dev`).
- **A patch `X.Y.Z`** of any series, the newest too: fix branches `fix/X.Y.Z` or
  `fix/X.Y.Z-topic` from `release/X.Y.x` into that branch, tagged there. The steps
  marked *(patch)* apply only to it.

`release/X.Y.x` is created from the tag `vX.Y.0` when `X.Y.0` is released. It is never
merged into `dev` or `main`: `main` stays at `X.Y.0` until `X.Y+1.0`. A bug in both a
released series and `dev` gets a fix in each, written for that line's code, with one
issue and the same regression test (run it on both lines to see where the bug is).

## Checked in CI

These fail on their own; the list below doesn't repeat them.

- `CHANGELOG.md` has a section for every release up to the newest one in the branch's
  history, also for the patches of an older series
  (`tests/core/test_release_records.py`).
- Every image in `docs/images` is retaken by `docs/screenshots.py` or is a copy of an
  app icon, and every image is used by a page (same file).
- Every tool in a menu has a screenshot of its dialog, except the ones listed in
  `tests/core/test_docs_tools.py` (`KNOWN_MISSING`).
- The documentation builds as on Read the Docs, warnings as errors (`docs` job).
- Docker `latest` moves only for the highest release version
  (`.github/scripts/is-newest-release.sh`).

## 1. Preflight (when the release is planned)

- [ ] Every entry planned for the release (its milestone) is done, or moved to another
      release by the maintainer: list the open ones for the maintainer and get a
      decision on each. Release timing is the maintainer's decision; the planned bug
      fixes and features come first.
- [ ] The target branch's rules (`main`: branch protection; `release/*`: rulesets) and
      the check names they require (`all checks`) against the jobs of the workflows
      *on the branch being merged*: a maintenance branch can lag behind `dev` in CI.
- [ ] The workflows that run for the tag come from the tagged commit
      (`release.yml`, `docker.yml`): check them there, not on `main`.
- [ ] The `pypi` environment (required reviewer, `v*` tags only) and the tag
      ruleset (`v*` can't be updated or deleted).
- [ ] The issues the release closes, and which of them a pull request closes on its
      own (only one into the default branch does).

## 2. Documentation matches the release

Only after every planned fix and feature is merged (step 1).

- [ ] User guide pages for every new and changed tool, dialog and menu entry.
- [ ] Screenshots retaken from the version being released:
      `uv run python docs/screenshots.py DATAFILE` on macOS (see its docstring); none
      shows an older version. New tools: add their dialog to `SHOTS` and remove them
      from `KNOWN_MISSING`.
- [ ] Every page read in the rendered preview, not only the changed ones.

## 3. Changelog and version

- [ ] *(X.Y.0)* `uv.lock` current: if its last update (Dependabot's monthly pull
      request, or by hand) is more than about two weeks old, `uv lock --upgrade` on
      `prep/X.Y.0`, so the release ships current packages and they get the full test
      run. Changed dependencies of the Docker image go in the changelog.
- [ ] Dependabot alerts (Security tab) checked: a fix goes through `dev`, and for a
      released series through `release/X.Y.x` as a patch release. Dependabot's
      automatic security pull requests are off, since GitHub opens them against `main`.
- [ ] The release's section in `CHANGELOG.md`, dated, with the structure of the
      previous section; sections of released versions stay as published.
- [ ] Merged by pull request: `dev` into `main`, or *(patch)* `fix/X.Y.Z` into
      `release/X.Y.x`, all checks passed. A release branch is never merged into `dev`
      or `main`.

## 4. Tag and GitHub release

- [ ] Annotated tag `vX.Y.Z`, message `Version X.Y.Z`, on the merge commit.
- [ ] GitHub release from the tag, notes = the changelog section. Latest only for
      the highest version: *(patch)* of an older series `--latest=false`.

## 5. Published by CI from the release

Say the order before creating the release: the PyPI upload waits for approval.

- [ ] `release.yml` builds and checks the version; **check the build before approving**
      the `pypi` environment.
- [ ] `docker.yml` pushes `X.Y.Z` and `X.Y.Z-cpu` to ghcr.io (`latest` only for the
      highest version).
- [ ] Read the Docs builds `vX.Y.Z`; `stable` is the highest version.

## 6. Afterwards

- [ ] Each platform traces back to the tag and commit: PyPI files (hashes), image
      labels and digests, the Read the Docs version. Record the identifiers.
- [ ] Close the issues a pull request didn't close, with a comment naming the release.
- [ ] *(X.Y.0)* `main` into `dev`, so the tag is in `dev`'s history.
- [ ] *(X.Y.0)* Create `release/X.Y.x` from the tag `vX.Y.0`, for its patches.
- [ ] *(patch)* Into `dev`, by a pull request: the release's changelog section, as
      published (the changelog check fails on `dev` until it is there). Each bug the
      patch fixed is fixed on `dev` too, or its regression test shows `dev` doesn't
      have it; CI and workflow changes made on the release branch also go to `dev`.
- [ ] Delete the merged fix and release-preparation branches.
- [ ] `CITATION.cff` and the README's citation table only for a version a publication
      used.
