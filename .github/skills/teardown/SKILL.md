---
name: teardown
description: Full session-hygiene sweep across local dev servers/stray processes, git branches/stashes/worktrees (this repo and sibling repos), and /tmp + /private/tmp scratch files. Use when the user says "teardown", "clean house", "clean up after yourself", or asks to find/remove orphaned processes, branches, stashes, worktrees, or temp files left over from past sessions.
---

# Teardown — session hygiene sweep

This machine is shared across sessions (and possibly other concurrent users/agents). Past
sessions routinely leave behind: detached dev servers, stuck benchmark/build processes,
merged-but-undeleted git branches, abandoned worktrees, and scratch files in `/tmp`. This
skill finds and removes them — **safely**, without disturbing anything a concurrent session
is actively using.

The golden rule throughout: **report first, confirm before destructive action**, except for
artifacts unambiguously created by *this* session (e.g. a file you `rm -f`'d but left a
build byproduct behind) — those can be cleaned immediately without asking.

## 1. Orphaned processes (dev servers, stuck builds)

Find anything listening on a port (the actual "dev servers"):

```bash
lsof -iTCP -sTCP:LISTEN -n -P
```

For each hit, inspect the process tree to see what started it and how long it's been running:

```bash
ps -o pid,ppid,etime,command -p <pid>
```

Separately, scan for long-running CPU-heavy processes that aren't servers but look like
stuck/runaway builds or benchmarks (multi-day `etime`, high `%CPU`, owned by you):

```bash
ps aux | grep -iE "node|vite|wasmtime|cargo|rustc|clang|zig|python3? -m http"
```

A process is a credible teardown target when **both** hold:
- it (or its parent shell) has `PPID 1` (reparented — its original session is long gone), or
  an `etime` of many hours/days with no plausible reason to still be running
- nothing you can find currently depends on it (no other session's terminal, no lockfile
  with a fresh mtime, no README/task describing ongoing work)

Kill by exact PID (never by name):

```bash
kill <pid> <parent_pid_if_any>
```

Confirm with the user only if you're unsure a process is actually dead weight; killing
obvious orphaned `http.server`/`vite`/benchmark loops you can show have no active
dependents is fine to do directly and report afterward.

## 2. Git branches, stashes, worktrees — across ALL local repos, not just the current one

Past sessions touch sibling repos too. Discover them:

```bash
find ~ -maxdepth 3 -iname ".git" -type d 2>/dev/null
```

For each repo:

```bash
git worktree list
git stash list
git --no-pager branch -vv
git fetch --prune origin
```

### The squash-merge trap

**Never rely on `git branch --merged` alone.** If the repo squash-merges PRs (common on
GitHub), a landed branch's commits are never literal ancestors of the base branch — the
check silently says "not merged" for branches that very much are. This looks correct and
passes a casual glance while being wrong.

The reliable signal is GitHub's own PR state, not local ancestry:

```bash
gh pr list --repo <owner>/<repo> --state all --search "head:<branch>" \
  --json number,title,state,mergedAt,headRefName
```

A branch is safe to delete when its PR shows `"state": "MERGED"` (regardless of what
`git merge-base --is-ancestor` says). After confirming via `gh`, force-delete if the
plain `-d` refuses:

```bash
git branch -d <branch> 2>&1 || git branch -D <branch>   # -D only after gh confirms MERGED
```

A branch whose remote tracking ref shows `[origin/<branch>: gone]` (after
`git fetch --prune`) is a strong hint it was already deleted upstream (usually
auto-delete-on-merge) — but still verify via `gh pr list` before deleting locally;
`gone` alone doesn't prove it was merged (a closed-without-merging PR also deletes
the remote branch).

### Worktrees

Before removing a worktree, check it's actually clean — uncommitted work must never be
force-deleted:

```bash
git -C <worktree-path> status --short   # empty output = clean
git worktree remove <worktree-path>     # only if clean
```

If the branch is currently checked out (e.g. in the main worktree), `git checkout` another
branch (the repo's default branch) before deleting it.

### Stashes

List and inspect before dropping — a stash can hold real unfinished work from a different
session:

```bash
git stash list
git stash show -p stash@{0}   # inspect before dropping anything non-obvious
git stash drop                # only for entries you've verified are safe/empty/superseded
```

## 3. `/tmp` and `/private/tmp`

macOS symlinks `/tmp` → `/private/tmp`; check both names resolve to the same place before
assuming you've covered everything.

```bash
du -sh /private/tmp/*/ 2>/dev/null | sort -rh   # size up directories first
ls -la /private/tmp
```

**Before deleting anything**, rule out that it belongs to a concurrent session:

```bash
# Is any process using this path right now?
lsof +D /private/tmp/<candidate>
for pid in $(ps -ax -o pid=); do
  lsof -a -p "$pid" -d cwd -Fn 2>/dev/null | grep -q "/private/tmp/<candidate>" && echo "PID $pid is using it"
done

# Does it look like an active, unrelated git clone (not something this session created)?
cd /private/tmp/<candidate> && git remote -v && git log -1 --format="%H %ad %s" --date=iso && git status --short
```

Treat an item as **likely another concurrent session's workspace** (leave it alone) when
its mtime is within the last few minutes of your check, no process currently references it,
and its content/branch is unrelated to anything you did. Everything else datestamped
noticeably older than "now" (yesterday or earlier) that no process has open is fair game.

```bash
find /private/tmp -maxdepth 1 -user "$USER" ! -newermt "<today 00:00>" \
  ! -name <active-candidate-1> ! -name <active-candidate-2> -mindepth 1 -print0 \
  | xargs -0 rm -rf
```

Also check your own session's scratch output (anything you built with `-g`/debug flags
leaves byproducts like `.dSYM` bundles beyond the binary you explicitly `rm`'d) — clean
those without asking, since you created them.

## 4. Reporting

Summarize what was found and what was done/proposed, grouped by category (processes /
branches+worktrees+stashes / tmp files), and use `ask_user` to confirm before any bulk
destructive action on cross-repo or ambiguous items. Don't ask for confirmation on cleanup
of artifacts this same session created.
