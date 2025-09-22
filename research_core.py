# pylint: disable=line-too-long,useless-suppression
# ------------------------------------
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
# ------------------------------------

"""
DESCRIPTION:
    Core research functionality for Azure AI Foundry Agents Deep Research.
    This module contains reusable functions that can be called from both CLI and web interfaces.
"""

import os
import time
import re
from typing import Optional, Dict, List, Tuple, Callable, Any
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from azure.ai.agents import AgentsClient
from azure.ai.agents.models import DeepResearchTool, MessageRole, ThreadMessage
from dotenv import load_dotenv

# Telemetry and tracing imports
from azure.monitor.opentelemetry import configure_azure_monitor
from opentelemetry import trace
from azure.ai.agents.telemetry import AIAgentsInstrumentor

load_dotenv()

# Enable tracing for AI content (optional - contains message content)
os.environ["AZURE_TRACING_GEN_AI_CONTENT_RECORDING_ENABLED"] = "true"


def convert_citations_to_superscript(markdown_content):
    """
    Convert citation markers in markdown content to HTML superscript format.

    This function finds citation patterns like [78:12+source] and converts them to
    HTML superscript tags <sup>12</sup> for better formatting in markdown documents.
    It also consolidates consecutive citations by sorting and deduplicating them.

    Args:
        markdown_content (str): The markdown content containing citation markers

    Returns:
        str: The markdown content with citations converted to HTML superscript format
    """
    # Get tracer for this function
    tracer = trace.get_tracer(__name__)
    
    with tracer.start_as_current_span("convert_citations_to_superscript") as span:
        span.set_attribute("input.content_length", len(markdown_content))
        
        # Pattern to match [number:number+source]
        pattern = r"\u3010\d+:(\d+)\u2020source\u3011"

        # Replace with <sup>captured_number</sup>
        def replacement(match):
            citation_number = match.group(1)
            return f"<sup>{citation_number}</sup>"

        # First, convert all citation markers to superscript
        converted_text = re.sub(pattern, replacement, markdown_content)
        
        # Count initial citations
        initial_citations = len(re.findall(pattern, markdown_content))
        span.set_attribute("citations.initial_count", initial_citations)

        # Then, consolidate consecutive superscript citations
        # Pattern to match multiple superscript tags with optional commas/spaces
        # Matches: <sup>5</sup>,<sup>4</sup>,<sup>5</sup> or <sup>5</sup><sup>4</sup><sup>5</sup>
        consecutive_pattern = r"(<sup>\d+</sup>)(\s*,?\s*<sup>\d+</sup>)+"

        def consolidate_and_sort_citations(match):
            # Extract all citation numbers from the matched text
            citation_text = match.group(0)
            citation_numbers = re.findall(r"<sup>(\d+)</sup>", citation_text)

            # Convert to integers, remove duplicates, and sort
            unique_sorted_citations = sorted(set(int(num) for num in citation_numbers))

            # If only one citation, return simple format
            if len(unique_sorted_citations) == 1:
                return f"<sup>{unique_sorted_citations[0]}</sup>"

            # If multiple citations, return comma-separated format
            citation_list = ",".join(str(num) for num in unique_sorted_citations)
            return f"<sup>{citation_list}</sup>"

        # Remove consecutive duplicate citations and sort them
        final_text = re.sub(consecutive_pattern, consolidate_and_sort_citations, converted_text)
        
        # Count final superscript citations
        final_citations = len(re.findall(r"<sup>[^<>]+</sup>", final_text))
        span.set_attribute("citations.final_count", final_citations)
        span.set_attribute("output.content_length", len(final_text))

        return final_text


