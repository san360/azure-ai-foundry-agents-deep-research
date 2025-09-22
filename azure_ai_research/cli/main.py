"""Command-line interface for Azure AI Deep Research."""

import argparse
import logging
import sys
from pathlib import Path
from typing import Optional
import json
from datetime import datetime

from azure_ai_research.infrastructure.config import AppConfig, get_default_config
from azure_ai_research.core.research import ResearchService, ResearchRequest
from azure_ai_research.security.validation import validate_research_query, ValidationError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class CLIProgressCallback:
    """Progress callback for CLI output."""
    
    def __init__(self, verbose: bool = False):
        """Initialize CLI progress callback."""
        self.verbose = verbose
        self.last_progress = 0.0
    
    def __call__(self, message: str, progress: float = 0.0, metadata: Optional[dict] = None):
        """CLI progress callback."""
        try:
            # Show progress bar and message
            progress_pct = int(progress * 100)
            
            if self.verbose or progress_pct != int(self.last_progress * 100):
                # Create progress bar
                bar_length = 30
                filled_length = int(bar_length * progress)
                bar = '█' * filled_length + '░' * (bar_length - filled_length)
                
                print(f"\r[{bar}] {progress_pct:3d}% {message}", end='', flush=True)
                
                if progress >= 1.0:
                    print()  # New line when complete
                
                self.last_progress = progress
                
            if self.verbose and metadata:
                print(f"\n  Metadata: {json.dumps(metadata, indent=2)}")
                
        except Exception as e:
            logger.error(f"Progress callback error: {e}")


