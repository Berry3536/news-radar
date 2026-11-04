# CLAUDE.md

News Radar: serverless personal dashboard. A scheduled GitHub Actions run (`update.yml`)
executes `aggregate.py` (feedparser) over `feeds.json`, then force-pushes `index.html` +
`data.json` as a single commit to the `gh-pages` branch, which GitHub Pages serves.
Public repository — never commit anything private (RULE12).

## Docs map

| File | Holds | Update when |
|---|---|---|
| `docs/ROADMAP.md` | Gates, tickets, defect register, GR log; the only place for status | A ticket starts or merges, a defect is found, a GR is proposed or closed |
| `docs/RULES.md` | RULE register: values, rationale, revision history, what we chose not to do | A rule is added or changed (also update `## Rules` below) |
| `docs/DESIGN.md` | What the product is: scope, files, data flow and formats (`feeds.json`, `data.json`), error model, known limits | Files, data formats or the pipeline change |
| `docs/RUNBOOK.md` | How to run it: dev and verify, operations (manual run, schedule checks, re-enable), release and hotfix, QA, release history | A procedure changes or a release ships |
| `README.md` | Korean introduction and quick start for humans; links into `docs/` | The quick start or the doc links change |

All four `docs/` files are in Korean.

## Commands

```powershell
uv sync                              # .venv from uv.lock (Python 3.13), incl. ruff
uv run pytest                        # unit tests for the filter/date/dedup helpers
uv run python aggregate.py           # writes data.json (network)
uv run python -m http.server         # preview at http://localhost:8000
```

## Rules

Values and rationale in `docs/RULES.md`; same numbers.

| Rule | Statement | Enforced in |
|---|---|---|
| RULE1 | `data.json` is published only on the `gh-pages` branch; it is never committed to `master`/`develop`. | `.gitignore`, `update.yml` publish step, Forbidden |
| RULE2 | Only the `update.yml` workflow writes `gh-pages`: one commit (`index.html`, `data.json`, `.nojekyll`), force-pushed on every run. | `update.yml`, `.claude/settings.json` deny, Forbidden |
| RULE3 | Feeds, keyword filters and limits live only in `feeds.json`; no feed URL, keyword or limit is hard-coded. | `aggregate.py` `main`, CI `feeds.json` parse check |
| RULE4 | One failing feed is skipped and logged `[FAIL]`; it never aborts the run. A feed fails on an exception, or on `bozo` with zero entries. | `aggregate.py` `build_category`/`collect_feed`, `test_build_category_filters_dedups_sorts_and_caps` |
| RULE5 | Keyword filter on title + summary, case-insensitive: any exclude keyword drops the item (exclude wins); an empty include list passes everything, otherwise one include keyword must match. | `aggregate.passes_filters`, `test_passes_filters` |
| RULE6 | Dates are normalized to UTC; items older than `max_age_days` (14) are dropped; undated items are kept and sorted last. | `aggregate.parse_date`/`build_category`, `test_parse_date_*` |
| RULE7 | Deduplication is per category; the key is the link without query string and trailing `/`, or the lowercased title when there is no link; the first item wins. | `aggregate.dedup_key`/`build_category`, `test_dedup_key_*` |
| RULE8 | Each category is sorted newest first and capped at `max_items_per_category` (40). | `aggregate.build_category`, `test_build_category_filters_dedups_sorts_and_caps` |
| RULE9 | The collector's only runtime dependency is `feedparser`. | `pyproject.toml` `dependencies` |
| RULE10 | The dashboard is the single file `index.html` with no external JS; it fetches `data.json` from the same path. | `index.html`, `update.yml` publish step |
| RULE11 | Strings from `data.json` (title, source, link, category label) and the search text are HTML-escaped before they reach the DOM. | `index.html` `esc()` |
| RULE12 | Public repository: nothing private is committed; secrets live only in GitHub Secrets. | Review |
| RULE13 | Not done: sources without RSS/Atom are not collected (no scraping). | — |
| RULE14 | Not done: collection on the exact schedule is not guaranteed (cron 00/06/12/18 UTC is best effort). | — |
| RULE15 | Not done: no server, no database, no history of past collections; each run overwrites the published copy. | — |

## Forbidden

- Committing `data.json` to `master`/`develop`; it is published only on `gh-pages`.
- Pushing to `gh-pages` by hand; only the workflow writes it.

<!-- stark-kit:begin level=standard kit=0.3.5 — generated; edit stark-kit, then `kit.py sync` -->

# Kit rules

## Level: standard

A defect here costs time, not irreversible losses: it is caught by tests or fixed by a
patch release. Keep ceremony proportional to the change.

1. **Scope.** For anything beyond a small fix, state Goal / Acceptance in two to five lines in the
   `Current work` section of `docs/ROADMAP.md`, set the ticket `in progress`, and get a quick OK before coding.
