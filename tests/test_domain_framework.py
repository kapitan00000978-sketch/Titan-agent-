"""
Unit and integration tests for the Universal Agent Omni-Domain Adaptation Framework.
Verifies domain profiling across software engineering, finance, healthcare, legal, science, and custom enterprise domains.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from titan_agent.core.domain import BUILTIN_DOMAINS, DomainManager, DomainProfile
from titan_agent.tools import ToolRegistry


def test_builtin_domains_presence():
    """Verify core industry domains are pre-registered and complete."""
    expected_domains = {
        "universal",
        "software_engineering",
        "finance",
        "healthcare",
        "legal",
        "marketing",
        "science",
        "education",
        "ecommerce",
        "customer_support",
        "multimedia",
        "cybersecurity",
    }
    assert expected_domains.issubset(set(BUILTIN_DOMAINS.keys()))

    # Verify healthcare domain has clinical safety guardrail
    health = BUILTIN_DOMAINS["healthcare"]
    assert any("CLINICAL SAFETY DISCLAIMER" in g for g in health.mandatory_guardrails)
    assert health.icon == "⚕️"

    # Verify finance domain has non-advisory disclaimer
    fin = BUILTIN_DOMAINS["finance"]
    assert any("NON-ADVISORY DISCLAIMER" in g for g in fin.mandatory_guardrails)
    assert fin.icon == "📈"

    # Verify legal domain has legal counsel disclaimer
    legal = BUILTIN_DOMAINS["legal"]
    assert any("LEGAL COUNSEL DISCLAIMER" in g for g in legal.mandatory_guardrails)
    assert legal.icon == "⚖️"


def test_domain_profile_serialization():
    """Verify DomainProfile serialization to/from dictionary."""
    profile = DomainProfile(
        name="biotech",
        display_name="Biotechnology & Genetics",
        icon="🧬",
        description="Genomic sequencing and CRISPR workflow analysis.",
        system_prompt_overlay="1. Verify gene identifiers against NCBI.",
        mandatory_guardrails=["Comply with bio-safety standards."],
        preferred_tools=["web_search", "python_eval"],
        forbidden_tools=["dangerous_tool"],
    )
    d = profile.to_dict()
    assert d["name"] == "biotech"
    assert d["icon"] == "🧬"

    rebuilt = DomainProfile.from_dict(d)
    assert rebuilt.name == "biotech"
    assert rebuilt.display_name == "Biotechnology & Genetics"
    assert rebuilt.mandatory_guardrails == ["Comply with bio-safety standards."]
    assert rebuilt.forbidden_tools == ["dangerous_tool"]

    overlay = rebuilt.build_overlay_text()
    assert "🧬 BIOTECHNOLOGY & GENETICS" in overlay
    assert "Verify gene identifiers against NCBI" in overlay
    assert "Comply with bio-safety standards" in overlay


def test_domain_manager_switching_and_aliases():
    """Verify switching active domain and resolving colloquial aliases."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        dm = DomainManager(domains_dir=Path(tmp_dir), default_domain="universal")
        assert dm.active_domain_name == "universal"

        # Switch to finance
        dm.switch_domain("finance")
        assert dm.active_domain_name == "finance"
        assert dm.active_domain.display_name == "Finance, Banking & Quantitative Modeling"

        # Switch using alias 'dev' -> 'software_engineering'
        dm.switch_domain("dev")
        assert dm.active_domain_name == "software_engineering"

        # Switch using alias 'med' -> 'healthcare'
        dm.switch_domain("med")
        assert dm.active_domain_name == "healthcare"

        # Switch using alias 'law' -> 'legal'
        dm.switch_domain("law")
        assert dm.active_domain_name == "legal"

        # Unknown domain raises ValueError
        with pytest.raises(ValueError, match="Unknown domain 'non_existent_xyz'"):
            dm.switch_domain("non_existent_xyz")


def test_custom_domain_registration_and_persistence():
    """Verify registering a custom enterprise domain, saving to disk, and reloading."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        domains_path = Path(tmp_dir)
        dm = DomainManager(domains_dir=domains_path)

        custom = DomainProfile(
            name="logistics_supply",
            display_name="Global Freight & Maritime Logistics",
            icon="🚢",
            description="Container tracking, port demurrage analysis, and freight forwarding.",
            system_prompt_overlay="1. Model port turnaround times and container detention rates.",
            mandatory_guardrails=["Verify IMO/HS codes before shipping declarations."],
            preferred_tools=["web_search", "python_eval"],
            forbidden_tools=["destructive_cmd"],
        )

        dm.register_domain(custom, persist=True)

        # Check JSON was saved
        saved_file = domains_path / "logistics_supply.json"
        assert saved_file.exists()

        # Create fresh manager pointing to same folder
        dm2 = DomainManager(domains_dir=domains_path)
        assert dm2.get_domain("logistics_supply") is not None
        dm2.switch_domain("logistics_supply")
        assert dm2.active_domain.icon == "🚢"
        assert "GLOBAL FREIGHT" in dm2.build_system_overlay()

        # Test tool restriction
        allowed, err = dm2.is_tool_allowed("destructive_cmd")
        assert allowed is False
        assert "restricted under active domain" in err

        allowed_ok, err_ok = dm2.is_tool_allowed("web_search")
        assert allowed_ok is True
        assert err_ok is None


def test_cannot_delete_builtin_domain():
    """Verify built-in system domains are protected from deletion."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        dm = DomainManager(domains_dir=Path(tmp_dir))
        with pytest.raises(ValueError, match="Cannot delete built-in system domain"):
            dm.delete_custom_domain("finance")


@pytest.mark.asyncio
async def test_tool_registry_domain_integration():
    """Verify ToolRegistry exposes and executes all domain management tools."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        workspace_path = Path(tmp_dir)
        registry = ToolRegistry(workspace=workspace_path)
        defs = registry.get_tool_definitions()
        names = {d["function"]["name"] for d in defs}

        assert "domain_list" in names
        assert "domain_switch" in names
        assert "domain_get_active" in names
        assert "domain_create" in names

        # 1. Test domain_list
        list_res = await registry.execute_tool("domain_list", {})
        assert "Universal Agent Industry Domains" in list_res
        assert "finance" in list_res
        assert "healthcare" in list_res
        assert "legal" in list_res

        # 2. Test domain_switch
        switch_res = await registry.execute_tool("domain_switch", {"domain": "finance"})
        assert "Switched Active Domain" in switch_res
        assert "Finance" in switch_res

        # 3. Test domain_get_active
        active_res = await registry.execute_tool("domain_get_active", {})
        assert "Current Active Domain Profile" in active_res
        assert "finance" in active_res
        assert "NON-ADVISORY DISCLAIMER" in active_res

        # 4. Test domain_create
        create_res = await registry.execute_tool(
            "domain_create",
            {
                "name": "aerospace_avionics",
                "display_name": "Aerospace & Avionics Systems",
                "description": "DO-178C software assurance and flight dynamics.",
                "system_prompt_overlay": "Follow Level-A safety critical guidelines.",
                "icon": "✈️",
                "mandatory_guardrails": ["Require dual-redundancy proof on flight controls."],
            },
        )
        assert "Custom Domain Profile `aerospace_avionics` created" in create_res
        assert "✈️" in create_res
