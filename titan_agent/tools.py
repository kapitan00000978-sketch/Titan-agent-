import asyncio
import os
import platform
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

try:
    from ddgs import DDGS
except ImportError:
    from duckduckgo_search import DDGS
from . import config as _cfg
from .config import TASK_QUEUE_FILE, WORKSPACE_DIR
from .core.guardrails.policy import PolicyEngine


def _command_timeout(base: float) -> float:
    """Command/process timeout in seconds.

    Phase 8 FULL access removes the 45s command ceiling (and the 60s raw-run
    default): long builds, big installs and slow network jobs are allowed to
    run for up to 10 minutes before the watchdog intervenes.
    """
    return 600.0 if _cfg.full_access_enabled() else base


def _subagent_worker_cap() -> int:
    """Parallel subagent worker bound. Phase 8 FULL access raises 2 -> 8."""
    return 8 if _cfg.full_access_enabled() else 2


def _tokenize(text: str) -> list[str]:
    """Lowercase alphanumeric tokens for lightweight lexical ranking."""
    return re.findall(r"[a-z0-9][a-z0-9_\-']*", text.lower())


class WorkspaceRAG:
    """Zero-dependency retrieval over the workspace.

    A lightweight, lexical (BM25-style) index over text files: documents are
    split into overlapping chunks, scored against the query, and the top
    chunks are returned with file paths so the LLM can answer WITH citations.
    No external embeddings, no API keys — everything runs locally.
    """

    CHUNK_SIZE = 900
    CHUNK_OVERLAP = 140
    MAX_FILE_BYTES = 512 * 1024
    TEXT_SUFFIXES: frozenset[str] = frozenset({
        ".py", ".js", ".jsx", ".ts", ".tsx", ".html", ".css", ".md", ".txt",
        ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".csv", ".xml",
        ".sql", ".sh", ".ps1", ".bat", ".env", ".log",
    })

    def __init__(self, workspace: Path):
        self.workspace = Path(workspace)

    def _iter_documents(self):
        """Yield (relative_path, text) for every searchable file in the workspace."""
        if not self.workspace.exists():
            return
        for fpath in self.workspace.rglob("*"):
            if not fpath.is_file():
                continue
            if fpath.suffix.lower() not in self.TEXT_SUFFIXES:
                continue
            try:
                if fpath.stat().st_size > self.MAX_FILE_BYTES:
                    continue
                text = fpath.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            if not text.strip():
                continue
            yield fpath.relative_to(self.workspace).as_posix(), text

    @staticmethod
    def _chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
        if len(text) <= size:
            return [text]
        chunks = []
        start = 0
        while start < len(text):
            end = start + size
            chunk = text[start:end]
            chunks.append(chunk)
            if end >= len(text):
                break
            start = end - overlap
        return chunks

    @staticmethod
    def _bm25(chunk_tokens: list[str], query_tokens: list[str], avg_len: float, k1: float = 1.5, b: float = 0.75) -> float:
        if not chunk_tokens or not query_tokens or avg_len <= 0:
            return 0.0
        dl = len(chunk_tokens)
        freq: dict[str, int] = {}
        for t in chunk_tokens:
            freq[t] = freq.get(t, 0) + 1
        score = 0.0
        for qt in set(query_tokens):
            f = freq.get(qt, 0)
            if f == 0:
                continue
            tf_part = (f * (k1 + 1)) / (f + k1 * (1 - b + b * (dl / avg_len)))
            score += tf_part
        return score

    def search(self, query: str, top_k: int = 4) -> list[dict[str, Any]]:
        query_tokens = _tokenize(query)
        if not query_tokens:
            return []
        candidates: list[dict[str, Any]] = []
        for rel_path, text in self._iter_documents():
            chunks = self._chunk_text(text)
            chunk_lens = [len(_tokenize(c)) for c in chunks]
            avg_len = max(1.0, sum(chunk_lens) / len(chunk_lens)) if chunk_lens else 1.0
            for i, chunk in enumerate(chunks):
                ct = _tokenize(chunk)
                score = self._bm25(ct, query_tokens, avg_len)
                if score <= 0:
                    continue
                # Bonus for earlier chunks (files usually front-load meaning).
                score += max(0.0, 0.15 * (1 - i / max(len(chunks), 1)))
                candidates.append({
                    "path": rel_path,
                    "chunk_index": i,
                    "score": round(score, 4),
                    "snippet": chunk.strip()[:700],
                })
        candidates.sort(key=lambda c: c["score"], reverse=True)
        # Keep at most one chunk per file unless the file is clearly central.
        picked: list[dict[str, Any]] = []
        per_file: dict[str, int] = {}
        for c in candidates:
            per_file[c["path"]] = per_file.get(c["path"], 0) + 1
            if per_file[c["path"]] <= 2 and len(picked) < max(top_k, 1):
                picked.append(c)
        return picked[:top_k]


