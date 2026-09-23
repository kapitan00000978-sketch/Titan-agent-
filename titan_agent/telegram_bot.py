"""Telegram Bot Runner for Titan Agent.

Allows users to control and converse with Titan Agent directly via Telegram.
Supports /start, /help, /status, /mode, /effort commands and executes autonomous
agent tasks in real time with status updates.
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
from typing import Any

import aiohttp

from .agent import TitanAgent
from .config import (
    DEFAULT_MODEL,
    DEFAULT_PROVIDER,
    MCP_CONFIG_FILE,
    WORKSPACE_DIR,
)
from .llm_client import LLMClient
from .mcp_client import MCPManager
from .memory import MemoryManager
from .tools import ToolRegistry

logger = logging.getLogger("titan_agent.telegram_bot")


class TitanTelegramBot:
    """Async Telegram Bot client using HTTP long-polling."""

    def __init__(
        self,
        token: str,
        agent: TitanAgent | None = None,
    ):
        self.token = token.strip()
        self.base_url = f"https://api.telegram.org/bot{self.token}"
        self.agent = agent
        self.offset = 0
        self.running = False
        self.user_settings: dict[int, dict[str, str]] = {}  # chat_id -> {mode, effort}

    async def _init_agent(self) -> TitanAgent:
        if self.agent is not None:
            return self.agent
        llm = LLMClient()
        tools = ToolRegistry(WORKSPACE_DIR)
        mcp = MCPManager(MCP_CONFIG_FILE)
        mem = MemoryManager()
        self.agent = TitanAgent(llm=llm, tools=tools, mcp=mcp, memory=mem)
        return self.agent

    async def send_message(
        self,
        session: aiohttp.ClientSession,
        chat_id: int | str,
        text: str,
        parse_mode: str = "Markdown",
    ) -> dict[str, Any]:
        """Send a text message to a Telegram chat."""
        url = f"{self.base_url}/sendMessage"
        # Telegram max message length is 4096 chars
        chunk = text[:4000]
        payload = {
            "chat_id": chat_id,
            "text": chunk,
            "parse_mode": parse_mode,
        }
        try:
            async with session.post(url, json=payload, timeout=15) as res:
                if res.status != 200:
                    # Fallback without parse_mode in case of markdown parsing error
                    payload.pop("parse_mode", None)
                    async with session.post(url, json=payload, timeout=15) as retry_res:
                        return await retry_res.json()
                return await res.json()
        except Exception as e:
            logger.error("Failed to send message to %s: %s", chat_id, e)
            return {"ok": False, "error": str(e)}

    async def send_chat_action(
        self,
        session: aiohttp.ClientSession,
        chat_id: int | str,
        action: str = "typing",
    ) -> None:
        """Send typing action to indicate background processing."""
        url = f"{self.base_url}/sendChatAction"
        try:
            await session.post(url, json={"chat_id": chat_id, "action": action}, timeout=10)
        except Exception:
            pass

    async def handle_update(self, session: aiohttp.ClientSession, update: dict[str, Any]) -> None:
        """Process a single Telegram update."""
        message = update.get("message")
        if not message:
            return
        chat_id = message.get("chat", {}).get("id")
        text = str(message.get("text", "")).strip()
        if not chat_id or not text:
            return

        settings = self.user_settings.setdefault(chat_id, {"mode": "fast", "effort": "medium"})

        # Command handling
        if text.startswith("/start") or text.startswith("/help"):
            msg = (
                "⚡ *Assalomu alaykum! Men TITAN AGENT — Avtonom AI Yordamchisiman.*\n\n"
                "Menga istalgan vazifani bering (kod yozish, tahlil qilish, buyruqlar bajarish):\n\n"
                "📌 *Buyruqlar:*\n"
                "• `/mode <fast|deep|deep_search>` — Rejimni tanlash (Hozir: `" + settings["mode"] + "`)\n"
                "• `/effort <low|medium|high|ultra>` — Kuch darajasini tanlash (Hozir: `" + settings["effort"] + "`)\n"
                "• `/status` — Tizim va model holatini ko'rish\n"
                "• `/help` — Yordam menyusi\n\n"
                "Shunchaki vazifangizni xabar sifatida yozib yuboring!"
            )
            await self.send_message(session, chat_id, msg)
            return

        if text.startswith("/mode"):
            parts = text.split()
            if len(parts) > 1 and parts[1].lower() in ("fast", "deep", "deep_search"):
                settings["mode"] = parts[1].lower()
                await self.send_message(session, chat_id, f"✅ Rejim o'zgartirildi: *{settings['mode']}*")
            else:
                await self.send_message(session, chat_id, "ℹ️ Foydalanish: `/mode <fast|deep|deep_search>`")
            return

        if text.startswith("/effort"):
            parts = text.split()
            if len(parts) > 1 and parts[1].lower() in ("low", "medium", "high", "ultra"):
                settings["effort"] = parts[1].lower()
                await self.send_message(session, chat_id, f"✅ Kuch darajasi o'zgartirildi: *{settings['effort']}*")
            else:
                await self.send_message(session, chat_id, "ℹ️ Foydalanish: `/effort <low|medium|high|ultra>`")
            return

        if text.startswith("/status"):
            msg = (
                "⚡ *Titan Agent Holati:*\n"
                f"• Provider: `{DEFAULT_PROVIDER}`\n"
                f"• Model: `{DEFAULT_MODEL}`\n"
                f"• Rejim: `{settings['mode']}`\n"
                f"• Kuch: `{settings['effort']}`\n"
                f"• Status: `Online & Ready`"
            )
            await self.send_message(session, chat_id, msg)
            return

        # Execute Task through Titan Agent
        await self.send_chat_action(session, chat_id, "typing")
        agent = await self._init_agent()
        session_id = f"tg_{chat_id}"

        status_msg = await self.send_message(
            session,
            chat_id,
            "⚡ *Titan vazifani tahlil qilmoqda va bajarmoqda...*",
        )

        final_answer = ""
        try:
            async for ev in agent.run_task(
                text,
                session_id=session_id,
                mode=settings["mode"],
                effort=settings["effort"],
            ):
                if ev.type == "final_answer":
                    final_answer = (final_answer + "\n\n" + str(ev.data)).strip() if final_answer else str(ev.data)
                elif ev.type == "error":
                    final_answer = f"⚠️ Xatolik: {ev.data}"
        except Exception as e:
            final_answer = f"⚠️ Bajarishda xatolik yuz berdi: {e!s}"

        if not final_answer:
            final_answer = "(Javob ishlab chiqilmadi)"

        await self.send_message(session, chat_id, final_answer)

    async def start_polling(self) -> None:
        """Start long-polling loop for incoming updates."""
        self.running = True
        logger.info("Titan Telegram Bot started long-polling...")
        async with aiohttp.ClientSession() as session:
            while self.running:
                try:
                    url = f"{self.base_url}/getUpdates"
                    params = {"offset": self.offset, "timeout": 20}
                    async with session.get(url, params=params, timeout=30) as res:
                        if res.status == 200:
                            data = await res.json()
                            if data.get("ok"):
                                updates = data.get("result", [])
                                for update in updates:
                                    self.offset = update["update_id"] + 1
                                    asyncio.create_task(self.handle_update(session, update))
                        else:
                            await asyncio.sleep(2)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.warning("Polling connection error: %s", e)
                    await asyncio.sleep(3)


async def run_bot_standalone(token: str | None = None) -> None:
    bot_token = token or os.getenv("TITAN_TELEGRAM_BOT_TOKEN", "")
    if not bot_token:
        print("❌ Error: TITAN_TELEGRAM_BOT_TOKEN is not set in .env or passed as argument.")
        print("💡 Create a bot via @BotFather in Telegram and set TITAN_TELEGRAM_BOT_TOKEN=<your_token>")
        sys.exit(1)

    bot = TitanTelegramBot(token=bot_token)
    print("\n" + "=" * 60)
    print("⚡ TITAN AGENT TELEGRAM BOT IS ACTIVE")
    print("🤖 Send /start in Telegram to interact with Titan!")
    print("=" * 60 + "\n")
    await bot.start_polling()


if __name__ == "__main__":
    asyncio.run(run_bot_standalone())
