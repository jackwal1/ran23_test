from rich.table import Table
from rich.console import Console
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, filter_messages, SystemMessage
from langgraph.graph import MessagesState
from prompts.ran_sql_prompts_v2 import  RAN_SQL_AGENT_INSTRUCTION_PROMPT_V2
from collections.abc import Iterable

rich = Console()


async def process_chunks(chunk):
    """
    Process a chunk of data and extract information about tool calls made by the agent.

    Parameters:
        chunk (dict): A dictionary containing information about the agent's messages.

    Returns:
        None
    """

    # Check if the chunk contains data and if it's a dictionary
    if not isinstance(chunk, dict):
        rich.print("[red]The chunk is not a valid dictionary.[/red]")
        return

    data = chunk.get("data", {})
    if not isinstance(data, dict):
        rich.print("[red]The 'data' field is not a valid dictionary.[/red]")
        return

    output = data.get("output", {})
    messages = output

    if not isinstance(messages, Iterable) or isinstance(messages,AIMessage) \
            or isinstance(messages,ToolMessage):
        return
    if len(str(messages)) == 0:
        return

    # Iterate over messages
    for message in messages:
        # Check if the message contains additional_kwargs and tool_calls
        if hasattr(message, "additional_kwargs") and "tool_calls" in message.additional_kwargs:
            tool_calls = message.additional_kwargs["tool_calls"]

            # Process each tool call
            for tool_call in tool_calls:
                tool_name = tool_call.get("function", {}).get("name", "Unknown")
                try:
                    tool_arguments = eval(tool_call.get("function", {}).get("arguments", "{}"))
                except Exception:
                    tool_arguments = tool_call.get("function", {}).get("arguments", "{}")

                # Display tool call details
                rich.print(
                    f"\nThe agent is calling the tool [yellow]{tool_name}[/yellow] "
                    f"with the query [green]{tool_arguments}[/green].",
                    style="blue",
                )
        else:
            # Handle regular messages (without tool calls)
            agent_answer = getattr(message, "content", None)

            # Display the message content only if available
            if agent_answer:
                rich.print(f"\nAgent:\n[bright_magenta on bright_blue]{agent_answer}[/bright_magenta on bright_blue]")


# Define an async function to process checkpoints from the memory
async def process_checkpoints(checkpoints):
    """
    Asynchronously process a list of checkpoints, extracting and displaying key information about each checkpoint,
    including timestamp, checkpoint ID, and messages exchanged between the user and the agent.

    This function iterates over an asynchronous generator of checkpoints, collecting relevant details for each
    checkpoint, such as the timestamp of the checkpoint, its unique ID, and any associated messages. It formats
    and prints this information using the Rich library, allowing for a visually appealing output.

    Each checkpoint consists of a tuple where the first element is the index and the second element is an object
    containing various details about the checkpoint. The function distinguishes between messages from the user
    and the agent, displaying them accordingly.

    Parameters:
        checkpoints (list): A list of checkpoint tuples to be processed.

    Returns:
        None
    """

    rich.print("\n==========================================================\n")

    # Initialize an empty list to store the checkpoints
    checkpoints_list = []

    # Iterate over the checkpoints and add them to the list in an async way
    async for checkpoint_tuple in checkpoints:
        checkpoints_list.append(checkpoint_tuple)

    # Iterate over the list of checkpoints
    for idx, checkpoint_tuple in enumerate(checkpoints_list):
        # Extract key information about the checkpoint
        checkpoint = checkpoint_tuple.checkpoint
        messages = checkpoint["channel_values"].get("messages", [])

        # Display checkpoint information
        rich.print(f"[white]Checkpoint:[/white]")
        rich.print(f"[black]Timestamp: {checkpoint['ts']}[/black]")
        rich.print(f"[black]Checkpoint ID: {checkpoint['id']}[/black]")

        # Display checkpoint messages
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
        break  #just show the latest one. remove this to see all checkpoints

    rich.print("==========================================================")


