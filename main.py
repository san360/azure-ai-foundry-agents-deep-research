#!/usr/bin/env python3
"""Main entry point for Azure AI Deep Research application.

This is the legacy entry point that now uses the new modular architecture.
For new development, use azure_ai_research.cli.main directly.
"""

import sys
from azure_ai_research.cli.main import main as cli_main

if __name__ == "__main__":
    sys.exit(cli_main())
