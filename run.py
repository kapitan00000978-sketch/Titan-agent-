import argparse
import asyncio
import os
import sys
import webbrowser

import uvicorn

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass


def main():
    parser = argparse.ArgumentParser(description="Titan Agent - Ultra-powerful Autonomous AI Agent")
    parser.add_argument("--cli", action="store_true", help="Launch interactive Terminal CLI mode")
    parser.add_argument("--port", type=int, default=None, help="Web server port (default: from .env, usually 7860)")
    parser.add_argument("--no-browser", action="store_true", help="Do not automatically open the browser")
    parser.add_argument("--provider", default=None, help="Override LLM provider (puter, ollama, openrouter, deepseek, groq, lmstudio, openai)")
    parser.add_argument("--model", default=None, help="Override model name/id (e.g. hermes3:8b, deepseek/deepseek-v4-pro)")
    parser.add_argument("--mode", default=None, help="CLI mode: fast, deep or deep_search (default: fast)")

    args = parser.parse_args()

    # Apply overrides BEFORE importing config (config reads env at import time)
    if args.provider:
        os.environ["TITAN_PROVIDER"] = args.provider
    if args.model:
        os.environ["TITAN_MODEL"] = args.model
    if args.mode:
        os.environ["TITAN_MODE"] = args.mode

    # Import here so the env overrides take effect
    from titan_agent.config import SERVER_HOST, SERVER_PORT

    port = args.port or SERVER_PORT

    if args.cli:
        from cli import main as cli_main
        asyncio.run(cli_main())
    else:
        url = f"http://{SERVER_HOST}:{port}"
        print("\n" + "="*60)
        print("⚡ TITAN AGENT IS STARTING")
        print(f"🌐 Web Control Panel: {url}")
        print("🔌 MCP Protocol & Multi-Model System Active")
        print("="*60 + "\n")

        if not args.no_browser:
            try:
                webbrowser.open(url)
            except Exception:
                pass

        uvicorn.run("titan_agent.server:app", host=SERVER_HOST, port=port, reload=False)


if __name__ == "__main__":
    main()