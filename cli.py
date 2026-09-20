import asyncio
import os
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt

from titan_agent.agent import TitanAgent
from titan_agent.config import DEFAULT_MODEL, DEFAULT_PROVIDER, MCP_CONFIG_FILE
from titan_agent.llm_client import LLMClient
from titan_agent.mcp_client import MCPManager

console = Console()

VALID_MODES = ("fast", "deep", "deep_search")

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

    console.print(Panel.fit(
        "[bold cyan]⚡ TITAN AGENT[/bold cyan] - [italic]Autonomous AI System, far beyond classic agents[/italic]\n"
        "[dim]Model: " + model + f" ({provider}) | MCP System: Active | Mode: {mode}[/dim]\n"
        "[yellow]Type a command in Uzbek, Russian or English. Modes: fast | deep | deep_search (e.g. `mode deep`). "
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
            if lower_input in ("exit", "quit"):
                console.print("[bold red]Titan Agent stopped. Goodbye![/bold red]")
                await mcp.stop_all()
                break

            console.print(f"\n[bold magenta]⚡ Titan is working (mode: {mode})...[/bold magenta]")

            async for event in agent.run_task(user_input, session_id=session_id, mode=mode):
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
        except Exception as e:
            console.print(f"[bold red]Unexpected error:[/bold red] {e}")

if __name__ == "__main__":
    asyncio.run(main())