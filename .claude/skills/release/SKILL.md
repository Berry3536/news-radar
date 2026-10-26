---
name: release
description: Cut a gitflow release (release/X.Y.Z from develop → master + tag vX.Y.Z → back into develop → draft GitHub Release). User-invoked only.
disable-model-invocation: true
---

Release version: `$ARGUMENTS` (e.g. `1.3.0`). If missing, propose one from the changes since
the last tag (semver) and ask.

Read `.claude/kit.json` first:
- `commands.verify`, `commands.smoke` — "verify" below means run all of them.
- `release.version_file` — where the version lives (e.g. `pyproject.toml`).
- `release.notes_file` — optional repo file for notes, `{version}` is substituted.
- `release.preflight` — optional checks run on `develop` before branching; read-only
  (e.g. "list open Crit/High items in docs/BACKLOG.md").
- `release.branch_edits` — optional doc edits made on the release branch and included in
  the release commit (e.g. "update the Status block in docs/BACKLOG.md").

Stop and ask before every step marked **[confirm]**. Stop on any failure.

1. On `develop`, clean tree, `git pull --ff-only origin develop`. Run the `release.preflight`
   checks (read-only) and report them. **[confirm]**
2. `git switch -c release/X.Y.Z`. Verify.
3. Draft release notes from `git log --no-merges <last tag>..HEAD` (and the tracker's done
   items, if the project has one) **in the stark-kit format**: copy `templates/release-notes.md`
   from the kit (same layout as every existing GitHub Release of the repo) and fill it —
   Korean; title `## <제품> vX.Y.Z (YYYY-MM-DD)`; a one- or two-sentence 합니다체 summary;
   sections `변경 사항` (≤ 10 개조식 bullets, bold lead + colon, user-visible only, tracker
   IDs in parentheses), `미지원 / 주의`, `설치` (the repo's fixed install wording), then the
   `전체 변경 내역:` compare link. Write to the scratchpad (and `release.notes_file` if set)
   and show the user. **[confirm]**
4. Set the version in `release.version_file` and apply `release.branch_edits`. Commit
   `chore: release vX.Y.Z` on the release branch with the version, notes file, and those
   edits. Only version, notes, release doc edits, and last-minute fixes go here.
5. `git switch master && git pull --ff-only origin master && git merge --no-ff release/X.Y.Z`. Verify. **[confirm]**
6. `git tag -a vX.Y.Z -m "Release vX.Y.Z"`. **[confirm]**
7. `git switch develop && git merge --no-ff release/X.Y.Z`. Verify. Then `git branch -d release/X.Y.Z`.
8. `git push origin master develop vX.Y.Z`. **[confirm]** — this triggers the release
   workflow, which creates a **draft** GitHub Release.
9. `gh run watch` the release run (if the repo has one; otherwise `gh release create vX.Y.Z --draft`).
   Replace the generated body with the notes from step 3: `gh release edit vX.Y.Z --notes-file <notes>`
   (the release title stays the tag). Ask whether to mark it pre-release. **[confirm]**
10. Tell the user to review and publish the draft. Never publish it yourself.

Rollback before push: delete the local tag and reset local `master`/`develop` only with the
user's approval. After push: never delete a pushed tag; fix forward with `hotfix/X.Y.Z+1`.
