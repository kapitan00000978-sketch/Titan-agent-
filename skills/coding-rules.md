---
name: coding-rules
description: Engineering discipline — plan, test first, verify before claiming done.
keywords: code, coding, test, refactor, bug fix, software, engineer, python, javascript
---

# Coding Rules

Follow this playbook for any software engineering or code task.

## Plan first
1. Read the relevant files with `read_file` / `workspace_rag` BEFORE editing.
   Understand the existing structure, naming, and conventions.
2. STATE the approach in <thought> before touching code.

## Test first
3. Prefer writing or updating a test that expresses the expected behavior,
   then implement until it passes.
4. After changes, RUN the tests or a syntax check (`python -m py_compile`,
   `node --check`, etc.). Only then report done.

## Style discipline
5. Match the surrounding code: same indentation, naming, and structure.
6. Make the smallest change that solves the problem — no speculative refactors.

## Failure handling
7. If a command fails, read the error, adjust, retry. Do not paper over errors.
8. If a change has a known limitation, state it in the final answer.

## Security
9. Sanitize inputs; keep secrets out of code and logs.