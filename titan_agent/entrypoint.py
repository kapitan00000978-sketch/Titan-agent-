import asyncio
import os
import sys

# Ensure UTF-8 output on Windows
if sys.platform == "win32":
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (OSError, ValueError):
                pass


def universal_cli():
    """Universal Agent HP terminal entrypoint."""
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    import run

    if "--web" in sys.argv:
        run.main()
    elif "--tui" in sys.argv:
        from titan_agent.tui import TitanOS
        app = TitanOS()
        app.run()
    elif "--telegram" in sys.argv:
        from titan_agent.telegram_bot import run_bot_standalone
        asyncio.run(run_bot_standalone())
    else:
        from cli import main as cli_main
        asyncio.run(cli_main())


if __name__ == "__main__":
    universal_cli()
