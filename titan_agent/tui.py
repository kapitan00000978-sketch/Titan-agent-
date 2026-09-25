"""
Titan Terminal OS (TUI)
Provides a rich, interactive Command Line Operating System for Universal Agent HP.
"""
from __future__ import annotations

from ui.tui_app import UniversalAgentTUI, TitanOS, AgentsModal, CommandsModal

__all__ = ["UniversalAgentTUI", "TitanOS", "AgentsModal", "CommandsModal"]

if __name__ == "__main__":
    app = UniversalAgentTUI()
    app.run()
