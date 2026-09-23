import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from titan_agent.tools import ToolRegistry


@pytest.fixture
def registry(tmp_path):
    return ToolRegistry(tmp_path)


def test_docker_sandbox_in_tool_definitions(registry):
    defs = registry.get_tool_definitions()
    names = [d["function"]["name"] for d in defs]
    assert "docker_sandbox_run" in names
    tool_def = next(d["function"] for d in defs if d["function"]["name"] == "docker_sandbox_run")
    assert "command" in tool_def["parameters"]["required"]
    props = tool_def["parameters"]["properties"]
    assert "image" in props
    assert "memory_limit" in props
    assert "mount_workspace" in props
    assert "network" in props


@pytest.mark.asyncio
async def test_docker_sandbox_empty_command(registry):
    res = await registry.tool_docker_sandbox_run("")
    assert "Error: command is required" in res


@pytest.mark.asyncio
async def test_docker_sandbox_no_docker(registry):
    with patch("shutil.which", return_value=None):
        res = await registry.tool_docker_sandbox_run("echo hello")
        assert "docker executable not found" in res


@pytest.mark.asyncio
async def test_docker_sandbox_success(registry):
    mock_proc = AsyncMock()
    mock_proc.communicate.return_value = (b"hello sandbox\n", b"")
    mock_proc.returncode = 0

    with patch("shutil.which", return_value="/usr/bin/docker"), \
         patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec:
        res = await registry.tool_docker_sandbox_run(
            "echo hello sandbox",
            image="alpine:latest",
            memory_limit="256m",
            cpu_quota="0.5",
            mount_workspace=True,
            network="none",
        )
        assert "### DOCKER SANDBOX [alpine:latest] (Exit 0)" in res
        assert "STDOUT:\nhello sandbox" in res

        # Verify command flags passed to docker
        mock_exec.assert_called_once()
        args = mock_exec.call_args[0]
        assert args[0] == "/usr/bin/docker"
        assert "run" in args
        assert "--memory=256m" in args
        assert "--cpus=0.5" in args
        assert "--network=none" in args
        assert "-w" in args
        assert "/workspace" in args
        assert "alpine:latest" in args


@pytest.mark.asyncio
async def test_docker_sandbox_timeout(registry):
    async def _timeout_comm():
        raise asyncio.TimeoutError()

    mock_proc = AsyncMock()
    mock_proc.communicate.side_effect = _timeout_comm

    with patch("shutil.which", return_value="/usr/bin/docker"), \
         patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        res = await registry.tool_docker_sandbox_run("sleep 100", timeout=1.0)
        assert "timed out after 1s" in res


@pytest.mark.asyncio
async def test_docker_sandbox_error(registry):
    with patch("shutil.which", return_value="/usr/bin/docker"), \
         patch("asyncio.create_subprocess_exec", side_effect=OSError("Docker daemon down")):
        res = await registry.tool_docker_sandbox_run("echo fail")
        assert "Docker execution error: Docker daemon down" in res
