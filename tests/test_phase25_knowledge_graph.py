"""Tests for Phase 25: Causal Knowledge Graph Memory Layer."""
from titan_agent.core.memory.ast_graph_extractor import WorkspaceASTGraphExtractor
from titan_agent.core.memory.knowledge_graph import KnowledgeGraph
from titan_agent.tools import ToolRegistry


def test_kg_entity_and_relation_management(tmp_path):
    storage_file = tmp_path / "kg.json"
    kg = KnowledgeGraph(storage_file=storage_file)

    kg.add_entity("auth_service", entity_type="module", name="Authentication Service")
    kg.add_entity("jwt_handler", entity_type="class", name="JWTHandler")
    kg.add_relation("auth_service", "uses", "jwt_handler", properties={"weight": 1.0})

    assert len(kg.entities) == 2
    assert len(kg.relations) == 1
    assert "auth_service" in kg.entities
    assert "jwt_handler" in kg.entities

    # Test persistence
    kg.save()
    assert storage_file.exists()

    kg_loaded = KnowledgeGraph(storage_file=storage_file)
    assert len(kg_loaded.entities) == 2
    assert len(kg_loaded.relations) == 1
    assert kg_loaded.entities["jwt_handler"].name == "JWTHandler"


def test_kg_query_and_paths():
    kg = KnowledgeGraph()
    # A -> B -> C -> D
    kg.add_relation("A", "calls", "B")
    kg.add_relation("B", "calls", "C")
    kg.add_relation("C", "calls", "D")

    # Path finding
    node_path = kg.find_node_path("A", "D")
    assert node_path == ["A", "B", "C", "D"]
    edge_path = kg.find_path("A", "D")
    assert len(edge_path) == 3
    assert edge_path[0].source == "A"
    assert edge_path[-1].target == "D"

    # Neighbors
    outgoing = kg.query_neighbors("B", direction="outgoing")
    assert len(outgoing) == 1
    assert outgoing[0][1].id == "C"

    incoming = kg.query_neighbors("B", direction="incoming")
    assert len(incoming) == 1
    assert incoming[0][1].id == "A"

    both = kg.query_neighbors("B", direction="both")
    assert len(both) == 2


def test_kg_impact_analysis():
    kg = KnowledgeGraph()
    # Core -> ModA -> Feature1
    # Core -> ModB
    kg.add_relation("Core", "provides_base", "ModA")
    kg.add_relation("ModA", "powers", "Feature1")
    kg.add_relation("Core", "provides_base", "ModB")

    impact = kg.impact_analysis("Core")
    assert impact["root_entity"] == "Core"
    assert "ModA" in impact["direct_dependents"]
    assert "ModB" in impact["direct_dependents"]
    assert "Feature1" in impact["total_impacted_entities"]
    assert impact["depth_reached"] >= 2


def test_ast_graph_extractor(tmp_path):
    # Create sample Python codebase
    src = tmp_path / "pkg"
    src.mkdir()
    
    file_a = src / "base.py"
    file_a.write_text("class BaseService:\n    def execute(self):\n        pass\n", encoding="utf-8")
    
    file_b = src / "auth.py"
    file_b.write_text("from pkg.base import BaseService\n\nclass AuthService(BaseService):\n    def login(self):\n        return True\n", encoding="utf-8")

    extractor = WorkspaceASTGraphExtractor(tmp_path)
    kg = extractor.extract()

    # Verify extracted entities
    rel_a = str(file_a.relative_to(tmp_path)).replace("\\", "/")
    rel_b = str(file_b.relative_to(tmp_path)).replace("\\", "/")

    assert rel_a in kg.entities
    assert rel_b in kg.entities
    assert f"{rel_a}::BaseService" in kg.entities
    assert f"{rel_b}::AuthService" in kg.entities
    assert f"{rel_b}::login" in kg.entities

    # Verify mermaid output
    mermaid = kg.to_mermaid()
    assert "graph TD" in mermaid
    assert "AuthService" in mermaid


def test_tools_kg_integration(tmp_path):
    registry = ToolRegistry(workspace=tmp_path)
    
    # Tool: add fact
    add_out = registry.tool_kg_add_fact("Database", "hosts", "UsersTable")
    assert "Successfully added knowledge graph fact" in add_out

    # Tool: query
    query_out = registry.tool_kg_query("Database")
    assert "### KNOWLEDGE GRAPH QUERY: Database" in query_out
    assert "hosts" in query_out
    assert "UsersTable" in query_out

    # Tool: impact analysis
    registry.tool_kg_add_fact("UsersTable", "used_by", "AuthAPI")
    impact_out = registry.tool_kg_impact_analysis("Database")
    assert "### KNOWLEDGE GRAPH IMPACT ANALYSIS: Database" in impact_out
    assert "UsersTable" in impact_out
    assert "AuthAPI" in impact_out

    # Tool: index workspace
    test_py = tmp_path / "module.py"
    test_py.write_text("def hello_world():\n    return 'hi'\n", encoding="utf-8")
    index_out = registry.tool_kg_index_workspace()
    assert "Indexed workspace AST into Knowledge Graph" in index_out
