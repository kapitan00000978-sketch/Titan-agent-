"""Phase 11 — Intent Router: deterministic routing engine + tool surface tests."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from titan_agent.intent_router import ROUTE_RULES, IntentRoute, route_intent

# --------------------------------------------------------------------------
# Primary-role routing
# --------------------------------------------------------------------------

def test_route_basic_roles():
    cases = {
        # core Phase 9 roles
        "implement a login feature in the app": "coder",
        "fix the bug in the parser": "coder",
        "review my code for bugs": "reviewer",
        "check my code for correctness": "reviewer",
        "plan the migration steps": "planner",
        "research what the competitors charge": "researcher",
        "run the tests and report pass/fail": "tester",
        # Phase 11 quality / safety roles
        "security audit the payment module": "security",
        "check the login for SQL injection and secret leaks": "security",
        "write unit tests for the parser": "test_writer",
        "add test coverage for the new module": "test_writer",
        "summarize this long conversation": "summarizer",
        "remember that we chose FastAPI": "memory_keeper",
        "how much did the agents spend this month": "cost_watcher",
        "triage this error as critical or minor": "triager",
        # Phase 11 docs / ops / routing roles
        "update the README for the new API": "doc_writer",
        "write a changelog entry for today's commits": "changelogger",
        "deploy to staging and rollback on failure": "deployer",
        "check for outdated dependencies and update them": "dependency_updater",
        "which agent should handle this request": "router",
    }
    for task, expected in cases.items():
        route = route_intent(task)
        assert route.primary_role == expected, (
            f"{task!r} -> {route.primary_role} (want {expected})"
        )


def test_route_falls_back_on_empty_and_unknown():
    assert route_intent(None).primary_role == "generalist"
    assert route_intent("").primary_role == "generalist"
    assert route_intent("  ").primary_role == "generalist"
    assert route_intent("hello, how are you doing?").primary_role == "generalist"


# --------------------------------------------------------------------------
# Multi-role routing (supporting roles + tie-breaks)
# --------------------------------------------------------------------------

def test_route_supports_secondary_role():
    # test writer picks up a documentation companion
    route = route_intent("write unit tests for the login and update the README")
    assert route.primary_role == "test_writer"
    assert route.supporting_roles == ("doc_writer",)


def test_route_security_wins_over_reviewer_on_tie():
    # "review ... SQL injection": security rule is earlier, so it wins the tie
    # and the reviewer becomes the supporting role (the user's exact scenario).
    route = route_intent("review the new login for SQL injection")
    assert route.primary_role == "security"
    assert "reviewer" in route.supporting_roles


def test_route_reason_and_plan_text():
    route = route_intent("implement a login feature")
    assert route.reason.startswith("Matched keywords:")
    assert "coder" in route.reason
    text = route.plan_text()
    assert "Primary: coder" in text
    assert "Reason:" in text


def test_route_is_frozen_dataclass():
    r = IntentRoute(primary_role="coder")
    assert r.supporting_roles == ()
    assert r.reason == ""


# --------------------------------------------------------------------------
# Rule / roster integrity
# --------------------------------------------------------------------------

def test_rule_roles_all_resolve():
    from titan_agent.staff import get_specialist

    for keywords, role in ROUTE_RULES:
        assert keywords, f"empty keywords for {role}"
        assert get_specialist(role).id == role, f"role {role} not in roster"


def test_phase11_aliases_resolve():
    from titan_agent.staff import get_specialist

    for alias, want in {
        "audit": "security",
        "changelog": "changelogger",
        "deploy": "deployer",
        "docs": "doc_writer",
        "memory": "memory_keeper",
        "cost": "cost_watcher",
        "route": "router",
        "triage": "triager",
        "summary": "summarizer",
        "dependencies": "dependency_updater",
        "write_tests": "test_writer",
    }.items():
        assert get_specialist(alias).id == want, alias


# --------------------------------------------------------------------------
# Tool surface
# --------------------------------------------------------------------------

def test_tool_subagent_route_surface():
    from titan_agent.tools import ToolRegistry

    registry = ToolRegistry()
    out = registry.tool_subagent_route("implement a login")
    assert out.startswith("### INTENT ROUTE")
    assert "Primary: coder" in out
    assert "Error: task is required." in registry.tool_subagent_route("")
    assert "Error: task is required." in registry.tool_subagent_route(None)


def test_tool_catalog_includes_subagent_route():
    from titan_agent.tools import ToolRegistry

    defs = ToolRegistry().get_tool_definitions()
    names = [d.get("function", {}).get("name") for d in defs]
    assert "subagent_route" in names
    by_name = {d.get("function", {}).get("name", ""): d for d in defs}
    props = by_name["subagent_route"]["function"]["parameters"]["properties"]
    assert "task" in props
    assert "required" in by_name["subagent_route"]["function"]["parameters"]


def test_route_multilingual_uzbek_and_russian():
    """Verify that intent routing natively supports Uzbek and Russian tokens."""
    cases = {
        "ushbu funksiya uchun unit test yoz": "test_writer",
        "yangi versiyani serverga deploy qil": "deployer",
        "login tizimida xavfsizlik va zaiflikni tekshir": "security",
        "barcha testlarni ishga tushir": "tester",
        "matnni qisqartir va umumlashtir": "summarizer",
        "muhim qarorni xotiraga saqla": "memory_keeper",
        "kodni ko'rib chiq va taqriz ber": "reviewer",
        "loyiha uchun reja tuz": "planner",
        "xatoni to'g'irla va kod yoz": "coder",
        "написать код для новой фичи": "coder",
        "проверить безопасность системы": "security",
    }
    for task, expected in cases.items():
        route = route_intent(task)
        assert route.primary_role == expected, (
            f"{task!r} -> {route.primary_role} (want {expected})"
        )