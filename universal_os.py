#!/usr/bin/env python3
"""
Launcher for Universal Agent HP Terminal OS (TUI).
Run this script to boot the full-screen TUI dashboard.
"""
from ui.tui_app import UniversalAgentTUI

def main():
    print("Booting Universal Agent HP OS...")
    app = UniversalAgentTUI()
    app.run()

if __name__ == "__main__":
    main()
