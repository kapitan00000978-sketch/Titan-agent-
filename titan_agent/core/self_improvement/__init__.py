"""Self-Improvement Loop & Eval Suite package."""

from titan_agent.core.self_improvement.eval_suite import (
    EvalCase,
    EvalRunResult,
    EvalSuite,
)
from titan_agent.core.self_improvement.learning_engine import (
    ImprovementLesson,
    SelfImprovementLoop,
)

__all__ = [
    "EvalCase",
    "EvalRunResult",
    "EvalSuite",
    "ImprovementLesson",
    "SelfImprovementLoop",
]
