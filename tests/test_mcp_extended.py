"""Extended MCP config tests (Block 5: Hermes-class MCP server baseline)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from titan_agent.config import MCP_CONFIG_FILE
from titan_agent.mcp_client import MCPManager


def test_extended_servers_present_in_config():
    cfg = json.loads(MCP_CONFIG_FILE.read_text(encoding="utf-8"))
    servers = cfg.get("mcpServers", {})
    for needed in ("filesystem", "memory", "sequential-thinking", "everything",
                   "github", "fetch", "context7", "chrome-devtools", "obsidian"):
        assert needed in servers, f"missing MCP server: {needed}"


def test_every_server_has_command_and_args():
    cfg = json.loads(MCP_CONFIG_FILE.read_text(encoding="utf-8"))
    for name, details in cfg.get("mcpServers", {}).items():
        assert details.get("command"), name
        assert isinstance(details.get("args"), list), name


def test_env_placeholder_expansion(tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test_token_123")
    cfg_file = tmp_path / "mcp.json"
    cfg_file.write_text(json.dumps({
        "mcpServers": {
            "github": {
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-github"],
                "env": {"GITHUB_TOKEN": "{GITHUB_TOKEN}"}
            }
        }
    }), encoding="utf-8")
    mgr = MCPManager(cfg_file)
    details = mgr.load_config()["mcpServers"]["github"]
    cmd, _args, env = mgr._resolve_server_command(details, tmp_path)
    assert cmd == "npx"
    assert env["GITHUB_TOKEN"] == "ghp_test_token_123"


def test_missing_env_var_becomes_empty_not_crash(tmp_path, monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    cfg_file = tmp_path / "mcp.json"
    cfg_file.write_text(json.dumps({
        "mcpServers": {
            "github": {
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-github"],
                "env": {"GITHUB_TOKEN": "{GITHUB_TOKEN}"}
            }
        }
    }), encoding="utf-8")
    mgr = MCPManager(cfg_file)
    details = mgr.load_config()["mcpServers"]["github"]
    _, _, env = mgr._resolve_server_command(details, tmp_path)
    assert env["GITHUB_TOKEN"] == ""
    assert mgr.servers == {}  # nothing started, nothing crashed


def test_arg_env_placeholder_expansion(tmp_path, monkeypatch):
    monkeypatch.setenv("OBSIDIAN_VAULT", r"C:\Users\me\Documents\MyVault")
    cfg_file = tmp_path / "mcp.json"
    cfg_file.write_text(json.dumps({
        "mcpServers": {
            "obsidian": {
                "command": "npx",
                "args": ["-y", "obsidian-mcp@2", "serve", "--vault", "notes={OBSIDIAN_VAULT}"]
            }
        }
    }), encoding="utf-8")
    mgr = MCPManager(cfg_file)
    details = mgr.load_config()["mcpServers"]["obsidian"]
    cmd, args, _ = mgr._resolve_server_command(details, tmp_path)
    assert cmd == "npx"
    assert args == ["-y", "obsidian-mcp@2", "serve", "--vault", r"notes=C:\Users\me\Documents\MyVault"]


def test_missing_arg_env_var_becomes_empty(tmp_path, monkeypatch):
    monkeypatch.delenv("OBSIDIAN_VAULT", raising=False)
    cfg_file = tmp_path / "mcp.json"
    cfg_file.write_text(json.dumps({
        "mcpServers": {
            "obsidian": {
                "command": "npx",
                "args": ["-y", "obsidian-mcp@2", "serve", "--vault", "notes={OBSIDIAN_VAULT}"]
            }
        }
    }), encoding="utf-8")
    mgr = MCPManager(cfg_file)
    details = mgr.load_config()["mcpServers"]["obsidian"]
    _, args, _ = mgr._resolve_server_command(details, tmp_path)
    assert args[-1] == "notes="


def test_obsidian_config_uses_env_placeholder_for_vault():
    cfg = json.loads(MCP_CONFIG_FILE.read_text(encoding="utf-8"))
    obs = cfg["mcpServers"]["obsidian"]
    assert obs["command"] == "npx"
    assert "--vault" in obs["args"]
    assert any("OBSIDIAN_VAULT" in a for a in obs["args"])