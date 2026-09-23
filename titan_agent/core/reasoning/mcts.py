"""
Monte Carlo Tree Search (MCTS) Engine for Advanced Reasoning.

Implements MCTS for complex, multi-step problem solving.
Phases:
1. Selection (UCT - Upper Confidence Bound applied to Trees)
2. Expansion (LLM thought generation)
3. Simulation/Evaluation (Value network / LLM heuristic scoring)
4. Backpropagation
"""
from __future__ import annotations

import json
import math
from collections.abc import AsyncGenerator

from .interfaces import (
    IEvaluator,
    ILLMProvider,
    IReasoningEngine,
    ReasoningContext,
    complete_text,
)
from .tot import GENERATE_PROMPT, _last_content
from .types import (
    ActionType,
    ReasoningConfig,
    ReasoningStep,
    ReasoningTrace,
    StepStatus,
)


class MCTSNode:
    """A node in the Monte Carlo Search Tree."""
    def __init__(self, state: ReasoningTrace, parent: MCTSNode | None = None):
        self.state = state
        self.parent = parent
        self.children: list[MCTSNode] = []
        self.visits: int = 0
        self.value: float = 0.0
        self.is_terminal: bool = False
        self.is_expanded: bool = False

    def uct_score(self, exploration_constant: float = 1.414) -> float:
        """Calculate the UCT score to balance exploration vs exploitation."""
        if self.visits == 0:
            return float('inf') # Force exploration of unvisited nodes
        
        exploitation = self.value / self.visits
        # If parent has 0 visits, this shouldn't happen normally, but safeguard:
        parent_visits = self.parent.visits if self.parent else self.visits
        exploration = exploration_constant * math.sqrt(math.log(parent_visits) / self.visits)
        return exploitation + exploration

    def best_child(self) -> MCTSNode | None:
        """Return the child with the highest average value."""
        if not self.children:
            return None
        return max(self.children, key=lambda c: (c.value / c.visits) if c.visits > 0 else 0)


