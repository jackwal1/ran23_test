import ast
# import os
# import re
from collections.abc import Iterable
from typing import Dict, Optional, Any

# from dotenv import load_dotenv
# from rich.console import Console
from rich.table import Table
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, SystemMessage
from langgraph.graph import MessagesState
from prompts.prompts import  AGENT_INSTRUCTION_PROMPT_v6
from utils import constants as CONST
# import logging
from langchain_core.prompts import PromptTemplate
from utils.log_init import logger
from llms.llms import chatmodel_mistral_large_ran_2

# Setup the logging configuration
# log_level = getattr(logging, CONST.LOG_LEVEL, logging.INFO)  # Fallback to INFO if not found

# logging.basicConfig(
#     level=log_level,
#     format="%(asctime)s - %(levelname)s - %(name)s - %(filename)s - %(funcName)s - Line: %(lineno)d - %(message)s",
#     datefmt="%Y-%m-%d %H:%M:%S"
# )

# logger = logging.getLogger("RAN")

# rich = Console()

# try:
#     # Fetch environment variables
#     AGENT_INSTRUCTION_PROMPT_v3 = os.environ["WATSONX_URL"]
# except Exception as e:
#     print(e)
#     print("Loading Environment Variables from local .env file")
#     load_dotenv()
#     AGENT_INSTRUCTION_PROMPT_v3 = os.environ["WATSONX_URL"]


async def process_chunks(chunk: Optional[Dict[str, Any]]) -> None:
    """
    Process a chunk of data and extract information about tool calls made by the agent.
    """
    logger.info(f'processing chunk -> {chunk}')
    if chunk is None:
        logger.error("Error: Chunk is None")
        return

    if not isinstance(chunk, dict):
        logger.error(f"Error: Expected dict for chunk, got {type(chunk).__name__}")
        return

    data = chunk.get("data")
    if data is None:
        logger.error("Error: No 'data' field found in chunk")
        return

    if not isinstance(data, dict):
        logger.error(f"Error: Expected dict for data, got {type(data).__name__}")
        return

    output = data.get("output")
    if output is None:
        return

    messages = output
    if messages is None:
        logger.error("Error: Messages is None")
        return

    if isinstance(messages, (AIMessage, ToolMessage)):
        return

    if not isinstance(messages, Iterable):
        return

    try:
        messages_list = list(messages)
        if not messages_list:
            logger.info("Warning: Empty messages list")
            return
    except TypeError:
        logger.error("Error: Could not convert messages to list")
        return

    for message in messages_list:
        try:
            if message is None:
                continue

            if hasattr(message, "additional_kwargs"):
                tool_calls = message.additional_kwargs.get("tool_calls")
                if tool_calls:
                    for tool_call in tool_calls:
                        if not isinstance(tool_call, dict):
                            continue

                        function_data = tool_call.get("function", {})
                        if not isinstance(function_data, dict):
                            continue

                        tool_name = function_data.get("name", "Unknown")
                        arguments_str = function_data.get("arguments", "{}")
                        try:
                            tool_arguments = ast.literal_eval(arguments_str)
                        except (ValueError, SyntaxError, TypeError):
                            tool_arguments = arguments_str

                        logger.info(
                            f"\nThe agent is calling the tool {tool_name} "
                            f"with the query {tool_arguments}.",
                            style="blue",
                        )
            else:
                agent_answer = getattr(message, "content", None)
                if agent_answer:
                    logger.info(f"\nAgent:\n[bright_magenta on bright_blue]{agent_answer}[/bright_magenta on bright_blue]")
        except Exception as e:
            print(f"Error processing message: {str(e)}")
            continue


async def process_checkpoints(checkpoints) -> None:
    """
    Asynchronously process a list of checkpoints, extracting and displaying key information about each checkpoint.
    """
    logger.info("\n==========================================================\n")
    checkpoints_list = []
    async for checkpoint_tuple in checkpoints:
        checkpoints_list.append(checkpoint_tuple)

    for idx, checkpoint_tuple in enumerate(checkpoints_list):
        checkpoint = checkpoint_tuple.checkpoint
        messages = checkpoint["channel_values"].get("messages", [])
        logger.info(f"[white]Checkpoint:[/white]")
        logger.info(f"[black]Timestamp: {checkpoint['ts']}[/black]")
        logger.info(f"[black]Checkpoint ID: {checkpoint['id']}[/black]")

        for message in messages:
            if isinstance(message, HumanMessage):
                logger.info(
                    f"[bright_magenta]User: {message.content}[/bright_magenta] [bright_cyan](Message ID: {message.id})[/bright_cyan]"
                )
            elif isinstance(message, AIMessage):
                logger.info(
                    f"[bright_magenta]Agent: {message.content}[/bright_magenta] [bright_cyan](Message ID: {message.id})[/bright_cyan]"
                )
        logger.info("")
        break  # Only show the latest checkpoint

    logger.info("==========================================================")


