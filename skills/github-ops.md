---
name: github-ops
description: GitHub & git discipline — commit hygiene, CI, code review loops.
keywords: github, git, commit, pull request, pr, branch, ci, repository, review
---

# GitHub Ops

Follow this playbook for any git/GitHub/repo task.

## Rules
1. CHECK STATE FIRST: run `git status`, `git branch`, `git log --oneline -10`
   before any change. Never overwrite unknown work.
2. SMALL COMMITS: one logical change per commit. Write a subject line that
   describes the WHY, not the what (`fix(api): validate input before insert`
   beats `update file`).
3. BRANCH BEFORE FEATURES: create a feature branch before non-trivial work;
   never commit directly to main unless the repo has no history.
4. PULL BEFORE PUSH: `git pull --rebase` before pushing to avoid races.
5. CI MENTALITY: before claiming done, verify the change actually runs —
   execute tests or at minimum a syntax check. Do not report "done" on
   unverified work.
6. SECURITY: never commit secrets, tokens, or keys. If you spot one already
   committed, flag it loudly.

## Code review loop
- Read the diff, not just the summary.
- Check: error handling, edge cases, naming, tests, and whether the change
  matches the stated intent.
- Report findings by severity (Critical / Important / Minor / Nit).