class MCTSEngine(IReasoningEngine):
    """Monte Carlo Tree Search reasoning engine for rigorous exploration."""

    def __init__(
        self,
        llm: ILLMProvider,
        evaluator: IEvaluator,
        config: ReasoningConfig | None = None,
    ):
        self.llm = llm
        self.evaluator = evaluator
        self.config = config or ReasoningConfig()
        self._context = ReasoningContext(config=self.config, llm=llm, evaluator=evaluator)

    async def reason(
        self,
        task: str,
        config: ReasoningConfig | None = None,
        trace: ReasoningTrace | None = None,
    ) -> ReasoningTrace:
        if config:
            self.config = config
            self._context.config = config
            
        root_trace = trace or ReasoningTrace(task=task)
        root_trace.steps = []
        root_node = MCTSNode(state=root_trace)

        # MCTS Loop
        iterations = getattr(self.config, 'mcts_simulations', 10)
        
        for _ in range(iterations):
            # 1. Selection
            leaf = self._select(root_node)
            
            # Check if leaf is a solution
            if not leaf.is_terminal:
                solved, confidence = await self.evaluator.is_solution(leaf.state, task)
                if solved:
                    leaf.is_terminal = True
                    leaf.value += confidence
                    self._backpropagate(leaf, confidence)
                    continue

            # 2. Expansion
            if not leaf.is_terminal and not leaf.is_expanded:
                await self._expand(leaf, task)
            
            # 3. Simulation / Evaluation
            # Instead of full rollout (which is expensive in LLMs), we evaluate the node's state
            if leaf.children:
                child = leaf.children[0] # Evaluate the first expanded child
                scores = await self.evaluator.evaluate(root_trace, [child.state])
                reward = scores[0] if scores else 0.5
                
                # 4. Backpropagation
                self._backpropagate(child, reward)
            else:
                # If no children generated (dead end)
                self._backpropagate(leaf, 0.0)
                
        # Find the best path
        best_node = root_node
        while best_node.children:
            best = best_node.best_child()
            if not best:
                break
            best_node = best
            
        best_trace = best_node.state
        
        # Check if the best trace solves it, if not explicitly evaluated yet
        if not best_node.is_terminal:
            solved, _ = await self.evaluator.is_solution(best_trace, task)
            
        if not best_trace.final_answer:
             last = best_trace.get_last_step()
             best_trace.final_answer = last.content if last else "No solution found"
             
        best_trace.completed_at = self._utcnow()
        return best_trace

    async def stream_reason(
        self,
        task: str,
        config: ReasoningConfig | None = None,
    ) -> AsyncGenerator[ReasoningStep, None]:
        if config:
            self.config = config
            self._context.config = config

        root_trace = ReasoningTrace(task=task)
        root_trace.steps = []
        root_node = MCTSNode(state=root_trace)

        iterations = getattr(self.config, 'mcts_simulations', 10)
        
        for i in range(1, iterations + 1):
            yield ReasoningStep(
                action_type=ActionType.PLAN,
                content=f"MCTS Iteration {i}/{iterations}: Exploring paths...",
                status=StepStatus.COMPLETED,
            )
            
            leaf = self._select(root_node)
            
            if not leaf.is_terminal:
                solved, confidence = await self.evaluator.is_solution(leaf.state, task)
                if solved:
                    leaf.is_terminal = True
                    self._backpropagate(leaf, confidence)
                    yield ReasoningStep(
                        action_type=ActionType.DECIDE,
                        content=leaf.state.final_answer or _last_content(leaf.state),
                        status=StepStatus.COMPLETED,
                    )
                    return

            if not leaf.is_terminal and not leaf.is_expanded:
                await self._expand(leaf, task)
            
            if leaf.children:
                child = leaf.children[0]
                scores = await self.evaluator.evaluate(root_trace, [child.state])
                reward = scores[0] if scores else 0.5
                self._backpropagate(child, reward)
                
                # Stream the newly evaluated step
                last_step = child.state.get_last_step()
                if last_step:
                    last_step.status = StepStatus.COMPLETED
                    yield last_step
            else:
                self._backpropagate(leaf, 0.0)

        # Extract best sequence
        best_node = root_node
        while best_node.children:
            best = best_node.best_child()
            if not best:
                break
            best_node = best
            
        best_trace = best_node.state
        best_trace.completed_at = self._utcnow()
        
        yield ReasoningStep(
            action_type=ActionType.DECIDE,
            content=best_trace.final_answer or _last_content(best_trace) or "No solution found",
            status=StepStatus.COMPLETED,
        )

    def _select(self, node: MCTSNode) -> MCTSNode:
        """Traverse the tree to a leaf node using UCT."""
        current = node
        while current.is_expanded and current.children:
            # If any child is unexplored (visits == 0), select it immediately
            unexplored = [c for c in current.children if c.visits == 0]
            if unexplored:
                return unexplored[0]
            
            # Otherwise, use UCT
            current = max(current.children, key=lambda c: c.uct_score())
        return current

    async def _expand(self, node: MCTSNode, task: str) -> None:
        """Generate candidate actions and attach them as children."""
        path_text = " -> ".join(
            s.content for s in node.state.steps if s.content
        ) or "(no progress yet)"
        
        branching_factor = getattr(self.config, 'tot_branching_factor', 3)
        
        # We reuse the ToT generation prompt to propose next thoughts
        raw = await complete_text(
            self.llm,
            messages=[
                {"role": "system", "content": "You output JSON only."},
                {"role": "user", "content": GENERATE_PROMPT.format(
                    task=task[:1500],
                    path=path_text[:2000],
                    count=branching_factor,
                )},
            ],
            temperature=self.config.temperature,
            max_tokens=min(self.config.max_thinking_tokens, 2000),
        )
        
        thoughts = self._parse_string_list(raw)
        
        for thought in thoughts[:branching_factor]:
            new_trace = node.state.model_copy(deep=True)
            new_trace.steps = [s for s in node.state.steps]
            new_trace.add_step(
                ReasoningStep(
                    action_type=ActionType.THINK,
                    content=thought,
                    status=StepStatus.COMPLETED,
                )
            )
            child = MCTSNode(state=new_trace, parent=node)
            node.children.append(child)
            
        node.is_expanded = True

    def _backpropagate(self, node: MCTSNode, reward: float) -> None:
        """Update values up to the root."""
        current: MCTSNode | None = node
        while current is not None:
            current.visits += 1
            current.value += reward
            current = current.parent

    @staticmethod
    def _parse_string_list(raw: str) -> list[str]:
        text = str(raw)
        start = text.find("[")
        end = text.rfind("]")
        if start == -1 or end <= start:
            cleaned = text.strip().strip('"')
            return [cleaned] if cleaned else []
        try:
            data = json.loads(text[start : end + 1])
            return [str(x).strip() for x in data if str(x).strip()]
        except (json.JSONDecodeError, TypeError):
            return [text.strip()] if text.strip() else []

    @staticmethod
    def _utcnow():
        from datetime import datetime, timezone
        return datetime.now(timezone.utc)
