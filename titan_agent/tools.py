import asyncio
import os
import platform
import re
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path
from typing import Any, Dict, List

try:
    from ddgs import DDGS
except ImportError:
    from duckduckgo_search import DDGS
from .config import WORKSPACE_DIR


class ToolRegistry:
    def __init__(self, workspace: Path = WORKSPACE_DIR):
        self.workspace = workspace
        self.workspace.mkdir(parents=True, exist_ok=True)

    def _resolve_path(self, rel_or_abs: str) -> Path:
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
        except Exception as e:
            return f"Tool execution failed for '{name}': {e!s}"

    async def tool_execute_command(self, command: str, cwd: str = "") -> str:
        working_dir = self._resolve_path(cwd) if cwd else self.workspace
        working_dir.mkdir(parents=True, exist_ok=True)
        try:
            # Use powershell on windows
            shell_cmd = ["powershell", "-NoProfile", "-Command", command] if sys.platform == "win32" else ["bash", "-c", command]
            proc = await asyncio.create_subprocess_exec(
                *shell_cmd,
                cwd=str(working_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=45.0)
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
            return "Error: Command timed out after 45 seconds."
        except Exception as e:
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
        except Exception as e:
            return f"Error reading file '{fpath}': {e!s}"

    def tool_write_file(self, path: str, content: str) -> str:
        fpath = self._resolve_path(path)
        try:
            fpath.parent.mkdir(parents=True, exist_ok=True)
            with open(fpath, "w", encoding="utf-8") as f:
                f.write(content)
            return f"Successfully wrote {len(content)} characters to {fpath}."
        except Exception as e:
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
        except Exception as e:
            return f"Error editing file '{fpath}': {e!s}"

    def tool_list_directory(self, path: str = "") -> str:
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
        except Exception as e:
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
        except Exception as e:
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
        except Exception as e:
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
        except Exception as e:
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

    async def tool_deep_coder(self, task_name: str, files: Dict[str, str], test_code: str = "") -> str:
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

    def tool_launch_application(self, app_or_command: str) -> str:
        try:
            if sys.platform == "win32":
                subprocess.Popen(f"start {app_or_command}", shell=True)
            else:
                subprocess.Popen(app_or_command, shell=True)
            return f"Launched application/command: '{app_or_command}'"
        except Exception as e:
            return f"Failed to launch application: {e!s}"

    def tool_system_info(self) -> str:
        """Reads live host environment facts (OS, CPU, RAM, disk, Python)."""
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
            except Exception as e:
                lines.append(f"RAM: read failed ({e})")

            # Disk on workspace drive
            try:
                usage = shutil.disk_usage(str(self.workspace))
                lines.append(f"Disk: {usage.free/(1024**3):.1f} GB free / {usage.total/(1024**3):.1f} GB total")
            except Exception:
                pass

            # Software hints
            try:
                node_ver = subprocess.run(["node", "--version"], capture_output=True, text=True, timeout=5).stdout.strip()
                lines.append(f"Node.js: {node_ver or 'not found'}")
            except Exception:
                pass
            try:
                git_ver = subprocess.run(["git", "--version"], capture_output=True, text=True, timeout=5).stdout.strip()
                lines.append(f"Git: {git_ver or 'not found'}")
            except Exception:
                pass

            lines.append(f"Workspace: {self.workspace}")
            return "\n".join(lines)
        except Exception as e:
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
        except Exception as e:
            return f"Manage processes error: {e!s}"
