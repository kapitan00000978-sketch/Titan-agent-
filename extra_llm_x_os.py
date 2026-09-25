#!/usr/bin/env python3
"""
Launcher for Extra LLM X Terminal OS.
Run this script to boot the TUI dashboard.
"""

import sys

# Ensure dependencies are available before launching
try:
    from textual.app import App
except ImportError:
    print("Error: 'textual' package is not installed.")
    print("Please run: pip install textual")
    sys.exit(1)

from titan_agent.agent import TitanAgent
from titan_agent.tui import TitanOS


def main():
    print("Booting Extra LLM X OS...")
    agent = TitanAgent()
    app = TitanOS(agent=agent)
    app.run()


if __name__ == "__main__":
    main()