async def display_messages(messages) -> None:
    table = Table(title="Chat State Messages", show_header=True, header_style="bold magenta")
    table.add_column("Type", style="cyan", justify="center")
    table.add_column("Content", style="green")
    table.add_column("Details", style="yellow")

    for msg in messages:
        if isinstance(msg, HumanMessage):
            msg_type = "HumanMessage"
            content = msg.content
            details = f"ID: {msg.id}"
        elif isinstance(msg, AIMessage):
            msg_type = "AIMessage"
            content = msg.content or "[No direct content]"
            tool_calls = msg.additional_kwargs.get('tool_calls', 'None')
            details = f"Tool Calls: {tool_calls}" if tool_calls != 'None' else f"ID: {msg.id}"
        elif isinstance(msg, ToolMessage):
            msg_type = "ToolMessage"
            content = msg.content
            details = f"Tool Name: {msg.name} | ID: {msg.id}"
        else:
            msg_type = "Unknown"
            content = "N/A"
            details = "N/A"

        if msg_type != "Unknown":
            table.add_row(msg_type, content, details)

    logger.info(table)


async def manage_memory(state: MessagesState):
    """
    Control the messages list sent to the LLM by trimming and reformatting messages.
    """
    messages = state['messages']
    trimmed_messages = messages[-10:]
    human_index = next(
        (i for i, message in enumerate(trimmed_messages) if isinstance(message, HumanMessage)), None
    )

    if human_index is not None:
        trimmed_messages = trimmed_messages[human_index:]
    else:
        trimmed_messages = []

    print("<================= messages to LLM  ==================> ")
    await display_messages(messages)
    return [SystemMessage(content=AGENT_INSTRUCTION_PROMPT_v6)] + trimmed_messages


async def process_chunks_non_streaming(chunk: Optional[Dict[str, Any]]) -> None:
    """
    Process a chunk of data in non-streaming mode and extract information about tool calls made by the agent.
    """
    if chunk is None:
        logger.error("Error: Chunk is None")
        return

    if not isinstance(chunk, dict):
        logger.error(f"Error: Expected dict for chunk, got {type(chunk).__name__}")
        return

    if "agent" not in chunk:
        logger.error("Error: No 'agent' field found in chunk")
        return

    agent_data = chunk.get("agent")
    if not isinstance(agent_data, dict):
        logger.error(f"Error: Expected dict for agent data, got {type(agent_data).__name__}")
        return

    messages = agent_data.get("messages")
    if not messages:
        logger.error("Error: No messages found in agent data")
        return

    if not isinstance(messages, (list, tuple)):
        logger.error(f"Error: Expected list or tuple for messages, got {type(messages).__name__}")
        return

    for message in messages:
        try:
            if message is None:
                continue

            if not hasattr(message, "additional_kwargs"):
                logger.info("Warning: Message missing additional_kwargs attribute")
                continue

            if "tool_calls" in message.additional_kwargs:
                tool_calls = message.additional_kwargs.get("tool_calls")
                if not tool_calls:
                    continue

                if not isinstance(tool_calls, (list, tuple)):
                    logger.info(f"Error: Expected list for tool_calls, got {type(tool_calls).__name__}")
                    continue

                for tool_call in tool_calls:
                    try:
                        if not isinstance(tool_call, dict):
                            continue

                        function_data = tool_call.get("function")
                        if not isinstance(function_data, dict):
                            continue

                        tool_name = function_data.get("name")
                        if not tool_name:
                            tool_name = "Unknown Tool"

                        arguments_str = function_data.get("arguments", "{}")
                        try:
                            tool_arguments = ast.literal_eval(arguments_str)
                        except (ValueError, SyntaxError, TypeError) as e:
                            print(f"Failed to parse tool arguments: {str(e)}")
                            tool_arguments = arguments_str

                        logger.info(
                            f"\nThe agent is calling the tool [on bright_yellow]{tool_name}[/on bright_yellow] "
                            f"with the query [on bright_yellow]{tool_arguments}[/on bright_yellow]. "
                            f"Please wait for the agent's answer[deep_sky_blue1]...[/deep_sky_blue1]",
                            style="deep_sky_blue1",
                        )
                    except Exception as e:
                        print(f"Error processing tool call: {str(e)}")
                        continue
            else:
                agent_answer = getattr(message, "content", None)
                if agent_answer:
                    logger.info(f"\nAgent:\n{agent_answer}", style="black on white")
        except Exception as e:
            print(f"Error processing message: {str(e)}")

SUMMARY_PROMPT = """
This is summary of the conversation to date: {summary}\n\n
Extend the summary by taking into account the following: {input_text}
"""

def generate_summary(
        input_text: str,
        old_summary: str,
) -> str:
    """
    Generate a summary of the input text, taking into account any existing summary.

    Args:
        input_text (str): The text to summarize
        old_summary (str): Any existing summary to consider

    Returns:
        str: The generated summary
    """
    prompt_template = PromptTemplate.from_template(SUMMARY_PROMPT)
    chain = prompt_template | chatmodel_mistral_large_ran_2
    summary = chain.invoke({"input_text": input_text, "old_summary": old_summary})
    return summary
