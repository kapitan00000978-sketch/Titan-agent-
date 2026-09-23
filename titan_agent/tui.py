"""
Titan Terminal OS (TUI)
Provides a rich, interactive Command Line Operating System for Titan.
"""
from __future__ import annotations

import asyncio
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Header, Footer, Input, RichLog
from textual.binding import Binding

from titan_agent.agent import TitanAgent
from titan_agent.core.reasoning.types import ActionType


class TitanOS(App):
    """The main TUI Application for Universal Agent HP."""
    
    TITLE = "Universal Agent HP"
    SUB_TITLE = "Terminal AI Operating System"

    CSS = """
    Screen {
        layout: horizontal;
        background: $surface;
    }
    #left_pane {
        width: 60%;
        height: 100%;
        border: solid $accent;
        padding: 0 1;
    }
    #right_pane {
        width: 40%;
        height: 100%;
        border: solid $secondary;
        padding: 0 1;
    }
    Input {
        dock: bottom;
        margin-top: 1;
    }
    RichLog {
        height: 100%;
        border: none;
    }
    .panel-title {
        text-align: center;
        background: $panel;
        color: $text;
        text-style: bold;
        padding: 1;
    }
    """

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit", show=True),
        Binding("ctrl+l", "clear_chat", "Clear", show=True)
    ]

    def __init__(self, agent: TitanAgent):
        super().__init__()
        self.agent = agent
        self.chat_log = RichLog(id="chat_log", highlight=True, markup=True)
        self.monitor_log = RichLog(id="monitor_log", highlight=True, markup=True)
        self.chat_input = Input(placeholder="Ask Titan a question or give a task...", id="chat_input")

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header(show_clock=True)
        with Horizontal():
            with Vertical(id="left_pane"):
                yield self.chat_log
                yield self.chat_input
            with Vertical(id="right_pane"):
                yield self.monitor_log
        yield Footer()

    def on_mount(self) -> None:
        """Called when app starts."""
        self.chat_log.write("[bold green]Welcome to Titan OS.[/bold green] System ready.")
        self.monitor_log.write("[bold blue]System Monitor Active.[/bold blue]")
        self.chat_input.focus()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle when user presses Enter in the input."""
        user_text = event.value.strip()
        if not user_text:
            return
            
        self.chat_input.value = ""
        self.chat_log.write(f"\n[bold yellow]User:[/bold yellow] {user_text}")
        
        asyncio.create_task(self.run_agent_task(user_text))

    async def run_agent_task(self, prompt: str) -> None:
        """Runs the agent and streams the logs to the monitor."""
        self.chat_log.write("[dim]Titan is thinking...[/dim]")
        
        # Setup log capture for the monitor panel
        import logging
        
        class MonitorHandler(logging.Handler):
            def __init__(self, tui):
                super().__init__()
                self.tui = tui
            
            def emit(self, record):
                msg = self.format(record)
                # Send to textual app thread-safely
                self.tui.call_from_thread(self.tui.monitor_log.write, f"[cyan][LOG][/cyan] {msg}")

        monitor_handler = MonitorHandler(self)
        monitor_handler.setLevel(logging.INFO)
        root_logger = logging.getLogger()
        root_logger.addHandler(monitor_handler)

        try:
            # We don't have stream_task, so we use the standard execution entrypoint
            # Assuming 'run_task' is the main entry point (as is standard)
            # Or if run is used, we'll try run() or run_task()
            if hasattr(self.agent, "run_task"):
                final_answer = await self.agent.run_task(prompt)
            elif hasattr(self.agent, "run"):
                final_answer = await self.agent.run(prompt)
            else:
                final_answer = "Error: Could not find run_task or run on TitanAgent."
                
            self.chat_log.write(f"\n[bold green]Titan:[/bold green]\n{final_answer}")
            self.monitor_log.write("[bold green][TASK COMPLETED][/bold green]")
        except Exception as e:
            self.chat_log.write(f"\n[bold red]System Error:[/bold red] {e}")
        finally:
            root_logger.removeHandler(monitor_handler)

    def action_clear_chat(self) -> None:
        """Clear the chat window."""
        self.chat_log.clear()
        self.chat_log.write("[bold green]Chat cleared.[/bold green]")
