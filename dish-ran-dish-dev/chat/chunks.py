import ast
from collections.abc import Iterable
from typing import Dict, Optional, Any
from rich.console import Console
from rich.table import Table
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, SystemMessage, filter_messages
from langgraph.graph import MessagesState
from utils.log_init import logger

rich = Console()

# process chunks
async def process_chunks(chunk: Optional[Dict[str, Any]]) -> None:
    """
    Process a chunk of data and extract information about tool calls made by the agent.
    """
    if chunk is None:
        rich.print("[red]Error: Chunk is None[/red]")
        return

    if not isinstance(chunk, dict):
        rich.print(f"[red]Error: Expected dict for chunk, got {type(chunk).__name__}[/red]")
        return

    data = chunk.get("data")
    if data is None:
        rich.print("[red]Error: No 'data' field found in chunk[/red]")
        return

    if not isinstance(data, dict):
        rich.print(f"[red]Error: Expected dict for data, got {type(data).__name__}[/red]")
        return

    output = data.get("output")
    if output is None:
        return

    messages = output
    if messages is None:
        rich.print("[red]Error: Messages is None[/red]")
        return

    if isinstance(messages, (AIMessage, ToolMessage)):
        return

    if not isinstance(messages, Iterable):
        return

    try:
        messages_list = list(messages)
        if not messages_list:
            rich.print("[yellow]Warning: Empty messages list[/yellow]")
            return
    except TypeError:
        rich.print("[red]Error: Could not convert messages to list[/red]")
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

                        rich.print(
                            f"\nThe agent is calling the tool [yellow]{tool_name}[/yellow] "
                            f"with the query [green]{tool_arguments}[/green].",
                            style="blue",
                        )
            else:
                agent_answer = getattr(message, "content", None)
                if agent_answer:
                    rich.print(f"\nAgent:\n[bright_magenta on bright_blue]{agent_answer}[/bright_magenta on bright_blue]")
        except Exception as e:
            logger.error(f"Error processing message: {str(e)}")
            continue


async def process_checkpoints(checkpoints) -> None:
    """
    Asynchronously process a list of checkpoints, extracting and displaying key information about each checkpoint.
    """
    rich.print("\n==========================================================\n")
    checkpoints_list = []
    async for checkpoint_tuple in checkpoints:
        checkpoints_list.append(checkpoint_tuple)

    for idx, checkpoint_tuple in enumerate(checkpoints_list):
        checkpoint = checkpoint_tuple.checkpoint
        messages = checkpoint["channel_values"].get("messages", [])
        rich.print(f"[white]Checkpoint:[/white]")
        rich.print(f"[black]Timestamp: {checkpoint['ts']}[/black]")
        rich.print(f"[black]Checkpoint ID: {checkpoint['id']}[/black]")

        for message in messages:
            if isinstance(message, HumanMessage):
                rich.print(
                    f"[bright_magenta]User: {message.content}[/bright_magenta] [bright_cyan](Message ID: {message.id})[/bright_cyan]"
                )
            elif isinstance(message, AIMessage):
                rich.print(
                    f"[bright_magenta]Agent: {message.content}[/bright_magenta] [bright_cyan](Message ID: {message.id})[/bright_cyan]"
                )
        rich.print("")
        break  # Only show the latest checkpoint

    rich.print("==========================================================")


async def display_messages(messages) -> None:
    table = Table(title="Chat State Messages", show_header=True, header_style="bold magenta")
    table.add_column("Type", style="cyan", justify="center")
    table.add_column("Content", style="green")
    table.add_column("Details", style="yellow")

    for msg in messages:
        if isinstance(msg, HumanMessage):
            msg_type = "HumanMessage"
            content = msg.content
            details = f"[b]ID:[/b] {msg.id}"
        elif isinstance(msg, AIMessage):
            msg_type = "AIMessage"
            content = msg.content or "[No direct content]"
            tool_calls = msg.additional_kwargs.get('tool_calls', 'None')
            details = f"[b]Tool Calls:[/b] {tool_calls}" if tool_calls != 'None' else f"[b]ID:[/b] {msg.id}"
        elif isinstance(msg, ToolMessage):
            msg_type = "ToolMessage"
            content = msg.content
            details = f"[b]Tool Name:[/b] {msg.name} | [b]ID:[/b] {msg.id}"
        elif isinstance(msg, SystemMessage):
            msg_type = "SystemMessage"
            content = msg.content
            details = f"[b]ID:[/b] {msg.id}"            
        else:
            msg_type = "Unknown"
            content = "N/A"
            details = "N/A"

        table.add_row(msg_type, content, details)

    rich.print(table)