def fetch_and_print_new_agent_response(
    thread_id: str,
    agents_client: AgentsClient,
    last_message_id: Optional[str] = None,
    progress_filename: str = "research_progress.txt",
    progress_callback: Optional[Callable[[str, List[Dict[str, str]]], None]] = None,
) -> Optional[str]:
    """
    Fetch the interim agent responses and citations from a thread and write them to a file.

    Args:
        thread_id (str): The ID of the thread to fetch messages from
        agents_client (AgentsClient): The Azure AI agents client instance
        last_message_id (Optional[str], optional): ID of the last processed message
            to avoid duplicates. Defaults to None.
        progress_filename (str, optional): Name of the file to write progress to.
            Defaults to "research_progress.txt".
        progress_callback (Optional[Callable], optional): Callback function to handle progress updates
            for web interface. Receives (agent_text, citations) as parameters.

    Returns:
        Optional[str]: The ID of the latest message if new content was found,
            otherwise returns the last_message_id
    """
    # Get tracer for this function
    tracer = trace.get_tracer(__name__)
    
    with tracer.start_as_current_span("fetch_agent_response") as span:
        span.set_attribute("thread.id", thread_id)
        span.set_attribute("progress.filename", progress_filename)
        span.set_attribute("last_message_id", last_message_id or "none")
        
        response = agents_client.messages.get_last_message_by_role(
            thread_id=thread_id,
            role=MessageRole.AGENT,
        )

        if not response or response.id == last_message_id:
            span.set_attribute("new_content_found", False)
            return last_message_id  # No new content

        # If not a "cot_summary", return.
        if not any(t.text.value.startswith("cot_summary:") for t in response.text_messages):
            span.set_attribute("new_content_found", False)
            span.set_attribute("response.type", "non_cot_summary")
            return last_message_id

        span.set_attribute("new_content_found", True)
        span.set_attribute("response.id", response.id)
        span.set_attribute("response.citations_count", len(response.url_citation_annotations))

        # Extract agent text and citations
        agent_text = "\n".join(t.text.value.replace("cot_summary:", "Reasoning:") for t in response.text_messages)
        citations = [{"title": ann.url_citation.title, "url": ann.url_citation.url} 
                    for ann in response.url_citation_annotations]

        print("\nAgent response:")
        print(agent_text)

        # Print citation annotations (if any)
        for ann in response.url_citation_annotations:
            print(f"URL Citation: [{ann.url_citation.title}]({ann.url_citation.url})")

        # Call progress callback for web interface
        if progress_callback:
            progress_callback(agent_text, citations)

        # Write progress to file
        with open(progress_filename, "a", encoding="utf-8") as fp:
            fp.write("\nAGENT>\n")
            fp.write(agent_text)
            fp.write("\n")

            for ann in response.url_citation_annotations:
                fp.write(f"Citation: [{ann.url_citation.title}]({ann.url_citation.url})\n")

        span.set_attribute("progress.written_to_file", True)
        return response.id


def create_research_summary(message: ThreadMessage, filepath: str = "research_report.md") -> None:
    """
    Create a formatted research report from an agent's thread message with numbered citations
    and a references section.

    Args:
        message (ThreadMessage): The thread message containing the agent's research response
        filepath (str, optional): Path where the research summary will be saved.
            Defaults to "research_report.md".

    Returns:
        None: This function doesn't return a value, it writes to a file
    """
    # Get tracer for this function
    tracer = trace.get_tracer(__name__)
    
    with tracer.start_as_current_span("create_research_summary") as span:
        span.set_attribute("output.filepath", filepath)
        
        if not message:
            print("No message content provided, cannot create research report.")
            span.set_attribute("summary.created", False)
            span.set_attribute("error", "No message content provided")
            return

        span.set_attribute("message.has_text", len(message.text_messages) > 0)
        span.set_attribute("message.text_messages_count", len(message.text_messages))
        span.set_attribute("message.citations_count", len(message.url_citation_annotations))

        with open(filepath, "w", encoding="utf-8") as fp:
            # Write text summary
            text_summary = "\n\n".join([t.text.value.strip() for t in message.text_messages])
            # Convert citations to superscript format
            text_summary = convert_citations_to_superscript(text_summary)
            fp.write(text_summary)

            # Write unique URL citations with numbered bullets, if present
            if message.url_citation_annotations:
                fp.write("\n\n## Citations\n")
                seen_urls = set()
                # Dictionary mapping full citation content to ordinal number
                citations_ordinals: Dict[str, int] = {}
                # List of citation URLs indexed by ordinal (0-based)
                text_citation_list: List[str] = []

                for ann in message.url_citation_annotations:
                    url = ann.url_citation.url
                    title = ann.url_citation.title or url

                    if url not in seen_urls:
                        # Use the full annotation text as the key to avoid conflicts
                        citation_key = ann.text if ann.text else f"fallback_{url}"

                        # Only add if this citation content hasn't been seen before
                        if citation_key not in citations_ordinals:
                            # Assign next available ordinal number (1-based for display)
                            ordinal = len(text_citation_list) + 1
                            citations_ordinals[citation_key] = ordinal
                            text_citation_list.append(f"[{title}]({url})")

                        seen_urls.add(url)

                # Write citations in order they were added
                unique_citations_count = len(text_citation_list)
                span.set_attribute("summary.unique_citations_count", unique_citations_count)
                
                for i, citation_text in enumerate(text_citation_list):
                    fp.write(f"{i + 1}. {citation_text}\n")

        span.set_attribute("summary.created", True)
        span.set_attribute("summary.file_size_bytes", os.path.getsize(filepath))
        print(f"Research report written to '{filepath}'.")


