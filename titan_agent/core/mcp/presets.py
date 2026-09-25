"""
MCP Presets & One-Line Connection Manager.

Allows connecting any world-class MCP server (PostgreSQL, GitHub, Slack,
Google Drive, Brave Search, Filesystem, SQLite, Puppeteer) with a single line of
configuration or a single tool call.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


@dataclass
class MCPPreset:
    """Metadata and execution template for an MCP server preset."""

    id: str
    name: str
    description: str
    command: str
    args: list[str]
    env_keys: list[str] = field(default_factory=list)
    default_env: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "command": self.command,
            "args": self.args,
            "env_keys": self.env_keys,
            "default_env": self.default_env,
        }


MCP_PRESETS: dict[str, MCPPreset] = {
    "postgres": MCPPreset(
        id="postgres",
        name="PostgreSQL Database MCP",
        description="Inspect schemas, run read queries, and analyze Postgres database tables.",
        command="npx",
        args=["-y", "@modelcontextprotocol/server-postgres", "{POSTGRES_URL}"],
        env_keys=["POSTGRES_URL"],
    ),
    "github": MCPPreset(
        id="github",
        name="GitHub Integration MCP",
        description="Search repos, create issues, view PRs, and inspect code branches via GitHub API.",
        command="npx",
        args=["-y", "@modelcontextprotocol/server-github"],
        env_keys=["GITHUB_PERSONAL_ACCESS_TOKEN"],
    ),
    "slack": MCPPreset(
        id="slack",
        name="Slack Workspace MCP",
        description="Send notifications, read channel messages, and collaborate in Slack.",
        command="npx",
        args=["-y", "@modelcontextprotocol/server-slack"],
        env_keys=["SLACK_BOT_TOKEN", "SLACK_TEAM_ID"],
    ),
    "brave_search": MCPPreset(
        id="brave_search",
        name="Brave Search MCP",
        description="High-privacy live web and news search using Brave Search API.",
        command="npx",
        args=["-y", "@modelcontextprotocol/server-brave-search"],
        env_keys=["BRAVE_API_KEY"],
    ),
    "filesystem": MCPPreset(
        id="filesystem",
        name="Local Filesystem MCP",
        description="Sandboxed file operations (read, write, list) under specified directory.",
        command="npx",
        args=["-y", "@modelcontextprotocol/server-filesystem", "{WORKSPACE}"],
    ),
    "sqlite": MCPPreset(
        id="sqlite",
        name="SQLite Database MCP",
        description="Connect and query local SQLite database files with zero setup.",
        command="npx",
        args=["-y", "@modelcontextprotocol/server-sqlite", "--db-path", "{WORKSPACE}/database.db"],
    ),
    "puppeteer": MCPPreset(
        id="puppeteer",
        name="Puppeteer Browser MCP",
        description="Headless browser navigation, screenshot capture, and JavaScript console inspection.",
        command="npx",
        args=["-y", "@modelcontextprotocol/server-puppeteer"],
    ),
    "gdrive": MCPPreset(
        id="gdrive",
        name="Google Drive MCP",
        description="Search and access Google Drive files, Google Docs, and spreadsheets.",
        command="npx",
        args=["-y", "@modelcontextprotocol/server-gdrive"],
    ),
}


class MCPPresetManager:
    """Manages preset resolution and dynamic config updates."""

    def __init__(self, config_file: Path | str | None = None):
        self.config_file = Path(config_file) if config_file else Path("mcp_servers.json")

    def list_presets(self) -> list[dict[str, Any]]:
        """Returns catalog of all registered MCP presets."""
        return [p.to_dict() for p in MCP_PRESETS.values()]

    def get_preset(self, preset_id: str) -> MCPPreset | None:
        """Find preset by ID or alias."""
        clean_id = preset_id.lower().strip().replace("-", "_")
        return MCP_PRESETS.get(clean_id)

    def generate_server_config(
        self,
        preset_id: str,
        env_overrides: dict[str, str] | None = None,
        custom_args: list[str] | None = None,
    ) -> tuple[dict[str, Any] | None, str]:
        """Builds a valid MCP server config definition from a preset."""
        preset = self.get_preset(preset_id)
        if not preset:
            available = ", ".join(MCP_PRESETS.keys())
            return None, f"Unknown preset '{preset_id}'. Available presets: {available}"

        env = dict(preset.default_env)
        if env_overrides:
            env.update(env_overrides)

        args = list(custom_args) if custom_args else list(preset.args)

        # Interpolate env values if present in args
        if env_overrides:
            interpolated_args = []
            for arg in args:
                for k, v in env_overrides.items():
                    arg = arg.replace(f"{{{k}}}", v)
                interpolated_args.append(arg)
            args = interpolated_args

        config = {
            "command": preset.command,
            "args": args,
            "env": env,
        }
        return config, ""

    def save_server_to_config(self, server_name: str, server_config: dict[str, Any]) -> bool:
        """Writes or updates a server definition in mcp_servers.json."""
        try:
            data = {"mcpServers": {}}
            if self.config_file.exists():
                try:
                    with open(self.config_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                except Exception:
                    data = {"mcpServers": {}}

            if "mcpServers" not in data or not isinstance(data["mcpServers"], dict):
                data["mcpServers"] = {}

            data["mcpServers"][server_name] = server_config

            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            return True
        except Exception as exc:
            log.warning("Failed to save MCP config: %s", exc)
            return False
