"""Unit tests for apply_patch and skill_save tools."""
from pathlib import Path
import pytest
from titan_agent.tools import ToolRegistry
from titan_agent.skills import SkillRegistry


@pytest.fixture
def registry(tmp_path):
    return ToolRegistry(tmp_path)


def test_apply_patch_success(registry, tmp_path):
    # Create sample file
    f = tmp_path / "hello.py"
    f.write_text("def hello():\n    print('old')\n", encoding="utf-8")

    patch = """--- a/hello.py
+++ b/hello.py
@@ -1,2 +1,2 @@
 def hello():
-    print('old')
+    print('new world')
"""
    res = registry.tool_apply_patch(patch)
    assert "PATCH APPLIED SUCCESSFULLY" in res
    assert "hello.py" in res

    content = f.read_text(encoding="utf-8")
    assert "print('new world')" in content


def test_apply_patch_empty_or_invalid(registry):
    res = registry.tool_apply_patch("")
    assert "Error: patch is required" in res

    res2 = registry.tool_apply_patch("just random text with no hunks")
    assert "No valid unified diff hunks" in res2


def test_apply_patch_conflict(registry, tmp_path):
    f = tmp_path / "code.py"
    f.write_text("def run():\n    return 123\n", encoding="utf-8")

    patch = """--- a/code.py
+++ b/code.py
@@ -1,2 +1,2 @@
 def missing_function():
-    return 999
+    return 000
"""
    res = registry.tool_apply_patch(patch)
    assert "Error: Patch conflict" in res


def test_skill_save_and_scan(tmp_path):
    skills_dir = tmp_path / "skills"
    reg = SkillRegistry(skills_dir=skills_dir)
    assert len(reg.list_skills()) == 0

    path = reg.save_skill(
        name="pytest-pro",
        description="Best practices for writing fast pytest suites",
        keywords="pytest, unit testing, fixtures",
        guidance="## Rules\n1. Use fixtures\n2. Keep tests fast",
    )
    assert path.exists()
    assert len(reg.list_skills()) == 1

    skill = reg.get_skill("pytest-pro")
    assert skill is not None
    assert skill.name == "pytest-pro"
    assert "fixtures" in skill.keywords
    assert "Use fixtures" in skill.body

    # Test match injection
    matches = reg.find_matches("write unit testing with pytest")
    assert len(matches) == 1
    assert matches[0].name == "pytest-pro"