def run_deep_research(
    research_query: str,
    progress_callback: Optional[Callable[[str, List[Dict[str, str]]], None]] = None,
    completion_callback: Optional[Callable[[str], None]] = None,
) -> Tuple[str, str]:
    """
    Run a deep research query using Azure AI Agents.

    Args:
        research_query (str): The research question to investigate
        progress_callback (Optional[Callable], optional): Callback function for progress updates
        completion_callback (Optional[Callable], optional): Callback function when research completes

    Returns:
        Tuple[str, str]: Tuple of (progress_file_path, report_file_path)
    """
    project_client = AIProjectClient(
        endpoint=os.environ["PROJECT_ENDPOINT"],
        credential=DefaultAzureCredential(),
    )
    
    # Configure telemetry and tracing
    connection_string = project_client.telemetry.get_application_insights_connection_string()
    configure_azure_monitor(connection_string=connection_string)
    
    # Instrument AI Agents for tracing
    AIAgentsInstrumentor().instrument()
    
    # Get tracer for custom spans
    tracer = trace.get_tracer(__name__)
    
    # Create unique file names with timestamp
    import datetime
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    progress_filename = f"research_progress_{timestamp}.txt"
    report_filename = f"research_report_{timestamp}.md"
    
    # Clear progress file
    with open(progress_filename, "w", encoding="utf-8") as fp:
        fp.write("# Deep Research Progress Log\n\n")
    
    # [START create_agent_with_deep_research_tool]
    bing_connection = project_client.connections.get(name=os.environ["BING_RESOURCE_NAME"])

    # Initialize a Deep Research tool with Bing Connection ID and Deep Research model deployment name
    deep_research_tool = DeepResearchTool(
        bing_grounding_connection_id=bing_connection.id,
        deep_research_model=os.environ["DEEP_RESEARCH_MODEL_DEPLOYMENT_NAME"],
    )

    # Create Agent with the Deep Research tool and process Agent run
    with project_client:
        with project_client.agents as agents_client:
            # Wrap the entire agent execution in a tracing span
            with tracer.start_as_current_span("deep_research_agent_execution") as main_span:
                main_span.set_attribute("agent.name", "my-agent")
                main_span.set_attribute("agent.instructions", "You are a helpful Agent that assists in researching scientific topics.")
                main_span.set_attribute("research.query", research_query)

                # Create a new agent that has the Deep Research tool attached.
                agent = agents_client.create_agent(
                    model=os.environ["MODEL_DEPLOYMENT_NAME"],
                    name="my-agent",
                    instructions="You are a helpful Agent that assists in researching scientific topics.",
                    tools=deep_research_tool.definitions,
                )

                print(f"Created agent, ID: {agent.id}")
                main_span.set_attribute("agent.id", agent.id)

                # Create thread for communication
                thread = agents_client.threads.create()
                print(f"Created thread, ID: {thread.id}")
                main_span.set_attribute("thread.id", thread.id)

                # Create message to thread
                message = agents_client.messages.create(
                    thread_id=thread.id,
                    role="user",
                    content=research_query,
                )
                print(f"Created message, ID: {message.id}")
                main_span.set_attribute("message.id", message.id)
                main_span.set_attribute("message.content_length", len(research_query))

                print(f"Start processing the message... this may take a few minutes to finish. Be patient!")
                
                # Wrap the run execution in its own span
                with tracer.start_as_current_span("agent_run_execution") as run_span:
                    # Poll the run as long as run status is queued or in progress
                    run = agents_client.runs.create(thread_id=thread.id, agent_id=agent.id)
                    run_span.set_attribute("run.id", run.id)
                    run_span.set_attribute("run.initial_status", run.status)
                    
                    last_message_id = None
                    iteration_count = 0
                    while run.status in ("queued", "in_progress"):
                        time.sleep(1)
                        iteration_count += 1
                        run = agents_client.runs.get(thread_id=thread.id, run_id=run.id)

                        last_message_id = fetch_and_print_new_agent_response(
                            thread_id=thread.id,
                            agents_client=agents_client,
                            last_message_id=last_message_id,
                            progress_filename=progress_filename,
                            progress_callback=progress_callback,
                        )
                        print(f"Run status: {run.status}")
                    
                    run_span.set_attribute("run.final_status", run.status)
                    run_span.set_attribute("run.iteration_count", iteration_count)

                    # Once the run is finished, print the final status and ID
                    print(f"Run finished with status: {run.status}, ID: {run.id}")

                    if run.status == "failed":
                        print(f"Run failed: {run.last_error}")
                        run_span.set_attribute("run.error", str(run.last_error))
                        main_span.set_attribute("execution.status", "failed")
                        return progress_filename, ""
                    else:
                        main_span.set_attribute("execution.status", "completed")

                # Wrap the final message processing in its own span
                with tracer.start_as_current_span("research_summary_creation") as summary_span:
                    # Fetch the final message from the agent in the thread and create a research summary
                    final_message = agents_client.messages.get_last_message_by_role(thread_id=thread.id, role=MessageRole.AGENT)
                    if final_message:
                        summary_span.set_attribute("final_message.id", final_message.id)
                        summary_span.set_attribute("final_message.has_citations", len(final_message.url_citation_annotations) > 0)
                        summary_span.set_attribute("final_message.citation_count", len(final_message.url_citation_annotations))
                        create_research_summary(final_message, report_filename)
                        summary_span.set_attribute("summary.created", True)
                        
                        # Call completion callback for web interface
                        if completion_callback:
                            completion_callback(report_filename)
                    else:
                        summary_span.set_attribute("summary.created", False)

                # Clean-up and delete the agent once the run is finished.
                agents_client.delete_agent(agent.id)
                print("Deleted agent")
                main_span.set_attribute("agent.deleted", True)
                
                return progress_filename, report_filename