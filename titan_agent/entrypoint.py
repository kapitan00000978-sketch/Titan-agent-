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
    import argparse

    parser = argparse.ArgumentParser(
        prog="universal",
        description=(
            "⚡ Universal Agent HP — 10-layer Autonomous AI Agent OS\n"
            "  Run an entire AI software company from your terminal.\n"
            "  Supports 500+ models, DAG planning, zero-loss rollback,\n"
            "  multi-agent debate, and continuous self-improvement."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  universal                                    Interactive CLI (default)\n"
            "  universal --web                              Web Control Panel\n"
            "  universal --tui                              Full-screen TUI\n"
            "  universal --telegram                         Telegram Bot\n"
            "  universal --provider ollama --model llama3   Use local Ollama\n"
            "  universal --mode deep --effort high          Deep reasoning\n"
            '  universal "Explain this code"                One-shot task\n'
            '  universal --meta "Build a REST API"          CEO orchestrator\n'
            '  universal --dag "Refactor and test"          DAG parallel planner\n'
            '  universal --strategy debate "Migrate?"       Multi-agent debate\n'
            "\n"
            "Interactive Slash Commands (inside CLI session):\n"
            "  /plan, /review, /fix, /test, /research, /security-scan\n"
            "  /explain, /remember, /handoff, /queue, /daemon\n"
            "  /skills, /memory, /status, /help, /clear\n"
            "  mode fast|deep|deep_search    effort auto|low|medium|high|ultra"
        ),
    )

    parser.add_argument("--web", action="store_true", help="Launch Web Control Panel in browser")
    parser.add_argument("--tui", action="store_true", help="Launch full-screen Terminal TUI (OpenCode-style)")
    parser.add_argument("--telegram", action="store_true", help="Launch Telegram Bot mode")
    parser.add_argument("--provider", type=str, help="LLM provider (ollama, openai, puter, deepseek, groq, lmstudio)")
    parser.add_argument("--model", type=str, help="Model name (e.g. deepseek-r1:8b, gpt-4o, claude-3-5-sonnet)")
    parser.add_argument("--mode", type=str, choices=["fast", "deep", "deep_search"], help="Reasoning mode (default: fast)")
    parser.add_argument("--effort", type=str, choices=["auto", "low", "medium", "high", "ultra"], help="Effort level (default: auto)")
    parser.add_argument("--strategy", type=str, choices=["auto", "plan", "react", "tot", "reflexion", "debate"], help="Reasoning strategy")
    parser.add_argument("--meta", action="store_true", help="Run with CEO Meta-Orchestrator & Team Leads")
    parser.add_argument("--dag", action="store_true", help="Run with DAG Wave-Based Parallel Planner")
    parser.add_argument("--department", "--dep", action="append", help="Target department(s) for Meta-Orchestrator")
    parser.add_argument("prompt", nargs="*", help="One-shot prompt to execute directly")

    args = parser.parse_args()

    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    # Apply overrides to env so config picks them up
    if args.provider:
        os.environ["TITAN_PROVIDER"] = args.provider
    if args.model:
        os.environ["TITAN_MODEL"] = args.model
    if args.mode:
        os.environ["TITAN_MODE"] = args.mode
    if args.effort:
        os.environ["TITAN_EFFORT"] = args.effort

    if args.web:
        import run
        run.main()
    elif args.tui:
        from titan_agent.tui import TitanOS
        app = TitanOS()
        app.run()
    elif args.telegram:
        from titan_agent.telegram_bot import run_bot_standalone
        asyncio.run(run_bot_standalone())
    else:
        # Build sys.argv for cli.py's argparse
        cli_args = []
        if args.provider:
            cli_args.extend(["--provider", args.provider])
        if args.model:
            cli_args.extend(["--model", args.model])
        if args.mode:
            cli_args.extend(["--mode", args.mode])
        if args.effort:
            cli_args.extend(["--effort", args.effort])
        if args.strategy:
            cli_args.extend(["--strategy", args.strategy])
        if args.meta:
            cli_args.append("--meta")
        if args.dag:
            cli_args.append("--dag")
        if args.department:
            for d in args.department:
                cli_args.extend(["--department", d])
        if args.prompt:
            cli_args.extend(args.prompt)

        sys.argv = ["universal"] + cli_args
        from cli import main as cli_main
        asyncio.run(cli_main())


if __name__ == "__main__":
    universal_cli()

