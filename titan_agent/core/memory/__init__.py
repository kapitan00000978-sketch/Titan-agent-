"""
Memory Core - Episodic, Semantic, Procedural and Working memory.

Implements MemGPT/Mem0-style memory patterns with SQLite persistence,
decay-aware retrieval scoring and episodic -> semantic consolidation.
"""
from .ast_graph_extractor import WorkspaceASTGraphExtractor
from .knowledge_graph import GraphEntity, GraphRelation, KnowledgeGraph
from .memory_system import MemorySystem
from .types import (
    ConsolidationResult,
    MemoryKind,
    MemoryQuery,
    MemoryRecord,
    MemoryStats,
)

__all__ = [
    "ConsolidationResult",
    "GraphEntity",
    "GraphRelation",
    "KnowledgeGraph",
    "MemoryKind",
    "MemoryQuery",
    "MemoryRecord",
    "MemoryStats",
    "MemorySystem",
    "WorkspaceASTGraphExtractor",
]