2. **Branch.** `feature/<slug>` or `bugfix/<slug>` from `develop`.
3. **Implement** until every `commands.verify` (and `commands.smoke`, if any) passes.
4. **Verify** non-trivial changes (new behavior, more than one module, release-relevant) with
   one fresh `verifier` subagent, `correctness` lens. Spot-check its findings before acting.
5. **Report**: what changed, verify output, findings and how each was handled.
6. **After user approval:** merge into `develop` with `--no-ff`. In `docs/ROADMAP.md` set the ticket
   `done <merge sha>`, mark the defects it closes `fixed by`, clear `Current work`.
7. **Gate Review.** When the gate's last ticket merges, check the exit criteria (one fresh `verifier`
   on the gate's cumulative diff, or the user's own check for non-code criteria) and add a `GRn` row
   with `proposed: <verdict>`. Only the user closes the GR.

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
- Cross-cutting code (logging, config, files, time, errors) follows `.claude/CONVENTIONS.md`;
  package layout and import layering are declared per repo (`kit.json` `layout`, `[tool.importlinter]`).
- Work is planned in `docs/ROADMAP.md` as gates `GATE0..GATEN`. Five ids, the same in every repo:
  `GATEn` (gate), `GATEn-Tk` (ticket, one branch of work), `GRn` (gate review, closed only by the user),
  `DEFECTn` (defect register, numbered as found), `RULEn` (what the product must always hold: invariants,
  limits, scope, things decided against). Branch slugs and commit summaries carry the ticket. A release is
  evidence for a GR, never a gate.
- Docs: `docs/ROADMAP.md` (status, the only place for it), `docs/RULES.md` (rule values, rationale,
  revision history), `docs/DESIGN.md` (what the product is), `docs/RUNBOOK.md` (how to run it) — all four
  exist in every repo, written in Korean, with the section names of the kit templates. `CLAUDE.md` stays
  English and holds the `## Rules` table (id, statement, where enforced) and `## Forbidden`. Do not restate
  what the code says; history lives in git and releases; other documents point at ids, never at status.

## Git (gitflow)

| Branch | From | Merges into | Notes |
|---|---|---|---|
| `master` | — | — | Release history only. Every commit is a merge from `release/*` or `hotfix/*`, tagged `vX.Y.Z`. |
| `develop` | `master` | — | Integration. Only merges from `feature/*`, `bugfix/*`, `release/*`, `hotfix/*`, `dependabot/*` (and `master` to resync). |
| `feature/<slug>` | `develop` | `develop` | New work. Slug starts with the ticket id when there is one (`feature/GATE1-T2-audit-fixes`). |
| `bugfix/<slug>` | `develop` | `develop` | Fix for something not yet released. |
| `release/X.Y.Z` | `develop` | `master` + `develop` | Version bump, release notes, last fixes only. Use the `release` skill. |
| `hotfix/X.Y.Z` | `master` | `master` + `develop` | Fix for a released version. Use the `gitflow` skill. |

- Merges into `master`/`develop` are always `--no-ff` with git's default message
  (`Merge branch 'feature/x' into develop`).
- Before merging into `develop`, put the branch on the current `develop` tip so the merge
  bubble shows its commits in order with no crossing lanes: `git switch <branch> && git rebase develop`
  (feature/bugfix branches are local, so nothing pushed is rewritten). A Dependabot branch is
  rebased by the bot: comment `@dependabot rebase` on its PR, wait for the new head, then merge;
  take Dependabot PRs one at a time. Never rebase `develop`, `master`, `release/*` or `hotfix/*`.
- Dependabot PRs are normally merged by the kit-managed workflow `.github/workflows/dependabot-merge.yml`
  (daily 12:23 UTC, runs from `master`): patch/minor updates only (strict level: development tools
  and GitHub Actions only), one at a time, after Dependabot rebased the PR onto the `develop` tip and
  its CI passed. Its merges read `Merge pull request #N from <owner>/dependabot/...`. A PR it will
  not merge gets the `needs-review` label and a comment: handle that one with the manual procedure
  (gitflow skill). Because `origin/develop` moves on its own, start local work with
  `git pull --ff-only origin develop`.
- Commit messages: `<type>(<scope>)?: <summary>`; types `feat fix docs refactor test chore perf build ci style revert`.
  Add the ticket id in the summary when there is one (`fix: refuse unknown keys (GATE1-T2)`).
- Never commit, merge into `develop`/`master`, push, tag, or publish a release without the user asking.
  Never force-push or rewrite pushed history.
- The gitflow guard (`.claude/hooks/gitflow_guard.py`, also installed as git hooks) blocks
  violations. If it blocks you, fix the workflow — do not bypass it (`--no-verify` is forbidden).

<!-- stark-kit:end -->
