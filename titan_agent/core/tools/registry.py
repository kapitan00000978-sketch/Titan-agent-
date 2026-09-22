"""
Tool Registry Core - typed tool specs, discovery, composition and sandboxing.

Wraps an existing tool executor (e.g. tools.ToolRegistry) with:
- Typed ToolSpec (category, risk, approval requirements)
- Discovery: search tools by keyword/category/risk
- Policy enforcement in front of every execution (guardrails)
- Composition: chain tool outputs into later tool inputs
- Parallel execution of independent calls
"""
from __future__ import annotations

import asyncio
import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from ...config import absolute_access_enabled, full_access_enabled
from ..guardrails import Decision, PolicyEngine
from ..reasoning.interfaces import IToolExecutor


class ToolCategory(str, Enum):
    """Semantic grouping for tool discovery."""

    FILESYSTEM = "filesystem"
    COMMAND = "command"
    NETWORK = "network"
    KNOWLEDGE = "knowledge"
    CODE = "code"
    PC_CONTROL = "pc_control"
    SYSTEM = "system"
    MISC = "misc"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class ToolSpec:
    """Typed description of a tool, derived from raw function schema."""

    name: str
    description: str = ""
    category: ToolCategory = ToolCategory.MISC
    risk: RiskLevel = RiskLevel.LOW
    requires_approval: bool = False
    parameters: dict[str, Any] = field(default_factory=dict)
    required: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """OpenAI-style function schema for LLM tool calling."""
        properties = {
            k: {"type": v.get("type", "string"), "description": v.get("description", "")}
            for k, v in self.parameters.items()
        }
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": self.required,
                },
            },
        }


# Heuristics for classifying raw tool definitions
_CATEGORY_HINTS: dict[ToolCategory, tuple[tuple[str, ...], ...]] = {
    ToolCategory.FILESYSTEM: (("read_file", "write_file", "edit_file", "list_directory", "file"),),
    ToolCategory.COMMAND: (("execute_command", "command", "shell", "terminal"),),
    ToolCategory.NETWORK: (("web_search", "scrape", "http", "fetch", "network", "url"),),
    ToolCategory.KNOWLEDGE: (("deep_search", "search", "knowledge", "memory", "rag", "remember"),),
    ToolCategory.CODE: (("python_eval", "deep_coder", "code", "compile", "run"),),
    ToolCategory.PC_CONTROL: (
        ("screenshot", "key_press", "mouse", "window", "clipboard", "desktop"),
    ),
    ToolCategory.SYSTEM: (
        ("process", "system", "service", "power", "registry", "environment"),
    ),
}

_RISK_HINTS: dict[str, RiskLevel] = {
    "command": RiskLevel.MEDIUM,
    "delete": RiskLevel.HIGH,
    "execute": RiskLevel.MEDIUM,
    "network": RiskLevel.MEDIUM,
    "process": RiskLevel.MEDIUM,
    "window": RiskLevel.MEDIUM,
    "screenshot": RiskLevel.MEDIUM,
    "registry": RiskLevel.HIGH,
}


