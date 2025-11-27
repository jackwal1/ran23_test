# from chat.chunks import process_chunks
# from chat.chunks import process_chunks

import traceback
import sys
import os
import logging
import json
from utils.log_init import logger
from utils import constants as CONST
# Set log level to ERROR for noisy libraries
# logging.getLogger().setLevel(logging.ERROR)
# logging.getLogger("ibm_watsonx_ai").setLevel(logging.ERROR)
# logging.getLogger("httpx").setLevel(logging.ERROR)
# logging.getLogger("ibm_watsonx_ai.wml_resource").setLevel(logging.ERROR)
# logging.getLogger("ibm_watsonx_ai.client").setLevel(logging.ERROR)
# logging.getLogger("urllib3").setLevel(logging.ERROR)
# logging.getLogger("psycopg").setLevel(logging.ERROR)
# logging.getLogger("psycopg_pool").setLevel(logging.ERROR)
# logging.getLogger("langchain_core").setLevel(logging.ERROR)
# logging.getLogger("langgraph").setLevel(logging.ERROR)

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import asyncio
import uuid
from typing import Dict
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.table import Table
from langchain_core.messages import HumanMessage, AIMessage

# Import your RAN agent
from agent.ran_config_qa_agent import initialize_ran_config_qa_agent, initialize_ran_config_qa_agent_medium
from utils.ran2_qa.ran_sql_agent_utils import display_messages
from agent.ran_pm_agent import initialize_ran_pm_agent
from agent.ran_qa_agent import initialize_ran_qa_agent
from agent.ran_automation_agent import initialize_ran_automation_agent
from agent.supervisor_agent import initialize_supervisor_agent

if sys.platform.startswith('win'):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

console = Console()

# Available agents mapping (easy to extend)
AGENTS = {
    "1": ("Supervisor Agent", initialize_supervisor_agent),    
    "2": ("RAN Config QA Agent", initialize_ran_config_qa_agent),
    "3": ("RAN Config QA Agent Medium", initialize_ran_config_qa_agent_medium),
    "4": ("RAN PM Agent", initialize_ran_pm_agent),
    "5": ("RAN QA Agent", initialize_ran_qa_agent),     
    "6": ("RAN Automation Agent", initialize_ran_automation_agent),
    # Add more agents here as needed
}

descriptions = {
    "Supervisor Agent": "Supervisor Agent",
    "RAN Config QA Agent": "RAN configuration and QA agent for DISH",
    "RAN Config QA Agent Medium": "RAN configuration and QA agent for DISH using medium model",
    "RAN PM Agent": "RAN Performance Metrics agent",
    "RAN QA Agent": "RAN generic question & answers agent",
    "RAN Automation Agent": "RAN automation agent",
    # Add more descriptions as needed
}

