"""
Phase 40 — Autonomous Dynamic Tool Synthesizer (Avtonom Vosita Sintezi).

Allows Titan Agent to synthesize, test, verify, and register new tools
on-the-fly during a live execution session when existing tools are insufficient.
"""
from __future__ import annotations

import ast
import asyncio
import importlib.util
import json
import logging
import re
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

log = logging.getLogger(__name__)


@dataclass
class SynthesizedToolSpec:
    """Specification of an autonomously created tool."""

    name: str
    description: str
    parameters: dict[str, Any]
    python_code: str
    test_code: str = ""
    is_async: bool = True
    verified: bool = False
    verification_notes: str = ""
    created_at: float = field(default_factory=lambda: asyncio.get_event_loop().time() if asyncio.get_event_loop().is_running() else 0.0)


class DynamicToolSynthesizer:
    """Synthesizes, tests in sandbox, and hot-injects Python tools into live registries."""

    def __init__(self, workspace_root: Path | str | None = None):
        self.workspace_root = Path(workspace_root) if workspace_root else Path.cwd()
        self.storage_dir = self.workspace_root / ".titan_synthesized_tools"
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.synthesized_registry: dict[str, SynthesizedToolSpec] = {}

    def validate_syntax(self, code: str) -> tuple[bool, str]:
        """Validates that the provided code is syntactically sound Python."""
        try:
            tree = ast.parse(code)
            # Ensure no syntax errors and contains at least one function definition
            funcs = [node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
            if not funcs:
                return False, "Code must define at least one function or async function."
            return True, f"Syntax valid. Functions defined: {', '.join(funcs)}"
        except SyntaxError as e:
            return False, f"SyntaxError at line {e.lineno}: {e.msg}"
        except Exception as e:
            return False, f"AST parsing failed: {e!s}"

    async def test_in_isolated_sandbox(
        self,
        tool_code: str,
        test_code: str,
        timeout: float = 30.0,
    ) -> tuple[bool, str]:
        """Executes the tool and its test script in an isolated temporary Python subprocess."""
        with tempfile.TemporaryDirectory(prefix="titan_synth_tool_") as tmpdir:
            tmppath = Path(tmpdir)
            module_file = tmppath / "synthesized_module.py"
            test_file = tmppath / "test_synthesized.py"

            module_file.write_text(tool_code, encoding="utf-8")

            # Runner script that imports the module and executes the test harness
            runner_script = (
                "import sys\n"
                "import asyncio\n"
                f"sys.path.insert(0, r'{tmppath}')\n"
                "import synthesized_module\n\n"
                f"{test_code}\n\n"
                "print('___SYNTHESIS_TEST_PASSED___')\n"
            )
            test_file.write_text(runner_script, encoding="utf-8")

            try:
                proc = await asyncio.create_subprocess_exec(
                    sys.executable,
                    str(test_file),
                    cwd=str(tmppath),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=timeout,
                )
                out = stdout_bytes.decode("utf-8", errors="ignore")
                err = stderr_bytes.decode("utf-8", errors="ignore")

                if proc.returncode == 0 and "___SYNTHESIS_TEST_PASSED___" in out:
                    return True, f"Sandbox test passed successfully.\n{out}"
                return False, f"Sandbox test failed with exit code {proc.returncode}.\nSTDOUT:\n{out}\nSTDERR:\n{err}"
            except asyncio.TimeoutError:
                return False, f"Sandbox test timed out after {timeout} seconds."
            except Exception as exc:
                return False, f"Sandbox execution error: {exc!s}"

    def compile_and_load_callable(
        self,
        name: str,
        code: str,
    ) -> tuple[Callable[..., Any] | None, bool, str]:
        """Compiles the code into a live module and extracts the main callable."""
        spec_name = f"titan_dyn_tool_{name}"
        try:
            with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w", encoding="utf-8") as tmp:
                tmp.write(code)
                tmp_path = Path(tmp.name)

            spec = importlib.util.spec_from_file_location(spec_name, tmp_path)
            if not spec or not spec.loader:
                return None, False, "Failed to create module spec."
            mod = importlib.util.module_from_spec(spec)
            sys.modules[spec_name] = mod
            spec.loader.exec_module(mod)

            # Find callable matching name or default convention
            target_fn = getattr(mod, name, None)
            if target_fn is None:
                # Look for tool_{name} or first defined function
                target_fn = getattr(mod, f"tool_{name}", None)
            if target_fn is None:
                for attr in dir(mod):
                    val = getattr(mod, attr)
                    if callable(val) and not attr.startswith("_"):
                        target_fn = val
                        break

            if target_fn is None:
                return None, False, f"No callable found in synthesized code for tool '{name}'."

            is_async = asyncio.iscoroutinefunction(target_fn)
            return target_fn, is_async, "Successfully loaded into memory."
        except Exception as exc:
            return None, False, f"Compilation/loading failed: {exc!s}"

    async def synthesize_and_register(
        self,
        name: str,
        description: str,
        parameters: dict[str, Any],
        python_code: str,
        test_code: str,
        registry: Any,
    ) -> tuple[bool, str]:
        """Validates, sandbox-tests, compiles, registers onto ToolRegistry, and persists."""
        norm_name = re.sub(r"[^a-zA-Z0-9_]", "_", name).strip("_").lower()
        if not norm_name:
            return False, "Error: Tool name must contain valid alphanumeric characters."

        # 1. Syntax validation
        valid_syntax, syn_msg = self.validate_syntax(python_code)
        if not valid_syntax:
            return False, f"Validation Error: {syn_msg}"

        # 2. Isolated sandbox test (if test_code provided)
        test_output = "No test code provided; skipping sandbox execution."
        if test_code.strip():
            passed, test_msg = await self.test_in_isolated_sandbox(python_code, test_code)
            if not passed:
                return False, f"Sandbox Verification FAILED:\n{test_msg}"
            test_output = test_msg

        # 3. Dynamic compilation and callable loading
        handler_fn, is_async, load_msg = self.compile_and_load_callable(norm_name, python_code)
        if handler_fn is None:
            return False, f"Loading Error: {load_msg}"

        # 4. Attach to ToolRegistry dynamically
        tool_handler_name = f"tool_{norm_name}"
        setattr(registry, tool_handler_name, handler_fn)

        # 5. Build standard OpenAI tool schema definition
        tool_def = {
            "type": "function",
            "function": {
                "name": norm_name,
                "description": f"[SYNTHESIZED TOOL] {description}",
                "parameters": parameters if isinstance(parameters, dict) and "type" in parameters else {
                    "type": "object",
                    "properties": parameters if isinstance(parameters, dict) else {},
                },
            },
        }

        # Store in dynamic definitions if registry supports it
        if hasattr(registry, "_synthesized_definitions"):
            registry._synthesized_definitions[norm_name] = tool_def
        else:
            registry._synthesized_definitions = {norm_name: tool_def}

        spec = SynthesizedToolSpec(
            name=norm_name,
            description=description,
            parameters=parameters,
            python_code=python_code,
            test_code=test_code,
            is_async=is_async,
            verified=True,
            verification_notes=test_output,
        )
        self.synthesized_registry[norm_name] = spec
        self.persist_tool(spec)

        log.info("Successfully synthesized, verified and registered dynamic tool: %s", norm_name)
        return True, (
            f"✅ Tool '{norm_name}' synthesized and verified successfully!\n"
            f"- Registered name: {norm_name}\n"
            f"- Async: {is_async}\n"
            f"- Sandbox: {test_output.splitlines()[0] if test_output else 'OK'}\n"
            "The tool is immediately available for invocation."
        )

    def persist_tool(self, spec: SynthesizedToolSpec) -> Path:
        """Persists the tool specification and source code to disk."""
        target_dir = self.storage_dir / spec.name
        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / "tool.py").write_text(spec.python_code, encoding="utf-8")
        if spec.test_code:
            (target_dir / "test.py").write_text(spec.test_code, encoding="utf-8")
        meta = {
            "name": spec.name,
            "description": spec.description,
            "parameters": spec.parameters,
            "is_async": spec.is_async,
            "verified": spec.verified,
            "created_at": spec.created_at,
        }
        (target_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
        return target_dir

    def load_persisted_tools(self, registry: Any) -> list[str]:
        """Loads previously synthesized tools from storage into the live registry."""
        loaded = []
        if not self.storage_dir.exists():
            return loaded

        for tool_dir in self.storage_dir.iterdir():
            if not tool_dir.is_dir():
                continue
            meta_file = tool_dir / "meta.json"
            code_file = tool_dir / "tool.py"
            if not meta_file.exists() or not code_file.exists():
                continue
            try:
                meta = json.loads(meta_file.read_text(encoding="utf-8"))
                code = code_file.read_text(encoding="utf-8")
                name = meta.get("name")
                if not name:
                    continue
                handler_fn, is_async, _ = self.compile_and_load_callable(name, code)
                if handler_fn:
                    setattr(registry, f"tool_{name}", handler_fn)
                    tool_def = {
                        "type": "function",
                        "function": {
                            "name": name,
                            "description": f"[SYNTHESIZED TOOL] {meta.get('description', '')}",
                            "parameters": meta.get("parameters", {"type": "object", "properties": {}}),
                        },
                    }
                    if not hasattr(registry, "_synthesized_definitions"):
                        registry._synthesized_definitions = {}
                    registry._synthesized_definitions[name] = tool_def
                    loaded.append(name)
            except Exception as e:
                log.warning("Could not load persisted synthesized tool from %s: %s", tool_dir, e)
        return loaded
