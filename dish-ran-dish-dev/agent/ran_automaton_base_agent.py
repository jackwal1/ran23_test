import traceback

from langgraph.graph import StateGraph, END, MessagesState
from typing import TypedDict, Dict, Any, Optional, List
from langchain_core.messages import (
    SystemMessage,
    HumanMessage,
    ToolMessage,
    AIMessage,
    RemoveMessage,
)
import json
import asyncio
from datetime import datetime
from utils.tokenization import get_tokens
from utils.network_agent_utils import display_messages
from utils.network_agent_utils import generate_summary
from dataclasses import dataclass
from utils.log_init import logger
from utils import constants as CONST
from langchain_core.runnables import RunnableConfig

# Import your updated user injection utility
from utils.user_id_injection import (
    register_user_session,
    get_user_from_thread,
    inject_user_context_into_state,
    TOOLS_REQUIRING_USER_ID
)

class AgentState(MessagesState):
    """A state class that extends MessagesState to include summary information.

    This class maintains the state of the agent's conversation, including messages
    and a summary of the conversation history.

    Attributes:
        summary (str): A summary of the conversation history
    """
    summary: str

class Telco_Agent:
    """IBM's telecommunications agent that implements a state-based conversation flow.

    This agent uses a graph-based architecture to manage conversation flow, tool usage,
    and memory management. It can handle tool calls, maintain conversation history,
    and manage token limits through summarization. It also supports filtering tool
    messages for LLM context while preserving all messages for audit purposes.

    Attributes:
        system (str): System instructions for the agent
        graph (StateGraph): The conversation flow graph
        tools (Dict): Dictionary of available tools
        checkpointer: Checkpoint manager for saving/loading agent state
        model: The language model used for generating responses
        token_memory_limit (int): Maximum number of tokens allowed in conversation history
        tool_calls_to_remember (int): Number of tool messages to keep in LLM context
        tools_needing_user_id (List[str]): List of tool names that require user_id injection
    """

    def __init__(
            self, model, tools, checkpointer, token_memory_limit=100000, system="",
            tool_calls_to_remember=None, tools_needing_user_id=None
    ):
        """Initialize the Telco Agent.

        Args:
            model: The language model to use for generating responses
            tools: List of tools available to the agent
            checkpointer: Checkpoint manager for saving/loading agent state
            token_memory_limit (int, optional): Maximum tokens in conversation history. Defaults to 100000.
            system (str, optional): System instructions for the agent. Defaults to "".
            tool_calls_to_remember (int, optional): Number of tool messages to keep in LLM context.
                If None (default), no filtering is applied. If set to a number, only that many recent
                tool messages are kept in the LLM context.
            tools_needing_user_id (List[str], optional): List of tool names that require user_id injection.
                If None, defaults to TOOLS_REQUIRING_USER_ID from utility file.
        """
        self.system = system
        self.tool_calls_to_remember = tool_calls_to_remember
        # Use default from utility file if not provided
        self.tools_needing_user_id = tools_needing_user_id or TOOLS_REQUIRING_USER_ID

        graph = StateGraph(AgentState)

        # Add async nodes - Using modified take_action method
        graph.add_node("llm", self.call_llm)
        graph.add_node("action", self.take_action)
        graph.add_node("memory", self.filter_memory)

        # Add conditional edges - SAME FLOW
        graph.add_conditional_edges(
            "llm", self.exists_action, {True: "action", False: "memory"}
        )
        graph.add_edge("action", "llm")
        graph.add_edge("memory", END)
        graph.set_entry_point("llm")

        # Compile the graph with checkpointer
        self.graph = graph.compile(checkpointer=checkpointer)
        self.tools = {t.name: t for t in tools}
        self.model = model.bind_tools(tools)
        self.token_memory_limit = token_memory_limit

    async def register_user_session(self, thread_id: str, user_id: str):
        """Convenience method to register user session through the agent"""
        logger.info(f"Registering user session via agent: {thread_id} -> {user_id}")
        await register_user_session(thread_id, user_id)

    async def get_user_from_thread(self, thread_id: str) -> str:
        """Convenience method to get user from thread through the agent"""
        logger.info(f"Getting user from thread via agent: {thread_id}")
        return await get_user_from_thread(thread_id)

    async def _inject_user_context(self, state: AgentState, config: RunnableConfig = None):
        """Inject user_id into tool calls that need it (selective injection)

        Uses the helper function from the utility file for consistency
        """
        logger.info("Starting user context injection process")
        await inject_user_context_into_state(state, config, self.tools_needing_user_id)
        logger.info("User context injection process completed")

    async def get_full_context_token_count(self, state: AgentState) -> int:
        """Get the total token count including tool descriptions that LangChain injects.

        This method reconstructs the full prompt as it would be sent to the model,
        including the tool descriptions that LangChain automatically injects.

        Args:
            state (AgentState): Current state of the agent

        Returns:
            int: Total token count including tool descriptions
        """
        # Build tool descriptions as LangChain would inject them
        tool_descriptions = []
        for tool in self.tools.values():
            # Get tool schema if available
            tool_schema = None
            if hasattr(tool, 'args_schema') and tool.args_schema:
                try:
                    tool_schema = tool.args_schema.model_json_schema()
                except Exception as e:
                    logger.error(f"Error getting tool schema: {e}")
                    tool_schema = None

            # Build tool description in LangChain format
            tool_desc = f"{tool.name}: {tool.description}"
            if tool_schema:
                tool_desc += f"\nParameters: {json.dumps(tool_schema, indent=2)}"
            tool_descriptions.append(tool_desc)

        tool_desc_str = "\n".join(tool_descriptions)

        # Build the system prompt with tool descriptions
        system_with_tools = self.system
        if state.get("summary", ""):
            system_with_tools += state.get("summary", "")

        if tool_desc_str:
            system_with_tools += f"\n\nYou have access to the following tools:\n\n{tool_desc_str}\n\nUse the tools when needed to answer the user's question."

        # Build the full prompt as it would be sent to the model
        full_prompt = f"System: {system_with_tools}\n"

        # Add conversation history (using filtered messages for token counting too)
        filtered_messages = self._filter_messages_for_llm(state["messages"])
        for msg in filtered_messages:
            if isinstance(msg, ToolMessage):
                full_prompt += "Tool: "
            elif isinstance(msg, AIMessage):
                full_prompt += "AI: "
            elif isinstance(msg, HumanMessage):
                full_prompt += "Human: "
            full_prompt += str(msg.content) + "\n"

        # Make token counting async-safe
        return await asyncio.get_event_loop().run_in_executor(None, get_tokens, full_prompt)

    def exists_action(self, state: AgentState) -> bool:
        """Check if the last message contains tool calls that need to be executed.

        Args:
            state (AgentState): Current state of the agent

        Returns:
            bool: True if there are tool calls to execute, False otherwise
        """
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
                            logger.error(
                                f"Error decoding tool call arguments, using arguments as string: {call['function']['arguments']}"
                            )
                            args = call["function"]["arguments"]

                        id = call["id"]
                        type = "tool_call"
                        corrected_tool_calls.append(
                            {"name": name, "args": args, "id": id, "type": type}
                        )
                    except (KeyError, json.JSONDecodeError) as e:
                        logger.error(f"Error processing tool call: {call}, Error: {e}")

                result.tool_calls = corrected_tool_calls
                state["messages"][-1] = result

            return len(result.tool_calls) > 0
        return False

    async def take_action(self, state: AgentState, config: RunnableConfig = None) -> Dict:
        """Execute tool calls from the last AI message concurrently with selective user ID injection.

        Args:
            state (AgentState): Current state of the agent
            config (RunnableConfig, optional): Configuration containing thread_id for user context

        Returns:
            Dict: Dictionary containing tool execution results
        """
        logger.info(f"Taking action with tools requiring user_id: {self.tools_needing_user_id}")

        # INJECT USER_ID BEFORE TOOL EXECUTION using utility function
        try:
            await self._inject_user_context(state, config)
        except Exception as e:
            logger.error(f"Error during user context injection: {e}")
            # Continue with tool execution even if user injection fails

        tool_calls = state["messages"][-1].tool_calls
        results = []

        # Execute all tool calls concurrently
        async def execute_tool_call(tool_call):
            logger.info(
                f"Agent is making a Tool Call at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ==> {tool_call}"
            )
            try:
                result = await self.tools[tool_call["name"]].ainvoke(tool_call["args"])
                logger.info(f"Tool {tool_call['name']} executed successfully")
                return ToolMessage(
                    tool_call_id=tool_call["id"],
                    name=tool_call["name"],
                    content=str(result)
                )
            except Exception as e:
                logger.error(f"Error invoking tool {tool_call['name']}: {e}")
                traceback.print_exc()
                return ToolMessage(
                    tool_call_id=tool_call["id"],
                    name=tool_call["name"],
                    content=f"Error: {str(e)}"
                )
            finally:
                logger.info(
                    f"Tool call {tool_call['name']} completed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                )

        # Execute all tool calls concurrently
        tool_results = await asyncio.gather(
            *[execute_tool_call(tool_call) for tool_call in tool_calls],
            return_exceptions=True
        )

        # Handle any exceptions that occurred during tool execution
        for i, result in enumerate(tool_results):
            if isinstance(result, Exception):
                logger.error(f"Tool call {i} failed with exception: {result}")
                results.append(
                    ToolMessage(
                        tool_call_id=tool_calls[i]["id"],
                        name=tool_calls[i]["name"],
                        content=f"Error: {str(result)}"
                    )
                )
            else:
                results.append(result)

        logger.info(f"Completed execution of {len(results)} tool calls")
        return {"messages": results}

    async def filter_memory(self, state: AgentState) -> Dict:
        """Manage conversation history by summarizing and trimming when token limit is exceeded.

        Args:
            state (AgentState): Current state of the agent

        Returns:
            Dict: Updated state with summarized history if needed
        """
        # Get the full token count including tool descriptions
        num_tokens = await self.get_full_context_token_count(state)
        logger.info(f"\nTokens in Chat History: {num_tokens}")

        if num_tokens > self.token_memory_limit:
            logger.info(f"We are going to trim and summarize the history")
            trim_idx = None
            for i in reversed(range(len(state["messages"]) - 4)):
                if isinstance(state["messages"][i], HumanMessage):
                    trim_idx = i
                    break

            if trim_idx is not None and trim_idx > 0:
                msgs_to_sum = state["messages"][:trim_idx]
                filtered_msgs = state["messages"][trim_idx:]

                summary = state.get("summary", "")

                # Make summarization async
                summarized_text = await asyncio.get_event_loop().run_in_executor(
                    None,
                    generate_summary,
                    " ".join([str(msg.content) for msg in msgs_to_sum]),
                    summary
                )

                summarized_text = "Summary:\n" + summarized_text
                logger.info(f"Successfully summarized history")
                logger.info(f"Trimmed {trim_idx+1} messages")
                logger.info(f"{summarized_text}")

                delete_messages = [RemoveMessage(id=m.id) for m in msgs_to_sum if m.id]
                return {"summary": summarized_text, "messages": delete_messages}
            else:
                logger.info(
                    f"\nHistory not long enough to summarize and trim"
                )

        return {}

    def _filter_messages_for_llm(self, messages: List) -> List:
        """Filter messages to keep only the specified number of tool messages for LLM context.

        This method preserves all messages for audit purposes but filters the context
        sent to the LLM to include only the last N tool messages and their corresponding
        AI tool call messages.

        Args:
            messages (List): List of all messages in the conversation

        Returns:
            List: Filtered messages for LLM context
        """
        logger.info(f"Filtering messages for LLM context with tool_calls_to_remember={self.tool_calls_to_remember}")

        if self.tool_calls_to_remember is None or self.tool_calls_to_remember < 0:
            # If tool_calls_to_remember is None or negative, don't filter tool messages
            return messages

        filtered_messages = []

        # Find indices of all ToolMessage objects
        tool_message_indices = [i for i, msg in enumerate(messages) if isinstance(msg, ToolMessage)]

        # Determine indices of the last n ToolMessage objects (or all if n is larger than available)
        n = min(self.tool_calls_to_remember, len(tool_message_indices))
        last_n_tool_indices = tool_message_indices[-n:] if n > 0 else []

        # Find the index of the first HumanMessage before the earliest of the last n ToolMessage
        start_index = 0
        if last_n_tool_indices:
            earliest_tool_index = min(last_n_tool_indices)
            # Search backward from the earliest ToolMessage to find the first HumanMessage
            for i in range(earliest_tool_index - 1, -1, -1):
                if isinstance(messages[i], HumanMessage):
                    start_index = i
                    break
        else:
            # Find the last HumanMessage if last_n_tool_indices is 0
            for i in range(len(messages) - 1, -1, -1):
                if isinstance(messages[i], HumanMessage):
                    start_index = i
                    break

        # Start from the first HumanMessage before the last n ToolMessage
        filtered_messages = messages[start_index:]

        return filtered_messages

    async def call_llm(self, state: AgentState) -> Dict:
        """Generate a response from the language model based on the current state.

        Args:
            state (AgentState): Current state of the agent

        Returns:
            Dict: Dictionary containing the model's response
        """
        messages = state["messages"]

        # Filter messages for LLM context while preserving all messages for audit
        filtered_messages = self._filter_messages_for_llm(messages)

        if self.system or state.get("summary", ""):
            filtered_messages = [
                                    SystemMessage(content=self.system + state.get("summary", ""))
                                ] + filtered_messages

        logger.info("-------------------------------- filtered messages ------------------------------")
        await display_messages(filtered_messages)

        try:
            message = await self.model.ainvoke(filtered_messages)

            # Get the full token count including tool descriptions
            full_token_count = await self.get_full_context_token_count(state)
            logger.info(f"\nToken Usage: {message.usage_metadata}")
            logger.info(f"\nTotal Context Tokens (including tool descriptions): {full_token_count}")

            return {"messages": [message]}

        except Exception as e:
            logger.error(f"Error in LLM call: {e}")
            # Return an error message instead of crashing
            error_message = AIMessage(content=f"I encountered an error: {str(e)}")
            return {"messages": [error_message]}

    async def run_agent(self, initial_state: AgentState, config: Optional[Dict] = None) -> Dict:
        """Run the agent with proper async handling.

        Args:
            initial_state (AgentState): Initial state for the agent
            config (Optional[Dict], optional): Configuration for the agent run

        Returns:
            Dict: Final state after agent execution
        """
        try:
            logger.info(f"Running agent with tools_needing_user_id: {self.tools_needing_user_id}")

            # Use astream_events for async streaming if available, otherwise use invoke
            if hasattr(self.graph, 'ainvoke'):
                result = await self.graph.ainvoke(initial_state, config=config)
            else:
                # Fallback to synchronous invoke if async not available
                result = await asyncio.get_event_loop().run_in_executor(
                    None, self.graph.invoke, initial_state, config
                )
            return result
        except Exception as e:
            logger.error(f"Error running agent: {e}")
            raise

    async def stream_agent(self, initial_state: AgentState, config: Optional[Dict] = None):
        """Stream agent execution with proper async handling.

        Args:
            initial_state (AgentState): Initial state for the agent
            config (Optional[Dict], optional): Configuration for the agent run

        Yields:
            Dict: State updates as they occur
        """
        try:
            logger.info(f"Streaming agent with tools_needing_user_id: {self.tools_needing_user_id}")

            if hasattr(self.graph, 'astream'):
                async for chunk in self.graph.astream(initial_state, config=config):
                    yield chunk
            else:
                # Fallback for non-async streaming
                for chunk in self.graph.stream(initial_state, config=config):
                    yield chunk
        except Exception as e:
            logger.error(f"Error streaming agent: {e}")
            raise