class ToolRegistry(IToolExecutor):
    """Policy-guarded, discovery-enabled wrapper around a tool executor."""

    def __init__(
        self,
        delegate: Any,
        policy: PolicyEngine | None = None,
        workspace: Path | None = None,
        require_approval_for: Iterable[str] | None = None,
    ):
        self.delegate = delegate
        self.policy = policy or PolicyEngine()
        self.workspace = Path(workspace) if workspace else None
        self.approval_required = set(require_approval_for or [])
        self._specs: dict[str, ToolSpec] = {}
        self._rebuild_specs()

    # ---------- Spec discovery ----------

    def _rebuild_specs(self) -> None:
        raw = self.delegate.get_tool_definitions()
        self._specs = {spec.name: spec for spec in (self._classify(d) for d in raw)}

    def _classify(self, raw: dict[str, Any]) -> ToolSpec:
        fn = raw.get("function", raw)
        name = fn.get("name", "")
        desc = fn.get("description", "")
        params = fn.get("parameters", {})
        properties = params.get("properties", {})
        required = params.get("required", [])

        category = ToolCategory.MISC
        for cat, hints in _CATEGORY_HINTS.items():
            if any(h in name.lower() for h in hints[0] if isinstance(h, str)):
                category = cat
                break
        # Fall back to description scan
        if category == ToolCategory.MISC:
            for cat, hints in _CATEGORY_HINTS.items():
                if any(h in desc.lower() for h in hints[0]):
                    category = cat
                    break

        risk = RiskLevel.LOW
        for hint, level in _RISK_HINTS.items():
            if hint in name.lower() or hint in desc.lower():
                risk = level
                break

        return ToolSpec(
            name=name,
            description=desc,
            category=category,
            risk=risk,
            requires_approval=(name in self.approval_required),
            parameters=properties,
            required=required,
        )

    def discover(
        self,
        query: str = "",
        category: ToolCategory | None = None,
        max_risk: RiskLevel | None = None,
        limit: int = 50,
    ) -> list[ToolSpec]:
        """Search tools by keyword, category and risk ceiling."""
        q = query.lower()
        results = []
        for spec in self._specs.values():
            if category and spec.category != category:
                continue
            if max_risk and _risk_rank(spec.risk) > _risk_rank(max_risk):
                continue
            if q and not (
                q in spec.name.lower() or q in spec.description.lower()
            ):
                continue
            results.append(spec)
        results.sort(key=lambda s: s.name)
        return results[:limit]

    def get(self, name: str) -> ToolSpec:
        if name not in self._specs:
            raise KeyError(f"Unknown tool: {name}")
        return self._specs[name]

    def all_specs(self) -> list[ToolSpec]:
        return sorted(self._specs.values(), key=lambda s: s.name)

    # ---------- IToolExecutor ----------

    def has_tool(self, name: str) -> bool:
        return name in self._specs and hasattr(self.delegate, f"tool_{name}")

    def get_available_tools(self) -> list[dict[str, Any]]:
        return [s.to_dict() for s in self._specs.values()]

    async def execute(
        self,
        tool_name: str,
        args: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> Any:
        """Execute with policy check and sandbox path enforcement."""
        if not self.has_tool(tool_name):
            raise LookupError(f"Unknown tool: {tool_name}")
        spec = self.get(tool_name)

        # Guardrail: policy decision in front of every execution.
        # For command tools the *command text* is the resource (so rules like
        # `rm -rf` -> deny actually match); for other tools it's the tool name.
        if spec.category == ToolCategory.COMMAND:
            action, resource = "execute_command", str(args.get("command", ""))
        else:
            action, resource = tool_name, tool_name
        # Phase 8: access mode is read at call-time so a runtime FULL/ABSOLUTE
        # toggle takes effect mid-run (approvals auto-granted; denies stay in
        # FULL, lifted only in ABSOLUTE).
        full = full_access_enabled()
        access = (
            PolicyEngine.ACCESS_ABSOLUTE
            if absolute_access_enabled()
            else (PolicyEngine.ACCESS_FULL if full else PolicyEngine.ACCESS_NORMAL)
        )
        decision = self.policy.check(action, resource, json.dumps(args, default=str), access=access)
        if decision.decision == Decision.DENY:
            raise PermissionError(f"Blocked by policy: {decision.reasons}")
        if (decision.decision == Decision.REQUIRE_APPROVAL or spec.requires_approval) and not full:
            raise PermissionError(
                f"Requires approval (tool={tool_name}): {decision.reasons}"
            )

        # Sandbox: enforce workspace root for path arguments (lifted in FULL
        # access — the agent may touch any path it can reach).
        if self.workspace and not full:
            args = dict(args)
            for key in ("path", "cwd", "file_path", "dir"):
                if key in args and isinstance(args[key], str):
                    args[key] = str(self._sandbox_path(args[key]))

        handler = getattr(self.delegate, f"tool_{tool_name}")
        result = handler(**args)
        if asyncio.iscoroutine(result) or hasattr(result, "__await__"):
            return await result
        return result

    def _sandbox_path(self, value: str) -> Path:
        """Resolve a path argument inside the workspace."""
        if self.workspace is None:
            raise PermissionError(
                "Workspace is not configured; sandboxed paths are unavailable."
            )
        p = Path(value).expanduser()
        if p.is_absolute():
            resolved = p.resolve()
            if not resolved.is_relative_to(self.workspace.resolve()):
                raise PermissionError(f"Path outside workspace: {value}")
            return resolved
        return (self.workspace / p).resolve()

    # ---------- Composition ----------

    async def compose(
        self,
        steps: list[tuple[str, dict[str, Any]]],
    ) -> list[Any]:
        """
        Chain tool calls where later args reference earlier outputs.

        Arg templates: {"$result": <step_index>, "$path": "field.path"}
        Example: compose([("web_search", {"query": "x"}),
                          ("read_file", {"path": {"$result": 0, "$path": "url"}})])
        """
        outputs: list[Any] = []
        for index, (name, args) in enumerate(steps):
            resolved = self._resolve_template(args, outputs)
            result = await self.execute(name, resolved)
            outputs.append(result)
        return outputs

    def _resolve_template(self, args: dict[str, Any], outputs: list[Any]) -> dict[str, Any]:
        resolved: dict[str, Any] = {}
        for key, value in args.items():
            if isinstance(value, dict) and "$result" in value:
                idx = value["$result"]
                source = outputs[idx]
                path = value.get("$path", "")
                if path:
                    for part in path.split("."):
                        if isinstance(source, dict):
                            source = source.get(part, source)
                        else:
                            source = str(source)
                            break
                resolved[key] = source if isinstance(source, str) else str(source)
            else:
                resolved[key] = value
        return resolved

    async def run_parallel(self, calls: list[tuple[str, dict[str, Any]]]) -> list[Any]:
        """Execute independent tool calls concurrently."""
        return list(
            await asyncio.gather(
                *(self.execute(name, args) for name, args in calls)
            )
        )

    def stats(self) -> dict[str, Any]:
        by_category: dict[str, int] = {}
        by_risk: dict[str, int] = {}
        for spec in self._specs.values():
            by_category[spec.category.value] = by_category.get(spec.category.value, 0) + 1
            by_risk[spec.risk.value] = by_risk.get(spec.risk.value, 0) + 1
        return {
            "total": len(self._specs),
            "by_category": by_category,
            "by_risk": by_risk,
        }


def _risk_rank(level: RiskLevel) -> int:
    return {RiskLevel.LOW: 1, RiskLevel.MEDIUM: 2, RiskLevel.HIGH: 3}[level]