class ToolRegistry:
    def __init__(self, workspace: Path = WORKSPACE_DIR):
        self.workspace = workspace
        self.workspace.mkdir(parents=True, exist_ok=True)
        # Phase 14: optional Human-in-the-loop manager. The approval gate itself
        # lives in agent.execute_tool_unified (single point for every loop), so
        # here we only accept the wiring to keep construction uniform.
        self.hitl = None
        self.hitl_timeout = 120.0

    def attach_hitl(self, hitl, hitl_timeout: float | None = None) -> None:
        """Accept the global HITL manager (approvals enforced at the agent layer)."""
        self.hitl = hitl
        if hitl_timeout is not None:
            self.hitl_timeout = hitl_timeout

    def _resolve_path(self, rel_or_abs: str | Path) -> Path:
        p = Path(rel_or_abs)
        if not p.is_absolute():
            p = (self.workspace / p).resolve()
        return p

    def get_tool_definitions(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "execute_command",
                    "description": "Executes a PowerShell or shell command in the operating system and returns stdout and stderr.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "command": {
                                "type": "string",
                                "description": "The exact command line string to run (e.g. 'dir', 'git status', 'npm test')."
                            },
                            "cwd": {
                                "type": "string",
                                "description": "Optional working directory. Defaults to workspace root."
                            }
                        },
                        "required": ["command"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "read_file",
                    "description": "Reads the content of a file from the filesystem.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "Path to the file to read."
                            }
                        },
                        "required": ["path"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "write_file",
                    "description": "Creates a new file or overwrites an existing file with provided content.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "Path where the file should be saved."
                            },
                            "content": {
                                "type": "string",
                                "description": "The full text content to write."
                            }
                        },
                        "required": ["path", "content"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "edit_file",
                    "description": "Performs exact string replacement in a file.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "Path of the file to edit."
                            },
                            "target_text": {
                                "type": "string",
                                "description": "Exact existing text block to be replaced."
                            },
                            "replacement_text": {
                                "type": "string",
                                "description": "New text block to insert in place of target_text."
                            }
                        },
                        "required": ["path", "target_text", "replacement_text"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "list_directory",
                    "description": "Lists contents of a directory with file names and sizes.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "Directory path to list. Defaults to current workspace."
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "web_search",
                    "description": "Searches the live internet using DuckDuckGo to get up-to-date web results, news, or facts.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "The search query."
                            },
                            "max_results": {
                                "type": "integer",
                                "description": "Maximum number of search results (default 5)."
                            }
                        },
                        "required": ["query"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "scrape_webpage",
                    "description": "Fetches raw text content from a web URL for reading articles or documentation.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "url": {
                                "type": "string",
                                "description": "Web URL to scrape."
                            }
                        },
                        "required": ["url"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "python_eval",
                    "description": "Executes Python code in a standalone process and returns stdout/stderr.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "code": {
                                "type": "string",
                                "description": "Python code to execute."
                            }
                        },
                        "required": ["code"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "workspace_rag",
                    "description": "Searches all text/code files inside the workspace using a fast local lexical (BM25) retrieval index and returns the most relevant snippets WITH their file paths. Use this instead of read_file when you need to answer a question from documents, notes, or code that may live anywhere in the workspace — it finds the exact relevant lines fast.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "The question or keywords to find inside workspace files."
                            },
                            "top_k": {
                                "type": "integer",
                                "description": "How many snippets to return (default 4, range 1-8)."
                            }
                        },
                        "required": ["query"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "deep_search",
                    "description": "Performs an in-depth multi-hop web research on a topic by querying multiple angles, scraping top websites, and synthesizing findings.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "topic": {
                                "type": "string",
                                "description": "The complex subject or question to research deeply."
                            }
                        },
                        "required": ["topic"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "deep_coder",
                    "description": "Autonomous deep software engineering cycle: writes multi-file code, verifies syntax, generates test harness, and executes tests.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "task_name": {
                                "type": "string",
                                "description": "Short identifier for the module or feature."
                            },
                            "files": {
                                "type": "object",
                                "description": "Dictionary of filename to file code content."
                            },
                            "test_code": {
                                "type": "string",
                                "description": "Python test script code that asserts correctness."
                            }
                        },
                        "required": ["task_name", "files"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "launch_application",
                    "description": "Launches a Windows desktop application or utility.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "app_or_command": {
                                "type": "string",
                                "description": "Application name or path (e.g. 'notepad', 'calc', 'explorer .', 'chrome')"
                            }
                        },
                        "required": ["app_or_command"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "system_info",
                    "description": "Returns live information about the host system: OS version, CPU, RAM (total/free), disk space, Python version — useful for environment-aware decisions.",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "manage_processes",
                    "description": "Lists or kills running OS processes. action='list' to see running processes (optionally filtered by pattern), action='kill' to terminate a process by PID or image name.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "action": {
                                "type": "string",
                                "enum": ["list", "kill"],
                                "description": "'list' to show processes, 'kill' to terminate."
                            },
                            "pattern": {
                                "type": "string",
                                "description": "For 'list': substring to filter process names. For 'kill': PID number or image name (e.g. 'notepad.exe')."
                            }
                        },
                        "required": ["action"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "clipboard_get",
                    "description": "Reads text from the system clipboard.",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "clipboard_set",
                    "description": "Writes text to the system clipboard.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "text": {
                                "type": "string",
                                "description": "Text to put on the clipboard."
                            }
                        },
                        "required": ["text"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "screenshot",
                    "description": "Takes a screenshot of the entire screen or a specific monitor and returns it as base64 PNG.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "monitor": {
                                "type": "integer",
                                "description": "Monitor index (0 = primary, 1 = secondary, etc.). Default 0.",
                                "default": 0
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "key_press",
                    "description": "Simulates keyboard key presses (e.g. 'ctrl+c', 'enter', 'alt+tab', 'win+r').",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "keys": {
                                "type": "string",
                                "description": "Key combination to press (e.g. 'ctrl+c', 'enter', 'alt+tab', 'win+r', 'f5')."
                            }
                        },
                        "required": ["keys"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "mouse_click",
                    "description": "Simulates a mouse click at the specified coordinates.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "x": {
                                "type": "integer",
                                "description": "X coordinate."
                            },
                            "y": {
                                "type": "integer",
                                "description": "Y coordinate."
                            },
                            "button": {
                                "type": "string",
                                "enum": ["left", "right", "middle"],
                                "description": "Mouse button to click. Default 'left'.",
                                "default": "left"
                            },
                            "double": {
                                "type": "boolean",
                                "description": "Whether to double-click. Default false.",
                                "default": False
                            }
                        },
                        "required": ["x", "y"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "mouse_move",
                    "description": "Moves the mouse cursor to the specified coordinates.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "x": {
                                "type": "integer",
                                "description": "X coordinate."
                            },
                            "y": {
                                "type": "integer",
                                "description": "Y coordinate."
                            },
                            "duration": {
                                "type": "number",
                                "description": "Duration in seconds for smooth movement. Default 0 (instant).",
                                "default": 0
                            }
                        },
                        "required": ["x", "y"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "list_windows",
                    "description": "Lists all visible windows with their titles, handles, and process names.",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "window_control",
                    "description": "Controls a window: minimize, maximize, restore, close, or bring to front.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "action": {
                                "type": "string",
                                "enum": ["minimize", "maximize", "restore", "close", "foreground"],
                                "description": "Action to perform on the window."
                            },
                            "title": {
                                "type": "string",
                                "description": "Window title (partial match) or handle (HWND as string)."
                            }
                        },
                        "required": ["action", "title"]
                    }
                }
            },
            # ================= Phase 7: Full Autonomy tools =================
            {
                "type": "function",
                "function": {
                    "name": "self_heal",
                    "description": "SELF-HEALING: runs a command and, if it fails, automatically diagnoses the error and applies deterministic repairs (installs a missing Python module via pip, retries transient failures) then re-runs the command until success or attempts are exhausted. Use this instead of execute_command when a dependency or flaky failure is suspected.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "command": {
                                "type": "string",
                                "description": "The exact command line string to run."
                            },
                            "cwd": {
                                "type": "string",
                                "description": "Optional working directory. Defaults to workspace root."
                            },
                            "max_attempts": {
                                "type": "integer",
                                "description": "Max run attempts including repairs (default 3)."
                            }
                        },
                        "required": ["command"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "download_file",
                    "description": "Downloads a file from a public http(s) URL into the workspace (SSRF-guarded: private/loopback targets are refused). Returns the saved path and size.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "url": {
                                "type": "string",
                                "description": "The public http(s) URL to download."
                            },
                            "dest": {
                                "type": "string",
                                "description": "Optional destination path inside the workspace (default: filename from the URL)."
                            }
                        },
                        "required": ["url"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "start_http_server",
                    "description": "Serves a directory (default workspace) over HTTP on localhost so the agent or user can browse generated files. Returns the URL. The server runs until the agent stops it with stop_http_server.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "port": {
                                "type": "integer",
                                "description": "Port to bind (default 8000)."
                            },
                            "directory": {
                                "type": "string",
                                "description": "Directory to serve (default workspace)."
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "stop_http_server",
                    "description": "Stops a previously started local HTTP server.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "port": {
                                "type": "integer",
                                "description": "Port of the server to stop (default 8000)."
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "take_screenshot",
                    "description": "Captures the primary screen to a PNG in the workspace (Windows; PowerShell-based, no extra deps). Use to visually inspect the current UI state.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "dest": {
                                "type": "string",
                                "description": "Optional PNG filename in the workspace (default screenshot_<ts>.png)."
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "self_update",
                    "description": "Pulls the latest code from git, installs requirements and runs the test suite for the project containing the workspace. Returns the update log. Use to keep Titan's own runtime current.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "run_tests": {
                                "type": "boolean",
                                "description": "Whether to run the test suite after updating (default true)."
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "task_enqueue",
                    "description": "AUTONOMOUS TASK QUEUE: adds a task that the daemon or another agent processes independently (with priorities, scheduling and retries). Returns the task id.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "task": {
                                "type": "string",
                                "description": "The task instruction/prompt to execute."
                            },
                            "name": {
                                "type": "string",
                                "description": "Optional short label for the task."
                            },
                            "priority": {
                                "type": "integer",
                                "description": "Priority: higher runs first (default 0)."
                            },
                            "schedule_at": {
                                "type": "number",
                                "description": "Optional epoch-seconds to run it at (default: now)."
                            }
                        },
                        "required": ["task"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "task_list",
                    "description": "Lists tasks in the autonomous task queue (optionally filtered by status: pending/running/done/failed/cancelled).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "status": {
                                "type": "string",
                                "description": "Optional status filter."
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Max tasks to return (default 20)."
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "task_stats",
                    "description": "Returns the autonomous task queue status counts (pending/running/done/failed/cancelled).",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "task_cancel",
                    "description": "Cancels a pending task in the autonomous queue.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "task_id": {
                                "type": "integer",
                                "description": "The task id to cancel."
                            }
                        },
                        "required": ["task_id"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "subagent_delegate",
                    "description": "DEDICATED SUBAGENT: runs one sub-task with a named specialist (fresh session/checkpoint) and returns its final answer. Roles: planner, researcher, coder, reviewer, tester, security, test_writer, summarizer, memory_keeper, cost_watcher, triager, doc_writer, changelogger, deployer, dependency_updater, router, generalist. Use to decompose a big task into isolated units of work with the right specialist per unit.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "task": {
                                "type": "string",
                                "description": "The sub-task to delegate."
                            },
                            "role": {
                                "type": "string",
                                "description": "Specialist role: planner | researcher | coder | reviewer | tester | security | test_writer | summarizer | memory_keeper | cost_watcher | triager | doc_writer | changelogger | deployer | dependency_updater | router | generalist (default generalist)."
                            },
                            "label": {
                                "type": "string",
                                "description": "Short label for the subagent (defaults to the role)."
                            }
                        },
                        "required": ["task"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "subagent_team",
                    "description": "DEDICATED SUBAGENT TEAM: runs several sub-tasks in parallel, each with its own specialist role (roles list parallel to tasks; missing roles default to generalist). Returns all results together. Use to fan out independent work items.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "tasks": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of sub-tasks to run in parallel."
                            },
                            "roles": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Optional list of specialist roles, one per task (planner/researcher/coder/reviewer/tester/security/test_writer/summarizer/memory_keeper/cost_watcher/triager/doc_writer/changelogger/deployer/dependency_updater/router/generalist)."
                            }
                        },
                        "required": ["tasks"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "subagent_roles",
                    "description": "Lists the available dedicated subagent roles with a description of when to use each. Call before delegating to pick the right specialist.",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "subagent_route",
                    "description": "INTENT ROUTER: decides which specialist role(s) should handle an incoming task (primary + supporting roles + why). Deterministic keyword routing — no model call. Use before delegating a big request.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "task": {
                                "type": "string",
                                "description": "The request to route to a specialist role."
                            }
                        },
                        "required": ["task"]
                    }
                }
            }
        ]

    async def execute_tool(self, name: str, args: dict[str, Any]) -> str:
        try:
            handler = getattr(self, f"tool_{name}", None)
            if not handler:
                return f"Error: Tool '{name}' does not exist."
            if asyncio.iscoroutinefunction(handler):
                return await handler(**args)
            else:
                return handler(**args)
        except (RuntimeError, OSError, ValueError) as e:
            return f"Tool execution failed for '{name}': {e!s}"

    async def tool_execute_command(self, command: str, cwd: str = "") -> str:
        working_dir = self._resolve_path(cwd) if cwd else self.workspace
        working_dir.mkdir(parents=True, exist_ok=True)
        timeout = _command_timeout(45.0)
        try:
            # Use powershell on windows
            shell_cmd = ["powershell", "-NoProfile", "-Command", command] if sys.platform == "win32" else ["bash", "-c", command]
            proc = await asyncio.create_subprocess_exec(
                *shell_cmd,
                cwd=str(working_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            out_str = stdout.decode('utf-8', errors='ignore')
            err_str = stderr.decode('utf-8', errors='ignore')
            res = []
            if out_str:
                res.append(f"STDOUT:\n{out_str.strip()}")
            if err_str:
                res.append(f"STDERR:\n{err_str.strip()}")
            res.append(f"Exit code: {proc.returncode}")
            return "\n".join(res) if res else "Command executed with no output."
        except asyncio.TimeoutError:
            return f"Error: Command timed out after {timeout:.0f} seconds."
        except (OSError, RuntimeError) as e:
            return f"Command execution error: {e!s}"

    def tool_read_file(self, path: str) -> str:
        fpath = self._resolve_path(path)
        if not fpath.exists():
            return f"Error: File '{fpath}' does not exist."
        if fpath.is_dir():
            return f"Error: '{fpath}' is a directory, not a file."
        try:
            with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            return content if content else "(File is empty)"
        except OSError as e:
            return f"Error reading file '{fpath}': {e!s}"

    def tool_write_file(self, path: str, content: str) -> str:
        fpath = self._resolve_path(path)
        try:
            fpath.parent.mkdir(parents=True, exist_ok=True)
            with open(fpath, "w", encoding="utf-8") as f:
                f.write(content)
            return f"Successfully wrote {len(content)} characters to {fpath}."
        except OSError as e:
            return f"Error writing file '{fpath}': {e!s}"

    def tool_edit_file(self, path: str, target_text: str, replacement_text: str) -> str:
        fpath = self._resolve_path(path)
        if not fpath.exists():
            return f"Error: File '{fpath}' does not exist."
        try:
            with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            if target_text not in content:
                return f"Error: target_text not found in '{fpath}'. Please verify exact character match."
            new_content = content.replace(target_text, replacement_text, 1)
            with open(fpath, "w", encoding="utf-8") as f:
                f.write(new_content)
            return f"Successfully updated '{fpath}'."
        except OSError as e:
            return f"Error editing file '{fpath}': {e!s}"

    def tool_list_directory(self, path: str | Path = "") -> str:
        target = self._resolve_path(path) if path else self.workspace
        if not target.exists():
            return f"Error: Directory '{target}' does not exist."
        try:
            items = []
            for item in target.iterdir():
                kind = "DIR" if item.is_dir() else "FILE"
                size = item.stat().st_size if item.is_file() else "-"
                items.append(f"[{kind}] {item.name} ({size} bytes)")
            return "\n".join(items) if items else "(Directory is empty)"
        except OSError as e:
            return f"Error listing directory '{target}': {e!s}"

    async def tool_web_search(self, query: str, max_results: int = 5) -> str:
        try:
            loop = asyncio.get_running_loop()
            def _search():
                results = []
                with DDGS() as ddgs:
                    for r in ddgs.text(query, max_results=max_results):
                        results.append(f"Title: {r.get('title')}\nSnippet: {r.get('body')}\nURL: {r.get('href')}\n---")
                return "\n".join(results) if results else "No results found."
            return await loop.run_in_executor(None, _search)
        except (RuntimeError, OSError) as e:
            return f"Search error: {e!s}"

    async def tool_scrape_webpage(self, url: str) -> str:
        try:
            req = urllib.request.Request(
                url,
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            )
            loop = asyncio.get_running_loop()
            def _fetch():
                with urllib.request.urlopen(req, timeout=15) as response:
                    html = response.read().decode('utf-8', errors='ignore')
                text = re.sub(r'<script.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
                text = re.sub(r'<style.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
                text = re.sub(r'<[^>]+>', ' ', text)
                clean_lines = [line.strip() for line in text.splitlines() if line.strip()]
                return "\n".join(clean_lines)[:6000]
            return await loop.run_in_executor(None, _fetch)
        except (urllib.error.URLError, OSError, RuntimeError) as e:
            return f"Scraping error for {url}: {e!s}"

    async def tool_python_eval(self, code: str) -> str:
        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable, "-c", code,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30.0)
            res = []
            if stdout:
                res.append(f"STDOUT:\n{stdout.decode('utf-8', errors='ignore')}")
            if stderr:
                res.append(f"STDERR:\n{stderr.decode('utf-8', errors='ignore')}")
            return "\n".join(res) if res else "(Code executed with no output)"
        except (OSError, RuntimeError, asyncio.TimeoutError) as e:
            return f"Python execution error: {e!s}"

    async def tool_deep_search(self, topic: str) -> str:
        from .deep_search import DeepSearchEngine
        engine = DeepSearchEngine()
        data = await engine.run(topic)
        summary = [f"### DEEP RESEARCH DOSSIER: {topic}"]
        summary.append(f"Sub-queries explored: {len(data['sub_queries'])}")
        summary.append(f"Unique sources analyzed: {data['total_sources_found']}\n")
        summary.append("#### Primary Sources:")
        for s in data["sources"][:5]:
            summary.append(f"- **{s['title']}**: {s['snippet']} (URL: {s['url']})")
        if data["deep_pages"]:
            summary.append("\n#### Deep Scraped Insights:")
            for p in data["deep_pages"]:
                summary.append(f"**[{p['title']}]**: {p['content'][:800]}...\n")
        return "\n".join(summary)

    async def tool_deep_coder(self, task_name: str, files: dict[str, str], test_code: str = "") -> str:
        from .deep_coder import DeepCoderEngine
        engine = DeepCoderEngine(self)
        res = await engine.execute_coding_cycle(task_name, files, test_code if test_code else None)
        out = [f"### DEEP CODING REPORT: {task_name}"]
        out.append(f"Status: {res['status']}")
        out.append("Created / Modified Files:")
        for f in res["created_files"]:
            out.append(f"- `{f['path']}`: {f['status']}")
        if res["syntax_checks"]:
            out.append("\nSyntax Validation:")
            for p, sc in res["syntax_checks"].items():
                out.append(f"- `{p}`: {'VALID' if sc['valid'] else 'ERROR: ' + sc['details']}")
        if res["test_passed"] is not None:
            out.append(f"\nUnit Test Execution: {'PASSED' if res['test_passed'] else 'FAILED'}")
            out.append(f"Output:\n```\n{res['test_output']}\n```")
        return "\n".join(out)

    def tool_workspace_rag(self, query: str, top_k: int = 4) -> str:
        try:
            rag = WorkspaceRAG(self.workspace)
            top_k = max(1, min(int(top_k or 4), 8))
            results = rag.search(query, top_k=top_k)
            if not results:
                return "No relevant snippets found in the workspace for this query."
            lines = [f"### WORKSPACE RAG RESULTS for: {query}"]
            for r in results:
                lines.append(f"\n**{r['path']}** (chunk {r['chunk_index']}, score {r['score']}):")
                lines.append(r["snippet"])
            return "\n".join(lines)
        except (RuntimeError, OSError, ValueError) as e:
            return f"Workspace RAG error: {e!s}"

    def tool_launch_application(self, app_or_command: str) -> str:
        try:
            if sys.platform == "win32":
                subprocess.Popen(f"start {app_or_command}", shell=True)
            else:
                subprocess.Popen(app_or_command, shell=True)
            return f"Launched application/command: '{app_or_command}'"
        except (OSError, subprocess.SubprocessError) as e:
            return f"Failed to launch application: {e!s}"

    def tool_system_info(self) -> str:
        """Reads live host environment facts (OS, CPU, RAM, disk, Python)."""
        import logging
        log = logging.getLogger(__name__)
        try:
            lines = []
            lines.append(f"OS: {platform.system()} {platform.release()} ({platform.version()})")
            lines.append(f"Machine: {platform.machine()} | Node: {platform.node()}")
            lines.append(f"Python: {platform.python_version()} ({sys.executable})")
            lines.append(f"CPU cores: {os.cpu_count() or 'unknown'}")

            # RAM (total + free)
            try:
                if sys.platform == "win32":
                    import ctypes
                    class MEMORYSTATUSEX(ctypes.Structure):
                        _fields_ = [
                            ("dwLength", ctypes.c_ulong),
                            ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong),
                            ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong),
                            ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong),
                            ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                        ]
                    stat = MEMORYSTATUSEX()
                    stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
                    if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                        total_gb = stat.ullTotalPhys / (1024 ** 3)
                        free_gb = stat.ullAvailPhys / (1024 ** 3)
                        lines.append(f"RAM: {free_gb:.1f} GB free / {total_gb:.1f} GB total ({stat.dwMemoryLoad}% used)")
                    else:
                        lines.append("RAM: unable to read")
                else:
                    with open("/proc/meminfo") as f:
                        meminfo = {}
                        for line in f:
                            parts = line.split(":", 1)
                            if len(parts) == 2:
                                meminfo[parts[0].strip()] = parts[1].strip()
                    total_kb = int(meminfo.get("MemTotal", "0").split()[0])
                    avail_kb = int(meminfo.get("MemAvailable", "0").split()[0])
                    lines.append(f"RAM: {avail_kb/1048576:.1f} GB free / {total_kb/1048576:.1f} GB total")
            except (OSError, ValueError) as e:
                log.debug("RAM read failed: %s", e)
                lines.append(f"RAM: read failed ({e})")

            # Disk on workspace drive
            try:
                usage = shutil.disk_usage(str(self.workspace))
                lines.append(f"Disk: {usage.free/(1024**3):.1f} GB free / {usage.total/(1024**3):.1f} GB total")
            except OSError as e:
                log.debug("Disk usage failed: %s", e)

            # Software hints
            try:
                node_ver = subprocess.run(["node", "--version"], capture_output=True, text=True, timeout=5, check=False).stdout.strip()
                lines.append(f"Node.js: {node_ver or 'not found'}")
            except (OSError, subprocess.SubprocessError) as e:
                log.debug("Node version check failed: %s", e)
            try:
                git_ver = subprocess.run(["git", "--version"], capture_output=True, text=True, timeout=5, check=False).stdout.strip()
                lines.append(f"Git: {git_ver or 'not found'}")
            except (OSError, subprocess.SubprocessError) as e:
                log.debug("Git version check failed: %s", e)

            lines.append(f"Workspace: {self.workspace}")
            return "\n".join(lines)
        except RuntimeError as e:
            log.error("System info error: %s", e)
            return f"System info error: {e!s}"

    async def tool_manage_processes(self, action: str = "list", pattern: str = "") -> str:
        """Lists or kills OS processes (tasklist/taskkill on Windows, ps/kill on Unix)."""
        action = (action or "list").lower()
        try:
            if sys.platform == "win32":
                if action == "list":
                    cmd = ["tasklist", "/FO", "CSV", "/NH"]
                    proc = await asyncio.create_subprocess_exec(
                        *cmd,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=20.0)
                    if stderr and not stdout:
                        return f"Error listing processes: {stderr.decode('utf-8', errors='ignore')[:500]}"
                    rows = []
                    for line in stdout.decode("utf-8", errors="ignore").splitlines():
                        line = line.strip()
                        if not line:
                            continue
                        parts = line.split('","')
                        if len(parts) >= 2:
                            name = parts[0].strip('"')
                            pid = parts[1].strip('"')
                            if pattern and pattern.lower() not in name.lower():
                                continue
                            rows.append(f"PID {pid}: {name}")
                    if not rows:
                        return f"No processes found matching '{pattern}'." if pattern else "No processes found."
                    return "\n".join(rows[:100])
                elif action == "kill":
                    if not pattern:
                        return "Error: manage_processes kill requires 'pattern' (PID or image name)."
                    cmd = ["taskkill", "/F"]
                    if pattern.strip().isdigit():
                        cmd += ["/PID", pattern.strip()]
                    else:
                        cmd += ["/IM", pattern.strip()]
                    proc = await asyncio.create_subprocess_exec(
                        *cmd,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=20.0)
                    out = (stdout or b"").decode("utf-8", errors="ignore").strip()
                    err = (stderr or b"").decode("utf-8", errors="ignore").strip()
                    return f"{out} {err}".strip() or f"Kill command finished (exit {proc.returncode})."
                else:
                    return f"Error: unknown action '{action}' (use 'list' or 'kill')."
            else:
                # Unix
                if action == "list":
                    proc = await asyncio.create_subprocess_exec(
                        "ps", "-eo", "pid,comm",
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=20.0)
                    rows = []
                    for line in stdout.decode("utf-8", errors="ignore").splitlines():
                        parts = line.split(None, 1)
                        if len(parts) == 2:
                            pid, name = parts[0], parts[1]
                            if pattern and pattern.lower() not in name.lower():
                                continue
                            rows.append(f"PID {pid}: {name}")
                    return "\n".join(rows[:100]) if rows else f"No processes found matching '{pattern}'."
                elif action == "kill":
                    if not pattern:
                        return "Error: manage_processes kill requires 'pattern' (PID)."
                    proc = await asyncio.create_subprocess_exec(
                        "kill", "-9", pattern.strip(),
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=20.0)
                    out = (stdout or b"").decode("utf-8", errors="ignore").strip()
                    err = (stderr or b"").decode("utf-8", errors="ignore").strip()
                    return f"{out} {err}".strip() or f"Kill command finished (exit {proc.returncode})."
                else:
                    return f"Error: unknown action '{action}' (use 'list' or 'kill')."
        except asyncio.TimeoutError:
            return "Error: process query timed out after 20 seconds."
        except (OSError, RuntimeError) as e:
            return f"Manage processes error: {e!s}"

    def tool_clipboard_get(self) -> str:
        """Reads text from the system clipboard."""
        try:
            if sys.platform == "win32":
                import ctypes
                ctypes.windll.user32.OpenClipboard(0)
                try:
                    if ctypes.windll.user32.IsClipboardFormatAvailable(13):  # CF_UNICODETEXT
                        h_mem = ctypes.windll.user32.GetClipboardData(13)
                        if h_mem:
                            locked = ctypes.windll.kernel32.GlobalLock(h_mem)
                            if locked:
                                text = ctypes.wstring_at(locked)
                                ctypes.windll.kernel32.GlobalUnlock(h_mem)
                                return text
                    return "(Clipboard empty or not text)"
                finally:
                    ctypes.windll.user32.CloseClipboard()
            else:
                # Unix: use xclip or xsel
                for cmd in [["xclip", "-selection", "clipboard", "-o"], ["xsel", "-b"]]:
                    try:
                        result = subprocess.run(cmd, capture_output=True, text=True, timeout=2, check=False)
                        if result.returncode == 0 and result.stdout:
                            return result.stdout
                    except (OSError, subprocess.SubprocessError):
                        continue
                return "(Clipboard tools not available: install xclip or xsel)"
        except RuntimeError as e:
            return f"Clipboard read error: {e!s}"

    def tool_clipboard_set(self, text: str) -> str:
        """Writes text to the system clipboard."""
        try:
            if sys.platform == "win32":
                import ctypes
                ctypes.windll.user32.OpenClipboard(0)
                try:
                    ctypes.windll.user32.EmptyClipboard()
                    h_mem = ctypes.windll.kernel32.GlobalAlloc(0x0042, (len(text) + 1) * 2)  # GMEM_MOVEABLE
                    if h_mem:
                        locked = ctypes.windll.kernel32.GlobalLock(h_mem)
                        if locked:
                            ctypes.memmove(locked, text.encode("utf-16-le"), len(text) * 2 + 2)
                            ctypes.windll.kernel32.GlobalUnlock(h_mem)
                            ctypes.windll.user32.SetClipboardData(13, h_mem)  # CF_UNICODETEXT
                            return f"Clipboard set ({len(text)} chars)"
                    return "Failed to allocate clipboard memory"
                finally:
                    ctypes.windll.user32.CloseClipboard()
            else:
                # Unix: use xclip or xsel
                for cmd in [["xclip", "-selection", "clipboard"], ["xsel", "-b", "-i"]]:
                    try:
                        proc = subprocess.run(cmd, input=text, text=True, timeout=2, capture_output=True, check=False)
                        if proc.returncode == 0:
                            return f"Clipboard set ({len(text)} chars)"
                    except (OSError, subprocess.SubprocessError):
                        continue
                return "(Clipboard tools not available: install xclip or xsel)"
        except RuntimeError as e:
            return f"Clipboard write error: {e!s}"

    def tool_screenshot(self, monitor: int = 0) -> str:
        """Takes a screenshot of the specified monitor and returns base64 PNG."""
        try:
            if sys.platform == "win32":
                import base64
                import ctypes
                from ctypes import wintypes

                # wintypes in the stdlib stubs omits the monitor/bitmap structs,
                # so define them explicitly (fields match the Win32 SDK).
                class _MONITORINFO(ctypes.Structure):
                    _fields_ = [
                        ("cbSize", wintypes.DWORD),
                        ("rcMonitor", wintypes.RECT),
                        ("rcWork", wintypes.RECT),
                        ("dwFlags", wintypes.DWORD),
                    ]

                class _BITMAPINFOHEADER(ctypes.Structure):
                    _fields_ = [
                        ("biSize", wintypes.DWORD),
                        ("biWidth", ctypes.c_long),
                        ("biHeight", ctypes.c_long),
                        ("biPlanes", ctypes.c_ushort),
                        ("biBitCount", ctypes.c_ushort),
                        ("biCompression", wintypes.DWORD),
                        ("biSizeImage", wintypes.DWORD),
                        ("biXPelsPerMeter", ctypes.c_long),
                        ("biYPelsPerMeter", ctypes.c_long),
                        ("biClrUsed", wintypes.DWORD),
                        ("biClrImportant", wintypes.DWORD),
                    ]

                class _BITMAPINFO(ctypes.Structure):
                    _fields_ = [
                        ("bmiHeader", _BITMAPINFOHEADER),
                        ("bmiColors", wintypes.DWORD * 1),
                    ]
                
                user32 = ctypes.windll.user32
                gdi32 = ctypes.windll.gdi32
                
                # Get monitor info
                monitors = []
                def enum_proc(hMonitor, hdcMonitor, lprcMonitor, dwData):
                    monitors.append(hMonitor)
                    return True
                MONITORENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HMONITOR, wintypes.HDC, ctypes.POINTER(wintypes.RECT), wintypes.LPARAM)
                user32.EnumDisplayMonitors(0, 0, MONITORENUMPROC(enum_proc), 0)
                
                if monitor >= len(monitors):
                    return f"Error: Monitor {monitor} not found (only {len(monitors)} monitors)"
                
                h_mon = monitors[monitor]
                mi = _MONITORINFO()
                mi.cbSize = ctypes.sizeof(mi)
                user32.GetMonitorInfoW(h_mon, ctypes.byref(mi))
                
                left, top, right, bottom = mi.rcMonitor.left, mi.rcMonitor.top, mi.rcMonitor.right, mi.rcMonitor.bottom
                width = right - left
                height = bottom - top
                
                hdc_screen = user32.GetDC(0)
                hdc_mem = gdi32.CreateCompatibleDC(hdc_screen)
                hbmp = gdi32.CreateCompatibleBitmap(hdc_screen, width, height)
                old_bmp = gdi32.SelectObject(hdc_mem, hbmp)
                
                gdi32.BitBlt(hdc_mem, 0, 0, width, height, hdc_screen, left, top, 0x00CC0020)  # SRCCOPY
                
                # Get bitmap bits
                bmi = _BITMAPINFO()
                bmi.bmiHeader.biSize = ctypes.sizeof(_BITMAPINFOHEADER)
                bmi.bmiHeader.biWidth = width
                bmi.bmiHeader.biHeight = -height  # negative for top-down
                bmi.bmiHeader.biPlanes = 1
                bmi.bmiHeader.biBitCount = 32
                bmi.bmiHeader.biCompression = 0  # BI_RGB
                
                bits = ctypes.create_string_buffer(width * height * 4)
                gdi32.GetDIBits(hdc_mem, hbmp, 0, height, bits, ctypes.byref(bmi), 0)
                
                # Convert to PNG using Python
                import io

                from PIL import Image
                img = Image.frombuffer('RGBA', (width, height), bits.raw, 'raw', 'BGRA', 0, 1)
                buf = io.BytesIO()
                img.save(buf, format='PNG')
                b64 = base64.b64encode(buf.getvalue()).decode('ascii')
                
                gdi32.SelectObject(hdc_mem, old_bmp)
                gdi32.DeleteObject(hbmp)
                gdi32.DeleteDC(hdc_mem)
                user32.ReleaseDC(0, hdc_screen)
                
                return f"data:image/png;base64,{b64}"
            else:
                # Unix: use scrot or maim
                import base64
                for cmd in [["scrot", "-u", "-"], ["maim", "-u"]]:
                    try:
                        result = subprocess.run(cmd, capture_output=True, timeout=5, check=False)
                        if result.returncode == 0 and result.stdout:
                            b64 = base64.b64encode(result.stdout).decode('ascii')
                            return f"data:image/png;base64,{b64}"
                    except (OSError, subprocess.SubprocessError):
                        continue
                return "(Screenshot tools not available: install scrot or maim)"
        except RuntimeError as e:
            return f"Screenshot error: {e!s}"

    def tool_key_press(self, keys: str) -> str:
        """Simulates keyboard key presses."""
        try:
            if sys.platform == "win32":
                import ctypes
                import time
                
                user32 = ctypes.windll.user32
                
                # Parse key combination
                key_map = {
                    'ctrl': 0x11, 'control': 0x11,
                    'alt': 0x12,
                    'shift': 0x10,
                    'win': 0x5B, 'windows': 0x5B,
                    'enter': 0x0D, 'return': 0x0D,
                    'tab': 0x09,
                    'esc': 0x1B, 'escape': 0x1B,
                    'space': 0x20,
                    'up': 0x26, 'down': 0x28, 'left': 0x25, 'right': 0x27,
                    'f1': 0x70, 'f2': 0x71, 'f3': 0x72, 'f4': 0x73,
                    'f5': 0x74, 'f6': 0x75, 'f7': 0x76, 'f8': 0x77,
                    'f9': 0x78, 'f10': 0x79, 'f11': 0x7A, 'f12': 0x7B,
                    'a': 0x41, 'b': 0x42, 'c': 0x43, 'd': 0x44, 'e': 0x45,
                    'f': 0x46, 'g': 0x47, 'h': 0x48, 'i': 0x49, 'j': 0x4A,
                    'k': 0x4B, 'l': 0x4C, 'm': 0x4D, 'n': 0x4E, 'o': 0x4F,
                    'p': 0x50, 'q': 0x51, 'r': 0x52, 's': 0x53, 't': 0x54,
                    'u': 0x55, 'v': 0x56, 'w': 0x57, 'x': 0x58, 'y': 0x59, 'z': 0x5A,
                    '0': 0x30, '1': 0x31, '2': 0x32, '3': 0x33, '4': 0x34,
                    '5': 0x35, '6': 0x36, '7': 0x37, '8': 0x38, '9': 0x39,
                }
                
                parts = [p.strip().lower() for p in keys.split('+')]
                vk_codes = [key_map.get(p) for p in parts if p in key_map]
                
                if not vk_codes:
                    return f"Error: Unknown keys in '{keys}'"
                
                # Press modifiers first
                for vk in vk_codes[:-1]:
                    user32.keybd_event(vk, 0, 0, 0)
                    time.sleep(0.01)
                
                # Press main key
                user32.keybd_event(vk_codes[-1], 0, 0, 0)
                time.sleep(0.02)
                user32.keybd_event(vk_codes[-1], 0, 2, 0)  # KEYEVENTF_KEYUP
                
                # Release modifiers
                for vk in reversed(vk_codes[:-1]):
                    user32.keybd_event(vk, 0, 2, 0)
                    time.sleep(0.01)
                
                return f"Pressed: {keys}"
            else:
                # Unix: use xdotool
                try:
                    subprocess.run(["xdotool", "key", keys], timeout=3, check=False)
                    return f"Pressed: {keys}"
                except (OSError, subprocess.SubprocessError):
                    return "(xdotool not installed)"
        except RuntimeError as e:
            return f"Key press error: {e!s}"

    def tool_mouse_click(self, x: int, y: int, button: str = "left", double: bool = False) -> str:
        """Simulates a mouse click at coordinates."""
        try:
            if sys.platform == "win32":
                import ctypes
                import time
                
                user32 = ctypes.windll.user32
                
                # Move to position
                user32.SetCursorPos(x, y)
                time.sleep(0.02)
                
                button_map = {"left": (0x02, 0x04), "right": (0x08, 0x10), "middle": (0x20, 0x40)}
                down, up = button_map.get(button, button_map["left"])
                
                def click_once():
                    user32.mouse_event(down, 0, 0, 0, 0)
                    time.sleep(0.02)
                    user32.mouse_event(up, 0, 0, 0, 0)
                
                click_once()
                if double:
                    time.sleep(0.1)
                    click_once()
                
                return f"Clicked {button} at ({x}, {y}){' (double)' if double else ''}"
            else:
                # Unix: use xdotool
                try:
                    btn_map = {"left": "1", "right": "3", "middle": "2"}
                    btn = btn_map.get(button, "1")
                    cmd = ["xdotool", "mousemove", str(x), str(y), "click"]
                    if double:
                        cmd.insert(-1, "--repeat")
                        cmd.insert(-1, "2")
                    else:
                        cmd.append(btn)
                    subprocess.run(cmd, timeout=3, check=False)
                    return f"Clicked {button} at ({x}, {y})"
                except (OSError, subprocess.SubprocessError):
                    return "(xdotool not installed)"
        except RuntimeError as e:
            return f"Mouse click error: {e!s}"

    def tool_mouse_move(self, x: int, y: int, duration: float = 0) -> str:
        """Moves mouse cursor to coordinates."""
        try:
            import time
            if sys.platform == "win32":
                import ctypes
                user32 = ctypes.windll.user32
                if duration > 0:
                    # Smooth move
                    cur_x, cur_y = user32.GetCursorPos()
                    steps = max(10, int(duration * 60))
                    for i in range(1, steps + 1):
                        t = i / steps
                        nx = int(cur_x + (x - cur_x) * t)
                        ny = int(cur_y + (y - cur_y) * t)
                        user32.SetCursorPos(nx, ny)
                        time.sleep(duration / steps)
                else:
                    user32.SetCursorPos(x, y)
                return f"Moved mouse to ({x}, {y})"
            else:
                subprocess.run(["xdotool", "mousemove", str(x), str(y)], timeout=3, check=False)
                return f"Moved mouse to ({x}, {y})"
        except RuntimeError as e:
            return f"Mouse move error: {e!s}"

    async def tool_list_windows(self) -> str:
        """Lists all visible windows."""
        try:
            if sys.platform == "win32":
                import ctypes
                from ctypes import wintypes
                
                user32 = ctypes.windll.user32
                
                windows = []
                
                def enum_windows(hwnd, lparam):
                    if user32.IsWindowVisible(hwnd):
                        length = user32.GetWindowTextLengthW(hwnd)
                        if length > 0:
                            buff = ctypes.create_unicode_buffer(length + 1)
                            user32.GetWindowTextW(hwnd, buff, length + 1)
                            title = buff.value
                            # Get process name
                            pid = wintypes.DWORD()
                            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                            try:
                                import psutil
                                proc = psutil.Process(pid.value)
                                proc_name = proc.name()
                            except RuntimeError:
                                proc_name = f"PID:{pid.value}"
                            windows.append(f"HWND:{hwnd} | {proc_name} | {title[:80]}")
                    return True
                
                WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
                user32.EnumWindows(WNDENUMPROC(enum_windows), 0)
                
                return "\n".join(windows[:50]) if windows else "No visible windows"
            else:
                # Unix: use wmctrl
                try:
                    result = await asyncio.to_thread(
                        subprocess.run, ["wmctrl", "-l"],
                        capture_output=True, text=True, timeout=3, check=False,
                    )
                    if result.returncode == 0:
                        return result.stdout[:3000]
                    return "(wmctrl not available)"
                except (OSError, subprocess.SubprocessError):
                    return "(wmctrl not installed)"
        except RuntimeError as e:
            return f"List windows error: {e!s}"

    async def tool_window_control(self, action: str, title: str) -> str:
        """Controls a window: minimize, maximize, restore, close, or bring to front."""
        try:
            if sys.platform == "win32":
                import ctypes
                from ctypes import wintypes
                
                user32 = ctypes.windll.user32
                
                target_hwnd = None
                
                # Try as HWND first
                if title.isdigit():
                    target_hwnd = wintypes.HWND(int(title))
                    if not user32.IsWindow(target_hwnd):
                        target_hwnd = None
                
                # Find by title if not found
                if not target_hwnd:
                    def enum_windows(hwnd, lparam):
                        nonlocal target_hwnd
                        if user32.IsWindowVisible(hwnd):
                            length = user32.GetWindowTextLengthW(hwnd)
                            if length > 0:
                                buff = ctypes.create_unicode_buffer(length + 1)
                                user32.GetWindowTextW(hwnd, buff, length + 1)
                                if title.lower() in buff.value.lower():
                                    target_hwnd = hwnd
                                    return False  # Stop enumeration
                        return True
                    
                    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
                    user32.EnumWindows(WNDENUMPROC(enum_windows), 0)
                
                if not target_hwnd:
                    return f"Window not found: {title}"
                
                action_map = {
                    "minimize": 6,      # SW_MINIMIZE
                    "maximize": 3,      # SW_MAXIMIZE
                    "restore": 9,       # SW_RESTORE
                    "close": None,      # Special: send WM_CLOSE
                    "foreground": None, # Special: SetForegroundWindow
                }
                
                if action == "close":
                    user32.PostMessageW(target_hwnd, 0x0010, 0, 0)  # WM_CLOSE
                    return f"Sent close message to window: {title}"
                elif action == "foreground":
                    user32.SetForegroundWindow(target_hwnd)
                    return f"Brought window to front: {title}"
                elif action in action_map:
                    user32.ShowWindow(target_hwnd, action_map[action])
                    return f"Window {action}: {title}"
                else:
                    return f"Unknown action: {action}"
            else:
                # Unix: use wmctrl/xdotool
                try:
                    if action == "close":
                        await asyncio.to_thread(subprocess.run, ["wmctrl", "-c", title], timeout=3, check=False)
                    elif action in ("minimize", "maximize", "restore"):
                        state_map = {"minimize": "-b add,iconic", "maximize": "-b add,maximized_vert,maximized_horz", "restore": "-b remove,maximized_vert,maximized_horz"}
                        await asyncio.to_thread(subprocess.run, ["wmctrl", "-r", title, state_map[action]], timeout=3, check=False)
                    elif action == "foreground":
                        await asyncio.to_thread(subprocess.run, ["wmctrl", "-a", title], timeout=3, check=False)
                    return f"Window {action}: {title}"
                except (OSError, subprocess.SubprocessError):
                    return "(wmctrl not installed)"
        except RuntimeError as e:
            return f"Window control error: {e!s}"

    # ================= Phase 7: Full Autonomy tools =================

    async def _run_command_raw(
        self,
        command: str,
        cwd: str = "",
        timeout: float = 60.0,
    ) -> tuple[int, str, str]:
        """Execute a command and return (exit_code, stdout, stderr) — no decoration.

        Used by self_heal so the repair loop can inspect raw output.
        Phase 8: FULL access raises the ceiling to 10 minutes.
        """
        timeout = _command_timeout(timeout) if _cfg.full_access_enabled() else (timeout or 60.0)
        working_dir = self._resolve_path(cwd) if cwd else self.workspace
        working_dir.mkdir(parents=True, exist_ok=True)
        shell_cmd = (
            ["powershell", "-NoProfile", "-Command", command]
            if sys.platform == "win32"
            else ["bash", "-c", command]
        )
        proc = await asyncio.create_subprocess_exec(
            *shell_cmd,
            cwd=str(working_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return 1, "", f"Command timed out after {timeout:.0f}s."
        return (
            proc.returncode or 0,
            stdout.decode("utf-8", errors="ignore"),
            stderr.decode("utf-8", errors="ignore"),
        )

    async def tool_self_heal(self, command: str, cwd: str = "", max_attempts: int = 3) -> str:
        """Self-healing command runner: run, diagnose failure, repair, re-run."""
        from .heal import SelfHealEngine

        engine = SelfHealEngine()
        result = await engine.heal(
            command,
            max_attempts=max_attempts,
            run=lambda cmd: self._run_command_raw(cmd, cwd=cwd),
        )
        return result.to_text()

    async def tool_download_file(self, url: str, dest: str = "") -> str:
        """SSRF-guarded download of a public http(s) URL into the workspace.

        Phase 8: FULL access removes the 100 MB safety cap and raises the fetch
        timeout to 2 minutes; ABSOLUTE access also skips the SSRF private-
        network guard and allows any scheme urlopen supports.
        """
        url = (url or "").strip()
        absolute = _cfg.absolute_access_enabled()
        if not absolute and not url.lower().startswith(("http://", "https://")):
            return "Error: only http(s) URLs are allowed."
        if not absolute:
            policy = PolicyEngine()
            check = policy.check_network_target(url)
            if check.decision == "deny":
                return f"Error: refused to download private/loopback target ({url})."
        try:
            target = self._resolve_path(dest) if dest else self.workspace
            if dest and dest.lower().endswith("/"):
                target.mkdir(parents=True, exist_ok=True)
            elif not dest:
                target = self.workspace
            fname = Path(url.split("?")[0].split("#")[0]).name or "download.bin"
            out_path = (target if target.is_dir() else self.workspace) / fname
            out_path.parent.mkdir(parents=True, exist_ok=True)
            req = urllib.request.Request(url, headers={"User-Agent": "Titan-Agent/8.0"})
            fetch_timeout = 120.0 if _cfg.full_access_enabled() else 30.0
            max_bytes = 2 * 1024 * 1024 * 1024 if _cfg.full_access_enabled() else 100 * 1024 * 1024

            def _fetch() -> bytes:
                with urllib.request.urlopen(req, timeout=fetch_timeout) as resp:
                    return resp.read()

            data = await asyncio.to_thread(_fetch)
            if len(data) > max_bytes:
                return f"Error: download exceeds {max_bytes // (1024 * 1024)} MB safety limit."
            out_path.write_bytes(data)
            return f"Downloaded {url}\nSaved: {out_path}\nSize: {len(data)} bytes"
        except (OSError, ValueError, urllib.error.URLError) as e:
            return f"Download failed: {e!s}"

    def _start_server(self, port: int, directory: Path) -> str:
        """Start (or return existing) ThreadingHTTPServer on localhost:port."""
        from functools import partial

        if not hasattr(self, "_http_servers"):
            self._http_servers: dict[int, ThreadingHTTPServer] = {}
        existing = self._http_servers.get(port)
        if existing:
            return f"Server already running at http://127.0.0.1:{port}"
        directory.mkdir(parents=True, exist_ok=True)
        handler = partial(SimpleHTTPRequestHandler, directory=str(directory))
        server = ThreadingHTTPServer(("127.0.0.1", port), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self._http_servers[port] = server
        return f"Serving {directory} at http://127.0.0.1:{port}"

    def tool_start_http_server(self, port: int = 8000, directory: str | Path = "") -> str:
        try:
            directory = self._resolve_path(directory) if directory else self.workspace
            port = int(port or 8000)
            # Phase 8: FULL access widens the allowed range to any valid port.
            lo, hi = (1, 65535) if _cfg.full_access_enabled() else (1024, 49151)
            if not lo <= port <= hi:
                return f"Error: port must be in {lo}-{hi}."
            return self._start_server(port, directory)
        except (OSError, ValueError) as e:
            return f"Could not start HTTP server: {e!s}"

    def tool_stop_http_server(self, port: int = 8000) -> str:
        port = int(port or 8000)
        server = getattr(self, "_http_servers", {}).get(port)
        if not server:
            return f"No HTTP server running on port {port}."
        server.shutdown()
        server.server_close()
        self._http_servers.pop(port, None)
        return f"Stopped HTTP server on port {port}."

    async def tool_take_screenshot(self, dest: str = "") -> str:
        """Capture the primary screen to a PNG (Windows via PowerShell)."""
        if sys.platform != "win32":
            return "Error: take_screenshot currently supports Windows only."
        fname = dest or f"screenshot_{int(time.time())}.png"
        out = self._resolve_path(fname)
        out.parent.mkdir(parents=True, exist_ok=True)
        ps = (
            "Add-Type -AssemblyName System.Windows.Forms,System.Drawing; "
            "$b = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds; "
            f"$bmp = New-Object System.Drawing.Bitmap($b.Width, $b.Height); "
            "$g = [System.Drawing.Graphics]::FromImage($bmp); "
            "$g.CopyFromScreen($b.Location, [System.Drawing.Point]::Empty, $b.Size); "
            f"$bmp.Save('{out}'); $g.Dispose(); $bmp.Dispose()"
        )
        try:
            proc = await asyncio.create_subprocess_exec(
                "powershell", "-NoProfile", "-Command", ps,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
            if not out.exists():
                return f"Screenshot failed: {stderr.decode('utf-8', errors='ignore')[:500]}"
            return f"Screenshot saved: {out} ({out.stat().st_size} bytes)"
        except (OSError, asyncio.TimeoutError) as e:
            return f"Screenshot error: {e!s}"

    async def tool_self_update(self, run_tests: bool = True) -> str:
        """Pull latest code, install requirements, run tests for the repo root."""
        repo = self.workspace
        # Walk up to find a .git dir
        while not (repo / ".git").exists() and repo.parent != repo:
            repo = repo.parent
        if not (repo / ".git").exists():
            return "No git repository found from workspace."
        lines = ["### SELF-UPDATE"]
        for cmd in ["git pull --ff-only", "git status --short"]:
            code, out, err = await self._run_command_raw(cmd, cwd=str(repo), timeout=120)
            lines.append(f"$ {cmd} (exit {code})")
            if out.strip():
                lines.append(out.strip())
            if err.strip():
                lines.append(err.strip())
        # requirements install (best-effort, optional)
        code, out, err = await self._run_command_raw(
            f'"{sys.executable}" -m pip install -r requirements.txt --quiet',
            cwd=str(repo),
            timeout=300,
        )
        lines.append(f"$ pip install -r requirements.txt (exit {code}){(' ' + err.strip()[:300]) if err.strip() else ''}")
        if run_tests and (repo / "tests").exists():
            code, out, err = await self._run_command_raw(
                f'"{sys.executable}" -m pytest -q',
                cwd=str(repo),
                timeout=600,
            )
            lines.append(f"\n$ pytest -q (exit {code})")
            if out.strip():
                lines.append(out.strip()[-1500:])
            if err.strip():
                lines.append(err.strip()[-500:])
        return "\n".join(lines)

    # ---- Autonomous task queue tools ----

    def _queue(self):
        from .queue import TaskQueue

        if not hasattr(self, "_task_queue") or self._task_queue is None:
            self._task_queue = TaskQueue(TASK_QUEUE_FILE)
        return self._task_queue

    def tool_task_enqueue(
        self,
        task: str,
        name: str = "",
        priority: int = 0,
        schedule_at: float = 0.0,
    ) -> str:
        if not task or not str(task).strip():
            return "Error: task is required."
        try:
            q = self._queue()
            tid = q.enqueue(
                str(task).strip(),
                name=name or None,
                priority=int(priority or 0),
                schedule_at=float(schedule_at or 0),
            )
            return f"Task #{tid} enqueued: {(name or task)[:80]}"
        except (OSError, ValueError) as e:
            return f"Enqueue failed: {e!s}"

    def tool_task_list(self, status: str = "", limit: int = 20) -> str:
        q = self._queue()
        tasks = q.list(status=status or None, limit=int(limit or 20))
        if not tasks:
            return "Task queue is empty."
        lines = ["### TASK QUEUE"]
        for t in tasks:
            lines.append(
                f"#{t.id} [{t.status}] prio={t.priority} attempts={t.attempts}/{t.max_attempts} :: {t.name}"
            )
        return "\n".join(lines)

    def tool_task_stats(self) -> str:
        q = self._queue()
        stats = q.stats()
        return "Queue stats: " + ", ".join(f"{k}={v}" for k, v in stats.items() if v) or "Queue is empty."

    def tool_task_cancel(self, task_id: int) -> str:
        ok = self._queue().cancel(int(task_id))
        return f"Task #{task_id} cancelled." if ok else f"Task #{task_id} not found or already running."

    # ---- Deep subagent tools (Phase 7) + dedicated staff (Phase 9) ----

    async def tool_subagent_delegate(
        self,
        task: str,
        role: str = "generalist",
        label: str = "",
    ) -> str:
        from .staff import StaffPool

        if not task or not str(task).strip():
            return "Error: task is required."
        pool = StaffPool()
        res = await pool.run(str(role or "generalist"), str(task).strip(), label=label or "")
        return res.to_text()

    async def tool_subagent_team(
        self,
        tasks: list[str],
        roles: list[str] | None = None,
    ) -> str:
        from .staff import StaffPool

        if not tasks:
            return "Error: tasks list is required."
        # Phase 8: FULL access raises the parallel subagent bound 2 -> 8.
        pool = StaffPool(max_workers=min(_subagent_worker_cap(), len(tasks)))
        results = await pool.team(
            [str(t) for t in tasks],
            roles=[str(r) for r in roles] if roles else None,
        )
        return "\n\n".join(r.to_text() for r in results)

    def tool_subagent_roles(self) -> str:
        from .staff import staff_catalog

        entries = staff_catalog()
        if not entries:
            return "No dedicated subagent roles configured."
        return "### DEDICATED SUBAGENT ROLES\n" + "\n".join(
            f"- {e['id']}: {e['title']} — {e['description']}" for e in entries
        )

    def tool_subagent_route(self, task: str) -> str:
        from .intent_router import route_intent

        if not task or not str(task).strip():
            return "Error: task is required."
        route = route_intent(str(task))
        return "### INTENT ROUTE\n" + route.plan_text()
