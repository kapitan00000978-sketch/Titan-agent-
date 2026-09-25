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
    parser.add_argument("--tui", action="store_true", help="Launch full-screen Terminal TUI mode (OpenCode/Textual style)")
    parser.add_argument("--web", action="store_true", help="Launch Web Control Panel UI in browser")

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
    import socket

    def _find_free_port(host: str, start_port: int) -> int:
        p = start_port
        while p < start_port + 200:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                try:
                    s.bind((host if host != "0.0.0.0" else "127.0.0.1", p))
                    return p
                except OSError:
                    p += 1
        return start_port

    requested_port = args.port or SERVER_PORT
    port = _find_free_port(SERVER_HOST, requested_port)
    if port != requested_port:
        print(f"ℹ️ Port {requested_port} is busy. Automatically switched to available port {port}.")

    if args.telegram:
        from titan_agent.telegram_bot import run_bot_standalone
        asyncio.run(run_bot_standalone())
    elif args.cli:
        from cli import main as cli_main
        asyncio.run(cli_main())
    elif args.tui or (not args.web and not args.port and len(sys.argv) == 1):
        from ui.tui_app import UniversalAgentTUI
        app = UniversalAgentTUI()
        app.run()
    else:
        display_host = "localhost" if SERVER_HOST in ("0.0.0.0", "127.0.0.1") else SERVER_HOST
        url = f"http://{display_host}:{port}"
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


def universal_cli():
    """Default entrypoint when invoked via `universal` command in terminal."""
    if "--web" in sys.argv:
        main()
    elif "--tui" in sys.argv:
        from ui.tui_app import UniversalAgentTUI
        app = UniversalAgentTUI()
        app.run()
    elif "--telegram" in sys.argv:
        from titan_agent.telegram_bot import run_bot_standalone
        asyncio.run(run_bot_standalone())
    else:
        # Default behavior of `universal` is interactive CLI terminal
        from cli import main as cli_main
        asyncio.run(cli_main())


if __name__ == "__main__":
    main()