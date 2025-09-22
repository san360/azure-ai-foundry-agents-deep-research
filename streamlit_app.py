#!/usr/bin/env python3
"""Streamlit application using the new modular architecture.

This is the new Streamlit entry point that uses the refactored azure_ai_research package.
"""

import sys
from pathlib import Path

# Add the current directory to Python path to find our package
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

# Import the main Streamlit app from our package
from azure_ai_research.web.app import main as streamlit_main

if __name__ == "__main__":
    streamlit_main()