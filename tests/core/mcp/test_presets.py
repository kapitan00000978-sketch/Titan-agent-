from titan_agent.core.mcp.presets import MCP_PRESETS, MCPPresetManager


def test_mcp_presets_catalog(tmp_path):
    mgr = MCPPresetManager(config_file=tmp_path / "mcp_servers.json")
    presets = mgr.list_presets()
    assert len(presets) >= 8

    preset_ids = {p["id"] for p in presets}
    assert "postgres" in preset_ids
    assert "github" in preset_ids
    assert "slack" in preset_ids
    assert "brave_search" in preset_ids
    assert "sqlite" in preset_ids
    assert "filesystem" in preset_ids


def test_mcp_preset_config_generation(tmp_path):
    mgr = MCPPresetManager(config_file=tmp_path / "mcp_servers.json")

    # Postgres config generation
    cfg, err = mgr.generate_server_config(
        "postgres",
        env_overrides={"POSTGRES_URL": "postgresql://user:pass@localhost:5432/mydb"},
    )
    assert not err
    assert cfg is not None
    assert "npx" in cfg["command"]
    assert any("postgresql://user:pass@localhost:5432/mydb" in a for a in cfg["args"])

    # Save to config file
    saved = mgr.save_server_to_config("my_pg", cfg)
    assert saved is True
    assert (tmp_path / "mcp_servers.json").exists()


def test_mcp_preset_unknown():
    mgr = MCPPresetManager()
    cfg, err = mgr.generate_server_config("non_existent_preset")
    assert cfg is None
    assert "Unknown preset" in err
