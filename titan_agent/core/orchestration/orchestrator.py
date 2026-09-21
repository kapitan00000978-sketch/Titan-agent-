"""
Agent Team Orchestrator - sequential, parallel, consensus and supervisor modes.

Implements AutoGen/LangGraph-style multi-agent coordination:
- Registry of typed agents (roles with system prompts)
- Sequential pipelines (coder -> reviewer -> tester)
- Parallel fan-out with result gathering
- Consensus runs (multiple opinions, agreement detection)
- Supervisor delegation with review loop
"""
from __future__ import annotations

import asyncio
import time
from collections.abc import Iterable

from ..reasoning.interfaces import ILLMProvider
from .types import (
    AgentResult,
    AgentRole,
    AgentSpec,
    ConsensusResult,
    OrchestrationMode,
    TeamRunResult,
)


class AgentNotFoundError(KeyError):
    """Requested agent role is not registered."""


class AgentTeam:
    """A team of role-based agents coordinated by an orchestrator."""

    def __init__(
        self,
        llm: ILLMProvider,
        agents: Iterable[AgentSpec] | None = None,
    ):
        self.llm = llm
        self._agents: dict[str, AgentSpec] = {}
        for spec in agents or []:
            self.register(spec)

    # ---------- Registry ----------

    def register(self, spec: AgentSpec) -> None:
        if spec.key in self._agents:
            raise ValueError(f"Agent role already registered: {spec.key}")
        self._agents[spec.key] = spec

    def register_role(
        self,
        role: AgentRole,
        system_prompt: str,
        name: str = "",
        model_hint: str | None = None,
    ) -> AgentSpec:
        spec = AgentSpec(
            role=role,
            name=name or role.value,
            system_prompt=system_prompt,
            model_hint=model_hint,
        )
        self.register(spec)
        return spec

    def get(self, role: AgentRole | str) -> AgentSpec:
        key = role.value if isinstance(role, AgentRole) else role
        if key not in self._agents:
            raise AgentNotFoundError(f"No agent registered for role: {key}")
        return self._agents[key]

    def roles(self) -> list[str]:
        return list(self._agents.keys())

    def has(self, role: AgentRole | str) -> bool:
        key = role.value if isinstance(role, AgentRole) else role
        return key in self._agents

    # ---------- Single agent ----------

    async def run_agent(
        self,
        role: AgentRole | str,
        task: str,
        context: str = "",
        temperature: float | None = None,
    ) -> AgentResult:
        """Run one agent on a task and return its output."""
        spec = self.get(role)
        started = time.perf_counter()
        prompt = spec.system_prompt
        if context:
            prompt += f"\n\nContext:\n{context[:6000]}"
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": task},
        ]
        try:
            raw = await self.llm.complete(
                messages=messages,
                temperature=(
                    temperature if temperature is not None else spec.temperature
                ),
                max_tokens=4096,
            )
            output = str(raw)
        except Exception as exc:  # noqa: BLE001 - report agent failure, don't crash team
            duration = (time.perf_counter() - started) * 1000
            return AgentResult(
                role=spec.role,
                agent_name=spec.name,
                output="",
                error=str(exc),
                duration_ms=round(duration, 2),
            )
        duration = (time.perf_counter() - started) * 1000
        return AgentResult(
            role=spec.role,
            agent_name=spec.name,
            output=output,
            duration_ms=round(duration, 2),
        )

    # ---------- Modes ----------

    async def run(
        self,
        task: str,
        mode: OrchestrationMode = OrchestrationMode.SEQUENTIAL,
        roles: list[AgentRole] | None = None,
        context: str = "",
    ) -> TeamRunResult:
        """Run the team in the chosen coordination mode."""
        if mode == OrchestrationMode.SEQUENTIAL:
            return await self._sequential(task, roles, context)
        if mode == OrchestrationMode.PARALLEL:
            return await self._parallel(task, roles, context)
        if mode == OrchestrationMode.CONSENSUS:
            return await self._consensus(task, roles or [AgentRole.CODER], context)
        if mode == OrchestrationMode.SUPERVISOR:
            return await self._supervisor(task, context)
        raise ValueError(f"Unsupported mode: {mode}")

    async def _sequential(
        self,
        task: str,
        roles: list[AgentRole] | None,
        context: str,
    ) -> TeamRunResult:
        result = TeamRunResult(mode=OrchestrationMode.SEQUENTIAL, task=task)
        pipeline = roles or self._default_pipeline()
        carry = context
        for role in pipeline:
            if carry:
                subtask = f"{task}\n\nPrevious output:\n{carry[:4000]}"
            else:
                subtask = task
            agent_result = await self.run_agent(role, subtask, carry)
            result.results[role.value] = agent_result
            result.trace.append(
                {"role": role.value, "ok": agent_result.ok, "agent": agent_result.agent_name}
            )
            if agent_result.ok:
                carry = agent_result.output
            else:
                # Fail fast on sequential pipeline errors
                result.final_output = f"Pipeline stopped: {agent_result.error}"
                result.completed_at = self._utcnow()
                return result
        result.final_output = carry
        result.completed_at = self._utcnow()
        return result

    async def _parallel(
        self,
        task: str,
        roles: list[AgentRole] | None,
        context: str,
    ) -> TeamRunResult:
        result = TeamRunResult(mode=OrchestrationMode.PARALLEL, task=task)
        pipeline = roles or self._default_pipeline()
        outcomes = await asyncio.gather(
            *(self.run_agent(role, task, context) for role in pipeline),
            return_exceptions=False,
        )
        for role, agent_result in zip(pipeline, outcomes):
            result.results[role.value] = agent_result
            result.trace.append(
                {"role": role.value, "ok": agent_result.ok, "agent": agent_result.agent_name}
            )
        # Combine outputs
        parts = [r.output for r in outcomes if r.ok and r.output]
        result.final_output = "\n\n---\n\n".join(parts)
        result.completed_at = self._utcnow()
        return result

    async def _consensus(
        self,
        task: str,
        roles: list[AgentRole],
        context: str,
    ) -> TeamRunResult:
        result = TeamRunResult(mode=OrchestrationMode.CONSENSUS, task=task)
        consensus = ConsensusResult()
        outcomes = await asyncio.gather(
            *(self.run_agent(role, task, context) for role in roles)
        )
        for role, agent_result in zip(roles, outcomes):
            consensus.add(agent_result)
            result.results[role.value] = agent_result

        # Simple agreement: pick the most common output
        from collections import Counter

        votes = Counter()
        for r in consensus.results:
            if r.ok and r.output:
                votes[r.output] += 1
        if votes:
            best, count = votes.most_common(1)[0]
            consensus.agreed_output = best
            consensus.confidence = count / max(1, len(consensus.results))

        result.final_output = consensus.agreed_output or "No consensus reached"
        result.completed_at = self._utcnow()
        return result

    async def _supervisor(self, task: str, context: str) -> TeamRunResult:
        """Supervisor delegates subtasks to specialists, then reviews."""
        result = TeamRunResult(mode=OrchestrationMode.SUPERVISOR, task=task)
        if not self.has(AgentRole.SUPERVISOR):
            raise AgentNotFoundError("SUPERVISOR role required for supervisor mode")

        # 1. Supervisor decomposes the task into subtasks
        plan_output = await self.run_agent(AgentRole.SUPERVISOR, task, context)
        result.results["supervisor_plan"] = plan_output

        # 2. Pass to specialists if available
        specialists = [
            r for r in self.roles()
            if r not in (AgentRole.SUPERVISOR.value,)
        ]
        for role_key in specialists:
            spec = self._agents[role_key]
            agent_result = await self.run_agent(
                spec.role,
                task,
                plan_output.output if plan_output.ok else context,
            )
            result.results[role_key] = agent_result

        # 3. Supervisor synthesizes a final decision from all outputs
        joined = "\n\n---\n\n".join(
            r.output for r in result.results.values() if r.ok
        )
        final = await self.run_agent(
            AgentRole.SUPERVISOR,
            "Synthesize the final answer from the specialist outputs.",
            joined or task,
        )
        result.final_output = final.output
        result.results["supervisor_final"] = final

        result.completed_at = self._utcnow()
        return result

    # ---------- Helpers ----------

    def _default_pipeline(self) -> list[AgentRole]:
        order = [
            AgentRole.PLANNER,
            AgentRole.CODER,
            AgentRole.REVIEWER,
            AgentRole.TESTER,
        ]
        return [r for r in order if self.has(r)] or [AgentRole.EXECUTOR]

    @staticmethod
    def _utcnow():
        from datetime import datetime, timezone

        return datetime.now(timezone.utc)