import asyncio
import os
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except (AttributeError, OSError, ValueError):
        pass  # best-effort: keep default streams if reconfigure is unsupported
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt

from titan_agent.agent import TitanAgent
from titan_agent.commands import ALL_COMMANDS, expand_slash, parse_local
from titan_agent.config import DEFAULT_MODEL, DEFAULT_PROVIDER, MCP_CONFIG_FILE
from titan_agent.llm_client import LLMClient
from titan_agent.mcp_client import MCPManager

console = Console()

VALID_MODES = ("fast", "deep", "deep_search")
VALID_EFFORTS = ("auto", "low", "medium", "high", "ultra")

async def resolve_cli_provider() -> tuple[str, str]:
    """Puter.js is browser-only, so the CLI auto-falls back to local Ollama."""
    provider, model = DEFAULT_PROVIDER, DEFAULT_MODEL
    if provider == "puter":
        console.print(
            "[yellow]ℹ️ Puter.js provider only works in the Web Dashboard (browser). "
            "Checking for local Ollama models...[/yellow]"
        )
        local = await LLMClient.detect_local_models()
        ollama = local.get("ollama") or []
        if ollama:
            provider, model = "ollama", ollama[0]
            console.print(f"[green]✅ Ollama found: {ollama[0]} → switched to it.[/green]")
        else:
            console.print(
                "[bold red]❌ No Ollama model was found on this computer.[/bold red]\n"
                "[yellow]Solution: (1) Install Ollama and pull a model: `ollama run hermes3`, or\n"
                "(2) Launch the Web Dashboard (Puter.js models run in the browser): python run.py[/yellow]"
            )
            raise SystemExit(1)
    return provider, model

