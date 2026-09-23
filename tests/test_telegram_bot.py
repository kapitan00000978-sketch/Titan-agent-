"""Unit tests for TitanTelegramBot."""
import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from titan_agent.agent import AgentEvent
from titan_agent.telegram_bot import TitanTelegramBot


@pytest.fixture
def bot():
    return TitanTelegramBot(token="123456:TEST_TOKEN")


@pytest.mark.asyncio
async def test_bot_commands_start_help(bot):
    session = AsyncMock()
    bot.send_message = AsyncMock()

    update = {
        "update_id": 1,
        "message": {
            "chat": {"id": 999},
            "text": "/start",
        },
    }
    await bot.handle_update(session, update)
    bot.send_message.assert_called_once()
    args = bot.send_message.call_args[0]
    assert args[1] == 999
    assert "Assalomu alaykum" in args[2]


@pytest.mark.asyncio
async def test_bot_commands_mode_and_effort(bot):
    session = AsyncMock()
    bot.send_message = AsyncMock()

    # Change mode
    await bot.handle_update(session, {
        "update_id": 2,
        "message": {"chat": {"id": 999}, "text": "/mode deep_search"},
    })
    assert bot.user_settings[999]["mode"] == "deep_search"
    assert "Rejim o'zgartirildi: *deep_search*" in bot.send_message.call_args[0][2]

    # Change effort
    await bot.handle_update(session, {
        "update_id": 3,
        "message": {"chat": {"id": 999}, "text": "/effort ultra"},
    })
    assert bot.user_settings[999]["effort"] == "ultra"
    assert "Kuch darajasi o'zgartirildi: *ultra*" in bot.send_message.call_args[0][2]


@pytest.mark.asyncio
async def test_bot_status_command(bot):
    session = AsyncMock()
    bot.send_message = AsyncMock()

    await bot.handle_update(session, {
        "update_id": 4,
        "message": {"chat": {"id": 999}, "text": "/status"},
    })
    bot.send_message.assert_called_once()
    assert "Titan Agent Holati" in bot.send_message.call_args[0][2]


@pytest.mark.asyncio
async def test_bot_executes_task(bot):
    session = AsyncMock()
    bot.send_message = AsyncMock()
    bot.send_chat_action = AsyncMock()

    mock_agent = MagicMock()

    async def _fake_run(*args, **kwargs):
        yield AgentEvent(event_type="status", data="thinking")
        yield AgentEvent(event_type="final_answer", data="Hisob-kitob bajarildi: 42")

    mock_agent.run_task = _fake_run
    bot.agent = mock_agent

    await bot.handle_update(session, {
        "update_id": 5,
        "message": {"chat": {"id": 999}, "text": "2+2 nechiga teng?"},
    })

    assert bot.send_message.call_count == 2
    # First is the status update, second is the final answer
    last_msg = bot.send_message.call_args_list[-1][0][2]
    assert "Hisob-kitob bajarildi: 42" in last_msg
