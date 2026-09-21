---
name: terminal-ops
description: Safe command-execution discipline — understand before running, never destroy data.
keywords: terminal, command, shell, powershell, cmd, execute, process, system, install
---

# Terminal Ops

Follow this playbook for any task that involves running commands.

## Rules
1. UNDERSTAND FIRST: state what the command does and why before running it.
2. READ-ONLY FIRST: list, inspect, and dry-run before any mutating action.
3. NEVER destroy data: no `rm -rf`, no `del /s /q` on unknown paths. If a
   destructive operation is genuinely required, say so in the final answer.
4. CHECK OUTPUT: read stderr and the exit code after every command. Never
   assume success — verify.
5. ENV SAFETY: don't clobber environment variables or PATH. Use scoped
   variables where possible.
6. TIME SAVER: prefer `dir`/`Get-ChildItem` and targeted searches over
   recursive scans of huge trees.
7. WINDOWS AWARE: remember this machine runs Windows — use PowerShell/cmd
   syntax, .cmd resolution for npx/npm, and backslash paths.