async def main():
    provider, model = await resolve_cli_provider()
    mode = os.getenv("TITAN_MODE", "fast").lower()
    if mode not in VALID_MODES:
        mode = "fast"
    effort = os.getenv("TITAN_EFFORT", "auto").lower()
    if effort not in VALID_EFFORTS:
        effort = "auto"

    console.print(Panel.fit(
        "[bold cyan]⚡ TITAN AGENT[/bold cyan] - [italic]Autonomous AI System, far beyond classic agents[/italic]\n"
        "[dim]Model: " + model + f" ({provider}) | MCP System: Active | Mode: {mode} | Effort: {effort}[/dim]\n"
        "[yellow]Type a command in Uzbek, Russian or English. Modes: fast | deep | deep_search (e.g. `mode deep`). "
        "Effort levels: low | medium | high | ultra (e.g. `effort high`). "
        "Slash commands: /plan, /review, /security-scan, /research, /fix, /test, /explain, "
        "/remember, /handoff, /help, /status, /skills, /memory, /handoffs, /clear. "
        "Type 'exit' to quit.[/yellow]",
        border_style="cyan"
    ))

    # Initialize MCP Manager
    mcp = MCPManager(MCP_CONFIG_FILE)
    with console.status("[bold green]Checking MCP servers...", spinner="dots"):
        await mcp.start_all()

    llm = LLMClient(provider=provider, model=model)
    agent = TitanAgent(mcp=mcp, llm=llm)

    session_id = "cli_session"

    while True:
        try:
            user_input = Prompt.ask("\n[bold green]You[/bold green]")
            if not user_input.strip():
                continue

            # Mode switch command
            lower_input = user_input.strip().lower()
            if lower_input.startswith("mode "):
                new_mode = lower_input.split(None, 1)[1].strip()
                if new_mode in VALID_MODES:
                    mode = new_mode
                    console.print(f"[bold cyan]Mode switched to: {mode}[/bold cyan]")
                else:
                    console.print(f"[bold red]Unknown mode: {new_mode}. Valid: {', '.join(VALID_MODES)}[/bold red]")
                continue
            # Effort level command (also accepts `/effort high`)
            if lower_input.startswith(("effort ", "/effort ")):
                new_effort = lower_input.split(None, 1)[1].strip()
                if new_effort in VALID_EFFORTS:
                    effort = new_effort
                    console.print(f"[bold cyan]Effort level switched to: {effort}[/bold cyan]")
                else:
                    console.print(f"[bold red]Unknown effort: {new_effort}. Valid: {', '.join(VALID_EFFORTS)}[/bold red]")
                continue
            # Slash commands: local ones (help/status/memory/...) and LLM ones (/plan, /review, ...)
            if lower_input.startswith("/"):
                local = parse_local(user_input)
                if local is not None:
                    name_l = local["name"]
                    if name_l == "help":
                        console.print(Panel.fit(
                            "\n".join(f"[cyan]/{k}[/cyan] — {v}" for k, v in ALL_COMMANDS.items()),
                            title="[bold magenta]Slash Commands[/bold magenta]",
                            border_style="magenta"
                        ))
                    elif name_l == "status":
                        console.print(f"[bold cyan]Provider:[/bold cyan] {provider} | [bold cyan]Model:[/bold cyan] {model}\n"
                                      f"[bold cyan]Mode:[/bold cyan] {mode} | [bold cyan]Effort:[/bold cyan] {effort}")
                    elif name_l == "skills":
                        skill_names = agent.skills.list_skills()
                        if skill_names:
                            console.print(Panel.fit(
                                "\n".join(f"- [cyan]{s['name']}[/cyan]: {s['description']}" for s in skill_names),
                                title="[bold magenta]Skill Playbooks[/bold magenta]",
                                border_style="magenta"
                            ))
                        else:
                            console.print("[yellow]No skills loaded.[/yellow]")
                    elif name_l == "memory":
                        query = local["arg"]
                        if not query:
                            facts = agent.memory.get_all_knowledge()
                            console.print("[yellow]Usage: /memory <query>[/yellow]")
                        else:
                            facts = agent.memory.search_knowledge(query, scope=None)
                        if facts and query:
                            console.print(Panel.fit(
                                "\n".join(f"- [{f.get('category')}] {f['key']}: {f['value']}" for f in facts),
                                title=f"[bold magenta]Memory: {query}[/bold magenta]",
                                border_style="magenta"
                            ))
                    elif name_l == "handoffs":
                        msgs = agent.memory.list_handoffs(status="open")
                        if msgs:
                            console.print(Panel.fit(
                                "\n".join(f"- [{m['id']}] {m['title']}" for m in msgs),
                                title="[bold magenta]Open Handoffs[/bold magenta]",
                                border_style="magenta"
                            ))
                        else:
                            console.print("[yellow]No open handoffs.[/yellow]")
                    elif name_l == "clear":
                        agent.memory.clear_session(session_id)
                        console.print("[bold cyan]Session history cleared.[/bold cyan]")
                    elif name_l == "queue":
                        from titan_agent.config import TASK_QUEUE_FILE
                        from titan_agent.queue import TaskQueue

                        q = TaskQueue(TASK_QUEUE_FILE)
                        sub = local["arg"].split(None, 1)
                        op = sub[0].lower() if sub else "list"
                        try:
                            if op == "list":
                                tasks = q.list(limit=50)
                                if not tasks:
                                    console.print("[yellow]Task queue is empty.[/yellow]")
                                else:
                                    console.print(Panel(
                                        "\n".join(
                                            f"[cyan]#{t.id}[/cyan] [{t.status}] prio={t.priority} "
                                            f"attempts={t.attempts}/{t.max_attempts} :: {t.name}"
                                            for t in tasks
                                        ),
                                        title="[bold magenta]Task Queue[/bold magenta]",
                                        border_style="magenta",
                                    ))
                            elif op == "stats":
                                console.print(f"[bold cyan]Queue stats:[/bold cyan] {q.stats()}")
                            elif op == "add":
                                task_text = sub[1].strip() if len(sub) > 1 else ""
                                if not task_text:
                                    console.print("[yellow]Usage: /queue add <task>[/yellow]")
                                else:
                                    tid = q.enqueue(task_text)
                                    console.print(f"[bold green]Task #{tid} enqueued.[/bold green]")
                            elif op == "cancel":
                                tid = int(sub[1]) if len(sub) > 1 else 0
                                ok = q.cancel(tid)
                                console.print(
                                    f"[green]Task #{tid} cancelled.[/green]" if ok
                                    else "[red]Task not found or already running.[/red]"
                                )
                            else:
                                console.print("[yellow]Unknown: /queue list|stats|add <task>|cancel <id>[/yellow]")
                        except (OSError, ValueError) as e:
                            console.print(f"[red]Queue error: {e}[/red]")
                    elif name_l == "daemon":
                        from titan_agent.config import (
                            DAEMON_POLL_INTERVAL,
                            TASK_QUEUE_FILE,
                        )
                        from titan_agent.daemon import TaskDaemon
                        from titan_agent.queue import TaskQueue

                        console.print("[bold magenta]⚙️  Daemon: processing due tasks (Ctrl+C to stop)...[/bold magenta]")
                        q = TaskQueue(TASK_QUEUE_FILE)

                        def _runner(task: str, opts: dict):
                            import asyncio as _aio

                            final = ""
                            err = ""

                            async def _run():
                                nonlocal final, err
                                try:
                                    async for ev in agent.run_task(task, session_id="daemon-cli", mode="fast"):
                                        if ev.type == "final_answer":
                                            final = ev.data
                                        elif ev.type == "error":
                                            err = str(ev.data)
                                except Exception as exc:  # noqa: BLE001
                                    err = str(exc)

                            try:
                                _aio.run(_run())
                            except Exception as exc:  # noqa: BLE001
                                err = str(exc)
                            return (0 if (final and not err) else 1), final or err or "(no answer)", []

                        # Route each queue task through the live agent (fully autonomous).
                        daemon = TaskDaemon(q, runner=_runner, poll_interval=DAEMON_POLL_INTERVAL)

                        import asyncio as _aio
                        try:
                            _aio.run(daemon.run_forever())
                        except KeyboardInterrupt:
                            console.print("\n[yellow]Daemon stopped by user.[/yellow]")
                    elif name_l == "exit":
                        console.print("[bold red]Titan Agent stopped. Goodbye![/bold red]")
                        await mcp.stop_all()
                        break
                    continue
                expanded = expand_slash(user_input)
                if expanded is not None:
                    mode = expanded["mode"]
                    effort = expanded["effort"]
                    console.print(f"[bold cyan]/{expanded['command']}[/bold cyan] → mode: {mode}, effort: {effort}")
                    user_input = expanded["prompt"]

            if lower_input in ("exit", "quit"):
                console.print("[bold red]Titan Agent stopped. Goodbye![/bold red]")
                await mcp.stop_all()
                break

            console.print(f"\n[bold magenta]⚡ Titan is working (mode: {mode}, effort: {effort})...[/bold magenta]")

            async for event in agent.run_task(user_input, session_id=session_id, mode=mode, effort=effort):
                if event.type == "thought":
                    console.print(Panel(
                        f"[italic dim]{event.data}[/italic dim]",
                        title="[magenta]🧠 Reasoning (Chain-of-Thought)[/magenta]",
                        border_style="magenta"
                    ))
                elif event.type == "tool_call":
                    name = event.data.get("name")
                    args = event.data.get("arguments")
                    console.print(f"🔧 [bold yellow]Tool called:[/bold yellow] [cyan]{name}[/cyan] -> [dim]{args}[/dim]")
                elif event.type == "tool_result":
                    res = event.data.get("result", "")
                    # Preview first 300 chars
                    preview = str(res)[:300] + ("..." if len(str(res)) > 300 else "")
                    console.print(f"📋 [dim green]Result:[/dim green] [dim]{preview}[/dim]")
                elif event.type == "final_answer":
                    console.print(Panel(
                        Markdown(event.data),
                        title="[bold green]Titan Agent Answer[/bold green]",
                        border_style="green"
                    ))
                elif event.type == "error":
                    console.print(f"[bold red]❌ Error:[/bold red] {event.data}")
                elif event.type == "status":
                    console.print(f"[dim blue]ℹ️ {event.data}[/dim blue]")

        except (KeyboardInterrupt, EOFError):
            console.print("\n[bold red]Process cancelled.[/bold red]")
            await mcp.stop_all()
            break
        except Exception as e:  # noqa: BLE001 - top-level loop must survive and report any error
            console.print(f"[bold red]Unexpected error:[/bold red] {e}")

if __name__ == "__main__":
    asyncio.run(main())