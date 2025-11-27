from typing import Dict, Any, Optional, List, Callable
from langgraph.graph import StateGraph, END, MessagesState
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage, AIMessage, RemoveMessage
from langchain_core.tools import StructuredTool
from langchain_core.language_models import BaseLanguageModel
from rich.console import Console
from utils.log_init import logger
from utils.network_agent_utils import display_messages
import json
# from datetime import datetime

console = Console()

class BaseSupervisorState(MessagesState):
    """State for supervisor agent, including active worker and summary."""
    active_agent: str = ""
    worker_thread_id: str = ""
    summary: str = ""

class BaseSupervisorAgent:
    """
    Modular, extensible base class for supervisor agents.
    Orchestrates multiple worker agents with configurable routing, memory, and tools.
    """
    def __init__(
        self,
        model: BaseLanguageModel,
        workers: Dict[str, Any],
        checkpointer: Any,
        token_memory_limit: int = 100000,
        system: str = "",
        tool_factory: Optional[Callable[[str], StructuredTool]] = None,
        routing_logic: Optional[Callable[[BaseSupervisorState], Optional[str]]] = None,
    ):
        """
        Args:
            model: The language model to use for generating responses
            workers: Dictionary of worker agents {name: graph}
            checkpointer: Checkpoint manager for saving/loading supervisor state
            token_memory_limit: Max tokens in conversation history
            system: System prompt for the supervisor
            tool_factory: Optional function to create handoff tools for each worker
            routing_logic: Optional function to override routing to workers
        """
        self.system = system
        self.workers = workers
        self.model = model
        self.token_memory_limit = token_memory_limit
        self.tool_factory = tool_factory or self._default_tool_factory
        self.routing_logic = routing_logic or self._default_routing_logic

        # Create supervisor tools for agent handoff
        self.tools_list = [self.tool_factory(name) for name in self.workers.keys()]
        self.tools_dict = {tool.name: tool for tool in self.tools_list}
        self.model_with_tools = model.bind_tools(self.tools_list)

        # Build the supervisor graph
        graph = StateGraph(BaseSupervisorState)
        graph.add_node("llm", self.call_llm)
        graph.add_node("action", self.take_action)
        graph.add_node("memory", self.filter_memory)
        graph.add_node("route_to_worker", self.route_to_worker)
        graph.add_conditional_edges(
            "llm", self.exists_action, {True: "action", False: "memory"}
        )
        graph.add_edge("action", "route_to_worker")
        graph.add_edge("route_to_worker", END)
        graph.add_edge("memory", END)
        graph.set_entry_point("llm")
        self.graph = graph.compile(checkpointer=checkpointer)

    def _default_tool_factory(self, name: str) -> StructuredTool:
        """Default: create a handoff tool for each worker agent."""
        def handoff_to_agent(user_message: str) -> str:
            return f"Handing off to {name} agent"
        return StructuredTool.from_function(
            func=handoff_to_agent,
            name=f"transfer_to_{name}",
            description=f"Transfer control to the {name} agent for specialized tasks"
        )

    def _default_routing_logic(self, state: BaseSupervisorState) -> Optional[str]:
        """Default: use active_agent in state, or None."""
        return getattr(state, "active_agent", None)

    def exists_action(self, state: BaseSupervisorState) -> bool:
        """Check if the last message contains tool calls to execute."""
        if state["messages"] and isinstance(state["messages"][-1], AIMessage):
            result = state["messages"][-1]
            tool_calls_from_kwargs = result.additional_kwargs.get("tool_calls", [])
            if tool_calls_from_kwargs:
                corrected_tool_calls = []
                for call in tool_calls_from_kwargs:
                    try:
                        name = call["function"]["name"]
                        try:
                            args = json.loads(call["function"]["arguments"])
                        except json.JSONDecodeError:
                            args = call["function"]["arguments"]
                        id = call["id"]
                        type = "tool_call"
                        corrected_tool_calls.append(
                            {"name": name, "args": args, "id": id, "type": type}
                        )
                    except (KeyError, json.JSONDecodeError):
                        pass
                result.tool_calls = corrected_tool_calls
                state["messages"][-1] = result
            return len(result.tool_calls) > 0
        return False

    async def take_action(self, state: BaseSupervisorState) -> Dict:
        """Execute tool calls from the last AI message."""
        tool_calls = state["messages"][-1].tool_calls
        results = []
        selected_worker = None
        for t in tool_calls:
            try:
                args = t.get("args", {})
                tool_name = t.get("name", "unknown_tool")
                tool_id = t.get("id", "unknown_id")
                if tool_name.startswith("transfer_to_"):
                    selected_worker = tool_name.replace("transfer_to_", "")
                result = await self.tools_dict[tool_name].ainvoke(args)
                results.append(
                    ToolMessage(
                        tool_call_id=tool_id, name=tool_name, content=str(result)
                    )
                )
                logger.info(f"Tool {tool_name} result: {result}")

            except Exception as e:
                results.append(
                    ToolMessage(tool_call_id=tool_id, name=tool_name, content=str(e))
                )
        if selected_worker:
            return {"messages": results, "active_agent": selected_worker}
        return {"messages": results}

    async def route_to_worker(self, state: BaseSupervisorState, config: dict = None) -> Dict:
        """Route the message to the appropriate worker agent."""
        user_message = None
        for msg in reversed(state["messages"]):
            if isinstance(msg, HumanMessage):
                user_message = msg.content
                break
        if not user_message:
            return {"messages": []}
        worker_name = state.get("active_agent") or self.routing_logic(state)
        if not worker_name:
            worker_name = list(self.workers.keys())[0]  # fallback to first worker
        supervisor_thread_id = None
        if config:
            supervisor_thread_id = config.get("configurable", {}).get("thread_id")
        worker_thread_id = f"{supervisor_thread_id}-{worker_name}" if supervisor_thread_id else worker_name
        state["active_agent"] = worker_name
        state["worker_thread_id"] = worker_thread_id
        worker_graph = self.workers[worker_name]
        try:
            result = await worker_graph.ainvoke(
                {"messages": [HumanMessage(content=user_message)]},
                {"recursion_limit": 15, "configurable": {"thread_id": worker_thread_id}},
            )
            final_messages = result.get("messages", []) if isinstance(result, dict) else (
                result.messages if hasattr(result, 'messages') else (result if isinstance(result, list) else [])
            )
            if final_messages:
                for msg in reversed(final_messages):
                    if isinstance(msg, AIMessage):
                        return {"messages": [msg]}
                return {"messages": [final_messages[-1]]}
            else:
                return {"messages": [AIMessage(content="No response from worker agent")]} 
        except Exception as e:
            return {"messages": [AIMessage(content=f"Error: {str(e)}")]} 

    async def filter_memory(self, state: BaseSupervisorState) -> Dict:
        """Summarize and trim history if token limit is exceeded."""
        messages = state["messages"]
        history_str = ""
        if self.system or state.get("summary", ""):
            history_str = "System: " + self.system + state.get("summary", "") + "\n"
        for msg in messages:
            if isinstance(msg, ToolMessage):
                history_str += "Tool: "
            elif isinstance(msg, AIMessage):
                history_str += "AI: "
            elif isinstance(msg, HumanMessage):
                history_str += "Human: "
            history_str += msg.content + "\n"
        # (Token counting and summarization logic can be customized)
        return {}

    async def call_llm(self, state: BaseSupervisorState, config: dict = None) -> Dict:
        active_agent = state.get("active_agent") or "None"
        console.print(f"[bold blue]Active agent: {active_agent}[/bold blue]")
        system_prompt = self.system.format(active_agent=active_agent)
        messages = state["messages"]
        if self.system or state.get("summary", ""):
            messages = [
                SystemMessage(content=system_prompt + state.get("summary", ""))
            ] + messages

        await display_messages(messages)

        message = await self.model_with_tools.ainvoke(messages)
        logger.info(message)
        return {"messages": [message]} 