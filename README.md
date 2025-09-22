# 🔬 Azure AI Deep Research# Azure AI Foundry Agents Deep Research



> **Enterprise-grade research application built with Azure AI Agents following SOLID principles and security best practices.**This project demonstrates how to use Azure AI Agents with the Deep Research tool to perform advanced research tasks, such as gathering and summarizing scientific findings using Bing Search and large language models (LLMs). The main example focuses on researching orca intelligence and communication.



[![Python](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](https://python.org)## Key Features

[![Azure AI](https://img.shields.io/badge/Azure%20AI-Agents%201.2.0b1-blue.svg)](https://azure.microsoft.com/en-us/products/ai-services)

[![Security](https://img.shields.io/badge/Security-Validated-green.svg)](./MIGRATION_GUIDE.md#security-improvements)- Uses Azure AI Agents and Deep Research tool for automated, citation-rich research.

[![Architecture](https://img.shields.io/badge/Architecture-SOLID-green.svg)](./REFACTORING_SUMMARY.md#solid-principles-implementation)- Integrates Bing Search for up-to-date scientific sources.

- Produces structured research progress logs and a final research report with citations.

## ✨ What's New- Includes utilities for citation formatting and report generation.

- Implements OpenTelemetry instrumentation for observability and tracing.

This codebase has been **completely refactored** from a monolithic structure to a secure, maintainable, enterprise-grade application:

## Project Structure

- 🛡️ **Security First**: Comprehensive input validation and output sanitization

- 🏗️ **SOLID Principles**: Modular architecture with clear separation of concerns  - `main.py`: Main script demonstrating agent creation, research execution, and report generation.

- 🔍 **Type Safe**: 100% type coverage with runtime validation- `research_progress.txt`: Incremental log of agent reasoning and findings.

- 📊 **Observable**: Full OpenTelemetry integration with structured logging- `research_report.md`: Final, formatted research report with citations.

- 🚀 **Performance**: Async support, connection pooling, and caching- `.env`: Environment variables for Azure endpoints and model names.

- 🧪 **Testable**: Dependency injection and protocol-based interfaces- `requirements.txt` / `pyproject.toml`: Python dependencies for Azure AI, OpenTelemetry, and environment management.



## 🚀 Quick Start## Requirements



### 1. Installation- Python 3.13+

```bash- Azure subscription with AI Foundry and Bing Search resources

# Clone repository- Required Python packages (see `requirements.txt` or `pyproject.toml`)

git clone <repository-url>

cd azure-ai-foundry-agents-deep-research

## Environment Variables

# Install dependencies

pip install -r requirements.txtCreate a `.env` file in the project root with the following variables:



# Or install as package```

pip install -e .PROJECT_ENDPOINT=<your-azure-ai-project-endpoint>

```MODEL_DEPLOYMENT_NAME=<your-model-deployment-name>

DEEP_RESEARCH_MODEL_DEPLOYMENT_NAME=<your-deep-research-model-deployment-name>

### 2. ConfigurationBING_RESOURCE_NAME=<your-bing-resource-name>

Create a `.env` file with your Azure credentials:```

```env

# Required Azure ConfigurationRefer to your Azure AI Foundry portal and Bing Search resource for the correct values.

PROJECT_ENDPOINT=https://your-project.azure.com

MODEL_DEPLOYMENT_NAME=your-model-deployment## Usage

DEEP_RESEARCH_MODEL_DEPLOYMENT_NAME=your-deep-research-model

BING_RESOURCE_NAME=your-bing-resource1. Set up your Azure resources and obtain endpoint/model names.

2. Copy `.env.template` to `.env` and fill in your actual Azure resource values.

# Optional Security Configuration

MAX_INPUT_LENGTH=10000### Option 1: Using Python Virtual Environment (venv)

MAX_OUTPUT_LENGTH=50000

LOG_LEVEL=INFO1. Create and activate a virtual environment:

```

   **Windows (PowerShell):**

### 3. Run the Application

```bash   ```powershell

# Quick start (interactive menu)   # Create virtual environment

python start.py   python -m venv venv

   

# Web interface (Streamlit)   # Activate virtual environment

streamlit run streamlit_app.py   .\venv\Scripts\Activate.ps1

   

# Command line interface     # Install dependencies

python main.py "What are the latest AI developments?"   pip install -r requirements.txt

   ```

# Interactive CLI

python main.py --interactive   **Windows (Git Bash):**



# Package CLI (after pip install)   ```bash

azure-ai-research "Your research query"   # Create virtual environment

```   python -m venv venv

   

## 🏗️ Architecture Overview   # Activate virtual environment

   source venv/Scripts/activate

The application follows a modular architecture with clear separation of concerns:   

   # Install dependencies

```   pip install -r requirements.txt

azure_ai_research/   ```

├── core/                   # Business logic

│   ├── research.py        # Research orchestration   **Linux/macOS:**

│   ├── citations.py       # Citation processing  

│   └── telemetry.py       # Observability   ```bash

├── infrastructure/        # External services   # Create virtual environment

│   ├── config.py         # Configuration management   python -m venv venv

│   ├── azure_client.py   # Azure client provider   

│   └── file_system.py    # Secure file operations   # Activate virtual environment

├── security/              # Security framework   source venv/bin/activate

│   └── validation.py     # Input/output validation   

├── web/                   # Streamlit interface   # Install dependencies

│   ├── app.py            # Main web application   pip install -r requirements.txt

│   ├── session.py        # Session management   ```

│   └── callbacks.py      # Progress callbacks

└── cli/                   # Command-line interface2. Run the application:

    └── main.py           # CLI application

```   **CLI Version:**

   ```bash

## 🌟 Key Features   python main.py

   ```

### 🔍 Advanced Research Capabilities

- **Deep Research Tool**: Leverages Azure AI Agents with Bing Search integration   **Web Interface (Recommended):**

- **Citation Rich**: Automatic citation extraction and formatting   ```bash

- **Progress Tracking**: Real-time research progress with detailed logging   streamlit run streamlit_app.py

- **Multiple Formats**: Support for JSON, Markdown, and plain text output   ```



### 🛡️ Enterprise Security   The web interface provides:

- **Input Validation**: Query length, content, and format validation   - Interactive research query input with examples

- **Output Sanitization**: HTML content cleaning and safe encoding   - Real-time progress updates with agent reasoning

- **Secure File Operations**: Atomic writes with directory traversal prevention   - Research history and report viewing

- **Credential Protection**: Secure environment variable handling   - Download functionality for generated reports

   - Environment status monitoring

### 🎯 User Interfaces

- **Web Interface**: Rich Streamlit application with real-time progress3. When finished, deactivate the virtual environment:

- **CLI Interface**: Full-featured command-line tool with interactive mode

- **Legacy Support**: Backward compatibility with original interfaces   ```bash

- **Progress Callbacks**: Real-time feedback for long-running operations   deactivate

   ```

### 📊 Observability & Monitoring  

- **OpenTelemetry Integration**: Full distributed tracing support### Option 2: Using uv (Alternative)

- **Structured Logging**: JSON-formatted logs with correlation IDs

- **Performance Metrics**: Execution timing and resource usage1. Install dependencies using [uv](https://github.com/astral-sh/uv):

- **Error Tracking**: Comprehensive error handling and reporting

   ```sh

## 🔧 Advanced Usage   uv pip install -r requirements.txt

   ```

### Programmatic API

```python2. Run the app using uv:

from azure_ai_research.core.research import ResearchService, ResearchRequest

from azure_ai_research.infrastructure.config import get_default_config   ```sh

   uv run main.py

# Initialize service   ```

config = get_default_config()

service = ResearchService(config)### Review Results



# Create research requestAfter running the application, review `research_progress.txt` for incremental findings and `research_report.md` for the final report.

request = ResearchRequest(
    query="Latest developments in quantum computing",
    enable_citations=True
)

# Execute research with progress tracking
def progress_callback(message: str, progress: float, metadata: dict):
    print(f"Progress: {progress:.1%} - {message}")

result = service.conduct_research_sync(request, progress_callback)

if result.success:
    print(f"Research completed: {result.content}")
    print(f"Citations found: {len(result.citations)}")
else:
    print(f"Research failed: {result.error_message}")
```

## 📚 Documentation

- **[Migration Guide](./MIGRATION_GUIDE.md)**: Complete guide for upgrading from the legacy codebase
- **[Refactoring Summary](./REFACTORING_SUMMARY.md)**: Detailed overview of architectural improvements
- **[Security Framework](./MIGRATION_GUIDE.md#security-improvements)**: Security features and best practices

## 🧪 Development

### Setup Development Environment
```bash
# Install with development dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/

# Type checking
mypy azure_ai_research/

# Code formatting
black azure_ai_research/
isort azure_ai_research/
```

## 🔄 Migration from Legacy

If you're upgrading from the original codebase:

1. **Read the Migration Guide**: [MIGRATION_GUIDE.md](./MIGRATION_GUIDE.md)
2. **Update Dependencies**: `pip install -r requirements.txt`
3. **Configure Environment**: Update your `.env` file with new variables
4. **Test Compatibility**: Use the legacy compatibility layer
5. **Gradual Migration**: Move to new APIs incrementally

## 🛠️ Troubleshooting

### Common Issues

**"Module not found" errors:**
```bash
# Ensure package is installed
pip install -e .

# Or add to Python path
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

**Azure authentication issues:**
```bash
# Check Azure CLI login
az login

# Verify environment variables
python -c "from azure_ai_research.infrastructure.config import get_default_config; print(get_default_config())"
```

## 📋 Requirements

- **Python**: 3.9+ (3.13+ recommended)
- **Azure Subscription**: With AI Foundry and Bing Search resources
- **Dependencies**: See `requirements.txt` or `pyproject.toml`
- **Environment**: Windows, macOS, or Linux

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Follow the code style: `black` and `isort` formatting
4. Add tests for new functionality
5. Ensure all tests pass: `pytest`
6. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

**Built with ❤️ using Azure AI, following enterprise-grade security and architectural best practices.**