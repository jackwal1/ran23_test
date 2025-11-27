import traceback
from langgraph.graph import StateGraph, END, MessagesState
from typing import TypedDict, Dict, Any, Optional, List, Union
from langchain_core.messages import (
    SystemMessage,
    HumanMessage,
    ToolMessage,
    AIMessage,
    RemoveMessage,
)
import json
import asyncio
import re
from utils.tokenization import get_tokens
from utils.network_agent_utils import display_messages
from utils.network_agent_utils import generate_summary
from dataclasses import dataclass
from utils.log_init import logger
from utils import constants as CONST
from datetime import datetime

# JSON extraction functions (from your provided code)
def extract_json_from_string(input_str: str) -> Optional[Union[dict, list]]:
    """
    Extract and normalize JSON from a string.
    This function handles multiple scenarios:
    1. Pure JSON strings (original functionality)
    2. JSON within markdown code blocks
    3. JSON mixed with other text
    4. Nested JSON structures
    5. JSON with common formatting issues
    Args:
        input_str: The string that may contain JSON
    Returns:
        The parsed JSON object (dict or list) or None if no valid JSON is found
    """
    if not input_str or not isinstance(input_str, str):
        return None
    input_str = input_str.strip()
    # Strategy 1: Try to parse the entire string as JSON directly (original functionality)
    try:
        return recursively_clean_json(json.loads(input_str))
    except json.JSONDecodeError:
        pass
    # Strategy 2: Try to find JSON using the original regex approach
    try:
        match = re.search(r'({.*}|\[.*\])', input_str, re.DOTALL)
        if match:
            try:
                return recursively_clean_json(json.loads(match.group(1)))
            except json.JSONDecodeError:
                pass
    except Exception as e:
        logger.error(f"Failed to parse JSON with original regex: {e}")
    # Strategy 3: Look for JSON in markdown code blocks
    json_in_block = _extract_json_from_markdown(input_str)
    if json_in_block is not None:
        return json_in_block
    # Strategy 4: Look for JSON objects or arrays in the text with more precise patterns
    json_candidates = _find_json_candidates(input_str)
    # Try each candidate until we find a valid one
    for candidate in json_candidates:
        try:
            # Try to parse as-is first
            return recursively_clean_json(json.loads(candidate))
        except json.JSONDecodeError:
            # If that fails, try to clean and parse
            cleaned = _clean_json_string(candidate)
            if cleaned:
                try:
                    return recursively_clean_json(json.loads(cleaned))
                except json.JSONDecodeError:
                    continue
    # If all strategies fail, return None
    return None

def _extract_json_from_markdown(text: str) -> Optional[Union[dict, list]]:
    """Extract JSON from markdown code blocks."""
    # Pattern for ```json...``` or ```...``` blocks
    pattern = r'```(?:json)?\s*(\{[\s\S]*?\}|\[[\s\S]*?\])\s*```'
    matches = re.findall(pattern, text, re.IGNORECASE)
    for match in matches:
        try:
            return recursively_clean_json(json.loads(match))
        except json.JSONDecodeError:
            continue
    return None

def _find_json_candidates(text: str) -> List[str]:
    """Find potential JSON strings in the text."""
    candidates = []
    # First, try the original simple pattern (for backward compatibility)
    simple_match = re.search(r'({.*}|\[.*\])', text, re.DOTALL)
    if simple_match:
        candidates.append(simple_match.group(1))
    # Then try more precise patterns for nested structures
    # Pattern for JSON objects with balanced braces
    object_pattern = r'(\{(?:[^{}]|(?:\{(?:[^{}]|(?:\{[^{}]*\}))*\}))*\})'
    # Pattern for JSON arrays with balanced brackets
    array_pattern = r'(\[(?:[^\[\]]|(?:\[(?:[^\[\]]|(?:\[[^\[\]]*\]))*\]))*\])'
    # Find all object candidates
    for match in re.finditer(object_pattern, text):
        candidates.append(match.group(1))
    # Find all array candidates
    for match in re.finditer(array_pattern, text):
        candidates.append(match.group(1))
    # Remove duplicates and sort by length (descending) to try the most substantial ones first
    candidates = list(dict.fromkeys(candidates))  # Preserve order while removing duplicates
    candidates.sort(key=len, reverse=True)
    return candidates

