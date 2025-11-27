from typing import Dict, Any, Optional, List, Callable
from langgraph.graph import StateGraph, END, MessagesState
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage, BaseMessage, AIMessage, RemoveMessage
from langchain_core.tools import StructuredTool
from langchain_core.language_models import BaseLanguageModel
from langchain_core.messages.utils import trim_messages
from rich.console import Console
from utils.log_init import logger
from utils.network_agent_utils import display_messages
import json
import asyncio

console = Console()


class BaseSupervisorState(MessagesState):
    """State for supervisor agent, including active worker and summary."""
    active_agent: str = ""
    worker_thread_id: str = ""
    summary: str = ""
    # Enhanced state for recovery tracking
    recovery_mode: bool = False
    last_failed_worker: Optional[str] = None
    error_count: int = 0
    pending_tool_calls: List[Dict] = []
    action_success: bool = True
    # Track processed tool call IDs to prevent duplicates
    processed_tool_call_ids: set = set()


class BaseSupervisorAgent:
    """
    Modular, extensible base class for supervisor agents.
    Orchestrates multiple worker agents with configurable routing, memory, and tools.
    Enhanced with robust error handling, recovery mechanisms, and proper conversation management.
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
            conversation_window: int = 15,
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
            conversation_window: Number of recent messages to include in LLM context (default: 15)
        """
        self.system = system
        self.workers = workers
        self.model = model
        self.token_memory_limit = token_memory_limit
        self.tool_factory = tool_factory or self._default_tool_factory
        self.routing_logic = routing_logic or self._default_routing_logic
        self.conversation_window = conversation_window

        # Create supervisor tools for agent handoff
        self.tools_list = [self.tool_factory(name) for name in self.workers.keys()]
        self.tools_dict = {tool.name: tool for tool in self.tools_list}
        self.model_with_tools = model.bind_tools(self.tools_list)

        # Build the supervisor graph with enhanced error handling
        graph = StateGraph(BaseSupervisorState)
        graph.add_node("llm", self.call_llm)
        graph.add_node("action", self.take_action)
        graph.add_node("memory", self.filter_memory)
        graph.add_node("route_to_worker", self.route_to_worker)
        graph.add_node("handle_worker_failure", self.handle_worker_failure)
        graph.add_node("recover_conversation", self.recover_conversation)

        graph.add_conditional_edges(
            "llm", self.exists_action, {True: "action", False: "memory"}
        )
        graph.add_conditional_edges(
            "action", self.check_action_success,
            {True: "route_to_worker", False: "handle_worker_failure"}
        )
        graph.add_edge("route_to_worker", END)
        graph.add_edge("handle_worker_failure", "recover_conversation")
        graph.add_edge("recover_conversation", END)
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
        """Execute tool calls from the last AI message with enhanced error tracking."""
        tool_calls = state["messages"][-1].tool_calls
        results = []
        selected_worker = None
        action_success = True
        state["pending_tool_calls"] = tool_calls

        # Initialize processed_tool_call_ids if not present
        if "processed_tool_call_ids" not in state:
            state["processed_tool_call_ids"] = set()

        for t in tool_calls:
            try:
                args = t.get("args", {})
                tool_name = t.get("name", "unknown_tool")
                tool_id = t.get("id", "unknown_id")

                # Skip duplicate tool calls
                if tool_id in state["processed_tool_call_ids"]:
                    logger.warning(f"Skipping duplicate tool call: {tool_id}")
                    continue

                # Mark as processed
                state["processed_tool_call_ids"].add(tool_id)

                if tool_name.startswith("transfer_to_"):
                    selected_worker = tool_name.replace("transfer_to_", "")
                    results.append(
                        ToolMessage(
                            tool_call_id=tool_id,
                            name=tool_name,
                            content=f"Transferring to {selected_worker} agent"
                        )
                    )
                    logger.info(f"Transfer to {selected_worker} agent initiated")
                    continue

                result = await self.tools_dict[tool_name].ainvoke(args)
                results.append(
                    ToolMessage(
                        tool_call_id=tool_id, name=tool_name, content=str(result)
                    )
                )
                logger.info(f"Tool {tool_name} result: {result}")
            except Exception as e:
                action_success = False
                results.append(
                    ToolMessage(tool_call_id=tool_id, name=tool_name, content=str(e))
                )
                logger.error(f"Tool {tool_name} failed: {str(e)}")

        if selected_worker:
            return {
                "messages": results,
                "active_agent": selected_worker,
                "action_success": action_success,
                "processed_tool_call_ids": state["processed_tool_call_ids"]
            }
        return {
            "messages": results,
            "action_success": action_success,
            "processed_tool_call_ids": state["processed_tool_call_ids"]
        }

    def check_action_success(self, state: BaseSupervisorState) -> bool:
        """Check if tool execution was successful."""
        success = state.get("action_success", True)
        logger.info(f"Action success check: {success}")
        return success

    async def handle_worker_failure(self, state: BaseSupervisorState) -> Dict:
        """Handle worker agent failures without alternative handoff."""
        state["recovery_mode"] = True
        state["error_count"] += 1
        state["last_failed_worker"] = state.get("active_agent", "")
        error_msg = AIMessage(
            content=f"I encountered an issue with the {state['last_failed_worker']} agent. "
                    f"Let me try to help you differently."
        )
        if state["error_count"] >= 3:
            error_msg = AIMessage(
                content="I'm experiencing technical difficulties with multiple services. "
                        "Please try again later or contact support."
            )
            return {"messages": [error_msg], "recovery_mode": False}
        return {"messages": [error_msg]}

    async def recover_conversation(self, state: BaseSupervisorState) -> Dict:
        """Recover conversation state after worker failure without retry."""
        recovery_msg = ToolMessage(
            tool_call_id="recovery",
            name="conversation_recovery",
            content="Conversation state recovered after worker failure"
        )
        state["recovery_mode"] = False
        state["pending_tool_calls"] = []
        return {"messages": [recovery_msg]}

    async def route_to_worker(self, state: BaseSupervisorState, config: dict = None) -> Dict:
        """Route the message to the appropriate worker agent with comprehensive response handling."""
        logger.info(f"Entering route_to_worker with active_agent: {state.get('active_agent')}")
        user_message = None
        for msg in reversed(state["messages"]):
            if isinstance(msg, HumanMessage):
                user_message = msg.content
                break
        if not user_message:
            logger.warning("No user message found in route_to_worker")
            return {"messages": []}
        worker_name = state.get("active_agent") or self.routing_logic(state)
        if not worker_name:
            logger.warning("No worker name found, using first worker")
            worker_name = list(self.workers.keys())[0]
        logger.info(f"Routing to worker: {worker_name}")
        supervisor_thread_id = None
        if config:
            supervisor_thread_id = config.get("configurable", {}).get("thread_id")
        worker_thread_id = f"{supervisor_thread_id}-{worker_name}" if supervisor_thread_id else worker_name
        state["active_agent"] = worker_name
        state["worker_thread_id"] = worker_thread_id
        if worker_name not in self.workers:
            logger.error(f"Worker {worker_name} not found in workers dictionary")
            return {"messages": [AIMessage(content=f"Worker agent {worker_name} not found.")]}
        worker_graph = self.workers[worker_name]
        try:
            logger.info(f"Invoking worker {worker_name} with message: {user_message}")

            # Get the supervisor's callback manager to pass to worker
            supervisor_callbacks = None
            if config and "callbacks" in config:
                supervisor_callbacks = config["callbacks"]

            # Create worker config with supervisor's callbacks
            worker_config = {
                "recursion_limit": 15,
                "configurable": {
                    "thread_id": worker_thread_id
                }
            }

            # Pass supervisor's callbacks to worker for event propagation
            if supervisor_callbacks:
                worker_config["configurable"]["callbacks"] = supervisor_callbacks

            result = await asyncio.wait_for(
                worker_graph.ainvoke(
                    {"messages": [HumanMessage(content=user_message)]},
                    worker_config,
                ),
                timeout=1800.0
            )

            logger.info(f"Worker {worker_name} returned result")
            final_messages = result.get("messages", []) if isinstance(result, dict) else (
                result.messages if hasattr(result, 'messages') else (result if isinstance(result, list) else [])
            )
            if not final_messages:
                logger.warning(f"Worker {worker_name} returned no messages")
                error_msg = AIMessage(
                    content=f"The {worker_name} agent didn't provide any response. "
                            f"Please try again or contact support if the issue persists."
                )
                return {"messages": [error_msg]}
            ai_message = None
            for msg in reversed(final_messages):
                if isinstance(msg, AIMessage):
                    ai_message = msg
                    break
            if ai_message:
                logger.info(f"Using AIMessage from worker {worker_name}")
                return {"messages": [ai_message]}
            else:
                logger.warning(f"Worker {worker_name} returned messages without AIMessage")
                synthetic_ai = AIMessage(
                    content=f"I notice the {worker_name} agent didn't provide a complete response. "
                            f"This might indicate a technical issue. The agent returned: "
                            f"{self._summarize_worker_messages(final_messages)} "
                            f"Please try your request again or contact support."
                )
                return {"messages": final_messages + [synthetic_ai]}
        except asyncio.TimeoutError:
            logger.error(f"Worker {worker_name} timed out after 30 minutes")
            timeout_msg = AIMessage(
                content=f"The {worker_name} agent is taking too long to respond. "
                        f"Please try a simpler request or contact support."
            )
            return {"messages": [timeout_msg]}
        except Exception as e:
            logger.error(f"Error invoking worker {worker_name}: {str(e)}")
            error_msg = AIMessage(
                content=f"I encountered an issue with the {worker_name} agent. "
                        f"Please try again or contact support if the problem continues."
            )
            return {"messages": [error_msg]}

    def _summarize_worker_messages(self, messages: List[BaseMessage]) -> str:
        """Create a user-friendly summary of worker messages for error reporting."""
        if not messages:
            return "no messages"
        message_types = [type(m).__name__ for m in messages]
        type_counts = {t: message_types.count(t) for t in set(message_types)}
        summary_parts = []
        for msg_type, count in type_counts.items():
            if msg_type == "HumanMessage":
                summary_parts.append(f"{count} user message{'s' if count > 1 else ''}")
            elif msg_type == "ToolMessage":
                summary_parts.append(f"{count} tool result{'s' if count > 1 else ''}")
            elif msg_type == "AIMessage":
                summary_parts.append(f"{count} assistant message{'s' if count > 1 else ''}")
            else:
                summary_parts.append(f"{count} {msg_type.lower()}{'s' if count > 1 else ''}")
        return ", ".join(summary_parts)

    def _apply_sliding_window(self, messages: List[BaseMessage]) -> List[BaseMessage]:
        """
        Apply sliding window using LangChain's trim_messages utility with message count.
        Keeps the last N messages while preserving conversation integrity.
        """
        # If we're within the limit, return as-is
        if len(messages) <= self.conversation_window:
            return messages

        try:
            # Use LangChain's trim_messages with message count strategy
            trimmed_messages = trim_messages(
                messages,
                # Keep the most recent messages
                strategy="last",
                # Use message count instead of tokens
                max_count=self.conversation_window,
                # Ensure chat history starts with human message (or system + human)
                start_on="human",
                # Ensure chat history ends with human or tool message
                end_on=("human", "tool"),
                # Preserve system message if present
                include_system=True,
                # Don't allow partial messages
                allow_partial=False,
            )
            logger.info(
                f"Trimmed messages from {len(messages)} to {len(trimmed_messages)} (last {self.conversation_window} messages)")
            return trimmed_messages
        except Exception as e:
            logger.error(f"Error trimming messages: {str(e)}")
            # Fallback to simple truncation if trim_messages fails
            logger.warning("Falling back to simple truncation")
            return messages[-self.conversation_window:]

    async def filter_memory(self, state: BaseSupervisorState) -> Dict:
        """Handle conversation flow when no tool calls are needed."""
        messages = state["messages"]
        # Check if the last message was an empty AI response
        if messages and isinstance(messages[-1], AIMessage) and not messages[-1].content:
            logger.warning("Empty AI response detected, generating fallback response")
            # Find the last human message
            last_human_msg = None
            for msg in reversed(messages):
                if isinstance(msg, HumanMessage):
                    last_human_msg = msg.content
                    break
            if last_human_msg:
                # Generate a proper response
                fallback_msg = AIMessage(
                    content="I understand you're asking about that. Let me help you with your question. "
                            "Could you please provide more details or rephrase your question?"
                )
                return {"messages": [fallback_msg]}
        return {}

    async def call_llm(self, state: BaseSupervisorState, config: dict = None) -> Dict:
        """
        Call the language model with properly trimmed conversation history.
        Uses message count-based trimming for simplicity and reliability.
        """
        active_agent = state.get("active_agent") or "None"
        console.print(f"[bold blue]Active agent: {active_agent}[/bold blue]")
        system_prompt = self.system.format(active_agent=active_agent)
        messages = state["messages"]

        # Apply message count-based trimming
        messages = self._apply_sliding_window(messages)
        logger.info(f"Applied message trimming: {len(messages)} messages retained")

        # Add system message at the beginning if present
        if self.system:
            messages = [SystemMessage(content=system_prompt)] + messages

        # Validate message sequence
        messages = self._validate_message_sequence(messages)
        await display_messages(messages)

        try:
            message = await self.model_with_tools.ainvoke(messages)
            logger.info(f"LLM response: {message}")

            # Handle empty responses
            if not message.content and not message.tool_calls:
                logger.warning("Empty LLM response, generating fallback")
                message = AIMessage(
                    content="I'm here to help! Could you please rephrase your question or provide more details?"
                )

            return {"messages": [message]}
        except Exception as e:
            logger.error(f"Error calling language model: {str(e)}")
            error_msg = AIMessage(
                content="I'm experiencing technical difficulties processing your request. "
                        "Please try again later or contact support."
            )
            return {"messages": [error_msg]}

    def _validate_message_sequence(self, messages: List[BaseMessage]) -> List[BaseMessage]:
        """
        Simple validation to ensure message sequence is valid.
        This is a simplified version since trim_messages handles most validation.
        """
        if not messages:
            return messages

        valid_messages = []
        i = 0
        while i < len(messages):
            msg = messages[i]

            # Skip orphaned ToolMessages (those without preceding AIMessage with tool calls)
            if isinstance(msg, ToolMessage):
                # Check if there's a preceding AIMessage with tool calls
                has_preceding_ai = False
                for j in range(len(valid_messages) - 1, -1, -1):
                    if isinstance(valid_messages[j], AIMessage) and hasattr(valid_messages[j], 'tool_calls') and \
                            valid_messages[j].tool_calls:
                        has_preceding_ai = True
                        break
                if not has_preceding_ai:
                    logger.warning(f"Skipping orphaned ToolMessage at index {i}")
                    i += 1
                    continue

            valid_messages.append(msg)
            i += 1

        return valid_messages