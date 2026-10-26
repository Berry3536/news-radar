---
name: gitflow
description: Start or finish gitflow branches (feature, bugfix, hotfix) the stark-kit way. Use when the user asks to start/finish a feature, bugfix or hotfix, or to sync develop. Releases use the release skill.
---

Arguments: `$ARGUMENTS` — `<start|finish> <feature|bugfix|hotfix> <slug|X.Y.Z>`. If missing, ask.

Rules: plain `git` only (no git-flow CLI). Stop on any failure. Steps marked **[confirm]**
need the user's explicit OK. Verify = every command in `.claude/kit.json` `commands.verify`
and `commands.smoke`.

## feature / bugfix

**start**: clean tree → `git switch develop` → `git pull --ff-only origin develop` →
`git switch -c <type>/<slug>`.

**finish**:
1. Clean tree on the branch; verify passes; the level workflow (CLAUDE.md) reached "report"
   and the user approved. **[confirm]**
2. `git switch develop && git pull --ff-only origin develop`
3. `git switch <type>/<slug> && git rebase develop` so the branch sits on the `develop` tip
   (the branch is local). On conflict: stop and report. If the rebase moved the branch, re-run verify.
4. `git switch develop && git merge --no-ff <type>/<slug>` (default message).
5. Verify on `develop`.
6. `git branch -d <type>/<slug>`. Pushing `develop` is a separate request. **[confirm]**

## dependabot PR (into develop)

One PR at a time. `git fetch origin`; if `origin/<dependabot-branch>` is not on the `develop`
tip (`git merge-base --is-ancestor develop origin/<branch>` fails), comment `@dependabot rebase`
on the PR (`gh pr comment <n> --body "@dependabot rebase"`) and wait for the bot's new head.
Then `git switch develop && git merge --no-ff origin/<branch>`, verify, push `develop`
**[confirm]**, and only then start the next PR (its rebase needs the pushed tip).

## hotfix (fix for a released version)

**start**: version = last tag + patch (`git describe --tags --abbrev=0 master`). Confirm it.
`git switch master && git pull --ff-only origin master && git switch -c hotfix/X.Y.Z`.
Set the version in `kit.json` `release.version_file` on the branch and commit
`chore: bump version to X.Y.Z`.

**finish**: same as `release` skill steps 5–9 with `hotfix/X.Y.Z` instead of `release/X.Y.Z`.

## sync

If `develop` lacks commits that exist on `master` (`git log develop..master`), propose
`git switch develop && git merge --no-ff master`. **[confirm]** (`master` is never rebased.)