def _clean_json_string(json_str: str) -> Optional[str]:
    """Clean a JSON string to handle common issues."""
    if not json_str:
        return None
    # Remove trailing commas before closing brackets or braces
    cleaned = re.sub(r',(\s*[}\]])', r'\1', json_str)
    # Remove JavaScript-style comments (// and /* */)
    # Single-line comments
    cleaned = re.sub(r'\/\/.*?(\n|$)', '', cleaned)
    # Multi-line comments
    cleaned = re.sub(r'\/\*.*?\*\/', '', cleaned, flags=re.DOTALL)
    # Remove leading/trailing whitespace
    cleaned = cleaned.strip()
    # Ensure the string starts with { or [ and ends with } or ]
    if (cleaned.startswith('{') and cleaned.endswith('}')) or \
            (cleaned.startswith('[') and cleaned.endswith(']')):
        return cleaned
    return None

def recursively_clean_json(data: Any) -> Any:
    """
    Recursively processes a JSON object or list,
    decoding nested JSON strings and normalizing primitives.
    (Original functionality preserved)
    """
    if isinstance(data, dict):
        return {k: recursively_clean_json(_try_parse_json(v)) for k, v in data.items()}
    elif isinstance(data, list):
        return [recursively_clean_json(_try_parse_json(item)) for item in data]
    return _normalize_primitive(data)

def _try_parse_json(value: Any) -> Any:
    """
    Tries to parse a value as JSON if it's a string.
    (Original functionality preserved)
    """
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed
        except (json.JSONDecodeError, TypeError):
            return _normalize_primitive(value)
    return value

def _normalize_primitive(value: Any) -> Any:
    """
    Converts strings like "true", "false", "null" to native Python types.
    Keeps numeric strings as-is.
    (Original functionality preserved)
    """
    if isinstance(value, str):
        val = value.strip().lower()
        if val == "true":
            return True
        elif val == "false":
            return False
        elif val == "null":
            return None
    return value

class AgentState(MessagesState):
    """A state class that extends MessagesState to include summary information.
    This class maintains the state of the agent's conversation, including messages,
    a summary of the conversation history, and fields for thinking and planning.
    Attributes:
        summary (str): A summary of the conversation history
        thought (str): Current thought about the situation
        plan (str): Current plan to address the user's request
    """
    thread_id: Optional[str]
    summary: str
    thought: str
    plan: str

