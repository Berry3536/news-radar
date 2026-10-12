# CLAUDE.md

News Radar: serverless personal dashboard. A scheduled GitHub Actions run (`update.yml`)
executes `aggregate.py` (feedparser) over `feeds.json`, then force-pushes `index.html` +
`data.json` as a single commit to the `gh-pages` branch, which GitHub Pages serves.
Public repository — never commit anything private.

## Files

| File | Holds |
|---|---|
| `feeds.json` | categories, feeds, keyword filters (the only file touched in normal operation) |
| `aggregate.py` | collector; per-feed failures are isolated and logged `[FAIL]` |
| `index.html` | single-file dashboard, no external JS |
| `README.md` | architecture, deployment, filter rules (Korean, for humans) |

## Commands

```powershell
python -m pip install -r requirements.txt
python aggregate.py                  # writes data.json (network)
python -m http.server                # preview at http://localhost:8000
```

## Forbidden

- Committing `data.json` to `master`/`develop`; it is published only on `gh-pages`.
- Pushing to `gh-pages` by hand; only the workflow writes it.

<!-- stark-kit:begin level=standard kit=0.1.3 — generated; edit stark-kit, then `kit.py sync` -->

# Kit rules

## Level: standard

A defect here costs time, not irreversible losses: it is caught by tests or fixed by a
patch release. Keep ceremony proportional to the change.

1. **Scope.** For anything beyond a small fix, state Goal / Acceptance in two to five lines
   and get a quick OK before coding.
2. **Branch.** `feature/<slug>` or `bugfix/<slug>` from `develop`.
3. **Implement** until every `commands.verify` (and `commands.smoke`, if any) passes.
4. **Verify** non-trivial changes (new behavior, more than one module, release-relevant) with
   one fresh `verifier` subagent, `correctness` lens. Spot-check its findings before acting.
5. **Report**: what changed, verify output, findings and how each was handled.
6. **After user approval:** merge into `develop` with `--no-ff`.

Commits on feature/bugfix branches are allowed without asking; merges into `develop`,
pushes, and tags still need the user's request.

## Working agreement

- Talk to the user in Korean. Code, comments, commit messages, and `CLAUDE.md` stay in English
  unless the project section says otherwise.
- Project facts (commands, architecture, invariants, forbidden commands) live in the project
  section above. Repository-wide rules live in this kit block; do not edit it by hand —
  change stark-kit and run `kit sync`.
- Fresh clone: run `git config core.hooksPath .githooks` (or `kit.py sync`) so the git hooks
  below are active. If `git config core.hooksPath` is empty, tell the user.
- Verify commands for this repo are in `.claude/kit.json` (`commands.verify`, `commands.smoke`).
- Never run a command listed under **Forbidden** in the project section, even to test something.

## Git (gitflow)

| Branch | From | Merges into | Notes |
|---|---|---|---|
| `master` | — | — | Release history only. Every commit is a merge from `release/*` or `hotfix/*`, tagged `vX.Y.Z`. |
| `develop` | `master` | — | Integration. Only merges from `feature/*`, `bugfix/*`, `release/*`, `hotfix/*` (and `master` to resync). |
| `feature/<slug>` | `develop` | `develop` | New work. Slug may start with a tracker ID (`feature/BL-055-audit-fixes`). |
| `bugfix/<slug>` | `develop` | `develop` | Fix for something not yet released. |
| `release/X.Y.Z` | `develop` | `master` + `develop` | Version bump, release notes, last fixes only. Use the `release` skill. |
| `hotfix/X.Y.Z` | `master` | `master` + `develop` | Fix for a released version. Use the `gitflow` skill. |

- Merges into `master`/`develop` are always `--no-ff` with git's default message
  (`Merge branch 'feature/x' into develop`).
- Commit messages: `<type>(<scope>)?: <summary>`; types `feat fix docs refactor test chore perf build ci style revert`.
  Add the tracker ID in the summary when there is one (`fix: refuse unknown keys (BL-055)`).
- Never commit, merge into `develop`/`master`, push, tag, or publish a release without the user asking.
  Never force-push or rewrite pushed history.
- The gitflow guard (`.claude/hooks/gitflow_guard.py`, also installed as git hooks) blocks
  violations. If it blocks you, fix the workflow — do not bypass it (`--no-verify` is forbidden).

<!-- stark-kit:end -->
