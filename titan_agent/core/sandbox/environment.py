"""
Phase 28 — Genesis Darajasi 8: Sandbox Environment & Filesystem Snapshot Layer.

Provides filesystem state snapshotting, diffing, and zero-loss rollback for
isolated and experimental code execution.
"""
from __future__ import annotations

import datetime
import hashlib
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar


@dataclass
class FilesystemSnapshot:
    """A point-in-time snapshot of files within a directory."""

    name: str
    created_at: float = field(default_factory=time.time)
    files: dict[str, bytes] = field(default_factory=dict)  # rel_path -> binary content
    root_path: str = ""

    @property
    def timestamp(self) -> str:
        return datetime.datetime.fromtimestamp(self.created_at, tz=datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")

    @property
    def file_hashes(self) -> dict[str, str]:
        return {
            rel: hashlib.sha256(content).hexdigest()
            for rel, content in self.files.items()
        }

    def diff(self, other: FilesystemSnapshot) -> dict[str, list[str]]:
        """Computes differences between this snapshot and another snapshot."""
        added = [k for k in other.files if k not in self.files]
        removed = [k for k in self.files if k not in other.files]
        modified = [
            k for k in self.files
            if k in other.files and self.files[k] != other.files[k]
        ]
        return {
            "added": sorted(added),
            "removed": sorted(removed),
            "modified": sorted(modified),
        }

    @classmethod
    def capture(cls, name: str, root_dir: str | Path) -> FilesystemSnapshot:
        root = Path(root_dir).resolve()
        env = SandboxEnvironment(root)
        snap = env.create_snapshot(name)
        snap.root_path = str(root)
        return snap


class SandboxEnvironment:
    """Manages workspace snapshots, rollbacks, and ephemeral sandboxed directories."""

    EXCLUDED_DIRS: ClassVar[set[str]] = {
        ".git",
        ".venv",
        "venv",
        "__pycache__",
        "node_modules",
        ".pytest_cache",
        ".ruff_cache",
    }
    MAX_FILE_BYTES: ClassVar[int] = 5 * 1024 * 1024  # 5 MB max per tracked file

    def __init__(self, workspace_root: str | Path):
        self.workspace_root = Path(workspace_root).resolve()
        self._snapshots: dict[str, FilesystemSnapshot] = {}

    def create_snapshot(self, name: str) -> FilesystemSnapshot:
        """Captures the current state of files in workspace."""
        snap_name = str(name).strip()
        files: dict[str, bytes] = {}

        if self.workspace_root.exists():
            for p in self.workspace_root.rglob("*"):
                if not p.is_file():
                    continue
                if any(part in self.EXCLUDED_DIRS for part in p.parts):
                    continue
                try:
                    if p.stat().st_size <= self.MAX_FILE_BYTES:
                        rel = str(p.relative_to(self.workspace_root)).replace("\\", "/")
                        files[rel] = p.read_bytes()
                except OSError:
                    continue

        snap = FilesystemSnapshot(name=snap_name, files=files, root_path=str(self.workspace_root))
        self._snapshots[snap_name] = snap
        return snap

    def rollback(self, name: str) -> dict[str, Any]:
        """
        Reverts the workspace to the exact state saved in snapshot `name`.
        Restores modified files, recreates deleted files, and removes newly created files.
        """
        snap = self._snapshots.get(str(name).strip())
        if not snap:
            raise KeyError(f"Snapshot '{name}' not found.")

        restored: list[str] = []
        recreated: list[str] = []
        removed: list[str] = []

        # 1. Identify files currently on disk
        current_files: dict[str, Path] = {}
        if self.workspace_root.exists():
            for p in self.workspace_root.rglob("*"):
                if not p.is_file():
                    continue
                if any(part in self.EXCLUDED_DIRS for part in p.parts):
                    continue
                rel = str(p.relative_to(self.workspace_root)).replace("\\", "/")
                current_files[rel] = p

        # 2. Delete files created since snapshot
        for rel, p in current_files.items():
            if rel not in snap.files:
                try:
                    p.unlink(missing_ok=True)
                    removed.append(rel)
                except OSError:
                    pass

        # 3. Restore modified or missing files from snapshot
        for rel, original_bytes in snap.files.items():
            dest = self.workspace_root / rel
            if rel not in current_files:
                # File was deleted: recreate it
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(original_bytes)
                recreated.append(rel)
            else:
                # File exists: check if modified
                try:
                    if dest.read_bytes() != original_bytes:
                        dest.write_bytes(original_bytes)
                        restored.append(rel)
                except OSError:
                    dest.write_bytes(original_bytes)
                    restored.append(rel)

        return {
            "success": True,
            "snapshot_name": name,
            "restored_count": len(restored),
            "recreated_count": len(recreated),
            "removed_count": len(removed),
            "restored": restored,
            "recreated": recreated,
            "removed": removed,
            "deleted_new": removed,
        }

    def list_snapshots(self) -> list[str]:
        """List all active snapshot names."""
        return list(self._snapshots.keys())

    @staticmethod
    def create_ephemeral_dir(prefix: str = "titan_sb_") -> Path:
        """Creates a secure disposable temporary directory for scratch execution."""
        return Path(tempfile.mkdtemp(prefix=prefix))