class Telco_Agent:
    """IBM's telecommunications agent that implements a state-based conversation flow
    with explicit thinking and planning steps.
    This agent uses a graph-based architecture to manage conversation flow, tool usage,
    and memory management. It can handle tool calls, maintain conversation history,
    and manage token limits through summarization. The thinking and planning steps
    make the agent's reasoning process more transparent.
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
            self, model, tools, checkpointer, token_memory_limit=100000, system="", tool_calls_to_remember=2
    ):
        """Initialize the Telco Agent with thinking and planning capabilities.
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

        # Add nodes for thinking, planning, and execution
        graph.add_node("think", self.think_node)
        graph.add_node("plan", self.plan_node)
        graph.add_node("llm", self.call_llm)
        graph.add_node("action", self.take_action)
        graph.add_node("memory", self.filter_memory)

        # Define the flow: think -> plan -> llm -> (action or memory)
        graph.set_entry_point("think")
        graph.add_edge("think", "plan")
        graph.add_edge("plan", "llm")

        # After LLM, check if action is needed
        graph.add_conditional_edges(
            "llm", self.exists_action, {True: "action", False: "memory"}
        )

        # After action, go back to thinking for the next iteration
        graph.add_edge("action", "think")

        # Memory management leads to end
        graph.add_edge("memory", END)

        # Compile the graph with checkpointer
        self.graph = graph.compile(checkpointer=checkpointer)
        self.tools = {t.name: t for t in tools}
        self.model = model.bind_tools(tools)
        self.token_memory_limit = token_memory_limit

    async def think_node(self, state: AgentState) -> Dict:
        """Generate a thought about the current situation in JSON format.
        This node analyzes the conversation history and current state to form
        a thought about what needs to be done next, formatted as valid JSON.
        Args:
            state (AgentState): Current state of the agent
        Returns:
            Dict: Updated state with the new thought
        """
        # Build a prompt for thinking with JSON format requirement
        thought_prompt = self.system + "\n\n" + state.get("summary", "") + "\n\n"
        thought_prompt += "You are a thinking assistant. Analyze the current conversation and provide a thought about what to do next.\n"
        thought_prompt += "You must respond with a valid JSON object containing a 'thought' field with your analysis.\n"
        thought_prompt += "Example response: {\"thought\": \"I need to check the user's account balance before proceeding.\"}\n"
        thought_prompt += "Conversation:\n"

        # Use filtered messages for context
        filtered_messages = self._filter_messages_for_llm(state["messages"])
        for msg in filtered_messages:
            if isinstance(msg, HumanMessage):
                thought_prompt += f"Human: {msg.content}\n"
            elif isinstance(msg, AIMessage):
                thought_prompt += f"AI: {msg.content}\n"
            elif isinstance(msg, ToolMessage):
                thought_prompt += f"Tool ({msg.name}): {msg.content}\n"

        thought_prompt += "\nYour JSON response: "

        # Generate thought
        thought_message = await self.model.ainvoke([HumanMessage(content=thought_prompt)])
        thought_content = thought_message.content

        # Extract JSON from response
        thought_json = extract_json_from_string(thought_content)

        # Validate and extract thought
        if thought_json and isinstance(thought_json, dict) and "thought" in thought_json:
            thought = thought_json["thought"]
            logger.info(f"Generated thought (JSON): {thought}")
        else:
            # Fallback to raw content if JSON extraction fails
            logger.warning(f"Failed to extract thought as JSON. Using raw content: {thought_content}")
            thought = thought_content

        return {"thought": thought}

    async def plan_node(self, state: AgentState) -> Dict:
        """Create a plan based on the current thought in JSON format.
        This node takes the thought generated in the previous step and creates
        a structured plan to address the user's request, formatted as valid JSON.
        Args:
            state (AgentState): Current state of the agent
        Returns:
            Dict: Updated state with the new plan
        """
        # Build a prompt for planning with JSON format requirement
        plan_prompt = self.system + "\n\n" + state.get("summary", "") + "\n\n"
        plan_prompt += f"**Thought:** {state['thought']}\n\n"
        plan_prompt += "Based on the thought and Agent Instructions, create a plan to address the user's request. The plan should be a list of steps.\n"
        plan_prompt += "If any step requires using a tool, specify the tool and the arguments in the plan.\n"
        plan_prompt += "You must respond with a valid JSON object containing a 'plan' field with your plan steps.\n"
        plan_prompt += "Example response: {\"plan\": [\"Step 1: Check account status\", \"Step 2: Verify user permissions\", \"Step 3: Process request\"]}\n"
        plan_prompt += "Your JSON response: "

        # Generate plan
        plan_message = await self.model.ainvoke([HumanMessage(content=plan_prompt)])
        plan_content = plan_message.content

        # Extract JSON from response
        plan_json = extract_json_from_string(plan_content)

        # Validate and extract plan
        if plan_json and isinstance(plan_json, dict) and "plan" in plan_json:
            plan = plan_json["plan"]
            # If plan is a list, join it into a string for consistency
            if isinstance(plan, list):
                plan = "\n".join([f"- {step}" for step in plan])
            logger.info(f"Generated plan (JSON): {plan}")
        else:
            # Fallback to raw content if JSON extraction fails
            logger.warning(f"Failed to extract plan as JSON. Using raw content: {plan_content}")
            plan = plan_content

        return {"plan": plan}

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

        # Add thought and plan if available
        if state.get("thought", ""):
            full_prompt += f"**Thought:**\n {state['thought']}\n"
        if state.get("plan", ""):
            full_prompt += f"**Plan:**\n {state['plan']}\n"

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

        # Create system message with thought and plan
        #system_content = self.system + state.get("summary", "")
        system_content = "You are a Smart Agent That strictly follows the Planning steps provided and also do not make tool calls prematurely."
        if state.get("thought", ""):
            system_content += f"\n\n**Thought:**\n {state['thought']}"
        if state.get("plan", ""):
            system_content += f"\n\n**Planning steps to be Strictly Followed:**\n {state['plan']}"

        filtered_messages = [SystemMessage(content=system_content)] + filtered_messages

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