class CLIApp:
    """Command-line application for Azure AI research."""
    
    def __init__(self):
        """Initialize CLI application."""
        try:
            self.config = get_default_config()
            self.research_service = ResearchService(self.config)
            logger.info("CLI application initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize CLI application: {e}")
            sys.exit(1)
    
    def create_parser(self) -> argparse.ArgumentParser:
        """Create command-line argument parser."""
        parser = argparse.ArgumentParser(
            description="Azure AI Deep Research CLI",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Examples:
  python -m azure_ai_research.cli.main "What are the latest AI developments?"
  python -m azure_ai_research.cli.main --query "Quantum computing breakthroughs" --output results.json
  python -m azure_ai_research.cli.main --interactive
            """
        )
        
        # Research query
        parser.add_argument(
            "query",
            nargs="?",
            help="Research query to execute"
        )
        
        parser.add_argument(
            "--query", "-q",
            dest="query_flag",
            help="Research query (alternative to positional argument)"
        )
        
        # Output options
        parser.add_argument(
            "--output", "-o",
            help="Output file path for results (JSON format)"
        )
        
        parser.add_argument(
            "--format", "-f",
            choices=["json", "markdown", "text"],
            default="text",
            help="Output format (default: text)"
        )
        
        # Research options
        parser.add_argument(
            "--no-citations",
            action="store_true",
            help="Disable citation extraction"
        )
        
        # Application options
        parser.add_argument(
            "--interactive", "-i",
            action="store_true",
            help="Interactive mode"
        )
        
        parser.add_argument(
            "--verbose", "-v",
            action="store_true",
            help="Verbose output"
        )
        
        parser.add_argument(
            "--config",
            help="Configuration file path"
        )
        
        parser.add_argument(
            "--log-level",
            choices=["DEBUG", "INFO", "WARNING", "ERROR"],
            default="INFO",
            help="Logging level"
        )
        
        # Service commands
        parser.add_argument(
            "--status",
            action="store_true",
            help="Show service status and exit"
        )
        
        parser.add_argument(
            "--list-logs",
            action="store_true",
            help="List available log files and exit"
        )
        
        return parser
    
    def run(self, args: Optional[list] = None) -> int:
        """Run CLI application."""
        try:
            parser = self.create_parser()
            parsed_args = parser.parse_args(args)
            
            # Configure logging
            logging.getLogger().setLevel(getattr(logging, parsed_args.log_level))
            
            # Handle service commands
            if parsed_args.status:
                return self._show_status()
            
            if parsed_args.list_logs:
                return self._list_logs()
            
            # Get query
            query = parsed_args.query or parsed_args.query_flag
            
            if parsed_args.interactive:
                return self._interactive_mode()
            elif not query:
                parser.error("Query is required. Use --query or provide as positional argument, or use --interactive mode.")
                return 1
            
            # Execute research
            return self._execute_research(query, parsed_args)
            
        except KeyboardInterrupt:
            print("\nOperation cancelled by user")
            return 130
        except Exception as e:
            logger.error(f"CLI application error: {e}")
            print(f"Error: {e}", file=sys.stderr)
            return 1
    
    def _execute_research(self, query: str, args) -> int:
        """Execute research query."""
        try:
            # Validate query
            validated_query = validate_research_query(query, self.config.security.max_input_length)
            
            # Create research request
            request = ResearchRequest(
                query=validated_query,
                enable_citations=not args.no_citations
            )
            
            print(f"Starting research for: {query}")
            print()
            
            # Create progress callback
            progress_callback = CLIProgressCallback(verbose=args.verbose)
            
            # Execute research
            result = self.research_service.conduct_research_sync(request, progress_callback)
            
            # Handle result
            if result.success:
                print("\n✅ Research completed successfully!")
                self._output_result(result, args)
                
                # Save log
                log_path = self.research_service.save_research_log(result)
                if args.verbose:
                    print(f"\nLog saved to: {log_path}")
                
                return 0
            else:
                print(f"\n❌ Research failed: {result.error_message}")
                return 1
                
        except ValidationError as e:
            print(f"Invalid query: {e}", file=sys.stderr)
            return 1
        except Exception as e:
            logger.error(f"Research execution failed: {e}")
            print(f"Research failed: {e}", file=sys.stderr)
            return 1
    
    def _output_result(self, result, args) -> None:
        """Output research result in specified format."""
        try:
            if args.format == "json":
                output_data = result.to_dict()
                output_text = json.dumps(output_data, indent=2, ensure_ascii=False)
            elif args.format == "markdown":
                output_text = self._format_as_markdown(result)
            else:  # text format
                output_text = self._format_as_text(result)
            
            # Write to file or stdout
            if args.output:
                output_path = Path(args.output)
                output_path.write_text(output_text, encoding='utf-8')
                print(f"Results saved to: {output_path}")
            else:
                print("\n" + "="*60)
                print("RESEARCH RESULTS")
                print("="*60)
                print(output_text)
                
        except Exception as e:
            logger.error(f"Failed to output result: {e}")
            print(f"Failed to output result: {e}", file=sys.stderr)
    
    def _format_as_text(self, result) -> str:
        """Format result as plain text."""
        lines = []
        
        # Content
        lines.append("Content:")
        lines.append("-" * 40)
        lines.append(result.content)
        lines.append("")
        
        # Citations
        if result.citations:
            lines.append("Citations:")
            lines.append("-" * 40)
            for i, citation in enumerate(result.citations, 1):
                title = citation.get("title", "Untitled")
                url = citation.get("url", "")
                lines.append(f"{i}. {title}")
                if url:
                    lines.append(f"   {url}")
            lines.append("")
        
        # Metadata
        lines.append("Metadata:")
        lines.append("-" * 40)
        lines.append(f"Execution time: {result.execution_time_seconds:.2f}s")
        lines.append(f"Citations found: {len(result.citations)}")
        
        return "\n".join(lines)
    
    def _format_as_markdown(self, result) -> str:
        """Format result as Markdown."""
        lines = []
        
        # Header
        lines.append("# Research Results")
        lines.append("")
        
        # Content
        lines.append("## Content")
        lines.append("")
        lines.append(result.content)
        lines.append("")
        
        # Citations
        if result.citations:
            lines.append("## Citations")
            lines.append("")
            for i, citation in enumerate(result.citations, 1):
                title = citation.get("title", "Untitled")
                url = citation.get("url", "")
                if url:
                    lines.append(f"{i}. [{title}]({url})")
                else:
                    lines.append(f"{i}. {title}")
            lines.append("")
        
        # Metadata
        lines.append("## Metadata")
        lines.append("")
        lines.append(f"- **Execution time**: {result.execution_time_seconds:.2f}s")
        lines.append(f"- **Citations found**: {len(result.citations)}")
        
        return "\n".join(lines)
    
    def _interactive_mode(self) -> int:
        """Run interactive mode."""
        print("Azure AI Deep Research - Interactive Mode")
        print("Type 'quit' or 'exit' to quit, 'help' for help")
        print()
        
        while True:
            try:
                query = input("Research query: ").strip()
                
                if not query:
                    continue
                
                if query.lower() in ["quit", "exit", "q"]:
                    print("Goodbye!")
                    return 0
                
                if query.lower() in ["help", "h", "?"]:
                    self._show_interactive_help()
                    continue
                
                if query.lower() == "status":
                    self._show_status()
                    continue
                
                # Execute research with default settings
                args = argparse.Namespace(
                    no_citations=False,
                    format="text",
                    output=None,
                    verbose=False
                )
                
                result_code = self._execute_research(query, args)
                
                if result_code == 0:
                    print("\nPress Enter to continue...")
                    input()
                
            except KeyboardInterrupt:
                print("\nType 'quit' to exit")
                continue
            except EOFError:
                print("\nGoodbye!")
                return 0
    
    def _show_interactive_help(self) -> None:
        """Show help for interactive mode."""
        print("""
Interactive Mode Commands:
  <query>       - Execute research query
  help, h, ?    - Show this help
  status        - Show service status
  quit, exit, q - Exit interactive mode
        """)
    
    def _show_status(self) -> int:
        """Show service status."""
        try:
            status = self.research_service.get_service_status()
            print("Service Status:")
            print(json.dumps(status, indent=2))
            return 0
        except Exception as e:
            print(f"Failed to get service status: {e}", file=sys.stderr)
            return 1
    
    def _list_logs(self) -> int:
        """List available log files."""
        try:
            logs = self.research_service.load_research_logs()
            
            if logs:
                print(f"Found {len(logs)} log files:")
                for i, log in enumerate(logs, 1):
                    timestamp = log.get("timestamp", "Unknown")
                    query = log.get("metadata", {}).get("query", "")[:50]
                    success = log.get("success", False)
                    status = "✅" if success else "❌"
                    print(f"{i:2d}. {status} {timestamp} - {query}...")
            else:
                print("No log files found")
            
            return 0
            
        except Exception as e:
            print(f"Failed to list logs: {e}", file=sys.stderr)
            return 1


def main():
    """Main CLI entry point."""
    app = CLIApp()
    return app.run()


if __name__ == "__main__":
    sys.exit(main())