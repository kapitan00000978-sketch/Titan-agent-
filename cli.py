import asyncio
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

async def resolve_cli_provider() -> tuple[str, str]:
    """Puter.js browser-only bo'lgani uchun CLI'da Ollama'ga avto-o'tadi."""
    provider, model = DEFAULT_PROVIDER, DEFAULT_MODEL
    if provider == "puter":
        console.print(
            "[yellow]ℹ️ Puter.js provayderi faqat Web Dashboardda (brauzerda) ishlaydi. "
            "CLI uchun mahalliy Ollama tekshirilmoqda...[/yellow]"
        )
        local = await LLMClient.detect_local_models()
        ollama = local.get("ollama") or []
        if ollama:
            provider, model = "ollama", ollama[0]
            console.print(f"[green]✅ Ollama topildi: {ollama[0]} → unga o'tildi.[/green]")
        else:
            console.print(
                "[bold red]❌ Kompyuterda Ollama modeli topilmadi.[/bold red]\n"
                "[yellow]Yechim: (1) Ollamani o'rnating va model yuklang: `ollama run hermes3`, yoki\n"
                "(2) Web Dashboard'ni ishga tushiring (Puter.js bepul modellari brauzerda ishlaydi): python run.py[/yellow]"
            )
            raise SystemExit(1)
    return provider, model

async def main():
    provider, model = await resolve_cli_provider()
    console.print(Panel.fit(
        "[bold cyan]⚡ TITAN AGENT[/bold cyan] - [italic]Hermes darajasidan ancha ustun Avtonom AI Tizimi[/italic]\n"
        "[dim]Model: " + model + f" ({provider}) | MCP Tizimi: Faol[/dim]\n"
        "[yellow]O'zbek, Rus va Ingliz tillarida buyruq bering. Chiqish uchun 'exit' deb yozing.[/yellow]",
        border_style="cyan"
    ))

    # Initialize MCP Manager
    mcp = MCPManager(MCP_CONFIG_FILE)
    with console.status("[bold green]MCP serverlar tekshirilmoqda...", spinner="dots"):
        await mcp.start_all()

    llm = LLMClient(provider=provider, model=model)
    agent = TitanAgent(mcp=mcp, llm=llm)

    session_id = "cli_session"

    while True:
        try:
            user_input = Prompt.ask("\n[bold green]Siz[/bold green]")
            if not user_input.strip():
                continue
            if user_input.lower() in ("exit", "quit", "chiqish"):
                console.print("[bold red]Titan Agent to'xtatildi. Xayr![/bold red]")
                await mcp.stop_all()
                break

            console.print("\n[bold magenta]⚡ Titan ishlayapti...[/bold magenta]")

            async for event in agent.run_task(user_input, session_id=session_id):
                if event.type == "thought":
                    console.print(Panel(
                        f"[italic dim]{event.data}[/italic dim]",
                        title="[magenta]🧠 Fikrlash (Reasoning / Chain-of-Thought)[/magenta]",
                        border_style="magenta"
                    ))
                elif event.type == "tool_call":
                    name = event.data.get("name")
                    args = event.data.get("arguments")
                    console.print(f"🔧 [bold yellow]Asbob chaqirildi:[/bold yellow] [cyan]{name}[/cyan] -> [dim]{args}[/dim]")
                elif event.type == "tool_result":
                    res = event.data.get("result", "")
                    # Preview first 300 chars
                    preview = str(res)[:300] + ("..." if len(str(res)) > 300 else "")
                    console.print(f"📋 [dim green]Natija:[/dim green] [dim]{preview}[/dim]")
                elif event.type == "final_answer":
                    console.print(Panel(
                        Markdown(event.data),
                        title="[bold green]Titan Agent Javobi[/bold green]",
                        border_style="green"
                    ))
                elif event.type == "error":
                    console.print(f"[bold red]❌ Xatolik:[/bold red] {event.data}")
                elif event.type == "status":
                    console.print(f"[dim blue]ℹ️ {event.data}[/dim blue]")

        except (KeyboardInterrupt, EOFError):
            console.print("\n[bold red]Jarayon bekor qilindi.[/bold red]")
            await mcp.stop_all()
            break
        except Exception as e:
            console.print(f"[bold red]Kutilmagan xatolik:[/bold red] {e}")

if __name__ == "__main__":
    asyncio.run(main())
