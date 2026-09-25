"""
Phase 09 — Active Working Memory Virtualizer (Jonli Tezkor Xotira Virtualizatori).

Maintains a hyper-compact, real-time structured Working Memory HUD that keeps
the agent permanently anchored to verified facts, active variables, and refuted
dead-ends across long-horizon executions without context degradation.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class WorkingMemoryState:
    """Structured working memory representation."""

    goal: str = ""
    active_subtask: str = ""
    confirmed_facts: list[str] = field(default_factory=list)
    refuted_dead_ends: list[str] = field(default_factory=list)
    pinned_paths: dict[str, str] = field(default_factory=dict)
    pending_todos: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "goal": self.goal,
            "active_subtask": self.active_subtask,
            "confirmed_facts": self.confirmed_facts,
            "refuted_dead_ends": self.refuted_dead_ends,
            "pinned_paths": self.pinned_paths,
            "pending_todos": self.pending_todos,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WorkingMemoryState:
        return cls(
            goal=data.get("goal", ""),
            active_subtask=data.get("active_subtask", ""),
            confirmed_facts=list(data.get("confirmed_facts", [])),
            refuted_dead_ends=list(data.get("refuted_dead_ends", [])),
            pinned_paths=dict(data.get("pinned_paths", {})),
            pending_todos=list(data.get("pending_todos", [])),
        )


class WorkingMemoryVirtualizer:
    """Manages real-time working memory mutations and generates the prompt HUD block."""

    def __init__(self, initial_goal: str = ""):
        self.state = WorkingMemoryState(goal=initial_goal)

    def set_goal(self, goal: str) -> None:
        self.state.goal = str(goal).strip()

    def set_subtask(self, subtask: str) -> None:
        self.state.active_subtask = str(subtask).strip()

    def confirm_fact(self, fact: str) -> None:
        cleaned = str(fact).strip()
        if cleaned and cleaned not in self.state.confirmed_facts:
            self.state.confirmed_facts.append(cleaned)
            if len(self.state.confirmed_facts) > 12:
                del self.state.confirmed_facts[0]

    def record_dead_end(self, dead_end: str) -> None:
        cleaned = str(dead_end).strip()
        if cleaned and cleaned not in self.state.refuted_dead_ends:
            self.state.refuted_dead_ends.append(cleaned)
            if len(self.state.refuted_dead_ends) > 8:
                del self.state.refuted_dead_ends[0]

    def pin_path(self, label: str, path: str) -> None:
        if label and path:
            self.state.pinned_paths[str(label).strip()] = str(path).strip()

    def add_todo(self, todo: str) -> None:
        cleaned = str(todo).strip()
        if cleaned and cleaned not in self.state.pending_todos:
            self.state.pending_todos.append(cleaned)

    def complete_todo(self, todo: str) -> bool:
        cleaned = str(todo).strip()
        if cleaned in self.state.pending_todos:
            self.state.pending_todos.remove(cleaned)
            return True
        return False

    def auto_observe_tool_outcome(self, tool_name: str, tool_args: dict[str, Any], tool_result: str) -> None:
        """Autonomously extracts confirmed facts, paths, and dead-ends from tool outcomes."""
        res_str = str(tool_result).strip()
        is_error = res_str.startswith("Error") or "failed" in res_str.lower()

        # Extract file paths from common args
        path_arg = tool_args.get("path") or tool_args.get("file")
        if path_arg and not is_error and tool_name in ("read_file", "write_file", "edit_file", "ast_replace_function"):
            self.pin_path(Path(str(path_arg)).name, str(path_arg))

        if is_error:
            # Record failed dead-end to avoid repetition
            arg_summary = ", ".join(f"{k}={v}" for k, v in list(tool_args.items())[:2])
            dead_end = f"Avoid {tool_name}({arg_summary}): {res_str[:80]}"
            self.record_dead_end(dead_end)
        else:
            if tool_name == "read_file" and len(res_str) > 0:
                self.confirm_fact(f"File verified on disk: {path_arg or 'target'} ({len(res_str)} chars)")
            elif tool_name in ("write_file", "edit_file", "ast_replace_function"):
                self.confirm_fact(f"Successfully modified: {path_arg or 'target'}")

    def render_hud_block(self, max_chars: int = 800) -> str:
        """Renders an ultra-compact working memory HUD for system prompt injection."""
        lines = ["### WORKING MEMORY HUD (Live Operational State):"]
        if self.state.goal:
            lines.append(f"- **Goal**: {self.state.goal[:120]}")
        if self.state.active_subtask:
            lines.append(f"- **Active Subtask**: {self.state.active_subtask}")
        if self.state.confirmed_facts:
            lines.append(f"- **Confirmed Facts**: {'; '.join(self.state.confirmed_facts[-4:])}")
        if self.state.refuted_dead_ends:
            lines.append(f"- **Refuted Dead-Ends (DO NOT REPEAT)**: {'; '.join(self.state.refuted_dead_ends[-3:])}")
        if self.state.pinned_paths:
            p_items = [f"{k}: `{v}`" for k, v in list(self.state.pinned_paths.items())[-3:]]
            lines.append(f"- **Key Paths**: {', '.join(p_items)}")
        if self.state.pending_todos:
            lines.append(f"- **Pending Todos**: {', '.join(self.state.pending_todos[:3])}")

        rendered = "\n".join(lines)
        if len(rendered) > max_chars:
            rendered = rendered[:max_chars] + "… (HUD truncated)]"
        return rendered
