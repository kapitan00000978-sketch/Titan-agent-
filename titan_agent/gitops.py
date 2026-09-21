"""
Phase 4 — Git-first workflow and auto-commit (Aider-style).

Safe Git operations for the live agent:

- repo detection via ``.git`` (walking up the tree)
- read-only status / diff inspection tools
- explicit commit (stage-all + commit) with local-author fallback so it works
  even in fresh repos without a global git identity
- ``auto_commit()`` helper for end-of-run Aider-style commits

All functions here are synchronous on purpose; async callers should run them
through ``asyncio.to_thread`` so the event loop never blocks.
"""
from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path

log = logging.getLogger(__name__)

GIT_AUTHOR_NAME = os.getenv("TITAN_GIT_NAME", "Titan Agent")
GIT_AUTHOR_EMAIL = os.getenv("TITAN_GIT_EMAIL", "titan@localhost")


def find_repo_root(start: Path | str) -> Path | None:
    """Walk up from ``start`` looking for a ``.git`` marker; None if absent."""
    current = Path(start).resolve()
    for _ in range(64):
        if (current / ".git").exists():
            return current
        if current.parent == current:
            return None
        current = current.parent
    return None


def _run(cwd: Path, *args: str, timeout: float = 20.0) -> tuple[int, str]:
    """Run git safely; never raises. Returns (returncode, combined output)."""
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return proc.returncode, ((proc.stdout or "") + (proc.stderr or "")).strip()
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 1, f"Error: git unavailable: {exc!s}"


def _require_repo(start: Path | str) -> tuple[Path | None, str]:
    root = find_repo_root(start)
    if root is None:
        return None, "Error: not a git repository (no .git found)."
    return root, ""


def git_status(start: Path | str) -> str:
    """One-line working-tree state (modified/untracked files)."""
    root, err = _require_repo(start)
    if root is None:
        return err
    code, out = _run(root, "status", "--short")
    if code != 0:
        return f"Error: {out}"
    return out or "(working tree clean)"


def git_diff(start: Path | str, stat_only: bool = True) -> str:
    """Show uncommitted changes (``--stat`` by default, full diff otherwise)."""
    root, err = _require_repo(start)
    if root is None:
        return err
    args = ["diff", "--stat"] if stat_only else ["diff"]
    code, out = _run(root, *args)
    if code != 0:
        return f"Error: {out}"
    if not out:
        untracked = git_status(root)
        if untracked != "(working tree clean)":
            return f"(no tracked modifications) — untracked files:\n{untracked}"
        return "(no uncommitted changes)"
    return out


def _ensure_local_author(root: Path) -> None:
    """Set local (repo-only) git identity if missing — never touches global config."""
    for key, value in (("user.email", GIT_AUTHOR_EMAIL), ("user.name", GIT_AUTHOR_NAME)):
        code, _ = _run(root, "config", key)
        if code != 0:
            _run(root, "config", key, value)


def git_commit(start: Path | str, message: str, add_all: bool = True) -> str:
    """Stage everything and commit with ``message`` (local author fallback)."""
    root, err = _require_repo(start)
    if root is None:
        return err
    _ensure_local_author(root)
    if add_all:
        _run(root, "add", "-A")
    code, _ = _run(root, "diff", "--cached", "--quiet")
    if code == 0:
        return "(nothing to commit — working tree clean)"
    code, out = _run(root, "commit", "-m", message)
    if code != 0:
        return f"Error committing: {out}"
    return f"Committed: {message}"


def auto_commit(start: Path | str, task: str, max_subject: int = 72) -> str:
    """Aider-style: commit all changes with a subject derived from the task."""
    subject = " ".join(str(task).split())[:max_subject] or "agent run"
    return git_commit(start, f"agent: {subject}")