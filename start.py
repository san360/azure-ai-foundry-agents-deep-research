#!/usr/bin/env python3
"""Quick start script for Azure AI Deep Research application."""

import sys
import os
from pathlib import Path

def main():
    """Quick start the application."""
    print("🔬 Azure AI Deep Research - Quick Start")
    print("="*50)
    
    # Check if environment is configured
    required_env_vars = [
        "PROJECT_ENDPOINT",
        "MODEL_DEPLOYMENT_NAME", 
        "DEEP_RESEARCH_MODEL_DEPLOYMENT_NAME",
        "BING_RESOURCE_NAME"
    ]
    
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]
    
    if missing_vars:
        print("❌ Missing required environment variables:")
        for var in missing_vars:
            print(f"   - {var}")
        print("\nPlease set these variables in your .env file or environment.")
        print("See MIGRATION_GUIDE.md for details.")
        return 1
    
    print("✅ Environment configuration looks good!")
    print("\nAvailable interfaces:")
    print("1. Web Interface (Streamlit)")
    print("2. Command Line Interface")
    print("3. Interactive CLI")
    
    while True:
        try:
            choice = input("\nSelect interface (1-3, or 'q' to quit): ").strip().lower()
            
            if choice == 'q' or choice == 'quit':
                print("Goodbye!")
                return 0
            elif choice == '1':
                print("\n🌐 Starting Streamlit web interface...")
                print("This will open in your default browser.")
                os.system("streamlit run streamlit_app.py")
                return 0
            elif choice == '2':
                query = input("\nEnter your research query: ").strip()
                if query:
                    print(f"\n🔍 Starting research: {query}")
                    os.system(f'python main.py "{query}"')
                    return 0
                else:
                    print("Please enter a valid query.")
            elif choice == '3':
                print("\n💬 Starting interactive CLI...")
                os.system("python main.py --interactive")
                return 0
            else:
                print("Invalid choice. Please select 1, 2, 3, or 'q'.")
                
        except KeyboardInterrupt:
            print("\n\nGoodbye!")
            return 0
        except Exception as e:
            print(f"Error: {e}")
            return 1

if __name__ == "__main__":
    sys.exit(main())