async def manage_memory(state: MessagesState, agent_instruction :str):
    """
    Control the messages list sent to the LLM by trimming and reformatting messages.
    """
    messages = state['messages']
    logger.info(f'##### --> Before Trim messages --> {messages}')

    # # Remove ToolMessage
    # messages = filter_messages(messages, exclude_types="tool")
    # print(messages)

    # # Remove AIMessage with no content
    # messages = [
    #     msg for msg in messages
    #     if not (isinstance(msg, AIMessage) and msg.content.strip() == '')
    # ]
    # logger.info(f'##### --> After Trim messages --> {messages}')
    
    trimmed_messages = messages[-10:]
    
    # Find the first user (HumanMessage) in the trimmed list
    human_index = next(
        (i for i, message in enumerate(trimmed_messages) if isinstance(message, HumanMessage)), None
    )

    if human_index is not None:
        # Slice from the first HumanMessage onward
        trimmed_messages = trimmed_messages[human_index:]
    else:
        trimmed_messages = []

    logger.info("<================= messages to LLM  ==================> ")
    await display_messages(messages)
    return [SystemMessage(content=agent_instruction)] + trimmed_messages


async def process_chunks_non_streaming(chunk: Optional[Dict[str, Any]]) -> None:
    """
    Process a chunk of data in non-streaming mode and extract information about tool calls made by the agent.
    """
    if chunk is None:
        rich.print("[red]Error: Chunk is None[/red]")
        return

    if not isinstance(chunk, dict):
        rich.print(f"[red]Error: Expected dict for chunk, got {type(chunk).__name__}[/red]")
        return

    if "agent" not in chunk:
        rich.print("[red]Error: No 'agent' field found in chunk[/red]")
        return

    agent_data = chunk.get("agent")
    if not isinstance(agent_data, dict):
        rich.print(f"[red]Error: Expected dict for agent data, got {type(agent_data).__name__}[/red]")
        return

    messages = agent_data.get("messages")
    if not messages:
        rich.print("[red]Error: No messages found in agent data[/red]")
        return

    if not isinstance(messages, (list, tuple)):
        rich.print(f"[red]Error: Expected list or tuple for messages, got {type(messages).__name__}[/red]")
        return

    for message in messages:
        try:
            if message is None:
                continue

            if not hasattr(message, "additional_kwargs"):
                rich.print("[yellow]Warning: Message missing additional_kwargs attribute[/yellow]")
                continue

            if "tool_calls" in message.additional_kwargs:
                tool_calls = message.additional_kwargs.get("tool_calls")
                if not tool_calls:
                    continue

                if not isinstance(tool_calls, (list, tuple)):
                    rich.print(f"[red]Error: Expected list for tool_calls, got {type(tool_calls).__name__}[/red]")
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
                            logger.error(f"Failed to parse tool arguments: {str(e)}")
                            tool_arguments = arguments_str

                        rich.print(
                            f"\nThe agent is calling the tool [on bright_yellow]{tool_name}[/on bright_yellow] "
                            f"with the query [on bright_yellow]{tool_arguments}[/on bright_yellow]. "
                            f"Please wait for the agent's answer[deep_sky_blue1]...[/deep_sky_blue1]",
                            style="deep_sky_blue1",
                        )
                    except Exception as e:
                        logger.error(f"Error processing tool call: {str(e)}")
                        continue
            else:
                agent_answer = getattr(message, "content", None)
                if agent_answer:
                    rich.print(f"\nAgent:\n{agent_answer}", style="black on white")
        except Exception as e:
            logger.error(f"Error processing message: {str(e)}")
