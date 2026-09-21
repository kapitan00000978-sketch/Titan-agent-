"""Skills system tests (Block 1: Hermes-style skill playbooks)."""
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from titan_agent.skills import SkillRegistry, _parse_front_matter


SKILL_DIR = Path(__file__).parent / "test_skills_dir"


def test_parse_front_matter():
    raw = "---\nname: foo\ndescription: Bar baz.\nkeywords: alpha, beta\n---\n\nBody text."
    meta = _parse_front_matter(raw)
    assert meta["name"] == "foo"
    assert meta["description"] == "Bar baz."
    assert meta["keywords"] == "alpha, beta"


def test_registry_scans_and_lists(tmp_path):
    d = tmp_path / "skills"
    d.mkdir()
    (d / "research-ops.md").write_text(
        "---\nname: research-ops\ndescription: Multi-source research playbook.\n"
        "keywords: research, sources, citations\n---\n\n# Steps\n1. Search.\n",
        encoding="utf-8",
    )
    (d / "other.txt").write_text("not a skill", encoding="utf-8")
    reg = SkillRegistry(d)
    names = [s["name"] for s in reg.list_skills()]
    assert names == ["research-ops"]
    assert "not a skill" not in str(reg.list_skills())


def test_find_matches_ranks_by_keywords(tmp_path):
    d = tmp_path / "skills"
    d.mkdir()
    (d / "a.md").write_text(
        "---\nname: research-ops\ndescription: Research playbook.\nkeywords: research, sources\n---\nbody",
        encoding="utf-8",
    )
    (d / "b.md").write_text(
        "---\nname: github-ops\ndescription: Git playbook.\nkeywords: git, commit, pr\n---\nbody",
        encoding="utf-8",
    )
    reg = SkillRegistry(d)
    matches = reg.find_matches("research the sources")
    assert matches
    assert matches[0].name == "research-ops"
    no_match = reg.find_matches("zzzqqq")
    assert no_match == []


def test_get_skill_returns_full_text(tmp_path):
    d = tmp_path / "skills"
    d.mkdir()
    (d / "coding.md").write_text(
        "---\nname: coding-rules\ndescription: Code discipline.\nkeywords: code\n---\n\nRun tests before done.",
        encoding="utf-8",
    )
    reg = SkillRegistry(d)
    skill = reg.get_skill("coding-rules")
    assert skill is not None
    assert "Run tests before done." in skill.full_text()
    assert reg.get_skill("missing") is None


def test_build_system_block_injects_matches(tmp_path):
    d = tmp_path / "skills"
    d.mkdir()
    (d / "sec.md").write_text(
        "---\nname: security-ops\ndescription: Security review playbook.\nkeywords: security, vuln\n---\n\nCheck injection.",
        encoding="utf-8",
    )
    reg = SkillRegistry(d)
    block = reg.build_system_block("run a security scan for vulnerabilities")
    assert "RELEVANT SKILL PLAYBOOKS" in block
    assert "security-ops" in block
    assert reg.build_system_block("nothing relevant here") == ""


def test_catalog_skills_available():
    """The real skills directory ships with playbook samples."""
    reg = SkillRegistry()
    names = {s["name"] for s in reg.list_skills()}
    assert "research-ops" in names
    assert "coding-rules" in names
    assert "security-ops" in names