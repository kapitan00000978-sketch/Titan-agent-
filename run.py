import argparse
import asyncio
import os
import sys
import webbrowser

import uvicorn

if sys.platform == "win32":
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding='utf-8', errors='replace')
            except (OSError, ValueError):
                pass  # best-effort: keep default streams if reconfigure is unsupported


def main():
    parser = argparse.ArgumentParser(description="Universal Agent HP - Ultra-powerful Autonomous AI Agent")
    parser.add_argument("--cli", action="store_true", help="Launch interactive Terminal CLI mode")
    parser.add_argument("--port", type=int, default=None, help="Web server port (default: from .env, usually 7860)")
    parser.add_argument("--no-browser", action="store_true", help="Do not automatically open the browser")
    parser.add_argument("--provider", default=None, help="Override LLM provider (puter, ollama, openrouter, deepseek, groq, lmstudio, openai)")
    parser.add_argument("--model", default=None, help="Override model name/id (e.g. hermes3:8b, deepseek/deepseek-v4-pro)")
    parser.add_argument("--mode", default=None, help="CLI mode: fast, deep or deep_search (default: fast)")
    parser.add_argument("--effort", default=None, help="Effort level: auto, low, medium, high or ultra (default: auto)")
    parser.add_argument("--telegram", action="store_true", help="Launch Telegram Bot mode")

    args = parser.parse_args()

    # Apply overrides BEFORE importing config (config reads env at import time)
    if args.provider:
        os.environ["TITAN_PROVIDER"] = args.provider
    if args.model:
        os.environ["TITAN_MODEL"] = args.model
    if args.mode:
        os.environ["TITAN_MODE"] = args.mode
    if args.effort:
        os.environ["TITAN_EFFORT"] = args.effort

    # Import here so the env overrides take effect
    from titan_agent.config import SERVER_HOST, SERVER_PORT

    port = args.port or SERVER_PORT

    if args.telegram:
        from titan_agent.telegram_bot import run_bot_standalone
        asyncio.run(run_bot_standalone())
    elif args.cli:
        from cli import main as cli_main
        asyncio.run(cli_main())
    else:
        url = f"http://{SERVER_HOST}:{port}"
        print("\n" + "="*60)
        print("⚡ UNIVERSAL AGENT HP IS STARTING")
        print(f"🌐 Web Control Panel: {url}")
        print("🔌 MCP Protocol & Multi-Model System Active")
        print("="*60 + "\n")

        if not args.no_browser:
            try:
                webbrowser.open(url)
            except (OSError, webbrowser.Error) as e:
                print(f"⚠️  Could not open browser automatically: {e}")

        uvicorn.run("titan_agent.server:app", host=SERVER_HOST, port=port, reload=False)


if __name__ == "__main__":
    main()