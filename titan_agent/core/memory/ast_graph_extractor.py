"""
Phase 25 — AST Graph Extractor: Scans Python codebase to extract structural & causal knowledge graphs.
"""
from __future__ import annotations

import ast
from pathlib import Path

from .knowledge_graph import KnowledgeGraph


class WorkspaceASTGraphExtractor:
    """Extracts code entities (files, classes, functions, imports) into a KnowledgeGraph."""

    def __init__(self, workspace_root: str | Path):
        self.workspace_root = Path(workspace_root)

    def extract(self, kg: KnowledgeGraph | None = None, max_files: int = 50) -> KnowledgeGraph:
        graph = kg or KnowledgeGraph()
        count = 0

        for py_file in self.workspace_root.rglob("*.py"):
            # Skip hidden, virtual environments and cache
            rel = str(py_file.relative_to(self.workspace_root))
            if any(part.startswith((".", "__")) or part in ("venv", "node_modules", ".git") for part in py_file.parts):
                continue

            self._process_file(py_file, rel, graph)
            count += 1
            if count >= max_files:
                break

        return graph

    def _process_file(self, file_path: Path, rel_path: str, graph: KnowledgeGraph) -> None:
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
            tree = ast.parse(content, filename=str(file_path))
        except (SyntaxError, OSError):
            return

        file_id = rel_path.replace("\\", "/")
        graph.add_entity(entity_id=file_id, entity_type="file", name=file_path.name)

        for node in ast.walk(tree):
            # Imports: `import x` or `from x import y`
            if isinstance(node, ast.Import):
                for alias in node.names:
                    mod_name = alias.name
                    graph.add_entity(mod_name, entity_type="module")
                    graph.add_relation(source=file_id, relation="imports", target=mod_name)
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                if mod:
                    graph.add_entity(mod, entity_type="module")
                    graph.add_relation(source=file_id, relation="imports", target=mod)

            # Class definitions and inheritance
            elif isinstance(node, ast.ClassDef):
                cls_id = f"{file_id}::{node.name}"
                graph.add_entity(cls_id, entity_type="class", name=node.name)
                graph.add_relation(source=file_id, relation="defines", target=cls_id)
                for base in node.bases:
                    if isinstance(base, ast.Name):
                        graph.add_relation(source=cls_id, relation="inherits", target=base.id)

            # Function and method definitions
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                fn_id = f"{file_id}::{node.name}"
                graph.add_entity(fn_id, entity_type="function", name=node.name)
                graph.add_relation(source=file_id, relation="defines", target=fn_id)