class StandaloneClient:
    def __init__(self):
        self.current_agent = None
        self.current_agent_name = None
        self.thread_id = None
        self.conversation_history = []

    def display_welcome(self):
        console.print(Panel.fit(
            "[bold blue]RAN Agent - Standalone Client[/bold blue]\n"
            "[dim]Interactive testing interface for RAN agents[/dim]",
            border_style="blue"
        ))

    def display_agents(self):
        table = Table(title="Available Agents")
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("Agent Name", style="green")
        table.add_column("Description", style="white")
        for agent_id, (name, _) in AGENTS.items():
            table.add_row(agent_id, name, descriptions.get(name, "No description"))
        console.print(table)

    def select_agent(self) -> bool:
        console.print("\n[bold yellow]Select an agent to test:[/bold yellow]")
        self.display_agents()
        while True:
            choice = Prompt.ask(
                "\nEnter agent ID",
                choices=list(AGENTS.keys()) + ["q"],
                default="1"
            )
            if choice.lower() == "q":
                return False
            if choice in AGENTS:
                self.current_agent_name, self.current_agent = AGENTS[choice]
                self.thread_id = f"{self.current_agent_name.lower().replace(' ', '-')}-{str(uuid.uuid4())[:8]}"
                console.print(f"\n[bold green]Selected: {self.current_agent_name}[/bold green]")
                console.print(f"[dim]Thread ID: {self.thread_id}[/dim]")
                return True
            else:
                console.print("[red]Invalid choice. Please try again.[/red]")

    async def initialize_agent(self):
        try:
            if self.current_agent is None:
                raise RuntimeError("No agent selected or agent initializer is None.")
            console.print(f"\n[bold blue]Initializing {self.current_agent_name}...[/bold blue]")
            self.agent_instance = await self.current_agent()
            console.print(f"[green]✓ {self.current_agent_name} initialized successfully![/green]\n")
        except Exception as e:
            console.print(f"[red]✗ Failed to initialize {self.current_agent_name}: {str(e)}[/red]")
            raise

    async def process_message_stream(self, message: str):
        try:
            console.print("[yellow]🤔 Thinking...[/yellow]")
            console.print(f"Agent name: {self.current_agent_name}")
            # console.print(f'self.thread_id type --> {self.thread_id}')
            # console.print(f'message --> {message}')
            async for event in self.agent_instance.astream_events(
                {"messages": [HumanMessage(content=message)]},
                {"configurable": {"thread_id": self.thread_id}},
                version="v2",
            ):
                try:
                    event_type = event["event"]
                    # print(f'event_type -> {event_type}')
                    if event_type.endswith("_stream") and "chunk" in event.get("data", {}):
                        chunk = event["data"].get("chunk")
                        if isinstance(chunk, AIMessage):
                            content = getattr(chunk, "content", "")
                            if content:
                                console.print(content, end="", style="bold blue")
                    elif event_type == "on_tool_start":
                        tool_data = event.get("data", {})
                        tool_name = tool_data.get("name") or tool_data.get("tool_call") or tool_data.get("tool") or None
                        if not tool_name and "function" in tool_data:
                            tool_name = tool_data["function"].get("name")
                        if not tool_name:
                            tool_name = str(tool_data) if tool_data else "Unknown tool"
                        console.print(f"\n[bold blue]🔧 Calling tool: {tool_name}[/bold blue]")
                    elif event_type == "on_tool_end":
                        console.print(f"\n[bold green]✓ Tool execution completed[/bold green]")
                except Exception as e:
                    console.print(f"\n[red]Error during streaming: {str(e)}[/red]")
                    break
        except Exception as e:
            console.print(f"\n[red]Error in process_message_stream: {str(e)}[/red]")

    # process chat stream - generic
    # async def process_chat_stream(self, message: str):
    #     """
    #     Process chat messages using langgraph with streaming implementation that properly
    #     handles ToolMessage events and appends sources as markdown HTML anchor tags after
    #     the model stream completes.

    #     The function processes events in this sequence:
    #     1. Streams model content in real-time
    #     2. Collects sources from ToolMessage events during streaming
    #     3. Appends formatted source links after content streaming ends

    #     Args:
    #         message (str): The input message to process
    #         thread_id (str): Unique identifier for the chat thread
    #         agent (str): relevant agent name

    #     Yields:
    #         str: Content chunks including model output and source information
    #     """
    #     try:
    #         # initialize agent
    #         # agent_runner = AGENTS[agent]
    #         # langgraph_agent = await agent_runner()  # Initialize selected agent

    #         # Initialize our source collection to gather sources during streaming
    #         sources = []
    #         is_streaming_complete = False
    #         # Start timing for the query response
    #         # start_time = time.perf_counter()

    #         print(f"##### --> streaming events")

    #         async for event in self.agent_instance.graph.astream_events(
    #                 {"messages": [HumanMessage(content=message)]},
    #                 {"recursion_limit": 10, "configurable": {"thread_id": self.thread_id}},
    #                 version="v2"
    #         ):
    #             # Calculate response time (latency)
    #             # response_time = time.perf_counter() - start_time
    #             # await process_chunks(event)
    #             event_type = event["event"]
    #             metadata = event.get('metadata')
    #             if isinstance(metadata, dict):
    #                 langgraph_node_value = metadata.get('langgraph_node')

    #             if event_type == "on_chat_model_stream" and langgraph_node_value == "llm":
    #                 # Handle the main content streaming from the language model
    #                 chunk = event["data"]["chunk"]
    #                 content = chunk.content if hasattr(chunk, "content") else str(chunk)
    #                 item = {'type': 'text', 'content': content}
    #                 yield f"data: {json.dumps(item)}"
    #                 yield "\n\n"
    #                 #yield content

    #             elif event_type == "on_tool_end":
    #                 logger.info(event)
    #                 # Extract source information from ToolMessage
    #                 tool_output = event["data"]["output"]

    #                 if isinstance(tool_output, str):
    #                     # Split content into lines, handling potential line breaks
    #                     lines = tool_output.split('\n')
    #                     current_file = None

    #                     for line in lines:
    #                         # Extract file name using string operations
    #                         if line.startswith('file_name ::'):
    #                             current_file = line.replace('file_name ::', '').strip()

    #                         # When we have file name, store them
    #                         if current_file:
    #                             source_tuple = (current_file)
    #                             if source_tuple not in sources:
    #                                 sources.append(source_tuple)
    #                                 # Reset for next pair
    #                                 current_file = None
    #             elif event_type == "on_chain_end":
    #                 # Mark streaming as complete when the chain ends
    #                 is_streaming_complete = True

    #         # After all streaming is complete, append sources if we have any
    #         if is_streaming_complete and sources:
    #             # Add formatting for the sources section
    #             source_item = {'type': 'text', 'content': "\n\n**Sources:**\n"}
    #             yield f"data: {json.dumps(source_item)}"
    #             yield "\n\n"

    #             # Generate and yield source links individually
    #             for file_name in sources:
    #                 # Format each source as a markdown bullet point with HTML anchor tag
    #                 source_link = f'• <a href="{CONST.FILE_ENDPOINT}{file_name}" target="_blank">{file_name}</a>\n'
    #                 source_file_item = {'type': 'text', 'content': source_link}
    #                 yield f"data: {json.dumps(source_file_item)}"
    #                 yield "\n\n"

    #     except Exception as e:
    #         logger.error(f"Error in streaming process: {str(e)}")
    #         logger.error(traceback.format_exc())
    #         error_message = {'type': 'error', 'content': "I encountered an issue while processing your request. Please try again."}
    #         yield f"data: {json.dumps(error_message)}"
    #         yield "\n\n"


    async def run_conversation_loop(self):
        console.print(f"\n[bold green]Starting conversation with {self.current_agent_name}[/bold green]")
        console.print("[dim]Type 'quit' or 'exit' to end the conversation[/dim]")
        console.print("[dim]Type 'clear' to clear conversation history[/dim]\n")
        while True:
            try:
                user_input = Prompt.ask(f"\n[bold cyan]You[/bold cyan]")
                if user_input.lower() in ["quit", "exit", "q"]:
                    console.print("\n[bold yellow]Ending conversation...[/bold yellow]")
                    break
                if user_input.lower() == "clear":
                    self.conversation_history = []
                    console.print("\n[green]Conversation history cleared[/green]")
                    continue
                if not user_input.strip():
                    continue
                self.conversation_history.append({"role": "user", "content": user_input})
                # Show chat state table before agent response
                state = {"messages": [HumanMessage(content=user_input)]}
                display_messages(state["messages"])
                console.print(f"\n[bold blue]{self.current_agent_name}[/bold blue]")
                await self.process_message_stream(user_input)
                console.print("\n")
            except KeyboardInterrupt:
                console.print("\n[bold yellow]Interrupted by user[/bold yellow]")
                break
            except Exception as e:
                console.print(f"\n[red]Error: {str(e)}[/red]")

    async def run(self):
        self.display_welcome()
        while True:
            if not self.select_agent():
                console.print("\n[bold yellow]Goodbye![/bold yellow]")
                break
            try:
                await self.initialize_agent()
                await self.run_conversation_loop()
                if not Confirm.ask("\n[bold yellow]Test another agent?[/bold yellow]"):
                    console.print("\n[bold yellow]Goodbye![/bold yellow]")
                    break
            except Exception as e:
                console.print(f"\n[red]Error: {str(e)}[/red]")
                if not Confirm.ask("\n[bold yellow]Try another agent?[/bold yellow]"):
                    break

async def main():
    client = StandaloneClient()
    await client.run()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print("\n[bold yellow]Goodbye![/bold yellow]")
    except Exception as e:
        console.print(f"\n[red]Fatal error: {str(e)}[/red]")
