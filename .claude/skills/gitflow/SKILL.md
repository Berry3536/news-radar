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
3. `git merge --no-ff <type>/<slug>` (default message). On conflict: stop and report.
4. Verify on `develop`.
5. `git branch -d <type>/<slug>`. Pushing `develop` is a separate request. **[confirm]**

## hotfix (fix for a released version)

**start**: version = last tag + patch (`git describe --tags --abbrev=0 master`). Confirm it.
`git switch master && git pull --ff-only origin master && git switch -c hotfix/X.Y.Z`.
Set the version in `kit.json` `release.version_file` on the branch and commit
`chore: bump version to X.Y.Z`.

**finish**: same as `release` skill steps 5–9 with `hotfix/X.Y.Z` instead of `release/X.Y.Z`.

## sync

If `develop` lacks commits that exist on `master` (`git log develop..master`), propose
`git switch develop && git merge --no-ff master`. **[confirm]**
