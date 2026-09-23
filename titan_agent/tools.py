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
import shlex
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


def _subagent_result_text(res: Any) -> str:
    """Phase 36: render a delegated-subagent result for the parent's context.

    Success keeps the classic report, but a FAILED or ERRORED child is turned
    into an Error-prefixed result so the uniform tool funnel treats it as a
    failed TOOL execution: it records in telemetry, increments the
    repeated-failure guard keyed by (tool, task), and warns the critic via the
    tool-evidence snippet. A weak parent must never treat a crashing child's
    half-baked output as proven work — this makes the failure loud AND
    self-reinforcing (re-delegating the identical task eventually gets blocked).
    """
    label = str(getattr(res, "label", "worker"))
    if getattr(res, "error", None):
        head = f"### SUBAGENT [{label}] - ERROR"
        body = str(res.error)
    elif getattr(res, "exit_code", 0) != 0:
        head = f"### SUBAGENT [{label}] - FAILED (exit {res.exit_code})"
        body = str(getattr(res, "final", "") or "(no output)")
    else:
        return res.to_text()
    return (
        f"Error: {head}\n{body}"
        "\n"
        "\u26a0 This delegated subagent FAILED - its output is UNPROVEN. "
        "Do not present it as done work: verify the files/tests yourself, or "
        "re-delegate with a corrected task."
    )


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
        base_defs = [
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
            },
            {
                "type": "function",
                "function": {
                    "name": "orchestrator_run",
                    "description": "META-ORCHESTRATOR (Genesis Level 1): Executes a high-level goal through the hierarchical organization (Chief Agent -> Department Leads -> Worker Specialists). Arbitrates conflicts and provides executive synthesis.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "goal": {
                                "type": "string",
                                "description": "The high-level project goal or complex task to orchestrate."
                            },
                            "departments": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Optional list of departments to involve: engineering, research, operations, quality_security. Defaults to automatic routing."
                            }
                        },
                        "required": ["goal"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "team_delegate",
                    "description": "DEPARTMENT DELEGATE (Genesis Level 2): Directly delegates a task to one of the 4 Department Leads (engineering, research, operations, quality_security). The lead assigns workers and applies first-line quality verification.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "department": {
                                "type": "string",
                                "description": "The department to delegate to: engineering, research, operations, or quality_security."
                            },
                            "task": {
                                "type": "string",
                                "description": "The task for the department to execute."
                            },
                            "role": {
                                "type": "string",
                                "description": "Optional preferred specialist worker within the department."
                            }
                        },
                        "required": ["department", "task"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "team_status",
                    "description": "Reports status, budget usage, and managed specialists across all 4 Department Leads and the Meta-Orchestrator.",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "dag_plan_and_run",
                    "description": "TASK GRAPH (Genesis Level 5): Decomposes a complex goal into a Directed Acyclic Graph (DAG) and executes independent nodes in parallel waves. Supports selective replanning on failures.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "goal": {
                                "type": "string",
                                "description": "The complex multi-step goal to plan as a DAG and execute."
                            }
                        },
                        "required": ["goal"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "dag_visualize",
                    "description": "Generates a visual Mermaid diagram and node dependency summary for a planned task graph.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "goal": {
                                "type": "string",
                                "description": "The goal to generate a DAG diagram for."
                            }
                        },
                        "required": ["goal"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "debate_solve",
                    "description": "MULTI-AGENT DEBATE (Genesis Level 4): Pits an Advocate against a Skeptic across multiple rounds on complex architectural or technical questions, with an authoritative Judge rendering the balanced consensus verdict.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "question": {
                                "type": "string",
                                "description": "The complex decision, architecture question, or trade-off to debate."
                            },
                            "rounds": {
                                "type": "integer",
                                "description": "Number of debate rounds (default 2)."
                            }
                        },
                        "required": ["question"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "reflexion_solve",
                    "description": "REFLEXION LOOP (Genesis Level 4): Solves a task with autonomous self-critique and iterative refinement up to 3 cycles, catching errors and improving before final response.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "task": {
                                "type": "string",
                                "description": "The task or problem to solve using self-critique and iterative refinement."
                            }
                        },
                        "required": ["task"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "kg_query",
                    "description": "KNOWLEDGE GRAPH (Genesis Level 3): Queries the causal and dependency knowledge graph around an entity up to N hops, returning related classes, functions, files, modules, and dependencies.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "entity_id": {
                                "type": "string",
                                "description": "The entity identifier (e.g. file path, class name, or function name)."
                            },
                            "depth": {
                                "type": "integer",
                                "description": "Graph traversal depth in hops (default 2)."
                            }
                        },
                        "required": ["entity_id"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "kg_impact_analysis",
                    "description": "KNOWLEDGE GRAPH IMPACT (Genesis Level 3): Computes the blast radius and downstream dependencies that will be impacted if a given function, class, or file is modified.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "entity_id": {
                                "type": "string",
                                "description": "The entity identifier to compute impact/blast radius for."
                            }
                        },
                        "required": ["entity_id"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "kg_add_fact",
                    "description": "KNOWLEDGE GRAPH (Genesis Level 3): Adds a custom semantic fact or causal dependency between two entities in the knowledge graph.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "source": {
                                "type": "string",
                                "description": "The source entity identifier."
                            },
                            "relation": {
                                "type": "string",
                                "description": "The relationship type (e.g., 'calls', 'depends_on', 'modifies', 'inherits')."
                            },
                            "target": {
                                "type": "string",
                                "description": "The target entity identifier."
                            }
                        },
                        "required": ["source", "relation", "target"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "kg_index_workspace",
                    "description": "KNOWLEDGE GRAPH (Genesis Level 3): Scans Python ASTs in the workspace to construct an automated dependency and inheritance knowledge graph.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "max_files": {
                                "type": "integer",
                                "description": "Maximum number of Python files to scan (default 50)."
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "tool_discover",
                    "description": "DYNAMIC TOOLS (Genesis Level 8): Searches and activates domain-specific tools on demand by keyword or category, keeping system prompt context lean.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "The search term, action, or tool name to look for (e.g. 'docker', 'browser', 'git', 'knowledge graph')."
                            },
                            "category": {
                                "type": "string",
                                "description": "Optional category filter: git, web_browser, genesis_orchestrator, reasoning, knowledge_graph, vector_rag, desktop_os, sandbox_verify."
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of tools to return (default 8)."
                            }
                        },
                        "required": ["query"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "tool_reliability_report",
                    "description": "TOOL RELIABILITY (Genesis Level 8): Reports Bayesian/EWMA health scores, failure rates, and auto-mitigation recommendations for tools.",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "model_route",
                    "description": "MODEL ROUTER (Genesis Level 7): Analyzes task complexity and determines the optimal LLM tier (FAST_CHEAP, STANDARD_CODING, DEEP_REASONING) with pricing estimates and failure escalation.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "task": {
                                "type": "string",
                                "description": "The task or prompt to analyze and route."
                            },
                            "prior_failures": {
                                "type": "integer",
                                "description": "Number of previous failures on this task (triggers escalation to higher reasoning tiers)."
                            }
                        },
                        "required": ["task"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "model_budget_status",
                    "description": "COGNITIVE BUDGET (Genesis Level 7): Inspects cumulative token spend, model-by-model usage breakdown, and remaining USD budget.",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "sandbox_execute",
                    "description": "EXECUTION SANDBOX (Genesis Level 6): Executes Python or shell code inside an isolated environment with filesystem snapshotting, static security AST scanning, timeout limits, and optional automatic rollback on failure.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "code": {
                                "type": "string",
                                "description": "The Python or shell code to safely execute."
                            },
                            "language": {
                                "type": "string",
                                "description": "Language of the code: 'python' or 'shell' (default 'python')."
                            },
                            "timeout": {
                                "type": "number",
                                "description": "Maximum execution time in seconds (default 30.0, max 120.0)."
                            },
                            "rollback_on_failure": {
                                "type": "boolean",
                                "description": "Whether to automatically rollback filesystem state to pre-execution snapshot if execution fails (default true)."
                            }
                        },
                        "required": ["code"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "sandbox_snapshot_create",
                    "description": "EXECUTION SANDBOX (Genesis Level 6): Takes an immediate point-in-time filesystem snapshot of the workspace with SHA-256 integrity hashes for safe rollback.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "description": "Name / label for the snapshot (e.g. 'pre_refactor_migration')."
                            }
                        },
                        "required": ["name"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "sandbox_snapshot_rollback",
                    "description": "EXECUTION SANDBOX (Genesis Level 6): Restores workspace files to a previously saved snapshot, reverting modifications, additions, and deletions.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "description": "Name of the snapshot to restore."
                            }
                        },
                        "required": ["name"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "drift_record_task",
                    "description": "DRIFT MONITORING (Genesis Level 9): Logs task execution telemetry (success, steps, latency, tokens, failed tools) for continuous quality regression tracking.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "task_id": {
                                "type": "string",
                                "description": "Unique identifier for the task or session."
                            },
                            "success": {
                                "type": "boolean",
                                "description": "Whether the task succeeded or failed."
                            },
                            "steps": {
                                "type": "integer",
                                "description": "Total steps / tool actions executed (default 1)."
                            },
                            "duration_sec": {
                                "type": "number",
                                "description": "Elapsed duration in seconds."
                            },
                            "tokens_used": {
                                "type": "integer",
                                "description": "Approximate token spend for this task."
                            },
                            "failed_tools": {
                                "type": "string",
                                "description": "Comma-separated list of tool names that failed during execution."
                            },
                            "category": {
                                "type": "string",
                                "description": "Task domain / category (e.g. coding, git, web, reasoning)."
                            }
                        },
                        "required": ["task_id", "success"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "drift_check",
                    "description": "DRIFT MONITORING (Genesis Level 9): Analyzes historical task telemetry for quality regression, success-rate drop, step inflation, and tool failure clusters.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "window_size": {
                                "type": "integer",
                                "description": "Number of recent tasks to evaluate against baseline (default 10)."
                            },
                            "threshold_drop": {
                                "type": "number",
                                "description": "Success rate drop threshold for warning alert (default 0.20 for 20% drop)."
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "drift_status",
                    "description": "DRIFT MONITORING (Genesis Level 9): Displays longitudinal telemetry summary, total recorded tasks, and health status.",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "self_improve_analyze_failure",
                    "description": "SELF-IMPROVEMENT (Genesis Level 10): Analyzes a failed task log, diagnoses root cause, and extracts a prescriptive operational rule/lesson.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "task_id": {
                                "type": "string",
                                "description": "Identifier of the failed task."
                            },
                            "prompt": {
                                "type": "string",
                                "description": "The original task prompt."
                            },
                            "failure_log": {
                                "type": "string",
                                "description": "Execution traceback, error messages, or failure explanation."
                            },
                            "failed_tools": {
                                "type": "string",
                                "description": "Comma-separated names of tools that failed."
                            },
                            "category": {
                                "type": "string",
                                "description": "Task domain (e.g. coding, git, reasoning, general)."
                            }
                        },
                        "required": ["task_id", "prompt", "failure_log"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "self_improve_eval_run",
                    "description": "SELF-IMPROVEMENT (Genesis Level 10): Runs the automated regression eval benchmark suite, reporting pass rates, scores, and regressions.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "category": {
                                "type": "string",
                                "description": "Optional category filter: coding, reasoning, security, git (or leave empty for all)."
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "self_improve_crystallize_lesson",
                    "description": "SELF-IMPROVEMENT (Genesis Level 10): Permanently records an extracted lesson into the Skill playbook library and Knowledge Graph.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "lesson_title": {
                                "type": "string",
                                "description": "Summary title of the learned rule / playbook."
                            },
                            "guidance": {
                                "type": "string",
                                "description": "Prescriptive workflow instructions and best practices to prevent future failure."
                            },
                            "category": {
                                "type": "string",
                                "description": "Domain category (e.g. coding, git, docker, general)."
                            }
                        },
                        "required": ["lesson_title", "guidance"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "docker_sandbox_run",
                    "description": "Runs code or shell commands inside an isolated, disposable Docker container with resource limits and optional workspace mounting.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "command": {
                                "type": "string",
                                "description": "The command to run inside the container (e.g. 'python -c \"print(1+1)\"' or 'sh -c \"ls -la\"')."
                            },
                            "image": {
                                "type": "string",
                                "description": "Docker image to use (default: 'python:3.12-slim'). Options: python:3.12-slim, node:20-slim, alpine:latest, ubuntu:22.04."
                            },
                            "memory_limit": {
                                "type": "string",
                                "description": "Memory limit for the container (e.g. '256m', '512m', '1g'). Default: '512m'."
                            },
                            "cpu_quota": {
                                "type": "string",
                                "description": "CPU quota / max CPUs (e.g. '0.5', '1.0'). Default: '1.0'."
                            },
                            "mount_workspace": {
                                "type": "boolean",
                                "description": "Whether to mount the host workspace directory to /workspace inside the container. Default: false."
                            },
                            "network": {
                                "type": "string",
                                "description": "Container network mode ('none' for airgapped sandbox, 'bridge' for internet). Default: 'bridge'."
                            },
                            "timeout": {
                                "type": "number",
                                "description": "Execution timeout in seconds. Default: 60.0."
                            }
                        },
                        "required": ["command"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "apply_patch",
                    "description": "Applies a unified diff patch to one or more files in the workspace with automatic hunk matching and safe rollback on error.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "patch": {
                                "type": "string",
                                "description": "The unified diff patch string (containing '---', '+++', and '@@' hunk headers)."
                            }
                        },
                        "required": ["patch"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "skill_save",
                    "description": "Creates or updates a persistent skill playbook in the skills library. Auto-loaded in future sessions matching the keywords.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "description": "Skill name / slug (e.g. 'docker-deploy', 'api-refactor')."
                            },
                            "description": {
                                "type": "string",
                                "description": "One-line description of the skill."
                            },
                            "keywords": {
                                "type": "string",
                                "description": "Comma-separated keywords for automatic injection matching."
                            },
                            "guidance": {
                                "type": "string",
                                "description": "Full markdown guidance body containing workflow steps and best practices."
                            }
                        },
                        "required": ["name", "guidance"]
                    }
                }
            }
            ,
            {
                "type": "function",
                "function": {
                    "name": "ast_patch_file",
                    "description": "Applies a targeted text replacement to a file and validates the resulting Python AST to ensure no syntax errors were introduced. Safer than normal editing for Python files.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "Path to the file to modify."},
                            "search_block": {"type": "string", "description": "The exact block of code to search for."},
                            "replace_block": {"type": "string", "description": "The new block of code to replace it with."}
                        },
                        "required": ["path", "search_block", "replace_block"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "deep_verify_code",
                    "description": "Runs a Deep Verification Loop on target code: generates tests, runs them in the sandbox, and heals the code if they fail.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "code": {"type": "string", "description": "The raw code to verify."},
                            "intent": {"type": "string", "description": "What the code is supposed to do."}
                        },
                        "required": ["code", "intent"]
                    }
                }
            }
        ]
        base_defs.extend([
            {
                "type": "function",
                "function": {
                    "name": "vector_rag_index",
                    "description": "Indexes the entire workspace into the Semantic Vector Database (ChromaDB) for advanced RAG.",
                    "parameters": {"type": "object", "properties": {}, "required": []}
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "vector_rag_search",
                    "description": "Searches the Semantic Vector Database for deeply relevant code snippets and context.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "The search query (natural language)."},
                            "top_k": {"type": "integer", "description": "Number of results to return (default 5)."}
                        },
                        "required": ["query"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "sast_scan",
                    "description": "Performs Static Application Security Testing (SAST) & OWASP Top 10 code audit on source code.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "code": {"type": "string", "description": "The source code string to audit."},
                            "filename": {"type": "string", "description": "Optional filename (e.g. app.py, handler.js)."}
                        },
                        "required": ["code"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "dependency_audit",
                    "description": "Audits dependencies and package manifests (requirements.txt, package.json) for known vulnerabilities (CVEs).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "manifest_file": {"type": "string", "description": "Path to dependency manifest (default: requirements.txt)."}
                        },
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "secret_scan",
                    "description": "Scans text, code, or logs for hardcoded API keys, tokens, and high-entropy credentials.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "text": {"type": "string", "description": "Text or code to scan for secrets."}
                        },
                        "required": ["text"]
                    }
                }
            }
        ])
        from .browser_automation import BrowserAutomation
        browser_defs = BrowserAutomation(self.workspace).get_tool_definitions()
        return base_defs + browser_defs

    @property
    def vector_rag(self):
        if getattr(self, "_vector_rag", None) is None:
            from .vector_rag import VectorRAG
            self._vector_rag = VectorRAG(self.workspace)
        return self._vector_rag

    def tool_vector_rag_index(self) -> str:
        return self.vector_rag.index_workspace()

    def tool_vector_rag_search(self, query: str, top_k: int = 5) -> str:
        return self.vector_rag.search(query, top_k)

    @property
    def browser_automation(self):
        if getattr(self, "_browser_automation", None) is None:
            from .browser_automation import BrowserAutomation
            self._browser_automation = BrowserAutomation(self.workspace)
        return self._browser_automation

    async def tool_browser_goto(self, url: str) -> str:
        return await self.browser_automation.tool_browser_goto(url)

    async def tool_browser_click(self, selector: str) -> str:
        return await self.browser_automation.tool_browser_click(selector)

    async def tool_browser_type(self, selector: str, text: str) -> str:
        return await self.browser_automation.tool_browser_type(selector, text)

    async def tool_browser_screenshot(self, filename: str = "screenshot.png") -> str:
        return await self.browser_automation.tool_browser_screenshot(filename)

    async def tool_browser_extract_text(self) -> str:
        return await self.browser_automation.tool_browser_extract_text()

    async def tool_browser_close(self) -> str:
        return await self.browser_automation.tool_browser_close()

    def tool_sast_scan(self, code: str, filename: str = "code.py") -> str:
        """Run SAST & OWASP Top 10 code audit."""
        from titan_agent.core.security.sast import SASTScanner
        report = SASTScanner().scan_code(code, filename=filename)
        if not report.findings:
            return "✅ SAST Scan Clean: No OWASP security issues detected."
        
        lines = [f"🛡️ **SAST & OWASP Security Report ({report.total_findings} findings)**:"]
        for f in report.findings:
            lines.append(f"- **[{f.severity}]** `{f.rule_id}` (line {f.line}): {f.title}")
            lines.append(f"  *Snippet:* `{f.snippet}`")
            lines.append(f"  *Fix:* {f.remediation}")
        return "\n".join(lines)

    def tool_dependency_audit(self, manifest_file: str = "requirements.txt") -> str:
        """Audit package manifests for vulnerabilities."""
        from titan_agent.core.security.dependency_auditor import DependencyAuditor
        target = self._resolve_path(manifest_file)
        if not target.is_file():
            # Check default workspace root
            target = self.workspace / manifest_file
        report = DependencyAuditor().audit_manifest_file(target)
        if not report.alerts:
            return f"✅ Dependency Audit Clean: {report.total_dependencies} dependencies analyzed, 0 known CVEs found."

        lines = [f"🛡️ **Supply-Chain Dependency Audit ({report.vulnerable_count} alerts)**:"]
        for a in report.alerts:
            lines.append(f"- **[{a.severity}]** `{a.package}` ({a.installed_spec})")
            lines.append(f"  *Advisory:* {a.advisory}")
            lines.append(f"  *Fix:* {a.recommendation}")
        return "\n".join(lines)

    def tool_secret_scan(self, text: str) -> str:
        """Scan text or code for high-entropy secrets and sensitive tokens."""
        from titan_agent.core.security.secret_scanner import SecretScanner
        scanner = SecretScanner()
        findings = scanner.scan(text)
        if not findings:
            return "✅ Secret Scan Clean: No exposed credentials or private keys detected."

        lines = [f"🚨 **Secret Scanner Alert ({len(findings)} secrets detected)**:"]
        for f in findings:
            masked = f.match[:4] + "..." if len(f.match) > 8 else "***"
            lines.append(f"- **[{f.severity}]** {f.secret_type}: `{masked}` (Entropy: {f.entropy})")
        lines.append(f"\n🔒 **Sanitized Redaction Preview:**\n```\n{scanner.redact(text)}\n```")
        return "\n".join(lines)

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

    async def tool_ast_patch_file(self, path: str, search_block: str, replace_block: str) -> str:
        from titan_agent.core.code_intel.ast_patcher import ASTPatcher, ASTPatchError
        target = self._resolve_path(path)
        if not target.exists():
            return f"Error: File {target} not found."
        original = target.read_text(encoding="utf-8")
        try:
            new_code = ASTPatcher.apply_replacement(original, search_block, replace_block)
            target.write_text(new_code, encoding="utf-8")
            return f"AST Patch applied successfully to {target}."
        except ASTPatchError as e:
            return f"Error applying AST patch: {e}"

    async def tool_deep_verify_code(self, code: str, intent: str) -> str:
        from titan_agent.core.verification.deep_verifier import DeepVerifier
        from titan_agent.llm_client import LLMClient
        llm = LLMClient()
        
        async def runner(script: str) -> str:
            return await self.tool_docker_sandbox_run(
                command=f"python -c {shlex.quote(script)}",
                image="python:3.11-slim",
                timeout=60.0,
            )
            
        verifier = DeepVerifier(llm, sandbox_runner=runner)
        result = await verifier.self_heal_loop(code, intent, max_iterations=3)
        if result["verified"]:
            return f"Deep Verify SUCCEEDED! Verified Code:\n{result['code']}\n\nFinal Output:\n{result['final_output']}"
        else:
            return f"Deep Verify FAILED after {result['iterations']} iterations.\nLast Output:\n{result['final_output']}\nLast Code:\n{result['code']}"


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
        return _subagent_result_text(res)

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
        return "\n\n".join(_subagent_result_text(r) for r in results)

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

    # ---- Phase 22 Genesis: Hierarchical Organization Tools ----

    async def tool_orchestrator_run(
        self,
        goal: str,
        departments: list[str] | None = None,
    ) -> str:
        from .orchestrator import MetaOrchestrator

        if not goal or not str(goal).strip():
            return "Error: goal is required."
        orch = getattr(self, "_meta_orchestrator", None)
        if orch is None:
            orch = MetaOrchestrator()
            self._meta_orchestrator = orch
        res = await orch.orchestrate(str(goal).strip(), departments=departments)
        return res.synthesis

    async def tool_team_delegate(
        self,
        department: str,
        task: str,
        role: str = "",
    ) -> str:
        from .team_leads import build_team_leads

        if not task or not str(task).strip():
            return "Error: task is required."
        dep = str(department or "engineering").strip().lower()
        leads = getattr(self, "_team_leads", None)
        if leads is None:
            leads = build_team_leads()
            self._team_leads = leads

        lead = leads.get(dep)
        if not lead:
            return f"Error: unknown department '{department}'. Choose from: engineering, research, operations, quality_security."

        res = await lead.execute_task(task=str(task).strip(), role=str(role).strip() if role else None)
        notes = f" (Notes: {', '.join(res.verification_notes)})" if res.verification_notes else ""
        return f"### TEAM DELIVERABLE: {lead.name} [{res.verification_verdict}]{notes}\nAssigned worker: {res.assigned_role}\n\n{res.output}"

    def tool_team_status(self) -> str:
        from .orchestrator import MetaOrchestrator

        orch = getattr(self, "_meta_orchestrator", None)
        if orch is None:
            orch = MetaOrchestrator()
            self._meta_orchestrator = orch

        b = orch.budget.summary()
        lines = [
            "### TITAN HIERARCHICAL ORGANIZATION STATUS",
            f"- **Meta-Orchestrator**: Active (Tokens spent: {b['total_tokens_spent']}, Steps spent: {b['total_steps_spent']})",
            f"- **Active Goal**: {orch.goal_memory.project_goal or '(None)'}",
            f"- **Milestones**: {len(orch.goal_memory.milestones)} recorded",
            "",
            "### DEPARTMENT LEADS (Level 2):",
        ]
        for dep, lead in orch.leads.items():
            lines.append(f"- **{lead.name}** (`{dep}`): Managing {len(lead.managed_roles)} roles ({', '.join(lead.managed_roles)})")

        return "\n".join(lines)

    async def tool_dag_plan_and_run(self, goal: str) -> str:
        from .orchestrator import MetaOrchestrator

        if not goal or not str(goal).strip():
            return "Error: goal is required."
        orch = getattr(self, "_meta_orchestrator", None)
        if orch is None:
            orch = MetaOrchestrator()
            self._meta_orchestrator = orch

        res = await orch.orchestrate_dag(str(goal).strip())
        self._last_dag_result = res
        return res.summary

    async def tool_dag_visualize(self, goal: str) -> str:
        from .core.dag import DAGPlanner

        if not goal or not str(goal).strip():
            return "Error: goal is required."
        planner = DAGPlanner()
        graph = await planner.create_dag_plan(str(goal).strip())
        mermaid = graph.to_mermaid()
        return f"### TASK GRAPH (DAG) VISUALIZATION\n```mermaid\n{mermaid}\n```\n\n**Topological Order**: {' -> '.join(graph.topological_sort())}"

    async def tool_debate_solve(self, question: str, rounds: int = 2) -> str:
        from .core.reasoning.debate import DebateEngine
        from .llm_client import LLMClient
        from .structured import LLMBridge

        if not question or not str(question).strip():
            return "Error: question is required."
        client = getattr(self, "_llm_client", None) or LLMClient()
        engine = DebateEngine(LLMBridge(client))
        res = await engine.run_debate(str(question).strip(), rounds=int(rounds or 2))
        return res.summary()

    async def tool_reflexion_solve(self, task: str) -> str:
        from .core.reasoning.reflexion import ReflexionEngine
        from .llm_client import LLMClient
        from .structured import LLMBridge

        if not task or not str(task).strip():
            return "Error: task is required."
        client = getattr(self, "_llm_client", None) or LLMClient()
        engine = ReflexionEngine(LLMBridge(client))
        res = await engine.run(str(task).strip(), max_cycles=3)
        status_line = f"Reflexion completed in {res.total_cycles} cycles (Verdict: {'PASS' if res.success else 'FAILED'}, Improved: {res.improved})"
        return f"### REFLEXION OUTCOME [{status_line}]\n\n{res.final_output}"

    @property
    def memory(self):
        if getattr(self, "_memory_mgr", None) is None:
            from .memory import MemoryManager
            self._memory_mgr = MemoryManager()
        return self._memory_mgr

    def tool_kg_query(self, entity_id: str, depth: int = 2) -> str:
        """KNOWLEDGE GRAPH: Queries the causal/dependency knowledge graph around an entity."""
        if not entity_id or not str(entity_id).strip():
            return "Error: entity_id is required."
        if not self.memory.knowledge_graph.entities:
            from .core.memory import WorkspaceASTGraphExtractor
            extractor = WorkspaceASTGraphExtractor(self.workspace)
            extractor.extract(kg=self.memory.knowledge_graph, max_files=50)

        res = self.memory.query_kg(str(entity_id).strip(), depth=int(depth or 2))
        lines = [f"### KNOWLEDGE GRAPH QUERY: {entity_id} ({res['total_connections']} connection(s))"]
        for c in res["connections"]:
            lines.append(f"- ({c['source']}) --[{c['relation']}]--> ({c['target']}) [neighbor: {c['neighbor_name']} ({c['neighbor_type']})]")
        if not res["connections"]:
            lines.append("No connections found for entity in knowledge graph.")
        return "\n".join(lines)

    def tool_kg_impact_analysis(self, entity_id: str) -> str:
        """KNOWLEDGE GRAPH: Computes downstream impact and blast radius if an entity is modified."""
        if not entity_id or not str(entity_id).strip():
            return "Error: entity_id is required."
        if not self.memory.knowledge_graph.entities:
            from .core.memory import WorkspaceASTGraphExtractor
            extractor = WorkspaceASTGraphExtractor(self.workspace)
            extractor.extract(kg=self.memory.knowledge_graph, max_files=50)

        res = self.memory.kg_impact(str(entity_id).strip())
        lines = [
            f"### KNOWLEDGE GRAPH IMPACT ANALYSIS: {entity_id}",
            f"- Direct Dependents: {len(res['direct_dependents'])} ({', '.join(res['direct_dependents']) if res['direct_dependents'] else 'none'})",
            f"- Total Blast Radius: {len(res['total_impacted_entities'])} entities",
            f"- Max Cascade Depth: {res['depth_reached']}",
        ]
        if res["total_impacted_entities"]:
            lines.append("\n**All Impacted Entities**:")
            for ent in res["total_impacted_entities"]:
                lines.append(f"- {ent}")
        return "\n".join(lines)

    def tool_kg_add_fact(self, source: str, relation: str, target: str) -> str:
        """KNOWLEDGE GRAPH: Adds a semantic fact or causal dependency between two entities."""
        if not source or not str(source).strip():
            return "Error: source is required."
        if not relation or not str(relation).strip():
            return "Error: relation is required."
        if not target or not str(target).strip():
            return "Error: target is required."
        s, r, t = str(source).strip(), str(relation).strip(), str(target).strip()
        self.memory.add_kg_fact(s, r, t)
        return f"Successfully added knowledge graph fact: ({s}) --[{r}]--> ({t})"

    def tool_kg_index_workspace(self, max_files: int = 50) -> str:
        """KNOWLEDGE GRAPH: Scans workspace ASTs to build knowledge graph."""
        from .core.memory import WorkspaceASTGraphExtractor
        extractor = WorkspaceASTGraphExtractor(self.workspace)
        kg = extractor.extract(kg=self.memory.knowledge_graph, max_files=int(max_files or 50))
        self.memory.knowledge_graph.save()
        return f"Indexed workspace AST into Knowledge Graph: {len(kg.entities)} entities, {len(kg.relations)} relations."

    @property
    def reliability_tracker(self):
        from .tool_stats import TOOL_RELIABILITY
        return TOOL_RELIABILITY

    def tool_discover(self, query: str, category: str = "", limit: int = 8) -> str:
        """DYNAMIC TOOLS: Searches and discovers available tools by keyword/category."""
        if not query or not str(query).strip():
            return "Error: query is required."
        from .core.tools.dynamic_registry import DynamicToolSelector
        defs = self.get_tool_definitions()
        matches = DynamicToolSelector.discover_tools(
            str(query).strip(),
            defs,
            category=str(category).strip(),
            limit=int(limit or 8),
        )
        if not matches:
            return f"No tools found matching query '{query}'."

        lines = [f"### DISCOVERED TOOLS ({len(matches)} matches for '{query}'):"]
        for td in matches:
            fn = td.get("function", td)
            name = fn.get("name", "unknown")
            desc = fn.get("description", "").split("\n")[0][:120]
            grade = self.reliability_tracker.get_grade(name)
            score = self.reliability_tracker.get_score(name)
            lines.append(f"- **{name}** [Grade {grade} ({score:.2f})]: {desc}")
        return "\n".join(lines)

    def tool_reliability_report(self) -> str:
        """TOOL RELIABILITY: Reports EWMA scores, grades, and mitigation advice."""
        return self.reliability_tracker.format_report_text()

    @property
    def model_router(self):
        if getattr(self, "_model_router", None) is None:
            from .core.routing import ModelRouter
            self._model_router = ModelRouter()
        return self._model_router

    @property
    def budget_tracker(self):
        if getattr(self, "_budget_tracker", None) is None:
            from .core.routing import CognitiveBudgetTracker
            self._budget_tracker = CognitiveBudgetTracker()
        return self._budget_tracker

    def tool_model_route(self, task: str, prior_failures: int = 0) -> str:
        """MODEL ROUTER: Analyzes task and returns recommended model tier and pricing."""
        if not task or not str(task).strip():
            return "Error: task is required."
        decision = self.model_router.route(str(task).strip(), prior_failures=int(prior_failures or 0))
        lines = [
            f"### MODEL ROUTE DECISION: `{decision.model_name}` [{decision.tier.value.upper()}]",
            f"- **Rationale**: {decision.rationale}",
            f"- **Input Pricing**: ${decision.estimated_input_cost_per_1k:.5f} / 1k tokens",
            f"- **Output Pricing**: ${decision.estimated_output_cost_per_1k:.5f} / 1k tokens",
            f"- **Escalated**: {decision.is_escalated}",
        ]
        return "\n".join(lines)

    def tool_model_budget_status(self) -> str:
        """COGNITIVE BUDGET: Reports cumulative token usage and USD expenditure."""
        return self.budget_tracker.format_status_text()

    @property
    def sandbox_env(self):
        if getattr(self, "_sandbox_env", None) is None:
            from .core.sandbox import SandboxEnvironment
            self._sandbox_env = SandboxEnvironment(self.workspace)
        return self._sandbox_env

    @property
    def safe_runner(self):
        if getattr(self, "_safe_runner", None) is None:
            from .core.sandbox import SafeScriptRunner
            self._safe_runner = SafeScriptRunner(self.workspace, sandbox_env=self.sandbox_env)
        return self._safe_runner

    def tool_sandbox_snapshot_create(self, name: str) -> str:
        """Creates an immediate point-in-time filesystem snapshot of the workspace."""
        if not name or not str(name).strip():
            return "Error: snapshot name is required."
        snap = self.sandbox_env.create_snapshot(str(name).strip())
        return (
            f"### WORKSPACE SNAPSHOT CREATED: `{snap.name}`\n"
            f"- Total files indexed: {len(snap.file_hashes)}\n"
            f"- Timestamp: {snap.timestamp}\n"
            f"- Root path: `{snap.root_path}`"
        )

    def tool_sandbox_snapshot_rollback(self, name: str) -> str:
        """Reverts workspace files to a previously captured snapshot."""
        if not name or not str(name).strip():
            return "Error: snapshot name is required."
        report = self.sandbox_env.rollback(str(name).strip())
        return (
            f"### WORKSPACE ROLLBACK EXECUTED [{name}]:\n"
            f"- Restored files: {len(report['restored'])}\n"
            f"- Deleted newly-created files: {len(report['deleted_new'])}\n"
            f"- Status: {'SUCCESS' if report['success'] else 'FAILED'}"
        )

    def tool_sandbox_execute(
        self,
        code: str,
        language: str = "python",
        timeout: float = 30.0,
        rollback_on_failure: bool = True,
    ) -> str:
        """Safely executes code in the sandbox with timeout and optional auto-rollback."""
        if not code or not str(code).strip():
            return "Error: code is required."
        res = self.safe_runner.run(
            code=code,
            language=str(language or "python"),
            timeout=float(timeout or 30.0),
            auto_rollback=bool(rollback_on_failure),
        )
        lines = [
            f"### SANDBOX EXECUTION RESULT ({res.language.upper()} | Exit {res.exit_code}):",
            f"- **Success**: {res.success}",
            f"- **Execution Time**: {res.duration_sec:.2f}s",
            f"- **Auto-Rolled Back**: {res.rolled_back}",
        ]
        if res.error:
            lines.append(f"- **Error / Alert**: {res.error}")
        if res.stdout:
            lines.append(f"\nSTDOUT:\n{res.stdout}")
        if res.stderr:
            lines.append(f"\nSTDERR:\n{res.stderr}")
        return "\n".join(lines)

    @property
    def drift_detector(self):
        if getattr(self, "_drift_detector", None) is None:
            from .core.monitoring import QualityDriftDetector
            storage = self.workspace / ".titan" / "drift_metrics.json"
            self._drift_detector = QualityDriftDetector(storage_path=storage)
        return self._drift_detector

    def tool_drift_record_task(
        self,
        task_id: str,
        success: bool,
        steps: int = 1,
        duration_sec: float = 1.0,
        tokens_used: int = 0,
        failed_tools: str = "",
        category: str = "general",
    ) -> str:
        """Logs task execution telemetry for continuous quality regression tracking."""
        if not task_id or not str(task_id).strip():
            return "Error: task_id is required."
        ft_list = [t.strip() for t in str(failed_tools or "").split(",") if t.strip()]
        metric = self.drift_detector.record_task(
            task_id=str(task_id).strip(),
            success=bool(success),
            steps=int(steps or 1),
            duration_sec=float(duration_sec or 1.0),
            tokens_used=int(tokens_used or 0),
            failed_tools=ft_list,
            category=str(category or "general"),
        )
        status_str = "SUCCESS" if metric.success else "FAILED"
        return (
            f"### DRIFT TELEMETRY RECORDED: `{metric.task_id}` [{status_str}]\n"
            f"- Category: {metric.category} | Steps: {metric.steps} | Duration: {metric.duration_sec:.2f}s\n"
            f"- Tokens: {metric.tokens_used} | Failed Tools: {', '.join(metric.failed_tools) or 'None'}\n"
            f"- Total historical records: {len(self.drift_detector.get_metrics())}"
        )

    def tool_drift_check(
        self,
        window_size: int = 10,
        threshold_drop: float = 0.20,
    ) -> str:
        """Analyzes historical task telemetry for quality regression and drift."""
        report = self.drift_detector.check_drift(
            window_size=int(window_size or 10),
            threshold_drop=float(threshold_drop or 0.20),
        )
        return report.format_report_text()

    def tool_drift_status(self) -> str:
        """Displays longitudinal telemetry summary and drift health status."""
        metrics = self.drift_detector.get_metrics()
        if not metrics:
            return "### DRIFT TELEMETRY: No task metrics recorded yet."
        successes = sum(1 for m in metrics if m.success)
        total = len(metrics)
        rate = (successes / total) * 100.0 if total > 0 else 0.0
        avg_steps = sum(m.steps for m in metrics) / total if total > 0 else 0.0
        avg_dur = sum(m.duration_sec for m in metrics) / total if total > 0 else 0.0
        last = metrics[-1]
        return (
            f"### DRIFT TELEMETRY STATUS (Total Tasks: {total})\n"
            f"- Cumulative Success Rate: {rate:.1f}% ({successes}/{total})\n"
            f"- Average Steps: {avg_steps:.1f} steps/task\n"
            f"- Average Latency: {avg_dur:.2f}s\n"
            f"- Most Recent Task: `{last.task_id}` ({'SUCCESS' if last.success else 'FAILED'}, {last.steps} steps)"
        )

    @property
    def self_improvement_loop(self):
        if getattr(self, "_self_improvement_loop", None) is None:
            from .core.self_improvement import SelfImprovementLoop
            self._self_improvement_loop = SelfImprovementLoop(workspace_root=self.workspace)
        return self._self_improvement_loop

    @property
    def eval_suite(self):
        if getattr(self, "_eval_suite", None) is None:
            from .core.self_improvement import EvalSuite
            self._eval_suite = EvalSuite()
        return self._eval_suite

    def tool_self_improve_analyze_failure(
        self,
        task_id: str,
        prompt: str,
        failure_log: str,
        failed_tools: str = "",
        category: str = "general",
    ) -> str:
        """Analyzes a failed task, diagnoses root cause, and synthesizes a prescriptive rule."""
        if not task_id or not str(task_id).strip():
            return "Error: task_id is required."
        if not prompt or not str(prompt).strip():
            return "Error: prompt is required."
        if not failure_log or not str(failure_log).strip():
            return "Error: failure_log is required."

        ft_list = [t.strip() for t in str(failed_tools or "").split(",") if t.strip()]
        lesson = self.self_improvement_loop.analyze_failure(
            task_id=str(task_id).strip(),
            prompt=str(prompt).strip(),
            failure_log=str(failure_log).strip(),
            failed_tools=ft_list,
            category=str(category or "general"),
        )
        return (
            f"### FAILURE ANALYSIS & LESSON LEARNED [{lesson.category.upper()}]\n"
            f"- **Task ID**: `{lesson.task_id}`\n"
            f"- **Root Cause**: {lesson.root_cause}\n"
            f"- **Guidance**: {lesson.guidance}\n"
            f"- **Extracted Rule**: > {lesson.rule_text}"
        )

    def tool_self_improve_eval_run(self, category: str = "") -> str:
        """Executes automated benchmark evaluation suite to verify capability and catch regressions."""
        cat = str(category or "").strip()
        report = self.eval_suite.run_suite(category=cat)
        lines = [
            f"### EVAL BENCHMARK RESULTS (Category: '{cat or 'all'}')",
            f"- **Pass Rate**: {report['pass_rate']}% ({report['passed']}/{report['total_cases']} cases passed)",
            f"- **Average Quality Score**: {report['average_score']:.2f} / 1.0",
            f"- **Average Duration**: {report['average_duration_sec']:.3f}s",
            "\nCases Summary:",
        ]
        for r in report["results"]:
            status_symbol = "✓ PASS" if r["passed"] else "✗ FAIL"
            lines.append(f"  • `{r['case_id']}`: {status_symbol} (Score: {r['score']})")
            if r.get("error"):
                lines.append(f"    - Error: {r['error']}")
        return "\n".join(lines)

    def tool_self_improve_crystallize_lesson(
        self,
        lesson_title: str,
        guidance: str,
        category: str = "general",
    ) -> str:
        """Permanently records an extracted lesson into the Skill playbook library and Knowledge Graph."""
        if not lesson_title or not str(lesson_title).strip():
            return "Error: lesson_title is required."
        if not guidance or not str(guidance).strip():
            return "Error: guidance is required."

        from .core.self_improvement import ImprovementLesson
        lesson = ImprovementLesson(
            task_id=f"manual_{int(time.time())}",
            category=str(category or "general").strip(),
            symptom=f"Learned rule: {lesson_title}",
            root_cause=str(lesson_title).strip(),
            guidance=str(guidance).strip(),
            rule_text=f"RULE [{category.upper()}]: {guidance}",
        )
        kg = getattr(self, "_kg", None)
        status = self.self_improvement_loop.crystallize_lesson(
            lesson,
            knowledge_graph=kg,
        )
        skill_name = status.get("skill_name", "unknown")
        return (
            f"### LESSON CRYSTALLIZED SUCCESSFULLY\n"
            f"- Saved as Skill Playbook: `{skill_name}` (Auto-injectable)\n"
            f"- Knowledge Graph Fact Added: {status.get('knowledge_fact_added', False)}\n"
            f"- Rule: {lesson.rule_text}"
        )

    async def tool_docker_sandbox_run(
        self,
        command: str,
        image: str = "python:3.12-slim",
        memory_limit: str = "512m",
        cpu_quota: str = "1.0",
        mount_workspace: bool = False,
        network: str = "bridge",
        timeout: float = 60.0,
    ) -> str:
        """Execute a shell command inside an isolated ephemeral Docker container."""
        if not command or not str(command).strip():
            return "Error: command is required."
        img = str(image or "python:3.12-slim").strip()
        mem = str(memory_limit or "512m").strip()
        cpus = str(cpu_quota or "1.0").strip()
        net = str(network or "bridge").strip()
        t = max(1.0, min(float(timeout or 60.0), 300.0))

        docker_bin = shutil.which("docker")
        if not docker_bin:
            return "Error: docker executable not found on host. Ensure Docker Desktop or docker engine is installed and in PATH."

        cmd = [
            docker_bin,
            "run",
            "--rm",
            f"--memory={mem}",
            f"--cpus={cpus}",
            f"--network={net}",
        ]
        if mount_workspace:
            cmd.extend(["-v", f"{self.workspace.resolve()}:/workspace", "-w", "/workspace"])

        cmd.extend([img, "sh", "-c", command])

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=t)
            out_str = stdout.decode("utf-8", errors="ignore").strip()
            err_str = stderr.decode("utf-8", errors="ignore").strip()
            res = [f"### DOCKER SANDBOX [{img}] (Exit {proc.returncode})"]
            if out_str:
                res.append(f"STDOUT:\n{out_str}")
            if err_str:
                res.append(f"STDERR:\n{err_str}")
            if not out_str and not err_str:
                res.append("(No output produced)")
            return "\n".join(res)
        except asyncio.TimeoutError:
            return f"Error: Docker container execution timed out after {t:.0f}s."
        except Exception as e:  # noqa: BLE001
            return f"Docker execution error: {e!s}"

    def tool_apply_patch(self, patch: str) -> str:
        """Applies a unified diff patch to files in the workspace."""
        if not patch or not str(patch).strip():
            return "Error: patch is required."

        lines = patch.strip().splitlines()
        file_diffs: list[tuple[str, list[list[str]]]] = []
        cur_file = None
        cur_hunks: list[list[str]] = []
        cur_hunk: list[str] | None = None

        for line in lines:
            if line.startswith("--- "):
                pass
            elif line.startswith("+++ "):
                raw_path = line[4:].strip().removeprefix("b/")
                if cur_file and cur_hunks:
                    file_diffs.append((cur_file, cur_hunks))
                cur_file = raw_path
                cur_hunks = []
                cur_hunk = None
            elif line.startswith("@@"):
                if cur_hunk is not None:
                    cur_hunks.append(cur_hunk)
                cur_hunk = []
            elif cur_hunk is not None:
                cur_hunk.append(line)
        if cur_file and cur_hunk is not None:
            cur_hunks.append(cur_hunk)
            file_diffs.append((cur_file, cur_hunks))

        if not file_diffs:
            return "Error: No valid unified diff hunks found in patch."

        applied_files = []
        for rel_path, hunks in file_diffs:
            fpath = self._resolve_path(rel_path)
            orig_text = ""
            if fpath.exists():
                orig_text = fpath.read_text(encoding="utf-8", errors="ignore")

            orig_lines = orig_text.splitlines()
            new_lines = list(orig_lines)

            for hunk in hunks:
                old_hunk_lines = [l[1:] for l in hunk if l.startswith(("-", " "))]
                new_hunk_lines = [l[1:] for l in hunk if l.startswith(("+", " "))]

                match_idx = -1
                hunk_len = len(old_hunk_lines)
                if hunk_len == 0:
                    new_lines.extend(new_hunk_lines)
                    continue

                for i in range(len(new_lines) - hunk_len + 1):
                    if new_lines[i : i + hunk_len] == old_hunk_lines:
                        match_idx = i
                        break

                if match_idx == -1:
                    stripped_old = [l.strip() for l in old_hunk_lines]
                    for i in range(len(new_lines) - hunk_len + 1):
                        if [l.strip() for l in new_lines[i : i + hunk_len]] == stripped_old:
                            match_idx = i
                            break

                if match_idx != -1:
                    new_lines[match_idx : match_idx + hunk_len] = new_hunk_lines
                else:
                    return f"Error: Patch conflict in '{rel_path}' - hunk could not be matched."

            fpath.parent.mkdir(parents=True, exist_ok=True)
            ends_newline = orig_text.endswith("\n") or not orig_text
            fpath.write_text("\n".join(new_lines) + ("\n" if ends_newline else ""), encoding="utf-8")
            applied_files.append(rel_path)

        return f"### PATCH APPLIED SUCCESSFULLY\nModified files: {', '.join(applied_files)} ({len(file_diffs)} file(s))"

    def tool_skill_save(
        self,
        name: str,
        guidance: str,
        description: str = "",
        keywords: str = "",
    ) -> str:
        """Creates or updates a persistent skill playbook in the skills library."""
        from .skills import SkillRegistry

        if not name or not str(name).strip():
            return "Error: skill name is required."
        if not guidance or not str(guidance).strip():
            return "Error: skill guidance is required."
        registry = SkillRegistry()
        try:
            path = registry.save_skill(name, description, keywords, guidance)
            return f"Skill '{name}' saved successfully to {path.name} ({len(guidance)} chars guidance). It will be auto-injected for matching tasks."
        except Exception as e:  # noqa: BLE001
            return f"Error saving skill: {e!s}"


