#!/usr/bin/env python3
"""Gitflow guard shared by Claude Code hooks and git hooks (stark-kit managed).

Modes:
  claude            PreToolUse hook. Reads the hook JSON on stdin; exit 2 blocks the call.
  pre-commit        No direct commits on master/develop; branch names must follow gitflow.
  pre-merge-commit  master accepts release/* and hotfix/* only; develop accepts feature/bugfix/release/hotfix/master.
  commit-msg FILE   Conventional commit types, or git's default merge message.
  pre-push          Tags must point at commits contained in master; never delete master/develop.

The Claude mode parses commands on a best-effort basis; the git hooks are the backstop.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys

PERMANENT = ("master", "develop")
BRANCH_RE = re.compile(r"^(master|develop|(feature|bugfix)/[A-Za-z0-9][A-Za-z0-9._-]*|(release|hotfix)/\d+\.\d+\.\d+)$")
COMMIT_TYPES = "feat fix docs refactor test chore perf build ci style revert"
COMMIT_RE = re.compile(
    rf"^({COMMIT_TYPES.replace(' ', '|')})(\([^)]+\))?!?: \S"
    r"|^Merge (branch|tag|remote-tracking branch) "
    r"|^(fixup|squash|amend)! "
)
TAG_RE = re.compile(r"^v\d+\.\d+\.\d+$")
MERGE_SOURCES = {
    "master": ("release/", "hotfix/"),
    "develop": ("feature/", "bugfix/", "release/", "hotfix/", "master", "dependabot/"),  # master: resync
}


class Blocked(Exception):
    pass


def git(*args: str) -> str:
    result = subprocess.run(["git", *args], capture_output=True, text=True, encoding="utf-8")
    return result.stdout.strip() if result.returncode == 0 else ""


def current_branch() -> str:
    return git("branch", "--show-current")


def merging() -> bool:
    return bool(git("rev-parse", "-q", "--verify", "MERGE_HEAD"))


def check_branch_name(name: str) -> None:
    if not BRANCH_RE.match(name):
        raise Blocked(
            f"branch name '{name}' is not gitflow. Use feature/<slug>, bugfix/<slug>, release/X.Y.Z or hotfix/X.Y.Z."
        )


def merge_head_sources() -> list[str]:
    names = []
    for scope in ([], ["-r"]):
        names += git("branch", *scope, "--points-at", "MERGE_HEAD", "--format=%(refname:short)").splitlines()
    return names


def check_commit_on(branch: str) -> None:
    if branch in PERMANENT:
        if not merging():
            raise Blocked(f"direct commits on '{branch}' are not allowed. Start a feature/, bugfix/ or hotfix/ branch.")
        check_merge(branch, merge_head_sources())  # concluding a conflicted merge
    if branch:
        check_branch_name(branch)


def check_merge(target: str, sources: list[str]) -> None:
    allowed = MERGE_SOURCES.get(target)
    if not allowed:
        return
    names = [s.removeprefix("origin/") for s in sources]
    if not names or not any(n.startswith(allowed) for n in names):
        raise Blocked(
            f"'{target}' accepts merges only from {', '.join(p + '*' for p in allowed)} (got {names or 'unknown'})."
        )


def check_tag(name: str, commit: str) -> None:
    if not TAG_RE.match(name):
        raise Blocked(f"tag '{name}' must look like vX.Y.Z.")
    master = git("rev-parse", "-q", "--verify", "refs/heads/master") or git(
        "rev-parse", "-q", "--verify", "origin/master"
    )
    if not master or subprocess.run(["git", "merge-base", "--is-ancestor", commit, master]).returncode != 0:
        raise Blocked(f"tag '{name}' must point at a commit contained in master. Finish the release/hotfix first.")


# --- Claude PreToolUse -----------------------------------------------------------------

SEGMENT_SPLIT = re.compile(r"&&|\|\||;|\|")


def git_invocations(command: str) -> list[list[str]]:
    """Return argv lists (without the leading 'git' and its global options) for each git call."""
    calls = []
    for segment in SEGMENT_SPLIT.split(command):
        try:
            argv = shlex.split(segment, posix=True)
        except ValueError:
            argv = segment.split()
        while argv and ("=" in argv[0] and not argv[0].startswith("-")):  # VAR=value prefixes
            argv = argv[1:]
        if not argv or argv[0] not in ("git", "git.exe"):
            continue
        argv = argv[1:]
        while argv and argv[0].startswith("-"):  # git -C dir / -c k=v
            argv = argv[2:] if argv[0] in ("-C", "-c") else argv[1:]
        if argv:
            calls.append(argv)
    return calls


VALUE_OPTIONS = {"-m", "-F", "-u", "-s", "-X", "--message", "--file", "--local-user", "--strategy", "--strategy-option"}


def positional(args: list[str]) -> list[str]:
    """Non-option arguments, skipping the values of options that take one (e.g. -m <msg>)."""
    out, skip = [], False
    for arg in args:
        if skip:
            skip = False
        elif arg in VALUE_OPTIONS:
            skip = True
        elif not arg.startswith("-"):
            out.append(arg)
    return out


CREATE_FLAGS = ("-b", "-B", "-c", "-C", "--create", "--orphan")


def check_git_call(argv: list[str], branch: str) -> str:
    """Check one git call made while on `branch`; return the branch checked out afterwards."""
    sub, args = argv[0], argv[1:]
    if sub == "commit":
        check_commit_on(branch)
    elif sub == "merge" and "--abort" not in args and "--continue" not in args:
        if "--ff-only" in args or "--squash" in args:
            raise Blocked("gitflow merges into master/develop use --no-ff (no --ff-only/--squash).")
        check_merge(branch, positional(args))
    elif sub in ("checkout", "switch"):
        for flag in CREATE_FLAGS:
            if flag in args and args.index(flag) + 1 < len(args):
                new = args[args.index(flag) + 1]
                check_branch_name(new)
                return new
        if "--" not in args:
            names = positional(args)
            if names and (names[0] in PERMANENT or git("rev-parse", "-q", "--verify", f"refs/heads/{names[0]}")):
                return names[0]
    elif sub == "branch":
        names = positional(args)
        listing = any(a in args for a in ("-d", "-D", "--delete", "-a", "-r", "--list", "-v", "-vv", "--show-current"))
        if names and not listing:
            check_branch_name(names[0])
    elif sub == "push":
        if any(a in ("-f", "--force", "--force-with-lease", "--mirror") or a.startswith("--force") for a in args):
            raise Blocked("force push is not allowed.")
        for ref in positional(args)[1:]:
            if ref.startswith("+"):
                raise Blocked("force push is not allowed.")
            if ref in (":master", ":develop"):
                raise Blocked("deleting master/develop is not allowed.")
        if "--delete" in args and any(n in PERMANENT for n in positional(args)):
            raise Blocked("deleting master/develop is not allowed.")
    elif sub == "tag":
        names = positional(args)
        if names and not any(a in args for a in ("-d", "--delete", "-l", "--list", "-v", "--verify")):
            check_tag(names[0], names[1] if len(names) > 1 else branch or "HEAD")
    elif sub == "rebase" and branch in PERMANENT:
        raise Blocked(f"rebasing '{branch}' is not allowed.")
    return branch


def run_claude() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    command = (payload.get("tool_input") or {}).get("command") or ""
    try:
        branch = current_branch()
        for argv in git_invocations(command):  # follow switches inside compound commands
            branch = check_git_call(argv, branch)
    except Blocked as exc:
        print(f"gitflow-guard: {exc}", file=sys.stderr)
        return 2
    return 0


# --- git hooks -------------------------------------------------------------------------


def run_pre_merge_commit() -> None:
    # MERGE_HEAD does not exist yet here; git exports GITHEAD_<sha>=<name> for each merged head.
    sources = [v for k, v in os.environ.items() if k.startswith("GITHEAD_")]
    check_merge(current_branch(), sources)


def run_commit_msg(path: str) -> None:
    with open(path, encoding="utf-8") as f:
        first = next((line.strip() for line in f if line.strip() and not line.startswith("#")), "")
    if not COMMIT_RE.match(first):
        raise Blocked(f"commit message '{first}' must be '<type>(scope)?: summary' with type in {COMMIT_TYPES}.")


def run_pre_push() -> None:
    for line in sys.stdin:
        parts = line.split()
        if len(parts) != 4:
            continue
        local_ref, local_sha, remote_ref, _ = parts
        if set(local_sha) == {"0"}:
            if remote_ref.removeprefix("refs/heads/") in PERMANENT:
                raise Blocked("deleting master/develop is not allowed.")
            continue
        if remote_ref.startswith("refs/tags/"):
            check_tag(remote_ref.removeprefix("refs/tags/"), local_sha + "^{commit}")


def main(argv: list[str]) -> int:
    mode = argv[1] if len(argv) > 1 else ""
    if mode == "claude":
        return run_claude()
    try:
        if mode == "pre-commit":
            check_commit_on(current_branch())
        elif mode == "pre-merge-commit":
            run_pre_merge_commit()
        elif mode == "commit-msg":
            run_commit_msg(argv[2])
        elif mode == "pre-push":
            run_pre_push()
        else:
            print(f"gitflow-guard: unknown mode '{mode}'", file=sys.stderr)
            return 1
    except Blocked as exc:
        print(f"gitflow-guard: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
