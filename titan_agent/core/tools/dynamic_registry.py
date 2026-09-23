"""
Phase 26 — Genesis Darajasi 8: Dynamic Tool Discovery & Contextual Filtering.

Selects the most relevant subset of tool schemas based on the task intent,
reducing token consumption from 60+ tool definitions down to 12-18 highly
relevant tools while allowing on-demand discovery.
"""
from __future__ import annotations

import re
from typing import Any, ClassVar

from .reliability import ToolReliabilityTracker


class DynamicToolSelector:
    """Manages dynamic context-aware tool selection and discovery."""

    CORE_TOOLS: ClassVar[set[str]] = {
        "execute_command",
        "read_file",
        "write_file",
        "edit_file",
        "list_directory",
        "search_files",
        "tool_discover",
        "tool_reliability_report",
    }

    DOMAIN_BUNDLES: ClassVar[dict[str, list[str]]] = {
        "git": [
            "git_status",
            "git_diff",
            "git_commit",
            "git_branch",
            "git_log",
        ],
        "web_browser": [
            "browse_url",
            "web_search",
            "browser_open",
            "browser_click",
            "browser_type",
            "browser_extract",
            "browser_screenshot",
            "download_file",
        ],
        "genesis_orchestrator": [
            "orchestrator_run",
            "team_delegate",
            "team_status",
            "dag_plan_and_run",
            "dag_visualize",
            "drift_record_task",
            "drift_check",
            "drift_status",
        ],
        "reasoning": [
            "debate_solve",
            "reflexion_solve",
            "self_improve_analyze_failure",
            "self_improve_eval_run",
            "self_improve_crystallize_lesson",
        ],
        "knowledge_graph": [
            "kg_query",
            "kg_impact_analysis",
            "kg_add_fact",
            "kg_index_workspace",
        ],
        "vector_rag": [
            "vector_rag_index",
            "vector_rag_search",
        ],
        "desktop_os": [
            "screenshot",
            "key_press",
            "mouse_click",
            "mouse_move",
            "manage_processes",
            "list_windows",
            "window_control",
            "clipboard_get",
            "clipboard_set",
        ],
        "sandbox_verify": [
            "docker_sandbox_run",
            "deep_verify_code",
            "ast_patch_file",
            "self_heal",
            "apply_patch",
            "sandbox_execute",
            "sandbox_snapshot_create",
            "sandbox_snapshot_rollback",
        ],
    }

    DOMAIN_KEYWORDS: ClassVar[dict[str, list[str]]] = {
        "git": ["git", "branch", "commit", "checkout", "diff", "merge", "repo", "stash"],
        "web_browser": ["web", "url", "http", "https", "browse", "html", "internet", "search", "download", "scrape", "site"],
        "genesis_orchestrator": ["orchestrate", "ceo", "team", "department", "dag", "parallel", "plan", "hierarchy", "lead", "staff"],
        "reasoning": ["debate", "argue", "reflexion", "self-critique", "critique", "contemplate", "judge", "philosophy", "tradeoff"],
        "knowledge_graph": ["kg", "graph", "knowledge", "impact", "blast", "relation", "entity", "ast", "dependency", "module", "inherits"],
        "vector_rag": ["vector", "rag", "chroma", "semantic", "embedding", "similarity"],
        "desktop_os": ["window", "mouse", "keyboard", "process", "tasklist", "clipboard", "monitor", "screen", "click", "keys"],
        "sandbox_verify": ["docker", "container", "sandbox", "verify", "patch", "heal", "isolated", "safe", "unit test"],
    }

    @classmethod
    def select_tools(
        cls,
        task_text: str,
        all_tool_defs: list[dict[str, Any]],
        max_tools: int = 18,
        reliability_tracker: ToolReliabilityTracker | None = None,
    ) -> list[dict[str, Any]]:
        """
        Dynamically filters tool schemas for a given task prompt.
        Always includes Core tools, then ranks and adds relevant domain tools.
        """
        tool_map: dict[str, dict[str, Any]] = {}
        for td in all_tool_defs:
            fn = td.get("function", td)
            name = fn.get("name")
            if name:
                tool_map[name] = td

        selected_names: set[str] = set()

        # 1. Always select existing Core tools
        for core in cls.CORE_TOOLS:
            if core in tool_map:
                selected_names.add(core)

        # 2. Tokenize task text
        tokens = set(re.findall(r"\w+", task_text.lower()))

        # 3. Score domains
        domain_scores: list[tuple[str, int]] = []
        for domain, keywords in cls.DOMAIN_KEYWORDS.items():
            overlap = sum(1 for kw in keywords if kw in tokens or any(kw in t for t in tokens))
            if overlap > 0:
                domain_scores.append((domain, overlap))

        # Sort by relevance
        domain_scores.sort(key=lambda x: -x[1])

        # If no specific domain matches, pick top common bundles (e.g. genesis + reasoning + git)
        if not domain_scores:
            default_domains = ["genesis_orchestrator", "git", "sandbox_verify"]
            for d in default_domains:
                domain_scores.append((d, 1))

        # 4. Add tools from matching domains
        for domain, _ in domain_scores:
            bundle = cls.DOMAIN_BUNDLES.get(domain, [])
            for tool_name in bundle:
                if tool_name in tool_map and tool_name not in selected_names:
                    # Check reliability: skip Grade F tools if we are near cap
                    if reliability_tracker and not reliability_tracker.is_reliable(tool_name) and len(selected_names) >= max_tools - 2:
                        continue
                    selected_names.add(tool_name)
                    if len(selected_names) >= max_tools:
                        break
            if len(selected_names) >= max_tools:
                break

        # Return sorted list of tool definition dicts
        return [tool_map[name] for name in sorted(selected_names) if name in tool_map]

    @classmethod
    def discover_tools(
        cls,
        query: str,
        all_tool_defs: list[dict[str, Any]],
        category: str = "",
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Searches available tool definitions by keyword, category, or parameter names.
        """
        q = query.lower().strip()
        cat = category.lower().strip()
        matched: list[tuple[dict[str, Any], int]] = []

        for td in all_tool_defs:
            fn = td.get("function", td)
            name = fn.get("name", "").lower()
            desc = fn.get("description", "").lower()

            if cat:
                bundle = cls.DOMAIN_BUNDLES.get(cat, [])
                if name not in bundle and cat not in desc:
                    continue

            score = 0
            if q:
                if q == name:
                    score += 100
                elif q in name:
                    score += 30
                if q in desc:
                    score += 10
            else:
                score = 1

            if score > 0:
                matched.append((td, score))

        matched.sort(key=lambda x: -x[1])
        return [item[0] for item in matched[:limit]]
