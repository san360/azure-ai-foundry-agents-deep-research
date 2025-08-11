# Azure AI Foundry Agents Deep Research

This project demonstrates how to use Azure AI Agents with the Deep Research tool to perform advanced research tasks, such as gathering and summarizing scientific findings using Bing Search and large language models (LLMs). The main example focuses on researching orca intelligence and communication.

## Key Features

- Uses Azure AI Agents and Deep Research tool for automated, citation-rich research.
- Integrates Bing Search for up-to-date scientific sources.
- Produces structured research progress logs and a final research report with citations.
- Includes utilities for citation formatting and report generation.
- Implements OpenTelemetry instrumentation for observability and tracing.

## Project Structure

- `main.py`: Main script demonstrating agent creation, research execution, and report generation.
- `research_progress.txt`: Incremental log of agent reasoning and findings.
- `research_report.md`: Final, formatted research report with citations.
- `.env`: Environment variables for Azure endpoints and model names.
- `requirements.txt` / `pyproject.toml`: Python dependencies for Azure AI, OpenTelemetry, and environment management.

## Requirements

- Python 3.13+
- Azure subscription with AI Foundry and Bing Search resources
- Required Python packages (see `requirements.txt` or `pyproject.toml`)


## Environment Variables

Create a `.env` file in the project root with the following variables:

```
PROJECT_ENDPOINT=<your-azure-ai-project-endpoint>
MODEL_DEPLOYMENT_NAME=<your-model-deployment-name>
DEEP_RESEARCH_MODEL_DEPLOYMENT_NAME=<your-deep-research-model-deployment-name>
BING_RESOURCE_NAME=<your-bing-resource-name>
```

Refer to your Azure AI Foundry portal and Bing Search resource for the correct values.

## Usage

1. Set up your Azure resources and obtain endpoint/model names.
2. Fill in the `.env` file as described above.
3. Install dependencies using [uv](https://github.com/astral-sh/uv):

   ```sh
   uv pip install -r requirements.txt
   ```

4. Run the app using uv:

   ```sh
   uv run main.py
   ```

5. Review `research_progress.txt` for incremental findings and `research_report.md` for the final report.

## References

- See `research_report.md` for a sample output and citations.
- For more details, refer to the official [Deep Research Tool documentation](https://aka.ms/agents-deep-research).
