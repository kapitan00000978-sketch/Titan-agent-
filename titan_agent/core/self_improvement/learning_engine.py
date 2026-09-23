"""
Phase 30 — Genesis Darajasi 10: Self-Improvement Loop & Failure Learning Engine.

Analyzes failed tasks, distills actionable rules and lessons learned,
refines operational prompts, and crystallizes knowledge into persistent skills and memory.
"""
from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ImprovementLesson:
    """A distilled lesson learned from execution failure or suboptimal performance."""

    task_id: str
    category: str
    symptom: str
    root_cause: str
    guidance: str
    rule_text: str
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SelfImprovementLoop:
    """
    Cognitive reflection and self-improvement engine.
    Turns task failures into permanent, reusable skills and architectural guardrails.
    """

    def __init__(self, workspace_root: Path | str | None = None):
        self.workspace_root = Path(workspace_root).resolve() if workspace_root else Path.cwd()

    def analyze_failure(
        self,
        task_id: str,
        prompt: str,
        failure_log: str,
        failed_tools: list[str] | None = None,
        category: str = "general",
    ) -> ImprovementLesson:
        """
        Diagnoses why a task failed, extracting the root cause and a prescriptive rule.
        """
        tools = failed_tools or []
        log_snippet = failure_log.strip()[:300] if failure_log else "No execution log provided"

        # Heuristic / diagnostic classification
        if "syntaxerror" in failure_log.lower() or "indentationerror" in failure_log.lower():
            cause = "Python AST syntax or indentation malformation during file modification."
            rule = "Always validate syntax with ast_patch_file or run tests in sandbox before committing changes."
            guidance = "When editing Python source code, perform surgical AST replacement rather than raw multiline rewrites."
        elif "timeout" in failure_log.lower():
            cause = "Execution timeout exceeded threshold due to unbounded loops or blocking I/O."
            rule = "Decompose long-running tasks into DAG sub-tasks and enforce non-blocking execution."
            guidance = "Break tasks with multiple steps into parallel or sequential DAG nodes."
        elif tools:
            primary_tool = tools[0]
            cause = f"Repeated tool execution failure in `{primary_tool}`."
            rule = f"Verify required arguments and precondition state before invoking `{primary_tool}`."
            guidance = f"Ensure tool parameters match schema and verify file existence before calling `{primary_tool}`."
        else:
            cause = "Suboptimal problem decomposition or missing contextual preconditions."
            rule = "Formulate a step-by-step hypothesis plan before executing mutating commands."
            guidance = "Use reasoning debate or reflexion loop when facing ambiguous errors."

        return ImprovementLesson(
            task_id=task_id,
            category=category,
            symptom=f"Task '{task_id}' failed: {log_snippet}",
            root_cause=cause,
            guidance=guidance,
            rule_text=f"RULE [{category.upper()}]: {rule}",
        )

    def propose_prompt_refinement(
        self,
        task_category: str,
        current_prompt: str,
        lessons: list[ImprovementLesson],
    ) -> str:
        """
        Produces a proposed unified diff showing prompt updates incorporating lessons learned.
        """
        cat = task_category.upper()
        new_guidelines = [
            f"+ [LESSON LEARNED {cat}]: {l.guidance} (Avoid: {l.root_cause})"
            for l in lessons
        ]
        guidelines_block = "\n".join(new_guidelines)

        diff = [
            f"--- system_prompt_{task_category}.txt\t(original)",
            f"+++ system_prompt_{task_category}.txt\t(refined)",
            "@@ -1,5 +1,9 @@",
            " # Core Execution Guidance",
            f" Context: Operating in {task_category} mode.",
            guidelines_block,
            " Execute tools with high precision.",
        ]
        return "\n".join(diff)

    def crystallize_lesson(
        self,
        lesson: ImprovementLesson,
        skill_registry: Any = None,
        knowledge_graph: Any = None,
    ) -> dict[str, Any]:
        """
        Permanently crystallizes the lesson into:
        1. SkillRegistry as an auto-injected playbook
        2. KnowledgeGraph as a causal avoidance edge
        """
        status: dict[str, Any] = {
            "lesson_task_id": lesson.task_id,
            "skill_saved": False,
            "knowledge_fact_added": False,
        }

        # 1. Save to SkillRegistry
        if skill_registry is None:
            from titan_agent.skills import SkillRegistry
            skill_registry = SkillRegistry()

        skill_slug = f"learned-{lesson.category}-{int(time.time())}"
        description = f"Learned lesson from task {lesson.task_id}: {lesson.root_cause[:80]}"
        keywords = f"{lesson.category}, error-prevention, {lesson.task_id}"

        body = (
            f"# Operational Playbook: {lesson.category}\n\n"
            f"**Root Cause Prevented**: {lesson.root_cause}\n\n"
            f"### Prescribed Guidance:\n"
            f"{lesson.guidance}\n\n"
            f"### Mandatory Rule:\n"
            f"> {lesson.rule_text}\n"
        )
        try:
            skill_registry.save_skill(
                name=skill_slug,
                description=description,
                keywords=keywords,
                guidance=body,
            )
            status["skill_saved"] = True
            status["skill_name"] = skill_slug
        except Exception as e:  # noqa: BLE001
            status["skill_error"] = str(e)

        # 2. Add to Knowledge Graph if available
        if knowledge_graph is not None:
            try:
                knowledge_graph.add_relation(
                    source=f"category:{lesson.category}",
                    relation="governed_by_rule",
                    target=f"rule:{skill_slug}",
                    properties={"rule": lesson.rule_text},
                )
                status["knowledge_fact_added"] = True
            except Exception as e:  # noqa: BLE001
                status["kg_error"] = str(e)

        return status
