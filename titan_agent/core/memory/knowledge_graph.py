"""
Phase 25 — Level 6: Causal Knowledge Graph Memory.

Provides graph-based causal memory: entities (files, modules, concepts, phases, bugs)
and directed semantic relations (depends_on, imports, causes, modifies, calls).
Supports multi-hop path finding, neighbor querying, and impact analysis.
"""
from __future__ import annotations

import json
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class GraphEntity:
    id: str
    type: str  # "file", "module", "class", "function", "phase", "concept", "issue"
    name: str = ""
    properties: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "name": self.name or self.id,
            "properties": self.properties,
            "created_at": self.created_at,
        }


@dataclass
class GraphRelation:
    source: str
    relation: str  # "depends_on", "imports", "causes", "modifies", "calls", "inherits"
    target: str
    weight: float = 1.0
    properties: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "relation": self.relation,
            "target": self.target,
            "weight": self.weight,
            "properties": self.properties,
        }


class KnowledgeGraph:
    """In-memory Knowledge Graph with persistence and multi-hop causal reasoning."""

    def __init__(
        self,
        storage_path: str | Path | None = None,
        storage_file: str | Path | None = None,
    ):
        target_path = storage_path or storage_file
        self.storage_path = Path(target_path) if target_path else None
        self.entities: dict[str, GraphEntity] = {}
        self.out_edges: dict[str, list[GraphRelation]] = {}
        self.in_edges: dict[str, list[GraphRelation]] = {}

        if self.storage_path and self.storage_path.exists():
            self.load(self.storage_path)

    def add_entity(
        self,
        entity_id: str,
        entity_type: str = "concept",
        name: str = "",
        properties: dict[str, Any] | None = None,
    ) -> GraphEntity:
        """Register or update an entity in the graph."""
        e_id = str(entity_id).strip()
        entity = GraphEntity(
            id=e_id,
            type=entity_type,
            name=name or e_id,
            properties=properties or {},
        )
        self.entities[e_id] = entity
        self.out_edges.setdefault(e_id, [])
        self.in_edges.setdefault(e_id, [])
        return entity

    def add_relation(
        self,
        source: str,
        relation: str,
        target: str,
        weight: float = 1.0,
        properties: dict[str, Any] | None = None,
    ) -> GraphRelation:
        """Create a directed relation between source and target entities."""
        s = str(source).strip()
        t = str(target).strip()
        r = str(relation).strip().lower()

        # Auto-create entities if not present
        if s not in self.entities:
            self.add_entity(s, entity_type="concept")
        if t not in self.entities:
            self.add_entity(t, entity_type="concept")

        rel = GraphRelation(
            source=s,
            relation=r,
            target=t,
            weight=weight,
            properties=properties or {},
        )

        # Avoid duplicate edges
        existing = [e for e in self.out_edges[s] if e.relation == r and e.target == t]
        if not existing:
            self.out_edges[s].append(rel)
            self.in_edges[t].append(rel)

        return rel

    @property
    def relations(self) -> list[GraphRelation]:
        return [r for edges in self.out_edges.values() for r in edges]

    def get_entity(self, entity_id: str) -> GraphEntity | None:
        return self.entities.get(str(entity_id).strip())

    def query_neighbors(
        self,
        entity_id: str,
        relation: str | None = None,
        direction: str = "out",
    ) -> list[tuple[GraphRelation, GraphEntity]]:
        """Find immediate connected neighbors."""
        e_id = str(entity_id).strip()
        if e_id not in self.entities:
            return []

        results: list[tuple[GraphRelation, GraphEntity]] = []
        d = str(direction).strip().lower()
        is_out = d in ("out", "outgoing", "both")
        is_in = d in ("in", "incoming", "both")

        if is_out:
            for edge in self.out_edges.get(e_id, []):
                if (relation is None or edge.relation == relation.lower()) and edge.target in self.entities:
                    results.append((edge, self.entities[edge.target]))

        if is_in:
            for edge in self.in_edges.get(e_id, []):
                if (relation is None or edge.relation == relation.lower()) and edge.source in self.entities:
                    results.append((edge, self.entities[edge.source]))

        return results

    def find_path(
        self,
        start_id: str,
        end_id: str,
        max_depth: int = 4,
    ) -> list[GraphRelation] | None:
        """Find the shortest causal path between two entities using BFS."""
        s = str(start_id).strip()
        t = str(end_id).strip()
        if s not in self.entities or t not in self.entities:
            return None
        if s == t:
            return []

        # Queue contains: (current_node, path_of_edges)
        queue = deque([(s, [])])
        visited = {s}

        while queue:
            curr, path = queue.popleft()
            if len(path) >= max_depth:
                continue

            for edge in self.out_edges.get(curr, []):
                next_node = edge.target
                if next_node == t:
                    return path + [edge]
                if next_node not in visited:
                    visited.add(next_node)
                    queue.append((next_node, path + [edge]))

        return None

    def find_node_path(
        self,
        start_id: str,
        end_id: str,
        max_depth: int = 4,
    ) -> list[str] | None:
        """Find the shortest sequence of entity IDs from start to end."""
        edges = self.find_path(start_id, end_id, max_depth=max_depth)
        if edges is None:
            return None
        if not edges:
            return [start_id]
        return [edges[0].source] + [e.target for e in edges]

    def impact_analysis(self, entity_id: str, max_depth: int = 3) -> dict[str, Any]:
        """
        Analyze what entities are impacted if entity_id changes or fails.
        Follows outgoing relations such as 'depends_on', 'imports', 'calls', 'causes'.
        """
        e_id = str(entity_id).strip()
        if e_id not in self.entities:
            return {
                "root_entity": e_id,
                "found": False,
                "affected_count": 0,
                "affected_entities": [],
                "direct_dependents": [],
                "total_impacted_entities": [],
                "depth_reached": 0,
                "impact_chains": [],
            }

        affected: dict[str, int] = {}  # entity_id -> min_depth
        chains: list[list[str]] = []
        queue = deque([(e_id, 0, [e_id])])
        visited = {e_id}

        while queue:
            curr, depth, path = queue.popleft()
            if depth >= max_depth:
                continue

            for edge in self.out_edges.get(curr, []):
                tgt = edge.target
                new_path = path + [f"--[{edge.relation}]-->", tgt]
                chains.append(new_path)
                if tgt not in affected or depth + 1 < affected[tgt]:
                    affected[tgt] = depth + 1
                if tgt not in visited:
                    visited.add(tgt)
                    queue.append((tgt, depth + 1, path + [tgt]))

        affected_details = [
            {
                "id": aid,
                "type": self.entities[aid].type,
                "name": self.entities[aid].name,
                "depth": depth,
            }
            for aid, depth in sorted(affected.items(), key=lambda x: x[1])
        ]

        direct_dependents = [aid for aid, depth in affected.items() if depth == 1]
        total_impacted = list(affected.keys())
        max_depth_reached = max(affected.values()) if affected else 0

        return {
            "root_entity": e_id,
            "found": True,
            "affected_count": len(affected),
            "affected_entities": affected_details,
            "direct_dependents": direct_dependents,
            "total_impacted_entities": total_impacted,
            "depth_reached": max_depth_reached,
            "impact_chains": chains[:30],
        }

    def save(self, path: str | Path | None = None) -> None:
        p = Path(path) if path else self.storage_path
        if not p:
            return
        p.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "entities": [e.to_dict() for e in self.entities.values()],
            "relations": [
                rel.to_dict()
                for edges in self.out_edges.values()
                for rel in edges
            ],
        }
        p.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def load(self, path: str | Path | None = None) -> None:
        p = Path(path) if path else self.storage_path
        if not p or not p.exists():
            return
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            for item in data.get("entities", []):
                self.add_entity(
                    entity_id=item["id"],
                    entity_type=item.get("type", "concept"),
                    name=item.get("name", ""),
                    properties=item.get("properties", {}),
                )
            for r in data.get("relations", []):
                self.add_relation(
                    source=r["source"],
                    relation=r["relation"],
                    target=r["target"],
                    weight=r.get("weight", 1.0),
                    properties=r.get("properties", {}),
                )
        except (OSError, json.JSONDecodeError, KeyError):
            pass

    def to_mermaid(self, limit: int = 40, orientation: str = "TD") -> str:
        lines = [f"graph {orientation}"]
        seen_edges = 0
        for s, edges in self.out_edges.items():
            for edge in edges:
                if seen_edges >= limit:
                    break
                lines.append(f'    {s} -->|"{edge.relation}"| {edge.target}')
                seen_edges += 1
            if seen_edges >= limit:
                break
        return "\n".join(lines)

    def summary(self) -> dict[str, Any]:
        type_counts: dict[str, int] = {}
        for e in self.entities.values():
            type_counts[e.type] = type_counts.get(e.type, 0) + 1

        rel_counts: dict[str, int] = {}
        total_rels = 0
        for edges in self.out_edges.values():
            for r in edges:
                rel_counts[r.relation] = rel_counts.get(r.relation, 0) + 1
                total_rels += 1

        return {
            "total_entities": len(self.entities),
            "total_relations": total_rels,
            "entity_types": type_counts,
            "relation_types": rel_counts,
        }
