#!/usr/bin/env python3
"""
Launcher for Titan Terminal OS.
Run this script to boot the TUI dashboard.
"""

import sys
import asyncio

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
    print("Booting Titan OS...")
    # Initialize the agent
    agent = TitanAgent()
    
    # Create and run the Textual TUI
    app = TitanOS(agent=agent)
    app.run()

if __name__ == "__main__":
    main()
