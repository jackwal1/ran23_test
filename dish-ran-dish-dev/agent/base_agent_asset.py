import traceback
import uuid
from datetime import datetime

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
# from rich.console import Console
from datetime import datetime
from utils.tokenization import get_tokens
from utils.network_agent_utils import display_messages
from utils.network_agent_utils import generate_summary
# from chat.chunks import manage_memory, display_messages
from dataclasses import dataclass
from utils.log_init import logger
from utils import constants as CONST

# console = Console()

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
    """

    def __init__(
            self, model, tools, checkpointer, token_memory_limit=100000, system="", tool_calls_to_remember=None
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
        """
        self.system = system
        self.tool_calls_to_remember = tool_calls_to_remember
        graph = StateGraph(AgentState)

        # Add async nodes
        graph.add_node("llm", self.call_llm)
        graph.add_node("action", self.take_action)
        graph.add_node("memory", self.filter_memory)

        # Add conditional edges
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

    def _fix_malformed_json(self, json_str):
        """
        Attempt to fix common JSON formatting issues.

        Args:
            json_str (str): The potentially malformed JSON string

        Returns:
            str: A corrected JSON string if possible, or the original if no fixes applied
        """
        try:
            # First, try to parse as-is to see if it's valid
            json.loads(json_str)
            return json_str
        except json.JSONDecodeError:
            # If parsing fails, attempt to fix common issues
            fixed = json_str

            # Fix 1: Remove duplicate JSON objects if concatenated
            # Find the first complete JSON object
            brace_count = 0
            split_pos = -1
            for i, char in enumerate(fixed):
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        split_pos = i + 1
                        break

            if split_pos > 0 and split_pos < len(fixed):
                # Take only the first complete JSON object
                fixed = fixed[:split_pos]

            # Fix 2: Fix missing quotes after values (e.g., "value, -> "value",)
            import re
            fixed = re.sub(r':\s*"([^"]*),\s*"', r': "\1", ', fixed)

            # Fix 3: Fix double quotes at start of values (e.g., ""value" -> "value")
            fixed = re.sub(r':\s*""([^"]+)""', r': "\1"', fixed)

            # Fix 4: Ensure proper commas between key-value pairs
            fixed = re.sub(r'"\s+}', '"}', fixed)  # Remove whitespace before closing brace
            fixed = re.sub(r'"\s+"', '", "', fixed)  # Add commas between keys

            # Fix 5: Handle specific case where value is missing closing quote before comma
            # Example: "cell_name": "BOBOS01075F_2_n71_F-G, "duid" -> "cell_name": "BOBOS01075F_2_n71_F-G", "duid"
            fixed = re.sub(r':\s*"([^"]*),\s*"', r': "\1", ', fixed)

            # Fix 6: Handle missing quotes before null
            fixed = re.sub(r':\s*null,', r': null,', fixed)

            # Fix 7: Handle missing quotes before comma at end of string
            fixed = re.sub(r'"([^"]*),\s*$', r'"\1"', fixed)

            # Fix 8: Handle extra quotes before operation value
            fixed = re.sub(r'"operation":\s*""([^"]+)"', r'"operation": "\1"', fixed)

            # Fix 9: Handle extra quotes before target_tilt value
            fixed = re.sub(r'"target_tilt":\s*""([^"]+)"', r'"target_tilt": "\1"', fixed)

            # Fix 10: Ensure all keys are properly quoted
            fixed = re.sub(r'([{,]\s*)([a-zA-Z_]+)\s*:', r'\1"\2":', fixed)

            # Try to parse the fixed JSON
            try:
                json.loads(fixed)
                return fixed
            except json.JSONDecodeError:
                # If still not valid, return the original
                return json_str

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
                                f"Error decoding tool call arguments, attempting to fix: {call['function']['arguments']}"
                            )
                            # Try to fix the malformed JSON
                            fixed_json = self._fix_malformed_json(call["function"]["arguments"])
                            try:
                                args = json.loads(fixed_json)
                                logger.info(f"Successfully fixed malformed JSON")
                            except json.JSONDecodeError:
                                logger.error(
                                    f"Could not fix JSON, using arguments as string: {fixed_json}"
                                )
                                args = fixed_json

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

    async def take_action(self, state: AgentState) -> Dict:
        """Execute tool calls from the last AI message concurrently.

        Args:
            state (AgentState): Current state of the agent

        Returns:
            Dict: Dictionary containing tool execution results
        """
        tool_calls = state["messages"][-1].tool_calls
        results = []

        # Execute all tool calls concurrently
        async def execute_tool_call(tool_call):
            logger.info(
                f"Agent is making a Tool Call at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ==> {tool_call}[/]"
            )
            try:
                result = await self.tools[tool_call["name"]].ainvoke(tool_call["args"])
                # logger.info(f"Tool {tool_call['name']} result: {result}")
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
                logger.info(f"Tool call {i} failed with exception: {result}")
                results.append(
                    ToolMessage(
                        tool_call_id=tool_calls[i]["id"],
                        name=tool_calls[i]["name"],
                        content=f"Error: {str(result)}"
                    )
                )
            else:
                results.append(result)

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
        # if self.tool_calls_to_remember is None or self.tool_calls_to_remember <= 0:
        #     # If tool_calls_to_remember is 0 or negative, don't filter tool messages
        #     return messages

        # logger.info(f"Original messages: {messages}")

        if self.tool_calls_to_remember is None or self.tool_calls_to_remember < 0:
            # If tool_calls_to_remember is None or negative, don't filter tool messages
            return messages

        filtered_messages = []

        # Find indices of all ToolMessage objects
        tool_message_indices = [i for i, msg in enumerate(messages) if isinstance(msg, ToolMessage)]

        # Determine indices of the last n ToolMessage objects (or all if n is larger than available)
        n = min(self.tool_calls_to_remember, len(tool_message_indices))
        last_n_tool_indices = tool_message_indices[-n:] if n > 0 else []
        # logger.info(f"Last n ToolMessage indices: {last_n_tool_indices}")

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

        # logger.info(f"Start index for filtering: {start_index}")

        # Start from the first HumanMessage before the last n ToolMessage
        filtered_messages = messages[start_index:]

        return filtered_messages

    async def call_llm(self, state: AgentState, config: Optional[Dict] = None) -> Dict:
        """Generate a response from the language model based on the current state.
        Args:
            state (AgentState): Current state of the agent
            config: Configuration that may include event dispatch capabilities
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

            # Dispatch custom event through the callback manager
            if config and "configurable" in config and "callbacks" in config["configurable"]:
                callbacks = config["configurable"]["callbacks"]
                if hasattr(callbacks, "on_custom_event"):
                    try:
                        # Create a run_id if not available
                        run_id = getattr(callbacks, 'run_id', str(uuid.uuid4()))

                        # Dispatch the custom event
                        await callbacks.on_custom_event(
                            "llm_error",  # Event name
                            {  # Event data
                                "error": str(e),
                                "message": "I encountered an error while processing the request",
                                "node": "llm",
                                "timestamp": datetime.now().isoformat()
                            },
                            run_id=run_id
                        )
                        logger.info("Successfully dispatched custom error event from worker")
                    except Exception as event_error:
                        logger.error(f"Failed to dispatch custom event: {event_error}")

            # Return an error message for the supervisor
            error_message = AIMessage(content=f"I encountered an error while processing the request: {str(e)}")
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