def display_messages(messages):
    table = Table(title="Chat State Messages", show_header=True, header_style="bold magenta")
    table.add_column("Type", style="cyan", justify="center")
    table.add_column("Content", style="green")
    table.add_column("Details", style="yellow")

    for msg in messages:
        if isinstance(msg, HumanMessage):
            msg_type = "HumanMessage"
            content = str(msg.content)
            details = f"[b]ID:[/b] {msg.id}"
        elif isinstance(msg, AIMessage):
            msg_type = "AIMessage"
            content = str(msg.content or "[No direct content]")
            tool_calls = msg.additional_kwargs.get('tool_calls', 'None')
            details = f"[b]Tool Calls:[/b] {tool_calls}" if tool_calls != 'None' else f"[b]ID:[/b] {msg.id}"
        elif isinstance(msg, ToolMessage):
            msg_type = "ToolMessage"
            content = str(msg.content)
            details = f"[b]Tool Name:[/b] {msg.name} | [b]ID:[/b] {msg.id}"
        else:
            continue  # Skip unknown message types
        table.add_row(str(msg_type), str(content), str(details))

    rich.print(table)

from langchain_core.messages.utils import (
    trim_messages,
    count_tokens_approximately
)
async def manage_memory(state: MessagesState):
    # This is where we control the messages list sent to LLM
    messages = state['messages']
    #print('Complete state:')
    #display_messages(messages)

    # Use LangGraph's trim_messages utility
    trimmed_messages = trim_messages(
        messages,
        # Keep the last <= n_count tokens of the messages.
        strategy="last",
        token_counter=len,
        # When token_counter=len, each message
        # will be counted as a single token.
        # Remember to adjust for your use case
        max_tokens=20,
        # Most chat models expect that chat history starts with either:
        # (1) a HumanMessage or
        # (2) a SystemMessage followed by a HumanMessage
        start_on="human",
        # Most chat models expect that chat history ends with either:
        # (1) a HumanMessage or
        # (2) a ToolMessage
        end_on=("human", "tool"),
        # Usually, we want to keep the SystemMessage
        # if it's present in the original history.
        # The SystemMessage has special instructions for the model.
        include_system=True,
    )

    # Option 1: Add system message if none exists
    if not any(isinstance(msg, SystemMessage) for msg in trimmed_messages):
        trimmed_messages = [SystemMessage(content=RAN_SQL_AGENT_INSTRUCTION_PROMPT_V2)] + trimmed_messages

    # Option 2: Always prepend system message (uncomment if you want to force it)
    # trimmed_messages = [SystemMessage(content=RAN_SQL_AGENT_INSTRUCTION_PROMPT_V2)] + trimmed_messages

    print('final state to LLM: \n')
    display_messages(trimmed_messages)

    # Return the trimmed messages
    return trimmed_messages
async def process_chunks_non_streaming(chunk):
    """
    Process a chunk of data and extract information about tool calls made by the agent.

    This function processes a chunk of data and checks if it contains information about an agent. If the chunk contains
    an agent's message, it iterates over the messages in the agent's messages. For each message, it checks if the
    message contains tool calls. If a tool call is found, the function extracts the tool name and query from the
    message and prints a formatted message using the Rich library. If no tool call is found, the function extracts
    the agent's answer from the message and prints it using the Rich library, allowing for a visually appealing output.

    Parameters:
        chunk (dict): A dictionary containing information about the agent's messages.

    Returns:
        None
    """
    #print('chunk received: ', chunk)
    #chunk["messages"].pretty_print()
    # Check if the chunk contains an agent's message
    if "agent" in chunk:
        # Iterate over the messages in the chunk
        for message in chunk["agent"]["messages"]:
            # Check if the message contains tool calls
            if "tool_calls" in message.additional_kwargs:
                # If the message contains tool calls, extract and display an informative message with tool call details

                # Extract all the tool calls
                tool_calls = message.additional_kwargs["tool_calls"]

                # Iterate over the tool calls
                for tool_call in tool_calls:
                    #print('Tool call: ', tool_call)
                    # Extract the tool name
                    tool_name = tool_call["function"]["name"]
                    #print('tool name --> ', tool_name)

                    # Extract the tool query
                    tool_arguments = eval(tool_call["function"]["arguments"])
                    #tool_query = tool_arguments["query"]
                    tool_query = tool_arguments

                    # Display an informative message with tool call details
                    rich.print(
                        f"\nThe agent is calling the tool [on bright_yellow]{tool_name}[/on bright_yellow] with the query [on bright_yellow]{tool_query}[/on bright_yellow]. Please wait for the agent's answer[deep_sky_blue1]...[/deep_sky_blue1]",
                        style="deep_sky_blue1",
                    )
            else:
                # If the message doesn't contain tool calls, extract and display the agent's answer

                # Extract the agent's answer
                agent_anser = message.content

                # Display the agent's answer
                rich.print(f"\nAgent:\n{agent_anser}", style="black on white")