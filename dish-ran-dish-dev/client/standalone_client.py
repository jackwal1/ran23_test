#!/usr/bin/env python3
"""
Standalone Client for Testing RAN Agents

This client allows direct testing of agents without running the FastAPI server.
It provides an interactive interface to select and test different agents with
rich logging and real-time streaming output.
"""

import sys
import os
import logging
# Set log level to ERROR for noisy libraries
logging.getLogger().setLevel(logging.ERROR)
logging.getLogger("ibm_watsonx_ai").setLevel(logging.ERROR)
logging.getLogger("httpx").setLevel(logging.ERROR)
logging.getLogger("ibm_watsonx_ai.wml_resource").setLevel(logging.ERROR)
logging.getLogger("ibm_watsonx_ai.client").setLevel(logging.ERROR)
logging.getLogger("urllib3").setLevel(logging.ERROR)
logging.getLogger("psycopg").setLevel(logging.ERROR)
logging.getLogger("psycopg_pool").setLevel(logging.ERROR)
logging.getLogger("langchain_core").setLevel(logging.ERROR)
logging.getLogger("langgraph").setLevel(logging.ERROR)

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
from agent.ran_automation_agent import initialize_ran_automation_agent

console = Console()

# Available agents mapping (easy to extend)
AGENTS = {
    "1": ("RAN Config QA Agent", initialize_ran_config_qa_agent),
    "2": ("RAN Automation Agent", initialize_ran_automation_agent),
    # Add more agents here as needed
}

descriptions = {
    "RAN Config QA Agent": "RAN configuration and QA agent for DISH",
    "RAN Config QA Agent Medium": "RAN configuration and QA agent for DISH using medium model",
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
            async for event in self.agent_instance.astream_events(
                {"messages": [HumanMessage(content=message)]},
                {"configurable": {"thread_id": self.thread_id}},
                version="v2",
            ):
                try:
                    event_type = event["event"]
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
